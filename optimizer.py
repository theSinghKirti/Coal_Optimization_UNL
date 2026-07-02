"""
optimizer.py
Pure LP optimization engine (no FastAPI / HTTP concerns).
Loaded by both routes and standalone scripts.
"""
import json
from pathlib import Path
from typing import Dict, Optional
import pulp

from config import DATA_DIR


# ── JSON helpers ──────────────────────────────────────────────────────────────

def load_json(filename: str) -> list:
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filename: str, data: dict) -> None:
    path = DATA_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── Plant name normalisation ──────────────────────────────────────────────────

PLANT_ALIASES: Dict[str, str] = {"Obra": "Obra B"}
COST_PLANT_ALIASES: Dict[str, str] = {"Panki": "Panki Extn"}


def _apply_aliases(rows: list, alias_map: Dict[str, str]) -> list:
    for row in rows:
        row["plant"] = alias_map.get(row["plant"], row["plant"])
    return rows


# ── Core optimisation function ────────────────────────────────────────────────

def run_optimisation(
    custom_demands: Optional[Dict[str, float]] = None,
    market_premium: float = 1.35,
) -> dict:
    """
    Solve the coal allocation LP:
        minimise  Σ landed_cost[p,c] · x[p,c]  +  Σ shortfall[p] · avg_cost[p] · premium
        s.t.      Σ_c x[p,c] + shortfall[p] >= monthly_demand[p]   ∀ p
                  x[p,c]                     <= acq_cap_mt[p,c]     ∀ (p,c)
                  x[p,c], shortfall[p]       >= 0

    Returns a result dict compatible with the frontend demoSnapshot schema.
    """
    # --- Load inputs -------------------------------------------------------
    constraints = _apply_aliases(load_json("constraints_registry.json"), PLANT_ALIASES)
    costs       = _apply_aliases(load_json("cost_inputs.json"),          COST_PLANT_ALIASES)
    daily       = load_json("daily_fuel.json")

    # --- Build demand from monthly linkage ----------------------------------
    demand: Dict[str, float] = {}
    for row in daily:
        if row.get("fuel_type") == "COAL" and isinstance(row.get("monthly_linkage"), (int, float)):
            p = row["plant"]
            demand[p] = max(demand.get(p, 0), row["monthly_linkage"])

    if custom_demands:
        for p, val in custom_demands.items():
            if val is not None:
                demand[p] = val

    # --- ACQ caps (annual Lac MT → monthly MT) ------------------------------
    LAC_MT_TO_MT = 100_000
    acq_cap: Dict[tuple, float] = {}
    for row in constraints:
        key = (row["plant"], row["company"])
        monthly_mt = (row["acq_lac_mt"] * LAC_MT_TO_MT) / 12
        acq_cap[key] = acq_cap.get(key, 0) + monthly_mt

    # --- Landed cost map ----------------------------------------------------
    cost_map: Dict[tuple, float] = {}
    for row in costs:
        if row.get("landed_cost_rs_mt") is not None:
            cost_map[(row["plant"], row["company"])] = row["landed_cost_rs_mt"]

    plants = sorted(demand.keys())
    pairs  = [(p, c) for (p, c) in acq_cap if p in demand]

    # --- Baseline cost (simple average across contracted sources) -----------
    baseline_cost = 0.0
    for p in plants:
        known = [cost_map[(p, c)] for (pp, c) in pairs if pp == p and (p, c) in cost_map]
        if known:
            baseline_cost += demand[p] * (sum(known) / len(known))

    # --- Plant-average cost for shortfall premium --------------------------
    plant_avg_cost: Dict[str, float] = {}
    for p in plants:
        known = [cost_map[(p, c)] for (pp, c) in pairs if pp == p and (p, c) in cost_map]
        plant_avg_cost[p] = sum(known) / len(known) if known else 5000.0

    # --- LP formulation -----------------------------------------------------
    prob = pulp.LpProblem("coal_allocation", pulp.LpMinimize)

    x = {
        pair: pulp.LpVariable(f"x_{pair[0].replace(' ','_')}_{pair[1]}", lowBound=0)
        for pair in pairs
    }
    shortfall = {
        p: pulp.LpVariable(f"shortfall_{p.replace(' ','_')}", lowBound=0)
        for p in plants
    }

    # Objective
    prob += (
        pulp.lpSum(x[pair] * cost_map.get(pair, 1e6) for pair in pairs)
        + pulp.lpSum(shortfall[p] * plant_avg_cost[p] * market_premium for p in plants)
    )

    # Demand constraints
    for p in plants:
        plant_pairs = [pair for pair in pairs if pair[0] == p]
        prob += (
            pulp.lpSum(x[pair] for pair in plant_pairs) + shortfall[p] >= demand[p],
            f"demand_{p.replace(' ','_')}"
        )

    # ACQ cap constraints
    for pair in pairs:
        prob += x[pair] <= acq_cap[pair], f"acq_{pair[0].replace(' ','_')}_{pair[1]}"

    status = prob.solve(pulp.PULP_CBC_CMD(msg=0))

    # --- Parse results ------------------------------------------------------
    allocations = []
    total_cost  = 0.0
    for pair in pairs:
        qty = x[pair].value() or 0.0
        if qty > 0.5:
            cost = cost_map.get(pair, 0)
            total_cost += qty * cost
            allocations.append({
                "plant":               pair[0],
                "company":             pair[1],
                "allocated_mt":        round(qty, 1),
                "landed_cost_rs_mt":   cost,
                "acq_cap_mt":          round(acq_cap[pair], 1),
                "acq_utilisation_pct": round(100 * qty / acq_cap[pair], 1) if acq_cap[pair] else None,
            })

    shortfalls = []
    for p in plants:
        qty = shortfall[p].value() or 0.0
        if qty > 0.5:
            market_rate = plant_avg_cost[p] * market_premium
            total_cost += qty * market_rate
            shortfalls.append({
                "plant":                     p,
                "shortfall_mt":              round(qty, 1),
                "assumed_market_rate_rs_mt": round(market_rate, 0),
                "note": (
                    "Demand exceeds combined FSA + Bridge Linkage ACQ available this month; "
                    "sourced via e-auction/spot market at an assumed premium."
                ),
            })

    return {
        "status":                 pulp.LpStatus[status],
        "plants_covered":         plants,
        "total_optimized_cost_rs": round(total_cost, 0),
        "baseline_cost_rs":        round(baseline_cost, 0),
        "estimated_savings_rs":    round(baseline_cost - total_cost, 0),
        "estimated_savings_pct":   round(100 * (baseline_cost - total_cost) / baseline_cost, 2)
                                   if baseline_cost else None,
        "allocations": sorted(allocations, key=lambda r: (r["plant"], -r["allocated_mt"])),
        "shortfalls":  shortfalls,
    }
