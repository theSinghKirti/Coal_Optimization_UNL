import json
from pathlib import Path
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
import pulp

app = FastAPI(
    title="UNL Coal Optimization API",
    description="Backend API for coal source allocation optimization and operational data tracking.",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup paths relative to this file
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

def load_data_file(filename: str):
    path = DATA_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Data file '{filename}' not found.")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Error reading JSON from '{filename}'.")

def save_data_file(filename: str, data: dict):
    path = DATA_DIR / filename
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def execute_optimization(custom_demands: Optional[Dict[str, float]] = None, market_premium: float = 1.35) -> dict:
    # Load input files
    constraints = load_data_file("constraints_registry.json")
    costs = load_data_file("cost_inputs.json")
    daily = load_data_file("daily_fuel.json")

    # Apply plant name aliases for consistency
    PLANT_ALIASES = {"Obra": "Obra B"}
    for row in constraints:
        row["plant"] = PLANT_ALIASES.get(row["plant"], row["plant"])
    COST_PLANT_ALIASES = {"Panki": "Panki Extn"}
    for row in costs:
        row["plant"] = COST_PLANT_ALIASES.get(row["plant"], row["plant"])

    # 1. Build demand map from daily fuel linkage data
    demand = {}
    for row in daily:
        if row.get("fuel_type") == "COAL" and isinstance(row.get("monthly_linkage"), (int, float)):
            plant = row["plant"]
            demand[plant] = max(demand.get(plant, 0), row["monthly_linkage"])

    # Apply custom overrides if provided
    if custom_demands:
        for plant, val in custom_demands.items():
            if val is not None:
                demand[plant] = val

    # 2. Build monthly ACQ caps (ACQ is annual in Lac MT, pro-rated to monthly MT)
    LAC_MT_TO_MT = 100_000
    acq_cap = {}
    for row in constraints:
        plant, company = row["plant"], row["company"]
        monthly_cap_mt = (row["acq_lac_mt"] * LAC_MT_TO_MT) / 12
        acq_cap[(plant, company)] = acq_cap.get((plant, company), 0) + monthly_cap_mt

    # 3. Build landed cost map (falls back to averages if needed)
    cost_map = {}
    for row in costs:
        if row.get("landed_cost_rs_mt") is not None:
            cost_map[(row["plant"], row["company"])] = row["landed_cost_rs_mt"]

    plants = sorted(demand.keys())
    pairs = [(p, c) for (p, c) in acq_cap if p in demand]

    # Calculate baseline cost based on average of available contracted sources
    baseline_cost = 0
    for p in plants:
        known = [cost_map[(p, c)] for (pp, c) in pairs if pp == p and (p, c) in cost_map]
        if known:
            baseline_cost += demand[p] * (sum(known) / len(known))

    # 4. Formulate the LP Problem
    prob = pulp.LpProblem("coal_allocation", pulp.LpMinimize)
    
    # Variables: x[plant, company] = Quantity allocated this month (MT)
    x = {pair: pulp.LpVariable(f"x_{pair[0].replace(' ', '_')}_{pair[1]}", lowBound=0) for pair in pairs}
    
    # Shortfall variables to maintain feasibility (spot market/e-auction)
    shortfall = {p: pulp.LpVariable(f"shortfall_{p.replace(' ', '_')}", lowBound=0) for p in plants}
    
    # Determine plant average cost for pricing the shortfall premium
    plant_avg_cost = {}
    for p in plants:
        known = [cost_map[(p, c)] for (pp, c) in pairs if pp == p and (p, c) in cost_map]
        plant_avg_cost[p] = (sum(known) / len(known)) if known else 5000.0

    # Objective: Minimize blended landed cost + shortfall cost
    prob += pulp.lpSum(
        x[pair] * cost_map.get(pair, 1e6) for pair in pairs
    ) + pulp.lpSum(
        shortfall[p] * plant_avg_cost[p] * market_premium for p in plants
    )

    # Constraint: Meet demand (allocated from contracts + shortfall >= demand)
    for p in plants:
        plant_pairs = [pair for pair in pairs if pair[0] == p]
        prob += pulp.lpSum(x[pair] for pair in plant_pairs) + shortfall[p] >= demand[p], f"demand_{p.replace(' ', '_')}"

    # Constraint: Observe ACQ Caps
    for pair in pairs:
        prob += x[pair] <= acq_cap[pair], f"acq_cap_{pair[0].replace(' ', '_')}_{pair[1]}"

    # Solve the optimization problem
    status = prob.solve(pulp.PULP_CBC_CMD(msg=0))

    # Parse optimization outputs
    allocations = []
    total_cost = 0
    for pair in pairs:
        qty = x[pair].value() or 0
        if qty > 0.5:
            cost = cost_map.get(pair, 0)
            total_cost += qty * cost
            allocations.append({
                "plant": pair[0],
                "company": pair[1],
                "allocated_mt": round(qty, 1),
                "landed_cost_rs_mt": cost,
                "acq_cap_mt": round(acq_cap[pair], 1),
                "acq_utilisation_pct": round(100 * qty / acq_cap[pair], 1) if acq_cap[pair] else None,
            })

    shortfall_report = []
    total_shortfall_cost = 0
    for p in plants:
        qty = shortfall[p].value() or 0
        if qty > 0.5:
            cost = plant_avg_cost[p] * market_premium
            total_shortfall_cost += qty * cost
            shortfall_report.append({
                "plant": p,
                "shortfall_mt": round(qty, 1),
                "assumed_market_rate_rs_mt": round(cost, 0),
                "note": "Demand exceeds combined FSA + Bridge Linkage ACQ available this month; sourced via e-auction/spot market at an assumed premium.",
            })
    total_cost += total_shortfall_cost

    result = {
        "status": pulp.LpStatus[status],
        "plants_covered": plants,
        "total_optimized_cost_rs": round(total_cost, 0),
        "baseline_cost_rs": round(baseline_cost, 0),
        "estimated_savings_rs": round(baseline_cost - total_cost, 0),
        "estimated_savings_pct": round(100 * (baseline_cost - total_cost) / baseline_cost, 2) if baseline_cost else None,
        "allocations": sorted(allocations, key=lambda r: (r["plant"], -r["allocated_mt"])),
        "shortfalls": shortfall_report,
    }

    return result

class OptimizationRequest(BaseModel):
    custom_demands: Optional[Dict[str, float]] = Field(None, description="Custom demand overrides in MT for each plant (e.g. {'Anpara': 1000000.0})")
    market_premium: Optional[float] = Field(1.35, description="Multiplier for shortfall price premium (default is 1.35)")

@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse(url="/docs")

@app.get("/api/data/constraints")
def get_constraints():
    """Retrieve the current ACQ and Bridge Linkage constraints registry."""
    return load_data_file("constraints_registry.json")

@app.get("/api/data/costs")
def get_costs():
    """Retrieve the landed cost and variable cost dynamics for each plant and coal company."""
    return load_data_file("cost_inputs.json")

@app.get("/api/data/daily-fuel")
def get_daily_fuel():
    """Retrieve the daily report fuel positions and linkages."""
    return load_data_file("daily_fuel.json")

@app.get("/api/data/optimization-run")
def get_optimization_run():
    """Retrieve the results of the last recorded optimization run."""
    return load_data_file("optimization_run.json")

@app.get("/api/optimization/run")
def run_optimization():
    """Run the linear programming allocation model on the active database/files, save and return the results."""
    try:
        result = execute_optimization()
        save_data_file("optimization_run.json", result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")

@app.post("/api/optimization/run-dynamic")
def run_dynamic_optimization(req: OptimizationRequest):
    """Run the optimization model dynamically with custom demand overrides or custom market premiums without saving over the baseline run."""
    try:
        result = execute_optimization(custom_demands=req.custom_demands, market_premium=req.market_premium)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dynamic optimization failed: {str(e)}")

@app.get("/api/data/snapshot")
def get_combined_snapshot():
    """Aggregate constraints, costs, daily fuel, and the latest optimization run into a single response matching the frontend's expected format."""
    constraints = load_data_file("constraints_registry.json")
    daily_fuel = load_data_file("daily_fuel.json")
    try:
        optimization = load_data_file("optimization_run.json")
    except Exception:
        # Fallback if optimization hasn't been run/saved yet
        optimization = execute_optimization()
        save_data_file("optimization_run.json", optimization)
        
    return {
        "optimization": optimization,
        "daily_fuel": daily_fuel,
        "constraints": constraints,
        "generated_from": "FastAPI Dynamic Server"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
