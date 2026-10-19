import { useState, useEffect } from "react";
import api from "../services/api";
import { truncateHash, formatDate } from "../utils/helpers";
import { useNavigate } from "react-router-dom";
import { ShieldAlert, Terminal, Fingerprint, FileText, Package, Inbox } from "lucide-react"; // Import for SOC alert and cards

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [recentLogs, setRecentLogs] = useState([]);
  const [recentBatches, setRecentBatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [socAlerts, setSocAlerts] = useState([]); // State for all SOC alerts
  const [alertDismissed, setAlertDismissed] = useState(false);
  const [lastCompromisedCount, setLastCompromisedCount] = useState(0);
  const navigate = useNavigate();

  useEffect(() => {
    loadData();
    
    // SOC Integrity Scanner Polling
    const scannerInterval = setInterval(async () => {
      try {
        const res = await api._fetch("/api/v1/attack/scan-integrity");
        const data = await res.json();
        
        if (data.compromised_count > 0) {
          setSocAlerts(data.compromised_records);
          // Re-open alert if new records appeared
          setLastCompromisedCount(prev => {
            if (data.compromised_count > prev) {
              setAlertDismissed(false);
            }
            return data.compromised_count;
          });
        } else {
          setSocAlerts([]);
          setAlertDismissed(false);
          setLastCompromisedCount(0);
        }
      } catch (err) {
        console.error("SOC Scan error:", err);
      }
    }, 3000);

    return () => clearInterval(scannerInterval);
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [logsRes, batchesRes] = await Promise.all([
        api.getLogs({ limit: 5, offset: 0 }),
        api.getBatches({ limit: 10, offset: 0 }),
      ]);

      setRecentLogs(logsRes.items || []);
      const batches = batchesRes.items || [];
      setRecentBatches(batches);

      const open = batches.filter((b) => b.status === "open").length;
      const closed = batches.filter((b) => b.status === "closed").length;
      const anchored = batches.filter((b) => b.status === "anchored").length;

      setStats({
        totalLogs: logsRes.total || 0,
        totalBatches: batchesRes.total || 0,
        open,
        closed,
        anchored,
      });
    } catch {
      setStats({ totalLogs: 0, totalBatches: 0, open: 0, closed: 0, anchored: 0 });
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="loading-spinner">
        <div className="spinner"></div>
        Cargando dashboard...
      </div>
    );
  }

  return (
    <div>
      {/* SOC ALERT BANNER */}
      {socAlerts.length > 0 && !alertDismissed && (
        <div style={{
          backgroundColor: '#000', border: '3px solid #ef4444', borderRadius: '12px', padding: '24px', marginBottom: '32px',
          boxShadow: '0 0 30px rgba(239, 68, 68, 0.6)', animation: 'siren 1.5s infinite', color: '#fff', position: 'relative', overflow: 'hidden'
        }}>
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '4px', background: 'repeating-linear-gradient(45deg, #ef4444, #ef4444 10px, #000 10px, #000 20px)' }}></div>
          
          <button 
            onClick={() => setAlertDismissed(true)}
            style={{ position: 'absolute', top: '16px', right: '16px', background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '24px', fontWeight: 'bold' }}
            title="Ocultar alerta temporalmente"
          >
            ×
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '20px' }}>
            <ShieldAlert size={48} color="#ef4444" style={{ animation: 'pulse-red 1s infinite' }} />
            <div>
              <h2 style={{ color: '#ef4444', margin: 0, fontSize: '28px', textTransform: 'uppercase', letterSpacing: '2px', textShadow: '0 0 10px #ef4444' }}>BRECHA DE INTEGRIDAD DETECTADA</h2>
              <span style={{ color: '#fca5a5', fontFamily: 'monospace', fontSize: '14px' }}>MÓDULO SOC / ESCÁNER CONTINUO DE HASHES ACTIVO</span>
            </div>
          </div>
          <div style={{ backgroundColor: '#111827', padding: '20px', borderRadius: '8px', border: '1px solid #374151' }}>
            <p style={{ margin: '0 0 16px 0', fontSize: '16px', lineHeight: '1.5' }}>
              <strong>¡ALERTA CRÍTICA!</strong> El escáner ha detectado que <strong>{socAlerts.length}</strong> registro(s) en la base de datos subyacente {socAlerts.length > 1 ? 'han sido alterados' : 'ha sido alterado'}. 
              Los datos fueron modificados directamente sin pasar por la capa de aplicación, pero <strong>la huella criptográfica Merkle expuso el fraude</strong>.
            </p>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxHeight: '400px', overflowY: 'auto', paddingRight: '8px' }}>
              {socAlerts.map((alert, idx) => (
                <div key={idx} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', fontFamily: 'monospace', fontSize: '15px', backgroundColor: '#000', padding: '16px', borderRadius: '8px', border: '1px solid #ef4444' }}>
                  <div style={{ backgroundColor: '#111827', padding: '12px', borderRadius: '6px', borderLeft: '4px solid #ef4444' }}>
                    <div style={{ color: '#ef4444', marginBottom: '8px', fontWeight: 'bold' }}><Terminal size={16} style={{ verticalAlign: 'middle', marginRight: '4px' }}/> Log ID Comprometido</div>
                    <div>{alert.log_id}</div>
                    <div style={{ color: '#6b7280', fontSize: '12px', marginTop: '4px' }}>Evento: {alert.event_type}</div>
                  </div>
                  <div style={{ backgroundColor: '#111827', padding: '12px', borderRadius: '6px', borderLeft: '4px solid #10b981' }}>
                    <div style={{ color: '#10b981', marginBottom: '8px', fontWeight: 'bold' }}><Fingerprint size={16} style={{ verticalAlign: 'middle', marginRight: '4px' }}/> Hash Original (Seguro)</div>
                    <div style={{ wordBreak: 'break-all' }}>{alert.stored_hash}</div>
                  </div>
                  <div style={{ gridColumn: '1 / -1', backgroundColor: '#451a1a', padding: '12px', borderRadius: '6px', borderLeft: '4px solid #f59e0b', textAlign: 'center' }}>
                    <div style={{ color: '#f59e0b', marginBottom: '8px', fontWeight: 'bold' }}>Hash Calculado en Tiempo Real (Discrepancia)</div>
                    <div style={{ wordBreak: 'break-all', color: '#fca5a5' }}>{alert.calculated_hash}</div>
                    <div style={{ marginTop: '8px', fontSize: '12px', color: '#ef4444' }}>[ ! ] El hash actual no coincide con la firma original. Datos mutados.</div>
                  </div>
                </div>
              ))}
            </div>

            <div style={{ marginTop: '24px', textAlign: 'right' }}>
              <button className="btn btn-primary" style={{ backgroundColor: '#ef4444', border: 'none', padding: '12px 24px', fontSize: '16px', fontWeight: 'bold', boxShadow: '0 0 15px rgba(239, 68, 68, 0.5)' }} onClick={() => navigate('/verify')}>
                🔍 VALIDAR INMUTABILIDAD EN BLOCKCHAIN
              </button>
            </div>
          </div>
          <style>{`
            @keyframes siren { 0% { box-shadow: 0 0 10px rgba(239, 68, 68, 0.2); } 50% { box-shadow: 0 0 40px rgba(239, 68, 68, 0.8); } 100% { box-shadow: 0 0 10px rgba(239, 68, 68, 0.2); } }
            @keyframes pulse-red { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }
          `}</style>
        </div>
      )}

      <h1 className="page-title">Panel de Auditoría</h1>
      <p className="page-description">
        Resumen del sistema de logs inmutables con verificación Merkle y anclaje blockchain.
      </p>

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card" style={{ "--stat-accent": "var(--color-accent)" }}>
          <div className="stat-label">Total Logs</div>
          <div className="stat-value">{stats?.totalLogs ?? 0}</div>
          <div className="stat-detail">Registros de auditoría</div>
        </div>
        <div className="stat-card" style={{ "--stat-accent": "var(--color-info)" }}>
          <div className="stat-label">Total Batches</div>
          <div className="stat-value">{stats?.totalBatches ?? 0}</div>
          <div className="stat-detail">
            {stats?.open ?? 0} abiertos · {stats?.closed ?? 0} cerrados
          </div>
        </div>
        <div className="stat-card" style={{ "--stat-accent": "var(--color-success)" }}>
          <div className="stat-label">Anclados</div>
          <div className="stat-value">{stats?.anchored ?? 0}</div>
          <div className="stat-detail">En blockchain</div>
        </div>
        <div className="stat-card" style={{ "--stat-accent": "var(--color-warning)" }}>
          <div className="stat-label">Pendientes</div>
          <div className="stat-value">{stats?.closed ?? 0}</div>
          <div className="stat-detail">Por anclar</div>
        </div>
      </div>

      {/* Recent logs */}
      <div className="card mb-lg">
        <div className="card-header">
          <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={20} />
            Logs Recientes
          </span>
          <button className="btn btn-secondary btn-sm" onClick={() => navigate("/logs")}>
            Ver todos →
          </button>
        </div>
        {recentLogs.length > 0 ? (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Fuente</th>
                  <th>Acción</th>
                  <th>Hash</th>
                  <th>Fecha</th>
                </tr>
              </thead>
              <tbody>
                {recentLogs.map((log) => (
                  <tr key={log.id}>
                    <td>{log.source_app || "—"}</td>
                    <td>{log.event_type || "—"}</td>
                    <td className="mono">{truncateHash(log.content_hash, 10)}</td>
                    <td>{formatDate(log.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">
            <div className="icon" style={{ display: 'flex', justifyContent: 'center', marginBottom: '12px' }}>
              <Inbox size={48} color="#475569" strokeWidth={1.5} />
            </div>
            <p>No hay logs aún</p>
          </div>
        )}
      </div>

      {/* Recent batches */}
      <div className="card">
        <div className="card-header">
          <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Package size={20} />
            Batches Recientes
          </span>
          <button className="btn btn-secondary btn-sm" onClick={() => navigate("/batches")}>
            Ver todos →
          </button>
        </div>
        {recentBatches.length > 0 ? (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Estado</th>
                  <th>Hojas</th>
                  <th>Merkle Root</th>
                  <th>Creado</th>
                </tr>
              </thead>
              <tbody>
                {recentBatches.slice(0, 5).map((batch) => (
                  <tr key={batch.id} style={{ cursor: "pointer" }} onClick={() => navigate(`/batches/${batch.id}`)}>
                    <td style={{ fontWeight: 600 }}>#{batch.batch_number}</td>
                    <td>
                      <span className={`badge badge-${batch.status}`}>
                        {batch.status}
                      </span>
                    </td>
                    <td>{batch.leaf_count}</td>
                    <td className="mono">{truncateHash(batch.merkle_root, 10) || "—"}</td>
                    <td>{formatDate(batch.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">
            <div className="icon" style={{ display: 'flex', justifyContent: 'center', marginBottom: '12px' }}>
              <Inbox size={48} color="#475569" strokeWidth={1.5} />
            </div>
            <p>No hay batches aún</p>
          </div>
        )}
      </div>
    </div>
  );
}
