import React, { useState } from "react";
import { supabase } from "../lib/supabaseClient";

const PLANTS = [
  "Anpara",
  "Obra B",
  "Obra C",
  "Harduaganj",
  "Harduaganj Extn-II",
  "Parichha",
  "Jawaharpur",
  "Panki Extn"
];

// Initial demo data from the reference PDF Action Plan
const INITIAL_AGREEMENTS = [
  {
    ipp_name: "Bajaj Energy, Lalitpur TPS",
    ipp_vc: 3.39,
    unl_tps_name: "Panki",
    unl_vc: 3.31,
    tied_ipp_details: "Lalitpur, Lalitpur, UP",
    minimization_rule: "Already CCL coal with 10% premium. To improve coal quality, diversion of minimum 10 rakes per month from NCL is proposed.",
    target_vc: null,
    period_start: "2026-04-01",
    period_end: "2026-04-15"
  },
  {
    ipp_name: "Reliance Power, ROSA II",
    ipp_vc: 3.75,
    unl_tps_name: "Parichha",
    unl_vc: 3.69,
    tied_ipp_details: "ROSA, Shahjahanpur, UP",
    minimization_rule: "VC will reduce once unit will start operating at full load. SECL rakes (10 rakes per month) will be provided to compensate NCL diversion.",
    target_vc: null,
    period_start: "2026-04-01",
    period_end: "2026-04-15"
  },
  {
    ipp_name: "KSK Mahanadi",
    ipp_vc: 4.19,
    unl_tps_name: "Jawaharpur",
    unl_vc: 4.64,
    tied_ipp_details: "KSK Mahanadi, Chhattisgarh",
    minimization_rule: "Target VC = Rs 4.15/Unit, diversion from CCL (15 rakes/month), NCL (5 rakes per month), loading from SECL.",
    target_vc: 4.15,
    period_start: "2026-04-01",
    period_end: "2026-04-15"
  },
  {
    ipp_name: "BEPL, Khambharkhera",
    ipp_vc: 4.10,
    unl_tps_name: "Harduaganj D (2X250 MW)",
    unl_vc: 4.35,
    tied_ipp_details: "BEPL, Khambhankhera, Lakhimpur Kheri, UP",
    minimization_rule: "Target VC = Rs 3.70 /unit; after reduction in premium.",
    target_vc: 3.70,
    period_start: "2026-04-01",
    period_end: "2026-04-15"
  },
  {
    ipp_name: "BEPL, Utraula",
    ipp_vc: 3.99,
    unl_tps_name: "Harduaganj E (1X660 MW)",
    unl_vc: 4.10,
    tied_ipp_details: "BEPL, Utraula, Balrampur, UP",
    minimization_rule: "Target VC = Rs 3.60/unit",
    target_vc: 3.60,
    period_start: "2026-04-01",
    period_end: "2026-04-15"
  }
];

export default function IppAgreementForm() {
  const [agreements, setAgreements] = useState(INITIAL_AGREEMENTS);
  const [form, setForm] = useState({
    ipp_name: "",
    ipp_vc: "",
    unl_tps_parent: PLANTS[0],
    unl_tps_desc: "",
    unl_vc: "",
    tied_ipp_details: "",
    minimization_rule: "",
    target_vc: "",
    period_start: new Date().toISOString().slice(0, 10),
    period_end: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
  });
  const [status, setStatus] = useState(null);

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    const unl_tps_name = form.unl_tps_desc 
      ? `${form.unl_tps_parent} ${form.unl_tps_desc}`
      : form.unl_tps_parent;

    const newAgreement = {
      ipp_name: form.ipp_name,
      ipp_vc: parseFloat(form.ipp_vc) || 0,
      unl_tps_name: unl_tps_name,
      unl_vc: parseFloat(form.unl_vc) || 0,
      tied_ipp_details: form.tied_ipp_details || null,
      minimization_rule: form.minimization_rule || null,
      target_vc: form.target_vc ? parseFloat(form.target_vc) : null,
      period_start: form.period_start || null,
      period_end: form.period_end || null
    };

    if (supabase) {
      const { error } = await supabase.from("ipp_vc_agreements").insert(newAgreement);
      if (error) {
        setStatus(`Error saving to DB: ${error.message}`);
        return;
      }
    }

    setAgreements([newAgreement, ...agreements]);
    setStatus("✓ Agreement saved successfully.");
    
    // reset form (keep dates and parent plant)
    setForm({
      ...form,
      ipp_name: "",
      ipp_vc: "",
      unl_tps_desc: "",
      unl_vc: "",
      tied_ipp_details: "",
      minimization_rule: "",
      target_vc: ""
    });
    
    setTimeout(() => setStatus(null), 4000);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 30 }}>
      <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <div className="form-grid">
          <div className="form-field">
            <label className="form-label" htmlFor="ag-ipp-name">Name of IPP TPS</label>
            <input id="ag-ipp-name" className="form-input" placeholder="e.g. Bajaj Energy, Lalitpur TPS" value={form.ipp_name} onChange={update("ipp_name")} required />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="ag-ipp-vc">IPP Variable Charge (₹/Unit)</label>
            <input id="ag-ipp-vc" className="form-input" type="number" step="0.01" placeholder="e.g. 3.39" value={form.ipp_vc} onChange={update("ipp_vc")} required />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="ag-unl-parent">UNL TPS Parent Plant</label>
            <select id="ag-unl-parent" className="form-select" value={form.unl_tps_parent} onChange={update("unl_tps_parent")}>
              {PLANTS.map((p) => <option key={p}>{p}</option>)}
            </select>
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="ag-unl-desc">Specific Unit / Descriptor</label>
            <input id="ag-unl-desc" className="form-input" placeholder="e.g. D (2X250 MW) or Extn" value={form.unl_tps_desc} onChange={update("unl_tps_desc")} />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="ag-unl-vc">UNL Variable Charge (₹/Unit)</label>
            <input id="ag-unl-vc" className="form-input" type="number" step="0.01" placeholder="e.g. 3.31" value={form.unl_vc} onChange={update("unl_vc")} required />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="ag-tied-details">Tied IPP & Location</label>
            <input id="ag-tied-details" className="form-input" placeholder="e.g. Lalitpur, Lalitpur, UP" value={form.tied_ipp_details} onChange={update("tied_ipp_details")} />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="ag-target-vc">Target VC after Action (₹/Unit)</label>
            <input id="ag-target-vc" className="form-input" type="number" step="0.01" placeholder="e.g. 3.70 (Optional)" value={form.target_vc} onChange={update("target_vc")} />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="ag-start-date">Period Start</label>
            <input id="ag-start-date" className="form-input" type="date" value={form.period_start} onChange={update("period_start")} />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="ag-end-date">Period End</label>
            <input id="ag-end-date" className="form-input" type="date" value={form.period_end} onChange={update("period_end")} />
          </div>

          <div className="form-field full">
            <label className="form-label" htmlFor="ag-rules">VC Minimization Rules & Proposals</label>
            <textarea id="ag-rules" className="form-input" style={{ minHeight: 70, resize: "vertical" }} placeholder="e.g. Diversion of minimum 10 rakes per month from NCL..." value={form.minimization_rule} onChange={update("minimization_rule")} />
          </div>
        </div>

        <button type="submit" className="submit-btn" id="ag-submit">
          Save Agreement
        </button>

        {status && (
          <div className="status-msg">{status}</div>
        )}
      </form>

      <div style={{ marginTop: 20 }}>
        <h3 style={{ fontSize: 16, fontWeight: 700, color: "var(--heading-primary)", marginBottom: 12 }}>Active Reference Agreements</h3>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>IPP TPS (VC)</th>
                <th>UNL TPS (VC)</th>
                <th>Tied IPP & Location</th>
                <th>Target VC</th>
                <th>Minimization Rule / Action Plan</th>
              </tr>
            </thead>
            <tbody>
              {agreements.map((a, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 700 }}>
                    {a.ipp_name}
                    <div style={{ fontSize: 11, color: "var(--ink-muted)", fontFamily: "var(--font-mono)", marginTop: 2 }}>
                      ₹{a.ipp_vc?.toFixed(2)}/Unit
                    </div>
                  </td>
                  <td style={{ fontWeight: 700 }}>
                    {a.unl_tps_name}
                    <div style={{ fontSize: 11, color: "var(--ink-muted)", fontFamily: "var(--font-mono)", marginTop: 2 }}>
                      ₹{a.unl_vc?.toFixed(2)}/Unit
                    </div>
                  </td>
                  <td>{a.tied_ipp_details || "—"}</td>
                  <td style={{ fontWeight: 700, color: "var(--teal)", fontFamily: "var(--font-mono)" }}>
                    {a.target_vc ? `₹${a.target_vc.toFixed(2)}` : "—"}
                  </td>
                  <td style={{ fontSize: 12, lineHeight: 1.4, color: "var(--ink-muted)", fontFamily: "var(--font-body)" }}>
                    {a.minimization_rule || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
