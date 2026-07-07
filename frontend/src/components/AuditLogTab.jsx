import React, { useState, useEffect } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function AuditLogTab() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchLogs = async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/records/audit-logs`);
      if (resp.ok) {
        const data = await resp.json();
        setLogs(data);
      }
    } catch (err) {
      console.error("Error loading audit logs:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  return (
    <div className="page-content" id="tab-audit">
      <p className="section-intro">
        Audit trail tracking all manual submissions, reference document approvals, sync jobs, and optimization triggers.
      </p>

      <div className="panel">
        <div className="panel-header" style={{ marginBottom: 15 }}>
          <span className="panel-title">System Activity Log</span>
          <button className="nav-btn active" style={{ padding: "6px 12px", fontSize: 11 }} onClick={fetchLogs}>
            🔄 Refresh Trail
          </button>
        </div>

        {loading ? (
          <p>Loading activity logs...</p>
        ) : logs.length === 0 ? (
          <p style={{ color: "var(--ink-muted)", padding: "20px 0" }}>No audit log events captured yet.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table" style={{ fontSize: "12.5px" }}>
              <thead>
                <tr>
                  <th style={{ width: "20%" }}>Timestamp</th>
                  <th style={{ width: "25%" }}>Event Action</th>
                  <th style={{ width: "15%" }}>Entity</th>
                  <th style={{ width: "40%" }}>Event Details / Payload</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.audit_id}>
                    <td style={{ fontFamily: "var(--font-mono)", color: "var(--ink-muted)" }}>
                      {log.created_at ? log.created_at.replace("T", " ").slice(0, 19) : ""}
                    </td>
                    <td>
                      <span className="run-badge" style={{ 
                        background: log.action.includes("APPROVED") || log.action.includes("COMPLETED") ? "rgba(20,184,166,0.15)" :
                                    log.action.includes("FAIL") || log.action.includes("REJECT") ? "rgba(244,63,94,0.15)" : "rgba(99,102,241,0.15)",
                        color: log.action.includes("APPROVED") || log.action.includes("COMPLETED") ? "var(--teal)" :
                               log.action.includes("FAIL") || log.action.includes("REJECT") ? "var(--coral)" : "var(--indigo)",
                        border: "none",
                        fontSize: 10
                      }}>
                        {log.action}
                      </span>
                    </td>
                    <td style={{ color: "var(--ink-muted)" }}>{log.entity_type || "—"}</td>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--heading-primary)", lineHeight: 1.4 }}>
                      {log.detail ? JSON.stringify(log.detail, null, 1) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
