import React, { useState, useEffect } from "react";
import { apiUrl } from "../lib/api";

export default function ReviewQueueTab({ role, refreshLive }) {
  const [loading, setLoading] = useState(true);
  const [plants, setPlants] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [constraints, setConstraints] = useState([]);
  const [landedCosts, setLandedCosts] = useState([]);
  const [variableCosts, setVariableCosts] = useState([]);
  const [coalCompanies, setCoalCompanies] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  
  // Status and offline states
  const [statusMsg, setStatusMsg] = useState(null);
  const [offline, setOffline] = useState(false);
  const [resolvingId, setResolvingId] = useState(null);

  // User input states for mapping & review
  const [selectedPlants, setSelectedPlants] = useState({}); // { recordId: plantId }
  const [selectedCoalCompanies, setSelectedCoalCompanies] = useState({}); // { recordId: companyId }
  const [selectedSuppliers, setSelectedSuppliers] = useState({}); // { recordId: supplierId }
  
  // Confirmation Panel States
  const [confirmingApproveId, setConfirmingApproveId] = useState(null);
  const [confirmingRejectId, setConfirmingRejectId] = useState(null);
  const [rejectionReason, setRejectionReason] = useState("");

  const allowedRoles = ["Fuel Cell Analyst", "Fuel Cell Approver", "System Administrator"];

  const loadData = async () => {
    setLoading(true);
    setOffline(false);
    setStatusMsg(null);
    try {
      // Fetch in parallel with individual safe unpacking
      const [
        plantsRes,
        docsRes,
        constraintsRes,
        landedRes,
        vcRes,
        companiesRes,
        suppliersRes
      ] = await Promise.all([
        fetch(apiUrl("/plants?page_size=100")).then(r => r.json()).catch(() => null),
        fetch(apiUrl("/documents?page_size=100")).then(r => r.json()).catch(() => null),
        fetch(apiUrl("/fsa-constraints?page_size=100")).then(r => r.json()).catch(() => null),
        fetch(apiUrl("/landed-costs?page_size=100")).then(r => r.json()).catch(() => null),
        fetch(apiUrl("/variable-cost?page_size=100")).then(r => r.json()).catch(() => null),
        fetch(apiUrl("/coal-companies?page_size=100")).then(r => r.json()).catch(() => null),
        fetch(apiUrl("/suppliers?page_size=100")).then(r => r.json()).catch(() => null)
      ]);

      if (plantsRes === null && docsRes === null && constraintsRes === null) {
        throw new Error("Cannot reach FastAPI server");
      }

      setPlants(plantsRes?.items || plantsRes || []);
      setDocuments(docsRes?.items || docsRes || []);
      setConstraints(constraintsRes?.items || constraintsRes || []);
      setLandedCosts(landedRes?.items || landedRes || []);
      setVariableCosts(vcRes?.items || vcRes || []);
      setCoalCompanies(companiesRes?.items || companiesRes || []);
      setSuppliers(suppliersRes?.items || suppliersRes || []);
    } catch (err) {
      console.error("Error loading backend review queue data:", err);
      setOffline(true);
      setStatusMsg({ type: "error", message: "Backend offline. Could not load pending review queue." });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Lookup maps
  const plantMap = React.useMemo(() => {
    const m = {};
    plants.forEach(p => { m[p.id] = p.plant_name; });
    return m;
  }, [plants]);

  const docMap = React.useMemo(() => {
    const m = {};
    documents.forEach(d => { m[d.id] = d; });
    return m;
  }, [documents]);

  const companyMap = React.useMemo(() => {
    const m = {};
    coalCompanies.forEach(c => { m[c.id] = c.company_name; });
    return m;
  }, [coalCompanies]);

  const supplierMap = React.useMemo(() => {
    const m = {};
    suppliers.forEach(s => { m[s.id] = s.supplier_name; });
    return m;
  }, [suppliers]);

  // Construct queue items
  const queueItems = React.useMemo(() => {
    const items = [];

    // 1. FSA & Bridge Linkage Constraints
    constraints.forEach(c => {
      const isPending = c.status === "PENDING_REVIEW" || c.status === "REJECTED" || !c.plant_id;
      if (isPending) {
        items.push({
          id: c.id,
          category: "FSA_CONSTRAINT",
          type: c.constraint_type === "BRIDGE_LINKAGE" ? "Bridge Linkage" : "FSA Constraint",
          status: c.status,
          plantId: c.plant_id,
          rawSourceName: c.raw_source_name,
          coalCompany: c.coal_company,
          coalCompanyId: c.coal_company_id,
          quantity: c.quantity_mt ?? c.annual_contract_quantity_mt,
          quantityLac: c.quantity_lac_mt,
          monthlyCap: c.monthly_cap_mt,
          validTo: c.valid_to || c.contract_end_date,
          parserNotes: c.parser_notes,
          documentId: c.document_id,
          needsReview: c.status === "PENDING_REVIEW" || !c.plant_id
        });
      }
    });

    // 2. Landed Costs
    landedCosts.forEach(l => {
      const isPending = l.status === "PENDING_REVIEW" || l.status === "REJECTED" || l.needs_review || !l.plant_id;
      if (isPending) {
        items.push({
          id: l.id,
          category: "LANDED_COST",
          type: "Landed Cost",
          status: l.status,
          plantId: l.plant_id,
          rawSourceName: l.raw_source_name,
          supplierId: l.supplier_id,
          totalLandedCost: l.total_landed_cost,
          gcv: l.weighted_avg_gcv_kcal_per_kg,
          effectiveFrom: l.effective_from,
          effectiveTo: l.effective_to,
          parserNotes: l.parser_notes,
          documentId: l.document_id,
          needsReview: l.needs_review || !l.plant_id
        });
      }
    });

    // 3. Variable Costs
    variableCosts.forEach(v => {
      const isPending = v.needs_review === true || !v.plant_id;
      if (isPending) {
        items.push({
          id: v.id,
          category: "VARIABLE_COST",
          type: "Variable Cost",
          status: v.needs_review ? "NEEDS REVIEW" : "UNMAPPED PLANT",
          plantId: v.plant_id,
          rawSourceName: v.source_plant_name,
          variableCostPerUnit: v.variable_cost_per_unit,
          unit: v.unit,
          effectiveDate: v.effective_date,
          parserNotes: null,
          documentId: v.document_id,
          needsReview: v.needs_review
        });
      }
    });

    // Sort by timestamp if document metadata is available
    return items.sort((a, b) => {
      const aTime = docMap[a.documentId]?.created_at || "";
      const bTime = docMap[b.documentId]?.created_at || "";
      return bTime.localeCompare(aTime);
    });
  }, [constraints, landedCosts, variableCosts, docMap]);

  // Action Handlers
  const handleApprove = async (item) => {
    if (!allowedRoles.includes(role)) {
      setStatusMsg({ type: "error", message: `Access Denied: Your role '${role}' is not authorized to resolve tasks.` });
      return;
    }

    const mappedPlantId = selectedPlants[item.id] !== undefined ? selectedPlants[item.id] : item.plantId;
    if (!mappedPlantId) {
      setStatusMsg({ type: "error", message: "Cannot approve: Canonical plant mapping is required." });
      return;
    }

    setResolvingId(item.id);
    setStatusMsg(null);

    try {
      let resp;
      if (item.category === "FSA_CONSTRAINT") {
        const payload = {
          status: "APPROVED",
          plant_id: mappedPlantId,
          coal_company_id: selectedCoalCompanies[item.id] || item.coalCompanyId || null
        };
        resp = await fetch(apiUrl(`/fsa-constraints/${item.id}/review`), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
      } else if (item.category === "LANDED_COST") {
        const payload = {
          status: "APPROVED",
          plant_id: mappedPlantId,
          supplier_id: selectedSuppliers[item.id] || item.supplierId || null
        };
        resp = await fetch(apiUrl(`/landed-costs/${item.id}/review`), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
      } else if (item.category === "VARIABLE_COST") {
        const payload = {
          plant_id: mappedPlantId,
          needs_review: false
        };
        resp = await fetch(apiUrl(`/variable-cost/${item.id}/review`), {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
      }

      if (resp && resp.ok) {
        setStatusMsg({ type: "success", message: `✓ Record approved and now eligible for optimization.` });
        setConfirmingApproveId(null);
        // Refresh local data & global hooks
        await loadData();
        if (refreshLive) refreshLive();
      } else {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData?.error?.message || `Server returned ${resp.status}`);
      }
    } catch (err) {
      console.error("Approval error:", err);
      setStatusMsg({ type: "error", message: `Approval failed: ${err.message}` });
    } finally {
      setResolvingId(null);
    }
  };

  const handleReject = async (item) => {
    if (!allowedRoles.includes(role)) {
      setStatusMsg({ type: "error", message: `Access Denied: Your role '${role}' is not authorized to resolve tasks.` });
      return;
    }

    if (!rejectionReason.trim()) {
      setStatusMsg({ type: "error", message: "Cannot reject: Rejection reason is required." });
      return;
    }

    if (item.category === "VARIABLE_COST") {
      setStatusMsg({ type: "error", message: "Variable Cost review rejection is not supported by backend." });
      return;
    }

    setResolvingId(item.id);
    setStatusMsg(null);

    try {
      let resp;
      // We gather a rejection reason locally, but do not append to API parameters since the schema doesn't accept extra attributes.
      if (item.category === "FSA_CONSTRAINT") {
        const payload = {
          status: "REJECTED",
          plant_id: item.plantId || null,
          coal_company_id: item.coalCompanyId || null
        };
        resp = await fetch(apiUrl(`/fsa-constraints/${item.id}/review`), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
      } else if (item.category === "LANDED_COST") {
        const payload = {
          status: "REJECTED",
          plant_id: item.plantId || null,
          supplier_id: item.supplierId || null
        };
        resp = await fetch(apiUrl(`/landed-costs/${item.id}/review`), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
      }

      if (resp && resp.ok) {
        setStatusMsg({ type: "success", message: `Record rejected. It will not be used for optimization. (Reason: "${rejectionReason}")` });
        setConfirmingRejectId(null);
        setRejectionReason("");
        await loadData();
        if (refreshLive) refreshLive();
      } else {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData?.error?.message || `Server returned ${resp.status}`);
      }
    } catch (err) {
      console.error("Rejection error:", err);
      setStatusMsg({ type: "error", message: `Rejection failed: ${err.message}` });
    } finally {
      setResolvingId(null);
    }
  };

  const getStatusColor = (statusVal) => {
    if (!statusVal) return {};
    const norm = statusVal.toUpperCase();
    if (norm === "APPROVED") return { color: "var(--teal)", background: "rgba(13,148,136,0.08)" };
    if (norm === "REJECTED") return { color: "var(--coral)", background: "rgba(220,38,38,0.08)" };
    if (norm === "NEEDS REVIEW" || norm === "PENDING_REVIEW") return { color: "var(--amber)", background: "rgba(217,119,6,0.08)" };
    return { color: "var(--sky)", background: "rgba(2,132,199,0.08)" };
  };

  const getMsgStyle = (msg) => {
    if (!msg) return {};
    if (msg.type === "success") {
      return { background: "rgba(13,148,136,0.08)", borderColor: "rgba(13,148,136,0.25)", color: "var(--teal)" };
    }
    return { background: "rgba(220,38,38,0.08)", borderColor: "rgba(220,38,38,0.25)", color: "var(--coral)" };
  };

  if (loading) {
    return (
      <div className="page-content" id="tab-review">
        <p style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--ink-dim)", padding: "20px 0" }}>
          Loading pending review items…
        </p>
      </div>
    );
  }

  return (
    <div className="page-content" id="tab-review">
      {/* ── Status Header ── */}
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12 }}>
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
        <span style={{ fontSize: 11, color: "var(--ink-muted)", fontFamily: "var(--font-body)" }}>
          Direct connection to FastAPI review workflow.
        </span>
        <button
          onClick={loadData}
          style={{
            marginLeft: "auto",
            background: "var(--bg)", border: "1.5px solid var(--border)",
            borderRadius: 8, padding: "4px 10px", cursor: "pointer",
            fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-muted)",
            fontWeight: 600
          }}
        >
          ↻ Refresh Queue
        </button>
      </div>

      <p className="section-intro">
        Inspect extracted operational constraints, landed cost structures, and plant-level variable cost files.
        Ensure correct canonical mapping before approving items for coal allocation runs.
      </p>

      {/* ── Message Alert ── */}
      {statusMsg && (
        <div className="status-msg" style={{ marginBottom: 20, ...getMsgStyle(statusMsg) }}>
          {statusMsg.message}
        </div>
      )}

      {/* ── Offline Panel ── */}
      {offline ? (
        <div className="panel" style={{ padding: "40px 20px", textAlign: "center" }}>
          <h3 style={{ color: "var(--coral)" }}>⚠️ Connection Lost</h3>
          <p style={{ marginTop: 8, fontSize: 13, color: "var(--ink-muted)" }}>
            Unable to connect to the FastAPI document registry.
          </p>
          <button onClick={loadData} className="submit-btn" style={{ marginTop: 16, maxWidth: 160 }}>
            Retry Connection
          </button>
        </div>
      ) : queueItems.length === 0 ? (
        /* ── Empty State ── */
        <div className="panel" style={{ padding: "40px 20px", textAlign: "center", color: "var(--ink-muted)" }}>
          <h3>✓ Review Queue Empty</h3>
          <p style={{ marginTop: 8, fontSize: 13 }}>No records are waiting for review.</p>
        </div>
      ) : (
        /* ── Pending Items Grid ── */
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          {queueItems.map((item) => {
            const doc = docMap[item.documentId];
            const mappedPlantId = selectedPlants[item.id] !== undefined ? selectedPlants[item.id] : item.plantId;
            const isUnmapped = !mappedPlantId;

            return (
              <div key={item.id} className="panel" style={{ border: "1.5px solid var(--border-bright)" }}>
                
                {/* Panel Header */}
                <div className="panel-header" style={{ borderBottom: "1px solid var(--border)", paddingBottom: 12, marginBottom: 12 }}>
                  <div>
                    <span className="panel-badge violet" style={{ marginRight: 10, textTransform: "uppercase", fontSize: 9 }}>
                      {item.type}
                    </span>
                    <span style={{ fontSize: 12, color: "var(--ink-muted)" }}>
                      Source: <strong>{doc?.original_filename || "Reference Document"}</strong>
                      {doc?.created_at && ` (Uploaded: ${new Date(doc.created_at).toLocaleDateString("en-IN")})`}
                    </span>
                  </div>
                  <span className="panel-badge" style={{ ...getStatusColor(item.status), textTransform: "uppercase", fontSize: 9 }}>
                    {isUnmapped ? "UNMAPPED PLANT" : item.status.replace("_", " ")}
                  </span>
                </div>

                {/* Extracted Details Grid */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: 16 }}>
                  <div>
                    <h4 style={{ fontSize: 11, textTransform: "uppercase", color: "var(--ink-dim)", marginBottom: 6 }}>Extracted Data Fields</h4>
                    <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
                      {item.category === "FSA_CONSTRAINT" && (
                        <>
                          <div><strong>Coal Company:</strong> {item.coalCompany || "—"}</div>
                          <div><strong>Annual Quantity (ACQ):</strong> {item.quantity ? `${item.quantity.toLocaleString("en-IN")} MT` : "—"}</div>
                          {item.quantityLac && <div><strong>Quantity (Lac MT):</strong> {item.quantityLac}</div>}
                          {item.monthlyCap && <div><strong>Monthly Cap:</strong> {item.monthlyCap.toLocaleString("en-IN")} MT</div>}
                          {item.validTo && <div><strong>Valid To:</strong> {new Date(item.validTo).toLocaleDateString("en-IN")}</div>}
                        </>
                      )}
                      {item.category === "LANDED_COST" && (
                        <>
                          <div><strong>Total Landed Cost:</strong> {item.totalLandedCost ? `₹${item.totalLandedCost.toFixed(2)}/MT` : "—"}</div>
                          <div><strong>Weighted GCV:</strong> {item.gcv ? `${item.gcv.toFixed(0)} kcal/kg` : "—"}</div>
                          {item.effectiveFrom && (
                            <div><strong>Effective:</strong> {new Date(item.effectiveFrom).toLocaleDateString("en-IN")} to {item.effectiveTo ? new Date(item.effectiveTo).toLocaleDateString("en-IN") : "Indefinite"}</div>
                          )}
                        </>
                      )}
                      {item.category === "VARIABLE_COST" && (
                        <>
                          <div><strong>Variable Cost:</strong> {item.variableCostPerUnit ? `₹${item.variableCostPerUnit.toFixed(4)}/kWh` : "—"}</div>
                          {item.unit && <div><strong>Unit:</strong> {item.unit}</div>}
                          {item.effectiveDate && <div><strong>Effective Date:</strong> {new Date(item.effectiveDate).toLocaleDateString("en-IN")}</div>}
                        </>
                      )}
                    </div>
                  </div>

                  {/* Mapping Fields */}
                  <div>
                    <h4 style={{ fontSize: 11, textTransform: "uppercase", color: "var(--ink-dim)", marginBottom: 6 }}>Canonical Plant Association</h4>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      <div style={{ fontSize: 12 }}>
                        <span style={{ color: "var(--ink-dim)" }}>Extracted Source Name: </span>
                        <strong style={{ color: "var(--ink)" }}>{item.rawSourceName || "—"}</strong>
                      </div>
                      
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <label style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-muted)" }} htmlFor={`plant-select-${item.id}`}>
                          Mapped Canonical Plant:
                        </label>
                        <select
                          id={`plant-select-${item.id}`}
                          className="form-select"
                          style={{ fontSize: 12, padding: "5px 8px" }}
                          value={mappedPlantId || ""}
                          onChange={(e) => setSelectedPlants({ ...selectedPlants, [item.id]: e.target.value })}
                        >
                          <option value="">-- Mapped / Unresolved --</option>
                          {plants.map(p => (
                            <option key={p.id} value={p.id}>{p.plant_name}</option>
                          ))}
                        </select>
                        {isUnmapped && (
                          <div style={{ fontSize: 10, color: "var(--coral)", marginTop: 2 }}>
                            ⚠️ Plant mapping is required to enable approval actions.
                          </div>
                        )}
                      </div>

                      {/* Optional Coal Company dropdown for FSA */}
                      {item.category === "FSA_CONSTRAINT" && (
                        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 4 }}>
                          <label style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-muted)" }}>
                            Mapped Coal Company:
                          </label>
                          <select
                            className="form-select"
                            style={{ fontSize: 12, padding: "5px 8px" }}
                            value={selectedCoalCompanies[item.id] || item.coalCompanyId || ""}
                            onChange={(e) => setSelectedCoalCompanies({ ...selectedCoalCompanies, [item.id]: e.target.value })}
                          >
                            <option value="">-- Unmapped --</option>
                            {coalCompanies.map(c => (
                              <option key={c.id} value={c.id}>{c.company_name}</option>
                            ))}
                          </select>
                        </div>
                      )}

                      {/* Optional Supplier dropdown for Landed Cost */}
                      {item.category === "LANDED_COST" && (
                        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 4 }}>
                          <label style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-muted)" }}>
                            Mapped Supplier:
                          </label>
                          <select
                            className="form-select"
                            style={{ fontSize: 12, padding: "5px 8px" }}
                            value={selectedSuppliers[item.id] || item.supplierId || ""}
                            onChange={(e) => setSelectedSuppliers({ ...selectedSuppliers, [item.id]: e.target.value })}
                          >
                            <option value="">-- Unmapped --</option>
                            {suppliers.map(s => (
                              <option key={s.id} value={s.id}>{s.supplier_name}</option>
                            ))}
                          </select>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Parser Warnings / Notes */}
                {item.parserNotes && (
                  <div style={{ fontSize: 11, color: "var(--amber)", background: "rgba(217,119,6,0.05)", border: "1px solid rgba(217,119,6,0.15)", padding: "6px 12px", borderRadius: 6, marginBottom: 12 }}>
                    <strong>Parser Notes:</strong> {item.parserNotes}
                  </div>
                )}

                {/* ── Action Section ── */}
                {confirmingApproveId === item.id ? (
                  /* Compact Approval Confirmation Panel */
                  <div style={{ padding: 12, background: "rgba(13,148,136,0.05)", border: "1.5px dashed var(--teal)", borderRadius: 8 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--teal)", marginBottom: 8 }}>
                      Confirm Approval?
                    </div>
                    <p style={{ fontSize: 12, color: "var(--ink-muted)", marginBottom: 12 }}>
                      This will associate raw plant <strong>{item.rawSourceName}</strong> with canonical plant <strong>{plantMap[mappedPlantId]}</strong> and activate this record for optimizations.
                    </p>
                    <div style={{ display: "flex", gap: 10 }}>
                      <button
                        className="submit-btn"
                        style={{ background: "var(--teal)", fontSize: 12, padding: "4px 10px", minWidth: 100 }}
                        disabled={resolvingId === item.id}
                        onClick={() => handleApprove(item)}
                      >
                        {resolvingId === item.id ? "⏳ Approving…" : "Approve Record"}
                      </button>
                      <button
                        className="submit-btn"
                        style={{ background: "var(--border)", color: "var(--ink)", fontSize: 12, padding: "4px 10px", minWidth: 80 }}
                        onClick={() => setConfirmingApproveId(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : confirmingRejectId === item.id ? (
                  /* Compact Rejection Confirmation Panel */
                  <div style={{ padding: 12, background: "rgba(220,38,38,0.05)", border: "1.5px dashed var(--coral)", borderRadius: 8 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--coral)", marginBottom: 8 }}>
                      Confirm Rejection?
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 12 }}>
                      <label style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-muted)" }} htmlFor={`reject-reason-${item.id}`}>
                        Specify Rejection Reason (Required):
                      </label>
                      <input
                        id={`reject-reason-${item.id}`}
                        type="text"
                        className="form-input"
                        placeholder="e.g. Invalid document layout, GCV mismatch..."
                        style={{ fontSize: 12 }}
                        value={rejectionReason}
                        onChange={(e) => setRejectionReason(e.target.value)}
                      />
                    </div>
                    <div style={{ display: "flex", gap: 10 }}>
                      <button
                        className="submit-btn"
                        style={{ background: "var(--coral)", fontSize: 12, padding: "4px 10px", minWidth: 100 }}
                        disabled={resolvingId === item.id || !rejectionReason.trim()}
                        onClick={() => handleReject(item)}
                      >
                        {resolvingId === item.id ? "⏳ Rejecting…" : "Confirm Rejection"}
                      </button>
                      <button
                        className="submit-btn"
                        style={{ background: "var(--border)", color: "var(--ink)", fontSize: 12, padding: "4px 10px", minWidth: 80 }}
                        onClick={() => {
                          setConfirmingRejectId(null);
                          setRejectionReason("");
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  /* Default Actions */
                  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <button
                      className="submit-btn"
                      style={{ background: isUnmapped ? "var(--border)" : "var(--teal)", cursor: isUnmapped ? "not-allowed" : "pointer" }}
                      disabled={isUnmapped}
                      onClick={() => {
                        setConfirmingApproveId(item.id);
                        setConfirmingRejectId(null);
                      }}
                    >
                      Approve
                    </button>
                    
                    {/* Rejection is only supported for FSA & Landed Cost on the backend */}
                    {item.category !== "VARIABLE_COST" ? (
                      <button
                        className="submit-btn"
                        style={{ background: "var(--coral)" }}
                        onClick={() => {
                          setConfirmingRejectId(item.id);
                          setConfirmingApproveId(null);
                        }}
                      >
                        Reject
                      </button>
                    ) : (
                      <span style={{ fontSize: 11, color: "var(--ink-muted)", fontStyle: "italic", marginLeft: 10 }}>
                        Variable Cost review actions are limited to mapping updates. Rejection is not supported.
                      </span>
                    )}
                  </div>
                )}

              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
