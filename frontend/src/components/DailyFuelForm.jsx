import React, { useState } from "react";
import { supabase } from "../lib/supabaseClient";

const PLANTS = ["Anpara", "Obra B", "Obra C", "Harduaganj", "Harduaganj Extn-II", "Parichha", "Jawaharpur", "Panki Extn"];
const FUELS = ["COAL", "LDO", "LSHS"];

export default function DailyFuelForm() {
  const [form, setForm] = useState({
    plant: PLANTS[0],
    report_date: new Date().toISOString().slice(0, 10),
    fuel_type: "COAL",
    opening_balance_mt: "",
    receipt_mt: "",
    consumption_release_mt: "",
    closing_balance_mt: "",
  });
  const [status, setStatus] = useState(null);

  const opening = parseFloat(form.opening_balance_mt) || 0;
  const receipt = parseFloat(form.receipt_mt) || 0;
  const consumption = parseFloat(form.consumption_release_mt) || 0;
  const closing = parseFloat(form.closing_balance_mt) || 0;
  const expectedClosing = opening + receipt - consumption;
  const delta = +(expectedClosing - closing).toFixed(2);
  const mismatch = form.closing_balance_mt !== "" && Math.abs(delta) > 1;
  const reconReady = form.closing_balance_mt !== "";

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    if (!supabase) {
      setStatus("Demo mode — no Supabase project connected yet. Row not saved.");
      return;
    }
    const { error } = await supabase.from("daily_fuel").insert({
      ...form,
      opening_balance_mt: opening,
      receipt_mt: receipt,
      consumption_release_mt: consumption,
      closing_balance_mt: closing,
      reconciliation_flag: mismatch,
      reconciliation_delta: delta,
      submitted_via: "form",
    });
    setStatus(error ? `Error: ${error.message}` : "✓ Saved successfully.");
  };

  return (
    <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="form-grid">
        <div className="form-field">
          <label className="form-label" htmlFor="fp-plant">Plant</label>
          <select id="fp-plant" className="form-select" value={form.plant} onChange={update("plant")}>
            {PLANTS.map((p) => <option key={p}>{p}</option>)}
          </select>
        </div>

        <div className="form-field">
          <label className="form-label" htmlFor="fp-date">Report Date</label>
          <input id="fp-date" className="form-input" type="date" value={form.report_date} onChange={update("report_date")} />
        </div>

        <div className="form-field full">
          <label className="form-label" htmlFor="fp-fuel">Fuel Type</label>
          <select id="fp-fuel" className="form-select" value={form.fuel_type} onChange={update("fuel_type")}>
            {FUELS.map((f) => <option key={f}>{f}</option>)}
          </select>
        </div>

        <div className="form-field">
          <label className="form-label" htmlFor="fp-opening">Opening Balance (MT)</label>
          <input id="fp-opening" className="form-input" type="number" placeholder="0" value={form.opening_balance_mt} onChange={update("opening_balance_mt")} required />
        </div>

        <div className="form-field">
          <label className="form-label" htmlFor="fp-receipt">Receipt (MT)</label>
          <input id="fp-receipt" className="form-input" type="number" placeholder="0" value={form.receipt_mt} onChange={update("receipt_mt")} required />
        </div>

        <div className="form-field">
          <label className="form-label" htmlFor="fp-consumption">Consumption / Release (MT)</label>
          <input id="fp-consumption" className="form-input" type="number" placeholder="0" value={form.consumption_release_mt} onChange={update("consumption_release_mt")} required />
        </div>

        <div className="form-field">
          <label className="form-label" htmlFor="fp-closing">Closing Balance (MT)</label>
          <input id="fp-closing" className="form-input" type="number" placeholder="0" value={form.closing_balance_mt} onChange={update("closing_balance_mt")} required />
        </div>
      </div>

      {reconReady && (
        <div className={`form-recon ${mismatch ? "bad" : "ok"}`}>
          {mismatch
            ? `⚠ Reconciliation mismatch: expected ${expectedClosing.toFixed(0)} MT, entered ${closing} MT (Δ = ${delta} MT)`
            : `✓ Reconciliation OK — closing balance matches (expected ${expectedClosing.toFixed(0)} MT)`}
        </div>
      )}

      <button type="submit" className="submit-btn" id="fp-submit">
        Submit Entry
      </button>

      {status && (
        <div className="status-msg">{status}</div>
      )}
    </form>
  );
}
