/**
 * LogDetailPage — Detalle completo de un log individual con su proof Merkle.
 *
 * Muestra toda la información del log: contenido, hash, batch asignado,
 * leaf index, y permite generar y visualizar el Merkle Proof.
 */
import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api from "../services/api";
import { formatDate } from "../utils/helpers";

export default function LogDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [log, setLog] = useState(null);
  const [proof, setProof] = useState(null);
  const [verifyResult, setVerifyResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [proofLoading, setProofLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadLog();
  }, [id]);

  async function loadLog() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getLog(id);
      setLog(res);
    } catch {
      setError("No se pudo cargar el log");
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateProof() {
    setProofLoading(true);
    setProof(null);
    setVerifyResult(null);
    try {
      const proofRes = await api.getProof(id);
      setProof(proofRes);

      // Verificar automáticamente
      const verifyRes = await api.verifyProof({
        content_hash: proofRes.content_hash,
        merkle_root: proofRes.merkle_root,
        proof: proofRes.proof,
      });
      setVerifyResult(verifyRes);
    } catch {
      setError("No se pudo generar el proof. Verifica que el log esté asignado a un batch cerrado.");
    } finally {
      setProofLoading(false);
    }
  }

  function copyHash() {
    if (log?.content_hash) {
      navigator.clipboard.writeText(log.content_hash);
    }
  }

  if (loading) {
    return (
      <div className="loading-spinner">
        <div className="spinner"></div>
        Cargando log...
      </div>
    );
  }

  if (error && !log) {
    return (
      <div>
        <button className="btn btn-secondary btn-sm mb-lg" onClick={() => navigate("/logs")}>
          ← Volver a Logs
        </button>
        <div className="error-message">{error}</div>
      </div>
    );
  }

  if (!log) return null;

  return (
    <div>
      <button className="btn btn-secondary btn-sm mb-lg" onClick={() => navigate("/logs")}>
        ← Volver a Logs
      </button>

      <h1 className="page-title">Detalle del Log</h1>

      {error && <div className="error-message mb-md">{error}</div>}

      <div className="grid-2 mb-lg">
        {/* Información del log */}
        <div className="card">
          <div className="card-title mb-md">📝 Información del Registro</div>
          <div className="detail-grid">
            <span className="detail-label">ID</span>
            <span className="detail-value mono" style={{ fontSize: "0.78rem" }}>{log.id}</span>
            <span className="detail-label">Fuente</span>
            <span className="detail-value">{log.source_app || "—"}</span>
            <span className="detail-label">Acción</span>
            <span className="detail-value">{log.event_type || "—"}</span>
            <span className="detail-label">Fecha de creación</span>
            <span className="detail-value">{formatDate(log.created_at)}</span>
            {log.payload && (log.payload.username || log.payload.initiated_by || log.payload.teller || log.payload.created_by || log.payload.user_id) && (
              <>
                <span className="detail-label">Actor</span>
                <span className="detail-value">{log.payload.username || log.payload.initiated_by || log.payload.teller || log.payload.created_by || log.payload.user_id}</span>
              </>
            )}
            {log.payload?.ip && (
              <>
                <span className="detail-label">IP</span>
                <span className="detail-value mono">{log.payload.ip}</span>
              </>
            )}
          </div>
        </div>

        {/* Información criptográfica */}
        <div className="card">
          <div className="card-title mb-md">🔒 Datos Criptográficos</div>
          <div className="detail-grid">
            <span className="detail-label">Content Hash</span>
            <span className="detail-value mono" style={{ fontSize: "0.75rem", wordBreak: "break-all" }}>
              {log.content_hash}
              <button
                className="btn btn-secondary btn-sm"
                style={{ marginLeft: "8px", padding: "1px 6px", fontSize: "0.7rem" }}
                onClick={copyHash}
                title="Copiar hash"
              >
                📋
              </button>
            </span>
            <span className="detail-label">Algoritmo</span>
            <span className="detail-value">SHA-256</span>
            <span className="detail-label">Batch</span>
            <span className="detail-value">
              {log.batch_id ? (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => navigate(`/batches/${log.batch_id}`)}
                >
                  Ver Batch →
                </button>
              ) : (
                <span className="text-muted">No asignado</span>
              )}
            </span>
            <span className="detail-label">Leaf Index</span>
            <span className="detail-value">{log.leaf_index ?? "—"}</span>
          </div>
        </div>
      </div>

      {/* Contenido del log */}
      {log.payload && (
        <div className="card mb-lg">
          <div className="card-title mb-md">📄 Contenido del Registro (Payload)</div>
          <pre className="log-content-pre">{typeof log.payload === "string" ? log.payload : JSON.stringify(log.payload, null, 2)}</pre>
        </div>
      )}

      {/* Merkle Proof */}
      <div className="card mb-lg">
        <div className="card-header">
          <span className="card-title">🌳 Merkle Proof</span>
          {log.batch_id && (
            <button
              className="btn btn-primary btn-sm"
              disabled={proofLoading}
              onClick={handleGenerateProof}
            >
              {proofLoading ? "Generando..." : proof ? "🔄 Regenerar Proof" : "Generar Proof"}
            </button>
          )}
        </div>

        {!log.batch_id && (
          <p className="text-muted" style={{ fontSize: "0.85rem" }}>
            Este log no está asignado a un batch. El proof se generará cuando el log sea
            incluido en un batch y este sea cerrado.
          </p>
        )}

        {proof && (
          <div className="mt-md">
            <div className="detail-grid mb-md">
              <span className="detail-label">Merkle Root</span>
              <span className="detail-value mono" style={{ fontSize: "0.75rem", wordBreak: "break-all" }}>
                {proof.merkle_root}
              </span>
              <span className="detail-label">Leaf Index</span>
              <span className="detail-value">{proof.leaf_index}</span>
              <span className="detail-label">Batch</span>
              <span className="detail-value">#{proof.batch_number}</span>
              <span className="detail-label">Anclado</span>
              <span className="detail-value">
                <span className={`badge ${proof.is_anchored ? "badge-anchored" : "badge-closed"}`}>
                  {proof.is_anchored ? "Sí" : "No"}
                </span>
              </span>
            </div>

            <div className="card-title mb-md">Pasos del Proof ({proof.proof.length} nodos)</div>
            <div className="proof-steps">
              {proof.proof.map((step, i) => (
                <div key={i} className="proof-step">
                  <span className="step-number">{i + 1}</span>
                  <span className="position">{step.position}</span>
                  <span className="hash">{step.hash}</span>
                </div>
              ))}
            </div>

            {verifyResult && (
              <div className={`verify-result ${verifyResult.valid ? "success" : "failure"} mt-md`}>
                <strong>
                  {verifyResult.valid
                    ? "✅ Proof válido — el log no ha sido alterado"
                    : "❌ Proof inválido — posible manipulación detectada"}
                </strong>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
