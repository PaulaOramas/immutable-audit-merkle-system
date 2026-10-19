/**
 * BatchesPage — Explorador de batches con acciones.
 */
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import { truncateHash, formatDate } from "../utils/helpers";

export default function BatchesPage() {
  const [batches, setBatches] = useState([]);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    loadBatches();
  }, [filter]);

  async function loadBatches() {
    setLoading(true);
    try {
      const params = { limit: 50, offset: 0 };
      if (filter) params.status = filter;
      const res = await api.getBatches(params);
      setBatches(res.items || []);
      setTotal(res.total || 0);
    } catch {
      setBatches([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-lg">
        <div>
          <h1 className="page-title">Batches Merkle</h1>
          <p className="page-description" style={{ marginBottom: 0 }}>
            Agrupaciones de logs con su árbol Merkle y estado de anclaje blockchain.
          </p>
        </div>
      </div>

      {/* Filtros */}
      <div className="action-bar mb-lg">
        <button
          className={`btn ${filter === "" ? "btn-primary" : "btn-secondary"} btn-sm`}
          onClick={() => setFilter("")}
        >
          Todos
        </button>
        <button
          className={`btn ${filter === "open" ? "btn-primary" : "btn-secondary"} btn-sm`}
          onClick={() => setFilter("open")}
        >
          🟡 Open
        </button>
        <button
          className={`btn ${filter === "closed" ? "btn-primary" : "btn-secondary"} btn-sm`}
          onClick={() => setFilter("closed")}
        >
          🔵 Closed
        </button>
        <button
          className={`btn ${filter === "anchored" ? "btn-primary" : "btn-secondary"} btn-sm`}
          onClick={() => setFilter("anchored")}
        >
          🟢 Anchored
        </button>
      </div>

      {loading ? (
        <div className="loading-spinner">
          <div className="spinner"></div>
          Cargando batches...
        </div>
      ) : batches.length === 0 ? (
        <div className="empty-state">
          <div className="icon">📭</div>
          <p>No hay batches {filter ? `con estado "${filter}"` : ""}</p>
        </div>
      ) : (
        <div className="card">
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Estado</th>
                  <th>Hojas</th>
                  <th>Merkle Root</th>
                  <th>Prev Root</th>
                  <th>Creado</th>
                  <th>Cerrado</th>
                  <th>Acción</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((batch) => (
                  <tr key={batch.id}>
                    <td style={{ fontWeight: 600 }}>#{batch.batch_number}</td>
                    <td>
                      <span className={`badge badge-${batch.status}`}>
                        {batch.status}
                      </span>
                    </td>
                    <td>{batch.leaf_count}</td>
                    <td className="mono">{truncateHash(batch.merkle_root, 8) || "—"}</td>
                    <td className="mono">{truncateHash(batch.prev_batch_root, 6) || "—"}</td>
                    <td>{formatDate(batch.created_at)}</td>
                    <td>{formatDate(batch.closed_at)}</td>
                    <td>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => navigate(`/batches/${batch.id}`)}
                      >
                        Detalle
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
