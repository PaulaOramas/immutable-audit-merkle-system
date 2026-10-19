/**
 * EventTimeline — Lista de eventos generados en tiempo real.
 */
import { useEffect, useRef, useState } from "react";
import { ListX, FileJson, Terminal } from "lucide-react";

const SEVERITY_CLASS = {
  info: "sev-info",
  warning: "sev-warning",
  error: "sev-error",
  critical: "sev-critical",
};

export default function EventTimeline({ events, currentUser }) {
  const listRef = useRef(null);
  const [hackedLogs, setHackedLogs] = useState({});

  const handleHack = async (ev) => {
    if (!ev._id) return;
    
    const tamperedPayload = { ...ev.payload };
    
    if (currentUser?.role === 'dba_hacker') {
      if (tamperedPayload.amount) {
        tamperedPayload.amount = tamperedPayload.amount * 100; // Inflate amount (DBA)
      } else {
        tamperedPayload.manipulated_by_dba = true;
      }
    } else if (currentUser?.role === 'sql_hacker') {
      tamperedPayload.dest_account = "OFFSHORE-999-CAYMAN";
      if (tamperedPayload.amount) {
        tamperedPayload.amount = 99999.99;
      }
      tamperedPayload.injected_sql = "1' OR '1'='1";
    }

    try {
      const res = await fetch(`http://localhost:8000/api/v1/attack/tamper-database?log_id=${ev._id}&hacker_username=${currentUser?.username || "hacker"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(tamperedPayload)
      });
      if (res.ok) {
        setHackedLogs(prev => ({ ...prev, [ev._id]: true }));
      }
    } catch (err) {
      console.error("Hack failed:", err);
    }
  };

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = 0;
    }
  }, [events.length]);

  if (!events.length) {
    return (
      <div className="timeline-empty">
        <span className="timeline-empty-icon" style={{ display: 'flex', justifyContent: 'center' }}><ListX size={48} strokeWidth={1} /></span>
        <p>Aún no se han generado eventos.</p>
        <p className="text-muted">Usa los botones de arriba para simular actividad.</p>
      </div>
    );
  }

  return (
    <div className="timeline-list" ref={listRef}>
      {events.map((ev, i) => {
        const IconComp = ev._icon || FileJson;
        return (
          <div
            key={ev._localId || i}
            className={`timeline-item ${ev._status || ""} ${SEVERITY_CLASS[ev.severity] || ""}`}
          >
            <div className="timeline-dot" />
            <div className="timeline-content">
              <div className="timeline-header">
                <span className="timeline-icon" style={{ display: 'flex' }}><IconComp size={16} /></span>
                <span className="timeline-type">{ev._label || ev.event_type}</span>
              <span className={`timeline-severity ${SEVERITY_CLASS[ev.severity]}`}>
                {ev.severity}
              </span>
              <span className="timeline-time">
                {new Date(ev.payload?.timestamp || Date.now()).toLocaleTimeString()}
              </span>
            </div>
            <div className="timeline-details">
              {ev._status === "sent" && (
                <span className="timeline-badge badge-success">✓ Enviado</span>
              )}
              {ev._status === "error" && (
                <span className="timeline-badge badge-error">✗ Error</span>
              )}
              {ev._status === "pending" && (
                <span className="timeline-badge badge-pending">⏳ Pendiente</span>
              )}
              <code className="timeline-payload">
                {JSON.stringify(ev.payload, null, 0).slice(0, 120)}
                {JSON.stringify(ev.payload).length > 120 ? "…" : ""}
              </code>
              {["dba_hacker", "sql_hacker"].includes(currentUser?.role) && ev._status === "sent" && ev._id && (
                <button
                  onClick={() => handleHack(ev)}
                  disabled={hackedLogs[ev._id]}
                  style={{
                    marginTop: '8px', padding: '4px 8px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px',
                    backgroundColor: hackedLogs[ev._id] ? '#10b981' : '#ef4444', color: 'white', border: 'none', borderRadius: '4px', cursor: hackedLogs[ev._id] ? 'default' : 'pointer'
                  }}
                >
                  <Terminal size={12} />
                  {hackedLogs[ev._id] 
                    ? "BD Alterada (Exploit Exitoso)" 
                    : (currentUser.role === 'dba_hacker' ? "Ejecutar UPDATE SQL (Modificar BD)" : "Ejecutar Inyección SQL (Alterar Payload)")}
                </button>
              )}
            </div>
            {ev._hash && (
              <div className="timeline-hash">
                <span className="hash-label">Hash:</span>
                <code>{ev._hash}</code>
              </div>
            )}
          </div>
        </div>
        );
      })}
    </div>
  );
}
