import React, { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, LabelList, ResponsiveContainer
} from "recharts";
import {
  inr, shortPlant, COLORS, COMPANY_COLORS, CO_COLOR,
  IPP_VC, HEAT_RATE, BLEND_GCV, currentAllocations
} from "../lib/utils";

export default function PlantStatusTab({ optimization, daily_fuel, setShowDetailsDrawer, liveData }) {
  
  const recommendedAllocations = useMemo(() => {
    const list = optimization.allocations.map(a => ({
      plant: a.plant,
      company: a.company,
      allocated_mt: a.allocated_mt,
      landed_cost_rs_mt: a.landed_cost_rs_mt
    }));
    optimization.shortfalls.forEach(s => {
      list.push({
        plant: s.plant,
        company: "Market",
        allocated_mt: s.shortfall_mt,
        landed_cost_rs_mt: s.assumed_market_rate_rs_mt
      });
    });
    return list;
  }, [optimization]);

  const baselineTotalCost = useMemo(() => {
    return currentAllocations.reduce((sum, a) => sum + a.allocated_mt * a.landed_cost_rs_mt, 0);
  }, []);

  const optimizedTotalCost = useMemo(() => {
    return recommendedAllocations.reduce((sum, a) => sum + a.allocated_mt * a.landed_cost_rs_mt, 0);
  }, [recommendedAllocations]);

  const savings = baselineTotalCost - optimizedTotalCost;

  /* ── Plant-Status derived data ─────────────── */
  const plantStatusRows = useMemo(() => {
    const plants = optimization.plants_covered;

    return plants.map((plant) => {
      // allocations for this plant
      const allocs = optimization.allocations.filter((a) => a.plant === plant);
      const totalAlloc = allocs.reduce((s, a) => s + a.allocated_mt, 0);

      // source mix %
      const mix = allocs.map((a) => ({
        company: a.company,
        pct: totalAlloc > 0 ? (a.allocated_mt / totalAlloc) * 100 : 0,
        color: CO_COLOR[a.company] || "#8892a4",
      }));

      // blended landed cost Rs/MT (weighted average)
      const blendedLandedCost = totalAlloc > 0
        ? allocs.reduce((s, a) => s + a.landed_cost_rs_mt * a.allocated_mt, 0) / totalAlloc
        : 0;

      // VC NOW Rs/kWh
      const vcNow = blendedLandedCost > 0
        ? parseFloat(((blendedLandedCost * HEAT_RATE) / (BLEND_GCV * 1000)).toFixed(2))
        : null;

      // cheapest available source for this plant
      const cheapest = allocs.length
        ? allocs.reduce((a, b) => a.landed_cost_rs_mt < b.landed_cost_rs_mt ? a : b)
        : null;
      const vcOpt = cheapest
        ? parseFloat(((cheapest.landed_cost_rs_mt * HEAT_RATE) / (BLEND_GCV * 1000)).toFixed(2))
        : null;

      const delta = (vcOpt != null && vcNow != null) ? parseFloat((vcOpt - vcNow).toFixed(2)) : null;

      // daily fuel entry for this plant
      const fuel = daily_fuel.find((r) => r.plant === plant && r.fuel_type === "COAL");
      const days = fuel ? parseFloat(Number(fuel.days_stock_cover || 0).toFixed(1)) : null;
      const muMo = fuel ? Math.round((fuel.generation_mu || 0) * 30) : null;


      // ACQ utilisation (avg across sources)
      const avgUtil = allocs.length
        ? allocs.reduce((s, a) => s + (a.acq_utilisation_pct || 0), 0) / allocs.length
        : 0;

      // VS IPP
      const vsIPP = vcNow != null ? (vcNow <= IPP_VC ? "ahead" : "behind") : "—";

      // shortfall
      const shortfall = optimization.shortfalls.find((s) => s.plant === plant);

      return { plant, mix, vcNow, vcOpt, delta, days, muMo, avgUtil, vsIPP, shortfall };
    });
  }, [optimization, daily_fuel]);

  /* ── Fleet-level KPIs for Plant Status tab ── */
  const fleetKpis = useMemo(() => {
    // annual savings extrapolated (monthly * 12)
    const annualSaving = Math.abs(savings) * 12;

    // cheapest single source across all allocations
    const cheapestAlloc = optimization.allocations.length > 0 
      ? optimization.allocations.reduce((a, b) => a.landed_cost_rs_mt < b.landed_cost_rs_mt ? a : b)
      : { company: "Market", landed_cost_rs_mt: 5000 };
    const cheapestVc = parseFloat(
      ((cheapestAlloc.landed_cost_rs_mt * HEAT_RATE) / (BLEND_GCV * 1000)).toFixed(2)
    );

    // plants behind IPP
    const behind = plantStatusRows.filter((r) => r.vsIPP === "behind").length;
    const total  = plantStatusRows.length;

    return {
      annualSaving,
      cheapestSource: cheapestAlloc.company,
      cheapestVc,
      plantsBehind: behind,
      plantsTotal: total,
      stationsModelled: optimization.plants_covered.length,
    };
  }, [optimization, plantStatusRows, savings]);

  /* ── Recommended actions ────────────────────── */
  const recommendedActions = useMemo(() => {
    const actions = [];
    plantStatusRows.forEach(({ plant, vcNow, vcOpt, shortfall, mix }) => {
      if (shortfall) {
        actions.push({
          plant,
          text: `keep lifting above take-or-pay threshold to avoid under-lifting penalty.`,
          type: "warning",
        });
      }
      if (vcNow != null && vcOpt != null && vcNow > vcOpt) {
        actions.push({
          plant,
          text: `shift toward cheaper NCL/SECL to bring blended cost ₹${vcNow} → ₹${vcOpt} per kWh.`,
          type: "info",
        });
      }
    });
    return actions;
  }, [plantStatusRows]);

  const { connected, dashboardSummary } = liveData || {};
  const isOffline = connected === false;
  const liveRunStatus = dashboardSummary?.optimization?.run_status || null;
  const liveRunExists = dashboardSummary?.optimization?.latest_run_exists || false;

  return (
    <div className="page-content" id="tab-plantstatus">
      <p className="section-intro">
        Per-plant optimised allocation view: blended variable cost vs IPP benchmark,
        ACQ utilisation, stock cover, and recommended corrective actions.
      </p>

      {/* ── Live Backend Connection & Run Status Banner ── */}
      {liveData && (
        <div style={{ marginBottom: 16 }}>
          {isOffline ? (
            <div style={{
              background: "rgba(220,38,38,0.06)",
              border: "1.5px solid rgba(220,38,38,0.22)",
              borderRadius: 8,
              padding: 12,
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}>
              <span style={{ fontSize: 16 }}>⚠️</span>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--coral)", fontFamily: "var(--font-mono)" }}>
                  BACKEND OFFLINE
                </div>
                <div style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 2 }}>
                  Live backend status is unavailable. Displaying cached demo dashboard visualizations.
                </div>
              </div>
            </div>
          ) : !liveRunExists ? (
            <div style={{
              background: "rgba(148,163,184,0.06)",
              border: "1.5px solid rgba(148,163,184,0.22)",
              borderRadius: 8,
              padding: 12,
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}>
              <span style={{ fontSize: 16 }}>📊</span>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--ink-dim)", fontFamily: "var(--font-mono)" }}>
                  No Optimization Run Yet
                </div>
                <div style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 2 }}>
                  Run the optimization solver in the Allocation tab to generate live results.
                </div>
              </div>
            </div>
          ) : liveRunStatus === "COMPLETED" ? (
            <div style={{
              background: "rgba(13,148,136,0.06)",
              border: "1.5px solid rgba(13,148,136,0.22)",
              borderRadius: 8,
              padding: 12,
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}>
              <span style={{ fontSize: 16 }}>✓</span>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--teal)", fontFamily: "var(--font-mono)" }}>
                  LIVE RUN STATUS: COMPLETED / OPTIMAL
                </div>
                <div style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 2 }}>
                  The backend has successfully solved the coal allocation model.
                </div>
              </div>
            </div>
          ) : (
            <div style={{
              background: "rgba(220,38,38,0.06)",
              border: "1.5px solid rgba(220,38,38,0.22)",
              borderRadius: 8,
              padding: 12,
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}>
              <span style={{ fontSize: 16 }}>⚠️</span>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--coral)", fontFamily: "var(--font-mono)" }}>
                  OPTIMIZATION INCOMPLETE
                </div>
                <div style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 2 }}>
                  The live optimization solver run is incomplete because of critical data checks.
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Demo snapshot divider ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          margin: "8px 0 14px",
          padding: "8px 14px",
          background: "rgba(124,58,237,0.06)",
          border: "1.5px solid rgba(124,58,237,0.20)",
          borderRadius: 8,
        }}
      >
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            fontFamily: "var(--font-mono)",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: "var(--violet)",
            background: "rgba(124,58,237,0.10)",
            border: "1.5px solid rgba(124,58,237,0.25)",
            borderRadius: 20,
            padding: "2px 9px",
          }}
        >
          DEMO DATA
        </span>
        <span style={{ fontSize: 11, color: "var(--ink-muted)", fontFamily: "var(--font-body)" }}>
          The metrics, KPIs, and plant allocations below use demo snapshot data, not live backend values.
        </span>
      </div>

      {/* Fleet KPI strip */}
      <div className="ps-kpi-strip">
        <div className="ps-kpi" onClick={() => setShowDetailsDrawer(true)} style={{ cursor: "pointer" }}>
          <div className="ps-kpi-label">{savings >= 0 ? "Fleet Saving (DEMO)" : "Fleet Cost Increase (DEMO)"}</div>
          <div className={`ps-kpi-value ${savings >= 0 ? "teal" : "coral"}`}>
            {inr(fleetKpis.annualSaving, true)}
            <span className="ps-kpi-unit">Cr/yr</span>
          </div>
        </div>
        <div className="ps-kpi-divider" />
        <div className="ps-kpi">
          <div className="ps-kpi-label">Plants Behind Tied IPP (DEMO)</div>
          <div className="ps-kpi-value coral">
            {fleetKpis.plantsBehind}
            <span className="ps-kpi-unit">/ {fleetKpis.plantsTotal}</span>
          </div>
        </div>
        <div className="ps-kpi-divider" />
        <div className="ps-kpi">
          <div className="ps-kpi-label">Stations Modelled (DEMO)</div>
          <div className="ps-kpi-value teal">{fleetKpis.stationsModelled}</div>
        </div>
        <div className="ps-kpi-divider" />
        <div className="ps-kpi">
          <div className="ps-kpi-label">Cheapest Source (DEMO)</div>
          <div className="ps-kpi-value violet">{fleetKpis.cheapestSource}</div>
          <div className="ps-kpi-sub">₹{fleetKpis.cheapestVc}/kWh fuel</div>
        </div>
      </div>

      {/* Optimised allocation by plant */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <span className="panel-title">Optimised allocation by plant</span>
            <span style={{ marginLeft: 12, fontSize: 11, color: "var(--ink-dim)", fontFamily: "var(--font-mono)" }}>
              minimise blended fuel cost within ACQ, GCV floor &amp; take-or-pay
            </span>
          </div>
          <span className="panel-badge violet">DEMO DATA</span>
        </div>

        <table className="data-table ps-table">
          <thead>
            <tr>
              <th style={{ width: 140 }}>Plant</th>
              <th style={{ width: 280 }}>Optimised Source Mix</th>
              <th style={{ width: 72, textAlign: "right" }}>VC Now</th>
              <th style={{ width: 72, textAlign: "right" }}>VC Opt.</th>
              <th style={{ width: 80, textAlign: "right" }}>Δ Rs/kWh</th>
              <th style={{ width: 160 }}>ACQ Util.</th>
              <th style={{ width: 72, textAlign: "center" }}>Cover</th>
              <th style={{ width: 80, textAlign: "center" }}>vs IPP</th>
            </tr>
          </thead>
          <tbody>
            {plantStatusRows.map((row) => (
              <tr key={row.plant}>
                {/* Plant name */}
                <td>
                  <span className="status-plant-badge">{row.plant}</span>
                  {row.muMo != null && (
                    <div style={{ fontSize: 10, color: "var(--ink-dim)", fontFamily: "var(--font-mono)", marginTop: 4 }}>
                      {row.muMo.toLocaleString("en-IN")} MU/mo
                    </div>
                  )}
                </td>

                {/* Stacked source-mix bar */}
                <td>
                  <div className="mix-bar-track">
                    {row.mix.map((s, i) => (
                      <div
                        key={i}
                        className="mix-bar-seg"
                        style={{ width: s.pct + "%", background: s.color }}
                        title={`${s.company}: ${s.pct.toFixed(0)}%`}
                      />
                    ))}
                  </div>
                  <div className="mix-labels">
                    {row.mix.map((s, i) => (
                      <span key={i} className="mix-label" style={{ color: s.color }}>
                        {s.company} {s.pct.toFixed(0)}%
                      </span>
                    ))}
                  </div>
                </td>

                {/* VC Now */}
                <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>
                  {row.vcNow ?? "—"}
                </td>

                {/* VC Opt */}
                <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 600, color: "var(--teal)" }}>
                  {row.vcOpt ?? "—"}
                </td>

                {/* Delta */}
                <td style={{ textAlign: "right" }}>
                  {row.delta != null && (
                    <span
                      className="delta-badge"
                      style={{
                        color: row.delta < 0 ? "var(--teal)" : "var(--coral)",
                        background: row.delta < 0 ? "rgba(0,212,170,0.1)" : "rgba(255,107,107,0.1)",
                      }}
                    >
                      {row.delta < 0 ? "" : "+"}{row.delta}
                    </span>
                  )}
                </td>

                {/* ACQ Utilisation */}
                <td>
                  <div className="util-wrap">
                    <div className="util-track" style={{ flex: 1, width: "auto" }}>
                      <div
                        className={`util-fill${row.avgUtil > 100 ? " over" : ""}`}
                        style={{ width: Math.min(100, row.avgUtil) + "%" }}
                      />
                    </div>
                    <span className="util-pct" style={{ minWidth: 54 }}>
                      {row.avgUtil.toFixed(0)}% of ACQ
                    </span>
                  </div>
                  {row.shortfall && (
                    <div style={{ fontSize: 10, color: "var(--coral)", fontFamily: "var(--font-mono)", marginTop: 3 }}>
                      +{Math.round(row.shortfall.shortfall_mt / 1000)}k MT spot
                    </div>
                  )}
                </td>

                {/* Stock cover */}
                <td style={{ textAlign: "center" }}>
                  {row.days != null && (
                    <span
                      style={{
                        fontFamily: "var(--font-display)",
                        fontSize: 15,
                        fontWeight: 700,
                        color: row.days < 5 ? "var(--coral)" : row.days < 10 ? "var(--amber)" : "var(--teal)",
                      }}
                    >
                      {row.days}d
                    </span>
                  )}
                </td>

                {/* VS IPP badge */}
                <td style={{ textAlign: "center" }}>
                  <span
                    className="ipp-badge"
                    style={{
                      background: row.vsIPP === "ahead" ? "rgba(0,212,170,0.12)" : "rgba(255,107,107,0.12)",
                      color:      row.vsIPP === "ahead" ? "var(--teal)"           : "var(--coral)",
                      border:     `1px solid ${row.vsIPP === "ahead" ? "rgba(0,212,170,0.25)" : "rgba(255,107,107,0.25)"}`,
                    }}
                  >
                    {row.vsIPP}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Recommended actions */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Recommended actions</span>
          <span className="panel-badge violet">{recommendedActions.length} items</span>
        </div>
        <div className="rec-actions-list">
          {recommendedActions.map((a, i) => (
            <div key={i} className="rec-action-row">
              <span className="rec-action-plant">{a.plant}:</span>
              <span className="rec-action-text">{a.text}</span>
            </div>
          ))}
          {recommendedActions.length === 0 && (
            <div style={{ color: "var(--ink-dim)", fontFamily: "var(--font-mono)", fontSize: 12, padding: "8px 0" }}>
              All plants operating within optimal parameters.
            </div>
          )}
        </div>
      </div>

      {/* VC scatter: Now vs Opt per plant */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title-graphics">VC Now vs Optimised (₹/kWh)</span>
          <span className="panel-badge teal">Savings potential</span>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart
            data={plantStatusRows.map((r) => ({ plant: shortPlant(r.plant), now: r.vcNow, opt: r.vcOpt, ipp: IPP_VC }))}
            margin={{ top: 20, right: 24, left: -10, bottom: 0 }}
          >
            <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="plant" tick={{ fill: "#8892a4", fontSize: 10, fontFamily: "var(--font-mono)" }} textAnchor="middle" axisLine={false} tickLine={false} />
            <YAxis domain={[2.2, 4.5]} tick={{ fill: "#8892a4", fontSize: 10 }} axisLine={false} tickLine={false}
              tickFormatter={(v) => "₹" + v.toFixed(2)} />
            <Bar dataKey="now" name="VC Now" fill="var(--violet)" radius={[4, 4, 0, 0]}>
              <LabelList dataKey="now" position="top" formatter={(v) => v ? "₹" + v.toFixed(2) : ""} style={{ fill: "var(--violet)", fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700 }} />
            </Bar>
            <Bar dataKey="opt" name="VC Opt" fill="var(--teal)"   radius={[4, 4, 0, 0]}>
              <LabelList dataKey="opt" position="top" formatter={(v) => v ? "₹" + v.toFixed(2) : ""} style={{ fill: "var(--teal)", fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div style={{ display: "flex", gap: 20, marginTop: 10, paddingLeft: 4 }}>
          <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
            <span style={{ width: 10, height: 10, borderRadius: 2, background: "var(--violet)", display: "inline-block" }} />
            VC Now (blended)
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
            <span style={{ width: 10, height: 10, borderRadius: 2, background: "var(--teal)", display: "inline-block" }} />
            VC Optimised
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
            <span style={{ width: 10, height: 10, borderRadius: 2, background: "var(--amber)", display: "inline-block" }} />
            IPP Benchmark (₹{IPP_VC})
          </span>
        </div>
      </div>
    </div>
  );
}
