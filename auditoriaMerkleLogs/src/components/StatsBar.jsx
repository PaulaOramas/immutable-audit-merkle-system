/**
 * StatsBar — Muestra contadores de eventos enviados.
 */
export default function StatsBar({ stats }) {
  return (
    <div className="stats-bar">
      <div className="stat-card">
        <div className="stat-value">{stats.total}</div>
        <div className="stat-label">Total Enviados</div>
      </div>
      <div className="stat-card stat-info">
        <div className="stat-value">{stats.info}</div>
        <div className="stat-label">Info</div>
      </div>
      <div className="stat-card stat-warning">
        <div className="stat-value">{stats.warning}</div>
        <div className="stat-label">Warning</div>
      </div>
      <div className="stat-card stat-error">
        <div className="stat-value">{stats.error}</div>
        <div className="stat-label">Error</div>
      </div>
      <div className="stat-card stat-critical">
        <div className="stat-value">{stats.critical}</div>
        <div className="stat-label">Critical</div>
      </div>
      <div className="stat-card stat-connection">
        <div className={`connection-dot ${stats.connected ? "connected" : "disconnected"}`} />
        <div className="stat-label">{stats.connected ? "API Conectada" : "Desconectado"}</div>
      </div>
    </div>
  );
}
