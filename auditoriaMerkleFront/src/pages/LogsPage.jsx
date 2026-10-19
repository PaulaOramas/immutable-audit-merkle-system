/**
 * LogsPage — Explorador de logs de auditoría con búsquedas avanzadas y paginación.
 *
 * Permite filtrar logs por fuente, acción, rango de fechas y hash.
 * Cada fila es clickeable para navegar al detalle del log.
 */
import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import { truncateHash, formatDate } from "../utils/helpers";

export default function LogsPage() {
  const navigate = useNavigate();
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showFilters, setShowFilters] = useState(false);
  const limit = 20;

  // Filtros
  const [filters, setFilters] = useState({
    source: "",
    action: "",
    hash: "",
    dateFrom: "",
    dateTo: "",
  });

  // Filtros aplicados (solo se envían al hacer click en "Buscar")
  const [appliedFilters, setAppliedFilters] = useState({});

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const params = { offset: page * limit, limit, ...appliedFilters };
      // Limpiar params vacíos
      Object.keys(params).forEach((k) => {
        if (params[k] === "" || params[k] === undefined) delete params[k];
      });
      const res = await api.getLogs(params);
      setLogs(res.items || []);
      setTotal(res.total || 0);
    } catch {
      setLogs([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, appliedFilters]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  function handleApplyFilters(e) {
    e.preventDefault();
    setPage(0);
    const newFilters = {};
    if (filters.source) newFilters.source = filters.source;
    if (filters.action) newFilters.action = filters.action;
    if (filters.hash) newFilters.content_hash = filters.hash;
    if (filters.dateFrom) newFilters.date_from = filters.dateFrom;
    if (filters.dateTo) newFilters.date_to = filters.dateTo;
    setAppliedFilters(newFilters);
  }

  function handleClearFilters() {
    setFilters({ source: "", action: "", hash: "", dateFrom: "", dateTo: "" });
    setAppliedFilters({});
    setPage(0);
  }

  const totalPages = Math.ceil(total / limit);
  const hasActiveFilters = Object.keys(appliedFilters).length > 0;

  return (
    <div>
      <h1 className="page-title">Logs de Auditoría</h1>
      <p className="page-description">
        Todos los registros de auditoría ingestados en el sistema. Cada log tiene un
        hash SHA-256 que garantiza su integridad.
      </p>

      {/* Barra de búsqueda */}
      <div className="search-bar mb-lg">
        <div className="search-bar-top">
          <div className="search-quick">
            <span className="search-icon">🔍</span>
            <input
              className="search-input"
              type="text"
              placeholder="Buscar por fuente, acción o hash..."
              value={filters.source || filters.action || filters.hash}
              onChange={(e) => {
                const val = e.target.value;
                // Si parece un hash (hex largo), buscar por hash
                if (/^[a-f0-9]{8,}$/i.test(val)) {
                  setFilters((f) => ({ ...f, hash: val, source: "", action: "" }));
                } else {
                  setFilters((f) => ({ ...f, source: val, hash: "" }));
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleApplyFilters(e);
              }}
            />
            <button className="btn btn-primary btn-sm" onClick={handleApplyFilters}>
              Buscar
            </button>
            <button
              className={`btn btn-secondary btn-sm ${showFilters ? "active" : ""}`}
              onClick={() => setShowFilters(!showFilters)}
              title="Filtros avanzados"
            >
              ⚙️ Filtros
            </button>
            {hasActiveFilters && (
              <button className="btn btn-danger btn-sm" onClick={handleClearFilters}>
                ✕ Limpiar
              </button>
            )}
          </div>
        </div>

        {/* Filtros avanzados expandibles */}
        {showFilters && (
          <form className="search-filters" onSubmit={handleApplyFilters}>
            <div className="search-filter-group">
              <label className="form-label">Fuente</label>
              <input
                className="form-input"
                type="text"
                placeholder="ej: web-app, api-gateway"
                value={filters.source}
                onChange={(e) => setFilters((f) => ({ ...f, source: e.target.value }))}
              />
            </div>
            <div className="search-filter-group">
              <label className="form-label">Acción</label>
              <input
                className="form-input"
                type="text"
                placeholder="ej: login, transaction"
                value={filters.action}
                onChange={(e) => setFilters((f) => ({ ...f, action: e.target.value }))}
              />
            </div>
            <div className="search-filter-group">
              <label className="form-label">Content Hash</label>
              <input
                className="form-input"
                type="text"
                placeholder="SHA-256 completo o parcial"
                value={filters.hash}
                onChange={(e) => setFilters((f) => ({ ...f, hash: e.target.value }))}
              />
            </div>
            <div className="search-filter-group">
              <label className="form-label">Desde</label>
              <input
                className="form-input"
                type="date"
                value={filters.dateFrom}
                onChange={(e) => setFilters((f) => ({ ...f, dateFrom: e.target.value }))}
              />
            </div>
            <div className="search-filter-group">
              <label className="form-label">Hasta</label>
              <input
                className="form-input"
                type="date"
                value={filters.dateTo}
                onChange={(e) => setFilters((f) => ({ ...f, dateTo: e.target.value }))}
              />
            </div>
            <div className="search-filter-actions">
              <button className="btn btn-primary btn-sm" type="submit">
                🔍 Aplicar Filtros
              </button>
              <button className="btn btn-secondary btn-sm" type="button" onClick={handleClearFilters}>
                Limpiar
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Filtros activos */}
      {hasActiveFilters && (
        <div className="active-filters mb-md">
          <span className="active-filters-label">Filtros activos:</span>
          {appliedFilters.source && (
            <span className="filter-tag">Fuente: {appliedFilters.source}</span>
          )}
          {appliedFilters.action && (
            <span className="filter-tag">Acción: {appliedFilters.action}</span>
          )}
          {appliedFilters.content_hash && (
            <span className="filter-tag">Hash: {truncateHash(appliedFilters.content_hash, 8)}</span>
          )}
          {appliedFilters.date_from && (
            <span className="filter-tag">Desde: {appliedFilters.date_from}</span>
          )}
          {appliedFilters.date_to && (
            <span className="filter-tag">Hasta: {appliedFilters.date_to}</span>
          )}
        </div>
      )}

      {loading ? (
        <div className="loading-spinner">
          <div className="spinner"></div>
          Cargando logs...
        </div>
      ) : logs.length === 0 ? (
        <div className="empty-state">
          <div className="icon">📭</div>
          <p>
            {hasActiveFilters
              ? "No se encontraron logs con los filtros aplicados"
              : "No hay logs registrados"}
          </p>
          {hasActiveFilters && (
            <button className="btn btn-secondary btn-sm mt-md" onClick={handleClearFilters}>
              Limpiar filtros
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="card">
            <div className="card-header">
              <span className="card-title">
                {total} log{total !== 1 ? "s" : ""} encontrado{total !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Fuente</th>
                    <th>Acción</th>
                    <th>Usuario</th>
                    <th>Origen (IP:Puerto)</th>
                    <th>Content Hash</th>
                    <th>Batch</th>
                    <th>Leaf</th>
                    <th>Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => {
                    const user = log.payload?.username || log.payload?.initiated_by || log.payload?.teller || log.payload?.created_by || log.payload?.user_id || "Sistema";
                    return (
                    <tr
                      key={log.id}
                      className="clickable-row"
                      onClick={() => navigate(`/logs/${log.id}`)}
                      title="Ver detalle del log"
                    >
                      <td>{log.source_app || "—"}</td>
                      <td>{log.event_type || "—"}</td>
                      <td>{user}</td>
                      <td className="mono" style={{ fontSize: "0.8rem", color: "#64748b" }}>{log.payload?.ip || "—"}</td>
                      <td className="mono">{truncateHash(log.content_hash, 12)}</td>
                      <td>{log.batch_id ? "✓" : "—"}</td>
                      <td>{log.leaf_index ?? "—"}</td>
                      <td>{formatDate(log.created_at)}</td>
                    </tr>
                  )})}
                </tbody>
              </table>
            </div>
          </div>

          {totalPages > 1 && (
            <div className="pagination">
              <button disabled={page === 0} onClick={() => setPage(page - 1)}>
                ← Anterior
              </button>
              <span className="current">
                Página {page + 1} de {totalPages}
              </span>
              <button disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>
                Siguiente →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
