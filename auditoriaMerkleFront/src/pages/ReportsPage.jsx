/**
 * ReportsPage — Generación de reportes verificables de integridad.
 *
 * Permite seleccionar un batch y generar un reporte completo con:
 * - Información del batch y árbol Merkle
 * - Datos de anclaje blockchain
 * - Resultado de verificación cruzada
 * - Logs incluidos con sus hashes
 * - Exportación JSON y vista de impresión
 */
import { useState, useEffect } from "react";
import api from "../services/api";
import { formatDate } from "../utils/helpers";

export default function ReportsPage() {
  const [batches, setBatches] = useState([]);
  const [selectedBatchId, setSelectedBatchId] = useState("");
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [batchesLoading, setBatchesLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadBatches();
  }, []);

  async function loadBatches() {
    setBatchesLoading(true);
    try {
      const res = await api.getBatches({ limit: 100, offset: 0 });
      setBatches(res.items || []);
    } catch {
      setBatches([]);
    } finally {
      setBatchesLoading(false);
    }
  }

  async function generateReport() {
    if (!selectedBatchId) return;
    setLoading(true);
    setError(null);
    setReport(null);

    try {
      const batch = await api.getBatch(selectedBatchId);

      // Verificación cruzada si está anclado
      let verification = null;
      if (batch.status === "anchored") {
        try {
          verification = await api.crossVerifyBatch(selectedBatchId);
        } catch {
          /* puede no estar disponible */
        }
      }

      // Logs del batch
      let logs = [];
      try {
        const logsRes = await api.getLogs({ batch_id: selectedBatchId, limit: 200 });
        logs = logsRes.items || [];
      } catch {
        /* filtro por batch_id puede no estar soportado */
      }

      setReport({
        generated_at: new Date().toISOString(),
        batch,
        verification,
        logs,
      });
    } catch (e) {
      setError("Error al generar el reporte: " + (e.message || "Error desconocido"));
    } finally {
      setLoading(false);
    }
  }

  function exportJSON() {
    if (!report) return;
    const exportData = {
      report_type: "integrity_verification_report",
      system: "Merkle Audit System",
      version: "1.0",
      generated_at: report.generated_at,
      batch: {
        id: report.batch.id,
        batch_number: report.batch.batch_number,
        status: report.batch.status,
        leaf_count: report.batch.leaf_count,
        node_count: report.batch.node_count,
        merkle_root: report.batch.merkle_root,
        prev_batch_root: report.batch.prev_batch_root,
        created_at: report.batch.created_at,
        closed_at: report.batch.closed_at,
      },
      anchoring: (report.batch.anchors || []).map((a) => ({
        anchor_type: a.anchor_type,
        tx_hash: a.tx_hash,
        block_number: a.block_number,
        network: a.network,
        anchored_at: a.anchored_at,
      })),
      verification: report.verification
        ? {
            integrity: report.verification.integrity,
            local_merkle_root: report.verification.local_merkle_root,
            onchain_merkle_root: report.verification.onchain_merkle_root,
            message: report.verification.message,
            tx_verification: report.verification.tx_verification || null,
          }
        : null,
      logs: report.logs.map((l) => ({
        id: l.id,
        source: l.source_app,
        action: l.event_type,
        content_hash: l.content_hash,
        leaf_index: l.leaf_index,
        created_at: l.created_at,
      })),
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `reporte_integridad_batch_${report.batch.batch_number}_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function handlePrint() {
    window.print();
  }

  // Determinar estado general de integridad
  function getIntegrityStatus() {
    if (!report) return null;
    const b = report.batch;
    const v = report.verification;

    if (b.status === "anchored" && v?.integrity === "verified") {
      return { level: "verified", icon: "✅", label: "Integridad Verificada", desc: "El Merkle Root local coincide con el registrado en blockchain." };
    }
    if (b.status === "anchored" && v?.integrity === "mismatch") {
      return { level: "mismatch", icon: "❌", label: "Discrepancia Detectada", desc: "El Merkle Root local NO coincide con el registrado en blockchain." };
    }
    if (b.status === "anchored" && !v) {
      return { level: "pending", icon: "⚠️", label: "Anclado — Sin Verificar", desc: "El batch fue anclado pero no se pudo realizar la verificación cruzada." };
    }
    if (b.status === "closed") {
      return { level: "pending", icon: "🔵", label: "Cerrado — No Anclado", desc: "El batch está cerrado con Merkle Root calculado, pero aún no ha sido anclado en blockchain." };
    }
    return { level: "open", icon: "🟡", label: "Batch Abierto", desc: "El batch aún está recibiendo logs." };
  }

  const integrity = getIntegrityStatus();

  return (
    <div>
      <h1 className="page-title">Reportes de Integridad</h1>
      <p className="page-description">
        Genera reportes verificables que incluyen datos criptográficos, anclaje blockchain
        y estado de integridad de cada batch.
      </p>

      {/* Selector de batch */}
      <div className="card mb-lg no-print">
        <div className="card-title mb-md">📦 Seleccionar Batch</div>
        {batchesLoading ? (
          <div className="loading-spinner"><div className="spinner"></div>Cargando batches...</div>
        ) : (
          <div className="flex gap-md items-center" style={{ flexWrap: "wrap" }}>
            <select
              className="form-select"
              style={{ maxWidth: 420 }}
              value={selectedBatchId}
              onChange={(e) => setSelectedBatchId(e.target.value)}
            >
              <option value="">— Selecciona un batch —</option>
              {batches.map((b) => (
                <option key={b.id} value={b.id}>
                  Batch #{b.batch_number} — {b.status} — {b.leaf_count} hojas
                  {b.merkle_root ? ` — Root: ${b.merkle_root.slice(0, 12)}…` : ""}
                </option>
              ))}
            </select>
            <button
              className="btn btn-primary"
              disabled={!selectedBatchId || loading}
              onClick={generateReport}
            >
              {loading ? "Generando..." : "📄 Generar Reporte"}
            </button>
          </div>
        )}
      </div>

      {error && <div className="error-message mb-lg">{error}</div>}

      {/* Reporte generado */}
      {report && (
        <div className="report-container">
          {/* Acciones de exportación */}
          <div className="action-bar mb-lg no-print">
            <button className="btn btn-success btn-sm" onClick={exportJSON}>
              📥 Exportar JSON
            </button>
            <button className="btn btn-secondary btn-sm" onClick={handlePrint}>
              🖨️ Imprimir Reporte
            </button>
          </div>

          {/* Encabezado del reporte */}
          <div className="report-header">
            <div className="report-brand">
              <div className="report-logo">M</div>
              <div>
                <h2>Merkle Audit System</h2>
                <p>Reporte de Verificación de Integridad</p>
              </div>
            </div>
            <div className="report-meta">
              <div><span className="report-meta-label">Generado:</span> {formatDate(report.generated_at)}</div>
              <div><span className="report-meta-label">Batch:</span> #{report.batch.batch_number}</div>
            </div>
          </div>

          {/* Estado de integridad */}
          {integrity && (
            <div className={`report-integrity report-integrity-${integrity.level}`}>
              <span className="report-integrity-icon">{integrity.icon}</span>
              <div>
                <strong>{integrity.label}</strong>
                <p>{integrity.desc}</p>
              </div>
            </div>
          )}

          {/* Información del Batch */}
          <div className="report-section">
            <h3 className="report-section-title">📋 Información del Batch</h3>
            <div className="report-data-grid">
              <div className="report-data-row">
                <span className="report-data-label">ID</span>
                <span className="report-data-value mono">{report.batch.id}</span>
              </div>
              <div className="report-data-row">
                <span className="report-data-label">Número</span>
                <span className="report-data-value">#{report.batch.batch_number}</span>
              </div>
              <div className="report-data-row">
                <span className="report-data-label">Estado</span>
                <span className="report-data-value">
                  <span className={`badge badge-${report.batch.status}`}>{report.batch.status}</span>
                </span>
              </div>
              <div className="report-data-row">
                <span className="report-data-label">Hojas (Leaves)</span>
                <span className="report-data-value">{report.batch.leaf_count}</span>
              </div>
              <div className="report-data-row">
                <span className="report-data-label">Nodos del árbol</span>
                <span className="report-data-value">{report.batch.node_count || 0}</span>
              </div>
              <div className="report-data-row">
                <span className="report-data-label">Creado</span>
                <span className="report-data-value">{formatDate(report.batch.created_at)}</span>
              </div>
              <div className="report-data-row">
                <span className="report-data-label">Cerrado</span>
                <span className="report-data-value">{formatDate(report.batch.closed_at)}</span>
              </div>
            </div>
          </div>

          {/* Árbol Merkle */}
          <div className="report-section">
            <h3 className="report-section-title">🌳 Árbol Merkle</h3>
            <div className="report-data-grid">
              <div className="report-data-row">
                <span className="report-data-label">Merkle Root</span>
                <span className="report-data-value mono report-hash">{report.batch.merkle_root || "—"}</span>
              </div>
              <div className="report-data-row">
                <span className="report-data-label">Root del Batch Anterior</span>
                <span className="report-data-value mono report-hash">
                  {report.batch.prev_batch_root || "Genesis (sin batch anterior)"}
                </span>
              </div>
            </div>
          </div>

          {/* Anclaje Blockchain */}
          <div className="report-section">
            <h3 className="report-section-title">⛓️ Anclaje Blockchain</h3>
            {report.batch.anchors && report.batch.anchors.length > 0 ? (
              report.batch.anchors.map((anchor, i) => (
                <div key={i} className="report-anchor-card">
                  <div className="report-data-grid">
                    <div className="report-data-row">
                      <span className="report-data-label">Tipo</span>
                      <span className="report-data-value">
                        <span className="badge badge-anchored">{anchor.anchor_type}</span>
                      </span>
                    </div>
                    {anchor.tx_hash && (
                      <div className="report-data-row">
                        <span className="report-data-label">TX Hash</span>
                        <span className="report-data-value mono report-hash">{anchor.tx_hash}</span>
                      </div>
                    )}
                    {anchor.block_number && (
                      <div className="report-data-row">
                        <span className="report-data-label">Bloque</span>
                        <span className="report-data-value">{anchor.block_number}</span>
                      </div>
                    )}
                    {anchor.network && (
                      <div className="report-data-row">
                        <span className="report-data-label">Red</span>
                        <span className="report-data-value">{anchor.network}</span>
                      </div>
                    )}
                    <div className="report-data-row">
                      <span className="report-data-label">Fecha de anclaje</span>
                      <span className="report-data-value">{formatDate(anchor.anchored_at)}</span>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="report-empty">Este batch no tiene anclajes blockchain registrados.</div>
            )}
          </div>

          {/* Verificación Cruzada */}
          {report.verification && (
            <div className="report-section">
              <h3 className="report-section-title">🔍 Verificación Cruzada On-Chain</h3>
              <div className={`report-verify-result report-verify-${report.verification.integrity}`}>
                <strong>{report.verification.message}</strong>
              </div>
              <div className="report-data-grid mt-md">
                <div className="report-data-row">
                  <span className="report-data-label">Root Local (BD)</span>
                  <span className="report-data-value mono report-hash">{report.verification.local_merkle_root}</span>
                </div>
                <div className="report-data-row">
                  <span className="report-data-label">Root On-Chain</span>
                  <span className="report-data-value mono report-hash">{report.verification.onchain_merkle_root || "—"}</span>
                </div>
                {report.verification.tx_verification && (
                  <>
                    <div className="report-data-row">
                      <span className="report-data-label">TX Verificada</span>
                      <span className="report-data-value mono report-hash">
                        {report.verification.tx_verification.tx_hash}
                      </span>
                    </div>
                    <div className="report-data-row">
                      <span className="report-data-label">Bloque</span>
                      <span className="report-data-value">#{report.verification.tx_verification.block_number}</span>
                    </div>
                    <div className="report-data-row">
                      <span className="report-data-label">Estado TX</span>
                      <span className="report-data-value">{report.verification.tx_verification.status}</span>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          {/* Logs incluidos */}
          {report.logs.length > 0 && (
            <div className="report-section">
              <h3 className="report-section-title">📝 Registros de Auditoría ({report.logs.length})</h3>
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Fuente</th>
                      <th>Acción</th>
                      <th>Content Hash (SHA-256)</th>
                      <th>Leaf Index</th>
                      <th>Fecha</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.logs.map((log) => (
                      <tr key={log.id}>
                        <td>{log.source_app || "—"}</td>
                        <td>{log.event_type || "—"}</td>
                        <td className="mono" style={{ fontSize: "0.72rem" }}>{log.content_hash}</td>
                        <td>{log.leaf_index ?? "—"}</td>
                        <td>{formatDate(log.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Instrucciones de verificación */}
          <div className="report-section report-howto">
            <h3 className="report-section-title">🔐 Cómo Verificar Independientemente</h3>
            <ol className="report-steps-list">
              <li>
                <strong>Verificar hashes individuales:</strong> Recalcular el SHA-256 del contenido original de
                cada log y comparar con el <code>content_hash</code> listado.
              </li>
              <li>
                <strong>Reconstruir el árbol Merkle:</strong> Usar los hashes de las hojas para reconstruir
                el árbol de abajo hacia arriba y verificar que el root coincida con el <code>merkle_root</code>.
              </li>
              <li>
                <strong>Verificar anclaje on-chain:</strong> Consultar la transacción (<code>tx_hash</code>)
                en la red blockchain indicada y confirmar que el dato almacenado corresponde al Merkle Root.
              </li>
              <li>
                <strong>Comparar roots:</strong> El root local debe coincidir exactamente con el root
                almacenado en blockchain para garantizar no-repudio.
              </li>
            </ol>
          </div>

          {/* Pie del reporte */}
          <div className="report-footer">
            <p>Reporte generado automáticamente por Merkle Audit System</p>
            <p className="text-muted">{formatDate(report.generated_at)} — Batch #{report.batch.batch_number}</p>
          </div>
        </div>
      )}
    </div>
  );
}
