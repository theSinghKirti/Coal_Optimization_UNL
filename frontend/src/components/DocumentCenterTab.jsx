import React, { useState, useEffect, useCallback, useMemo } from "react";
import { apiUrl } from "../lib/api";

const DOC_TYPES = [
  { value: "VARIABLE_COST_PDF", label: "Variable Cost PDF (FastAPI Autoparse)" },
  { value: "FSA_BRIDGE_LINKAGE_DOCUMENT", label: "FSA / Bridge Linkage PDF (Manual Extract)" },
  { value: "LANDED_COST_DOCUMENT", label: "Landed Cost PDF (Manual Extract)" },
];

export default function DocumentCenterTab({ role, refreshLive }) {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null); // { type: 'success'|'error'|'info'|'warning', message: '' }

  // Plants list state for plant-scoped generic documents
  const [plants, setPlants] = useState([]);
  const [loadingPlants, setLoadingPlants] = useState(true);

  // Form State
  const [docType, setDocType] = useState("VARIABLE_COST_PDF");
  const [plantId, setPlantId] = useState("");
  const [notes, setNotes] = useState("");
  const [file, setFile] = useState(null);

  // Map to track extraction status/details of individual documents (docId -> { extracted, loading, error, records, notes })
  const [extractions, setExtractions] = useState({});

  // ── Fetch active plants ───────────────────────────────────────────────────
  useEffect(() => {
    const loadPlants = async () => {
      try {
        setLoadingPlants(true);
        const res = await fetch(apiUrl("/plants?page_size=100"));
        if (!res.ok) throw new Error("Could not load plants");
        const data = await res.json();
        setPlants((data.items || []).filter((p) => p.is_active));
      } catch (err) {
        console.error("Plants fetch failed", err);
      } finally {
        setLoadingPlants(false);
      }
    };
    loadPlants();
  }, []);

  const plantMap = useMemo(() => {
    return Object.fromEntries(plants.map((p) => [p.id, p.plant_name]));
  }, [plants]);

  // ── Fetch extraction status for a single document ─────────────────────────
  const fetchExtractionStatus = useCallback(async (docId, type) => {
    if (type !== "FSA_BRIDGE_LINKAGE_DOCUMENT" && type !== "LANDED_COST_DOCUMENT") {
      return;
    }
    setExtractions((prev) => ({
      ...prev,
      [docId]: { ...prev[docId], loading: true, error: null },
    }));

    try {
      const res = await fetch(apiUrl(`/documents/${docId}/extraction`));
      if (res.ok) {
        const data = await res.json();
        setExtractions((prev) => ({
          ...prev,
          [docId]: {
            extracted: data.extracted,
            loading: false,
            records: data.parsed_records || [],
            notes: data.parser_notes || [],
            error: null,
          },
        }));
      } else {
        setExtractions((prev) => ({
          ...prev,
          [docId]: { extracted: false, loading: false, error: "Failed status fetch", records: [], notes: [] },
        }));
      }
    } catch (err) {
      setExtractions((prev) => ({
        ...prev,
        [docId]: { extracted: false, loading: false, error: "Offline", records: [], notes: [] },
      }));
    }
  }, []);

  // ── Fetch documents list ──────────────────────────────────────────────────
  const fetchDocs = useCallback(async () => {
    try {
      setLoading(true);
      const resp = await fetch(apiUrl("/documents?page_size=100"));
      if (resp.ok) {
        const data = await resp.json();
        const items = data.items || [];
        setDocs(items);

        // Fetch extraction status for generic documents in parallel
        items.forEach((d) => {
          if (d.document_type === "FSA_BRIDGE_LINKAGE_DOCUMENT" || d.document_type === "LANDED_COST_DOCUMENT") {
            fetchExtractionStatus(d.id, d.document_type);
          }
        });
      }
    } catch (err) {
      console.error("Error fetching documents:", err);
      setStatusMsg({ type: "error", message: "Backend offline. Could not load document registry." });
    } finally {
      setLoading(false);
    }
  }, [fetchExtractionStatus]);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  // ── Handle file selection and validation ──────────────────────────────────
  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (!selectedFile) {
      setFile(null);
      return;
    }

    // Client-side PDF constraint check
    const isPDF = selectedFile.type === "application/pdf" || selectedFile.name.toLowerCase().endsWith(".pdf");
    if (!isPDF) {
      setStatusMsg({ type: "error", message: "Only PDF files are supported. Non-PDF selection rejected." });
      setFile(null);
      e.target.value = ""; // reset file input
      return;
    }

    setFile(selectedFile);
    setStatusMsg(null);
  };

  // ── Document upload flow ──────────────────────────────────────────────────
  const handleUpload = async (e) => {
    e.preventDefault();

    // Role check
    const allowedRoles = ["Fuel Cell Analyst", "Fuel Cell Approver", "System Administrator"];
    if (!allowedRoles.includes(role)) {
      setStatusMsg({ type: "error", message: `Access Denied: Role '${role}' is not authorized to upload reference files.` });
      return;
    }

    if (!file) {
      setStatusMsg({ type: "error", message: "Please select a PDF file to upload." });
      return;
    }

    setUploading(true);
    setStatusMsg({ type: "info", message: "Uploading document to FastAPI server…" });

    try {
      let resp;
      if (docType === "VARIABLE_COST_PDF") {
        // Variable cost upload goes to separate autoparse route
        const formData = new FormData();
        formData.append("file", file);
        resp = await fetch(apiUrl("/variable-cost/upload"), {
          method: "POST",
          body: formData,
        });
      } else {
        // Generic document upload
        const formData = new FormData();
        formData.append("file", file);
        formData.append("document_type", docType);
        if (plantId) {
          formData.append("plant_id", plantId);
        }
        if (notes) {
          formData.append("notes", notes);
        }
        resp = await fetch(apiUrl("/documents"), {
          method: "POST",
          body: formData,
        });
      }

      if (resp.ok) {
        const result = await resp.json();
        
        let msg = "✓ File uploaded successfully.";
        if (docType === "VARIABLE_COST_PDF") {
          msg += ` Parsed ${result.parsed_rows?.length || 0} rows (${result.rows_needing_review || 0} need review).`;
        }

        setStatusMsg({ type: "success", message: msg });
        setFile(null);
        setNotes("");
        setPlantId("");
        
        const fileInput = document.getElementById("doc-file");
        if (fileInput) fileInput.value = "";

        // Reload data
        await fetchDocs();
        if (refreshLive) refreshLive();
      } else {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `Upload failed with status ${resp.status}`);
      }
    } catch (err) {
      if (err.message.includes("Failed to fetch") || err.message.includes("NetworkError")) {
        setStatusMsg({ type: "error", message: "Backend unavailable. Document was not uploaded/extracted." });
      } else {
        setStatusMsg({ type: "error", message: err.message });
      }
    } finally {
      setUploading(false);
    }
  };

  // ── Document extraction trigger flow ──────────────────────────────────────
  const handleExtract = async (docId, type) => {
    if (extractions[docId]?.loading) return;

    setExtractions((prev) => ({
      ...prev,
      [docId]: { ...prev[docId], loading: true },
    }));

    try {
      const resp = await fetch(apiUrl(`/documents/${docId}/extract`), {
        method: "POST",
        headers: {
          Accept: "application/json",
        },
      });

      if (resp.ok) {
        const result = await resp.json();
        const recordsCount = result.parsed_records?.length || 0;
        const parserNotes = result.parser_notes || [];

        setExtractions((prev) => ({
          ...prev,
          [docId]: {
            extracted: true,
            loading: false,
            records: result.parsed_records || [],
            notes: parserNotes,
            error: null,
          },
        }));

        setStatusMsg({
          type: "success",
          message: `✓ Extraction completed: parsed ${recordsCount} records. Check registry details.`,
        });

        // Reload documents listing to capture the updated needs_review status
        await fetchDocs();
        if (refreshLive) refreshLive();
      } else {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || "Extraction failed.");
      }
    } catch (err) {
      console.error(err);
      setExtractions((prev) => ({
        ...prev,
        [docId]: { ...prev[docId], loading: false, error: err.message },
      }));
      setStatusMsg({
        type: "error",
        message: "Extraction could not be completed. Please verify the document type and PDF format.",
      });
    }
  };

  // ── Render Helpers ────────────────────────────────────────────────────────
  const getStatusStyle = (status) => {
    if (!status) return {};
    if (status.type === "success") {
      return { background: "rgba(13,148,136,0.08)", borderColor: "rgba(13,148,136,0.25)", color: "var(--teal)" };
    }
    if (status.type === "error") {
      return { background: "rgba(220,38,38,0.08)", borderColor: "rgba(220,38,38,0.25)", color: "var(--coral)" };
    }
    return { background: "var(--bg)", borderColor: "var(--border)", color: "var(--ink-muted)" };
  };

  return (
    <div className="page-content" id="tab-documents">
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
          Direct connection to the FastAPI document workflow.
        </span>
      </div>

      <p className="section-intro">
        Manage active contract documents, landed cost sheets, and variable cost PDFs. 
        Extract structured tables from PDFs dynamically for optimization runs.
      </p>

      {statusMsg && (
        <div className="status-msg" style={{ marginBottom: 20, ...getStatusStyle(statusMsg) }}>
          {statusMsg.message}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.6fr", gap: "28px", alignItems: "start" }}>
        
        {/* ── Left Column: Upload Section ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">Upload Reference Document</span>
              <span className="panel-badge violet">Ingestion</span>
            </div>
            
            <form onSubmit={handleUpload} style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 12 }}>
              
              {/* Document Type Dropdown */}
              <div className="form-field">
                <label className="form-label" htmlFor="doc-type">Document Type</label>
                <select
                  id="doc-type"
                  className="form-select"
                  value={docType}
                  onChange={(e) => setDocType(e.target.value)}
                >
                  {DOC_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Plant selection — hide if Variable Cost PDF (since backend upload route doesn't accept plant_id) */}
              {docType !== "VARIABLE_COST_PDF" && (
                <div className="form-field">
                  <label className="form-label" htmlFor="doc-plant">
                    Applicable Plant {loadingPlants && <span style={{ fontSize: 10, color: "var(--ink-dim)" }}>(loading…)</span>}
                  </label>
                  <select
                    id="doc-plant"
                    className="form-select"
                    value={plantId}
                    onChange={(e) => setPlantId(e.target.value)}
                  >
                    <option value="">All / Multi-plant</option>
                    {plants.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.plant_name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Optional Notes */}
              <div className="form-field">
                <label className="form-label" htmlFor="doc-notes">Notes / Reference Description</label>
                <input
                  id="doc-notes"
                  className="form-input"
                  placeholder="Optional reference notes…"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>

              {/* PDF Selector */}
              <div className="form-field">
                <label className="form-label" htmlFor="doc-file">Select PDF File</label>
                <input
                  id="doc-file"
                  type="file"
                  className="form-input"
                  accept=".pdf"
                  onChange={handleFileChange}
                  required
                />
                {file && (
                  <div style={{ marginTop: 6, fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-muted)" }}>
                    Selected: <strong>{file.name}</strong> ({(file.size / (1024 * 1024)).toFixed(2)} MB)
                  </div>
                )}
              </div>

              <button type="submit" className="submit-btn" disabled={uploading}>
                {uploading ? "Processing Ingestion…" : "Upload Document"}
              </button>
            </form>
          </div>
        </div>

        {/* ── Right Column: Document List Table ── */}
        <div className="panel">
          <div className="panel-header" style={{ marginBottom: 12 }}>
            <span className="panel-title">Official Document Registry</span>
            <button
              onClick={fetchDocs}
              disabled={loading}
              style={{
                background: "var(--bg)", border: "1.5px solid var(--border)",
                borderRadius: 8, padding: "4px 10px", cursor: "pointer",
                fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-muted)",
                fontWeight: 600
              }}
            >
              ↻ Refresh
            </button>
          </div>

          {loading ? (
            <p style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--ink-dim)", padding: "16px 0" }}>
              Loading document registry…
            </p>
          ) : docs.length === 0 ? (
            <p style={{ color: "var(--ink-muted)", padding: "20px 0", fontFamily: "var(--font-mono)", fontSize: 12 }}>
              No documents uploaded yet.
            </p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>File Details</th>
                    <th>Type</th>
                    <th>Plant Scope</th>
                    <th>Status / Action</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.map((d) => {
                    const typeLabelStr = d.document_type.replace(/_/g, " ");
                    const plantScopeName = d.plant_id ? plantMap[d.plant_id] || "Plant Scope" : "All / Multi-plant";
                    
                    const extInfo = extractions[d.id] || null;
                    const isVC = d.document_type === "VARIABLE_COST_PDF";

                    // Determine extraction badge text
                    let extBadge = "EXTRACTION PENDING";
                    if (isVC) extBadge = "EXTRACTED";
                    else if (extInfo?.extracted) extBadge = "EXTRACTED";
                    else if (extInfo?.loading) extBadge = "EXTRACTING";

                    return (
                      <tr key={d.id}>
                        <td>
                          <div style={{ fontWeight: 700, color: "var(--heading-primary)" }}>
                            {d.original_filename}
                          </div>
                          <div style={{ fontSize: 9, color: "var(--ink-dim)", fontFamily: "var(--font-mono)", marginTop: 2 }}>
                            SHA256: {d.sha256_hash.slice(0, 10)}… | Uploaded: {new Date(d.created_at).toLocaleDateString("en-IN")}
                          </div>
                          {d.notes && (
                            <div style={{ fontStyle: "italic", fontSize: 10, color: "var(--ink-muted)", marginTop: 4 }}>
                              Note: {d.notes}
                            </div>
                          )}
                          {/* Parser extraction messages display */}
                          {extInfo?.notes && extInfo.notes.length > 0 && (
                            <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 3 }}>
                              {extInfo.notes.map((note, idx) => (
                                <div key={idx} style={{ fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--amber)", background: "rgba(217,119,6,0.05)", border: "1px solid rgba(217,119,6,0.15)", padding: "2px 6px", borderRadius: 4 }}>
                                  {note}
                                </div>
                              ))}
                            </div>
                          )}
                        </td>
                        <td>
                          <span className="panel-badge" style={{ fontSize: 9, textTransform: "uppercase" }}>{typeLabelStr}</span>
                        </td>
                        <td style={{ fontSize: 12, color: "var(--ink)" }}>{plantScopeName}</td>
                        <td>
                          <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-start" }}>
                            
                            {/* Extraction Badge */}
                            <span style={{
                              fontSize: 9, fontWeight: 700, fontFamily: "var(--font-mono)",
                              background: extBadge === "EXTRACTED" ? "rgba(13,148,136,0.08)" : extBadge === "EXTRACTING" ? "rgba(2,132,199,0.08)" : "rgba(217,119,6,0.08)",
                              color: extBadge === "EXTRACTED" ? "var(--teal)" : extBadge === "EXTRACTING" ? "var(--sky)" : "var(--amber)",
                              padding: "2px 7px", border: "1px solid transparent", borderRadius: 12, textTransform: "uppercase"
                            }}>
                              {extBadge}
                            </span>

                            {/* Review Badges */}
                            {d.needs_review && (
                              <span style={{
                                fontSize: 9, fontWeight: 700, fontFamily: "var(--font-mono)",
                                background: "rgba(220,38,38,0.08)", color: "var(--coral)",
                                padding: "2px 7px", borderRadius: 12, textTransform: "uppercase"
                              }}>
                                NEEDS REVIEW
                              </span>
                            )}

                            {/* Review status badge */}
                            <span style={{
                              fontSize: 9, fontWeight: 700, fontFamily: "var(--font-mono)",
                              background: d.review_status === "approved" ? "rgba(13,148,136,0.08)" : d.review_status === "rejected" ? "rgba(220,38,38,0.08)" : "rgba(217,119,6,0.08)",
                              color: d.review_status === "approved" ? "var(--teal)" : d.review_status === "rejected" ? "var(--coral)" : "var(--amber)",
                              padding: "2px 7px", borderRadius: 12, textTransform: "uppercase"
                            }}>
                              {d.review_status}
                            </span>

                            {/* Extraction Trigger Button (Only for manually-extracted Generic PDFs) */}
                            {!isVC && (
                              <button
                                style={{
                                  background: "var(--bg)", border: "1.5px solid var(--border)",
                                  borderRadius: 6, padding: "3px 8px", fontSize: 10, cursor: extInfo?.loading ? "not-allowed" : "pointer",
                                  fontFamily: "var(--font-mono)", color: "var(--ink-muted)", fontWeight: 600,
                                  display: "flex", alignItems: "center", gap: 3
                                }}
                                disabled={extInfo?.loading}
                                onClick={() => handleExtract(d.id, d.document_type)}
                              >
                                {extInfo?.loading ? "⏳ Extracting…" : "⚡ Extract"}
                              </button>
                            )}

                            {/* Info on extracted items */}
                            {extInfo?.extracted && extInfo.records && (
                              <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--teal)" }}>
                                ({extInfo.records.length} records parsed)
                              </span>
                            )}

                            {/* Extraction Needs Review Warning */}
                            {extInfo?.extracted && d.needs_review && (
                              <div style={{ fontSize: 9, color: "var(--coral)", fontFamily: "var(--font-body)", fontStyle: "italic", maxWidth: 140 }}>
                                This extraction requires review before it can be used in optimization.
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
