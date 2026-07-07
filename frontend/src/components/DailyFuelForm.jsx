import React, { useState, useEffect } from "react";
import { apiUrl } from "../lib/api";

const FUELS = ["COAL", "LDO", "LSHS"];

export default function DailyFuelForm({ refreshLive }) {
  const [plants, setPlants] = useState([]);
  const [loadingPlants, setLoadingPlants] = useState(true);
  const [plantsError, setPlantsError] = useState(null);

  const [form, setForm] = useState({
    plant_id: "",
    report_date: new Date().toISOString().slice(0, 10),
    fuel_type: "COAL",
    opening_balance: "",
    receipt: "",
    consumption_release: "",
    closing_balance: "",
    remarks: "",
  });

  const [status, setStatus] = useState(null); // { type: 'success'|'error'|'info'|'warning'|'loading', message: '' }

  // ── Fetch active plants on mount ───────────────────────────────────────────
  useEffect(() => {
    const loadPlants = async () => {
      try {
        setLoadingPlants(true);
        const res = await fetch(apiUrl("/plants?page_size=100"));
        if (!res.ok) throw new Error(`Could not load plants: HTTP ${res.status}`);
        const data = await res.json();
        const activePlants = (data.items || []).filter((p) => p.is_active);
        setPlants(activePlants);
        if (activePlants.length > 0) {
          setForm((f) => ({ ...f, plant_id: activePlants[0].id }));
        }
        setPlantsError(null);
      } catch (err) {
        console.error("Plants fetch failed, falling back to static list", err);
        setPlantsError("Backend offline. Using local plant mapping.");
        const fallbackList = [
          { id: "anpara-uuid-mock", plant_name: "Anpara" },
          { id: "obra-b-uuid-mock", plant_name: "Obra B" },
          { id: "obra-c-uuid-mock", plant_name: "Obra C" },
          { id: "harduaganj-uuid-mock", plant_name: "Harduaganj" },
          { id: "jawaharpur-uuid-mock", plant_name: "Jawaharpur" },
          { id: "panki-uuid-mock", plant_name: "Panki Extn" },
          { id: "parichha-uuid-mock", plant_name: "Parichha" },
        ];
        setPlants(fallbackList);
        setForm((f) => ({ ...f, plant_id: fallbackList[0].id }));
      } finally {
        setLoadingPlants(false);
      }
    };
    loadPlants();
  }, []);

  // ── Calculation helpers ──────────────────────────────────────────────────
  const opening = parseFloat(form.opening_balance) || 0;
  const receipt = parseFloat(form.receipt) || 0;
  const consumption = parseFloat(form.consumption_release) || 0;
  const closing = parseFloat(form.closing_balance) || 0;

  const expectedClosing = opening + receipt - consumption;
  const delta = +(closing - expectedClosing).toFixed(2);
  const mismatch = form.closing_balance !== "" && Math.abs(delta) > 1.0;
  const reconReady = form.closing_balance !== "";

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  // ── Form submission ────────────────────────────────────────────────────────
  const submit = async (e) => {
    e.preventDefault();

    // 1. Client-side fuel check
    if (form.fuel_type !== "COAL") {
      setStatus({
        type: "error",
        message: "Only COAL fuel type daily stock submissions are supported by the backend system.",
      });
      return;
    }

    // 2. Client-side remarks requirement for warning record
    if (mismatch && !form.remarks.trim()) {
      setStatus({
        type: "error",
        message: "Reconciliation difference exceeds tolerance (1 MT); Remarks are mandatory for warning records.",
      });
      return;
    }

    setStatus({ type: "loading", message: "Submitting daily stock record..." });

    const payload = {
      plant_id: form.plant_id,
      report_date: form.report_date,
      opening_stock_mt: opening,
      receipt_mt: receipt,
      consumption_mt: consumption,
      closing_stock_mt: closing,
      remarks: form.remarks.trim() || null,
    };

    try {
      const resp = await fetch(apiUrl("/daily-stock"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      });

      // 3. Handle duplicates
      if (resp.status === 409) {
        setStatus({
          type: "error",
          message: "A daily stock record already exists for this plant and date.",
        });
        return;
      }

      // 4. Handle other errors
      if (!resp.ok) {
        let errorMsg = "Validation failed on backend.";
        try {
          const errData = await resp.json();
          if (errData.error && errData.error.message) {
            errorMsg = errData.error.message;
          } else if (errData.detail) {
            if (Array.isArray(errData.detail)) {
              errorMsg = errData.detail.map((d) => d.msg).join(", ");
            } else {
              errorMsg = errData.detail;
            }
          }
        } catch {
          errorMsg = `Server returned HTTP ${resp.status}`;
        }
        throw new Error(errorMsg);
      }

      // 5. Success
      const result = await resp.json();
      const backendValStatus = (result.validation_status || "ok").toUpperCase();

      setStatus({
        type: backendValStatus === "WARNING" ? "warning" : "success",
        message: `✓ Saved successfully. Backend status: ${backendValStatus}`,
      });

      // Reset numeric inputs and remarks
      setForm((prev) => ({
        ...prev,
        opening_balance: "",
        receipt: "",
        consumption_release: "",
        closing_balance: "",
        remarks: "",
      }));

      // 6. Refresh Fuel Position and status screens
      if (refreshLive) {
        refreshLive();
      }
    } catch (err) {
      if (err.message.includes("Failed to fetch") || err.message.includes("NetworkError")) {
        setStatus({
          type: "error",
          message: "Backend unavailable. Entry was not saved.",
        });
      } else {
        setStatus({
          type: "error",
          message: err.message,
        });
      }
    }
  };

  // Status visual overrides
  const getStatusStyles = () => {
    if (!status) return {};
    if (status.type === "success") {
      return { background: "rgba(13,148,136,0.08)", borderColor: "rgba(13,148,136,0.25)", color: "var(--teal)" };
    }
    if (status.type === "error") {
      return { background: "rgba(220,38,38,0.08)", borderColor: "rgba(220,38,38,0.25)", color: "var(--coral)" };
    }
    if (status.type === "warning") {
      return { background: "rgba(217,119,6,0.08)", borderColor: "rgba(217,119,6,0.25)", color: "var(--amber)" };
    }
    return { background: "var(--bg)", borderColor: "var(--border)", color: "var(--ink-muted)" };
  };

  return (
    <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 18 }} id="daily-stock-form">
      {/* Live Data Badge */}
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 4 }}>
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            fontFamily: "var(--font-mono)",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: "var(--teal)",
            background: "rgba(13,148,136,0.10)",
            border: "1.5px solid rgba(13,148,136,0.25)",
            borderRadius: 20,
            padding: "2px 9px",
          }}
        >
          LIVE BACKEND DATA
        </span>
        <span style={{ fontSize: 10, color: "var(--ink-dim)", fontFamily: "var(--font-body)" }}>
          Direct db submission layer
        </span>
      </div>

      {plantsError && (
        <div style={{ fontSize: 11, color: "var(--amber)", fontFamily: "var(--font-mono)" }}>
          ⚠️ {plantsError}
        </div>
      )}

      <div className="form-grid">
        {/* Plant select dropdown */}
        <div className="form-field">
          <label className="form-label" htmlFor="fp-plant">
            Plant {loadingPlants && <span style={{ fontSize: 10, fontStyle: "italic", color: "var(--ink-dim)" }}>(loading…)</span>}
          </label>
          <select
            id="fp-plant"
            className="form-select"
            value={form.plant_id}
            onChange={update("plant_id")}
            disabled={loadingPlants}
          >
            {plants.map((p) => (
              <option key={p.id} value={p.id}>
                {p.plant_name}
              </option>
            ))}
          </select>
        </div>

        {/* Date input */}
        <div className="form-field">
          <label className="form-label" htmlFor="fp-date">Report Date</label>
          <input
            id="fp-date"
            className="form-input"
            type="date"
            value={form.report_date}
            onChange={update("report_date")}
            required
          />
        </div>

        {/* Fuel type */}
        <div className="form-field full">
          <label className="form-label" htmlFor="fp-fuel">Fuel Type</label>
          <select
            id="fp-fuel"
            className="form-select"
            value={form.fuel_type}
            onChange={update("fuel_type")}
          >
            {FUELS.map((f) => (
              <option key={f} value={f} disabled={f !== "COAL"}>
                {f} {f !== "COAL" ? "(FastAPI Unsupported)" : ""}
              </option>
            ))}
          </select>
        </div>

        {/* Opening balance */}
        <div className="form-field">
          <label className="form-label" htmlFor="fp-opening">Opening Stock (MT)</label>
          <input
            id="fp-opening"
            className="form-input"
            type="number"
            min="0"
            step="0.01"
            placeholder="0"
            value={form.opening_balance}
            onChange={update("opening_balance")}
            required
          />
        </div>

        {/* Receipt */}
        <div className="form-field">
          <label className="form-label" htmlFor="fp-receipt">Receipt (MT)</label>
          <input
            id="fp-receipt"
            className="form-input"
            type="number"
            min="0"
            step="0.01"
            placeholder="0"
            value={form.receipt}
            onChange={update("receipt")}
            required
          />
        </div>

        {/* Consumption */}
        <div className="form-field">
          <label className="form-label" htmlFor="fp-consumption">Consumption (MT)</label>
          <input
            id="fp-consumption"
            className="form-input"
            type="number"
            min="0"
            step="0.01"
            placeholder="0"
            value={form.consumption_release}
            onChange={update("consumption_release")}
            required
          />
        </div>

        {/* Closing balance */}
        <div className="form-field">
          <label className="form-label" htmlFor="fp-closing">Closing Stock (MT)</label>
          <input
            id="fp-closing"
            className="form-input"
            type="number"
            min="0"
            step="0.01"
            placeholder="0"
            value={form.closing_balance}
            onChange={update("closing_balance")}
            required
          />
        </div>

        {/* Remarks field — Required if mismatch is active */}
        <div className="form-field full">
          <label className="form-label" htmlFor="fp-remarks">
            Remarks {mismatch && <span style={{ color: "var(--coral)", fontWeight: 700 }}>* (Required for mismatch)</span>}
          </label>
          <input
            id="fp-remarks"
            className="form-input"
            type="text"
            placeholder={mismatch ? "Reason for reconciliation mismatch..." : "Optional remarks..."}
            value={form.remarks}
            onChange={update("remarks")}
            required={mismatch}
          />
        </div>
      </div>

      {/* Recon preview panel */}
      {reconReady && (
        <div className={`form-recon ${mismatch ? "bad" : "ok"}`}>
          {mismatch
            ? `⚠ Reconciliation mismatch: expected ${expectedClosing.toFixed(1)} MT, entered ${closing.toFixed(1)} MT (Δ = ${delta > 0 ? "+" : ""}${delta} MT)`
            : `✓ Reconciliation OK — closing balance matches (expected ${expectedClosing.toFixed(1)} MT)`}
        </div>
      )}

      {/* Submit button */}
      <button type="submit" className="submit-btn" id="fp-submit" disabled={loadingPlants}>
        Submit Stock Entry
      </button>

      {/* Status messages */}
      {status && (
        <div className="status-msg" style={getStatusStyles()}>
          {status.message}
        </div>
      )}
    </form>
  );
}
