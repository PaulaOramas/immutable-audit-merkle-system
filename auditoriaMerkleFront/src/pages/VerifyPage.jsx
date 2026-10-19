/**
 * VerifyPage — Verificación de integridad de logs.
 */
import { useState } from "react";
import api from "../services/api";

export default function VerifyPage() {
  const [logId, setLogId] = useState("");
  const [proof, setProof] = useState(null);
  const [verifyResult, setVerifyResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Manual verify form
  const [manualHash, setManualHash] = useState("");
  const [manualRoot, setManualRoot] = useState("");
  const [manualProof, setManualProof] = useState("");
  const [manualResult, setManualResult] = useState(null);

  async function handleGetProof(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setProof(null);
    setVerifyResult(null);

    try {
      const res = await api.getProof(logId);
      setProof(res);

      // Verificar automáticamente
      const verifyRes = await api.verifyProof({
        content_hash: res.content_hash,
        merkle_root: res.merkle_root,
        proof: res.proof,
      });
      setVerifyResult(verifyRes);
    } catch {
      setError("No se pudo obtener el proof. Verifica el ID del log.");
    } finally {
      setLoading(false);
    }
  }

  async function handleManualVerify(e) {
    e.preventDefault();
    try {
      const proofSteps = JSON.parse(manualProof);
      const res = await api.verifyProof({
        content_hash: manualHash,
        merkle_root: manualRoot,
        proof: proofSteps,
      });
      setManualResult(res);
    } catch {
      setManualResult({ is_valid: false, error: "Error en los datos" });
    }
  }

  return (
    <div>
      <h1 className="page-title">Verificación de Integridad</h1>
      <p className="page-description">
        Genera y verifica pruebas criptográficas de Merkle para confirmar que un log
        no ha sido alterado.
      </p>

      <div className="grid-2">
        {/* Proof por Log ID */}
        <div className="card">
          <div className="card-title mb-md">🔍 Obtener Proof por Log ID</div>
          <form onSubmit={handleGetProof}>
            <div className="form-group">
              <label className="form-label">Log ID (UUID)</label>
              <input
                className="form-input"
                type="text"
                placeholder="ej: 550e8400-e29b-41d4-a716-..."
                value={logId}
                onChange={(e) => setLogId(e.target.value)}
                required
              />
            </div>
            <button className="btn btn-primary" disabled={loading || !logId}>
              {loading ? "Generando..." : "Generar Proof"}
            </button>
          </form>

          {error && <div className="error-message mt-md">{error}</div>}

          {proof && (
            <div className="mt-lg">
              <div className="card-title mb-md">📋 Merkle Proof</div>
              <div className="detail-grid mb-md">
                <span className="detail-label">Hash Actual (Recalculado)</span>
                <span className="detail-value mono" style={{ fontSize: "0.75rem", wordBreak: "break-all", color: proof.original_hash && proof.content_hash !== proof.original_hash ? "#ef4444" : "inherit" }}>
                  {proof.content_hash}
                </span>
                {proof.original_hash && proof.content_hash !== proof.original_hash && (
                  <>
                    <span className="detail-label" style={{ color: "#f59e0b" }}>Hash Original BD</span>
                    <span className="detail-value mono" style={{ fontSize: "0.75rem", wordBreak: "break-all", color: "#f59e0b" }}>
                      {proof.original_hash}
                    </span>
                  </>
                )}
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

              <div className="card-title mb-md">Pasos del Proof</div>
              <div className="proof-steps">
                {proof.proof.map((step, i) => (
                  <div key={i} className="proof-step">
                    <span className="position">{step.position}</span>
                    <span className="hash">{step.hash}</span>
                  </div>
                ))}
              </div>

              {verifyResult && (
                <div className={`verify-result ${verifyResult.is_valid ? "success" : "failure"} mt-md`}>
                  <strong>
                    {verifyResult.is_valid
                      ? "✅ Proof válido — el log no ha sido alterado"
                      : "❌ Proof inválido — posible manipulación"}
                  </strong>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Verificación manual */}
        <div className="card">
          <div className="card-title mb-md">🔧 Verificación Manual</div>
          <p className="text-muted mb-md" style={{ fontSize: "0.82rem" }}>
            Pega un content_hash, merkle_root y proof para verificar externamente.
          </p>
          <form onSubmit={handleManualVerify}>
            <div className="form-group">
              <label className="form-label">Content Hash</label>
              <input
                className="form-input"
                type="text"
                placeholder="SHA-256 hex..."
                value={manualHash}
                onChange={(e) => setManualHash(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Merkle Root</label>
              <input
                className="form-input"
                type="text"
                placeholder="Root esperado..."
                value={manualRoot}
                onChange={(e) => setManualRoot(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Proof (JSON)</label>
              <textarea
                className="form-textarea"
                placeholder='[{"hash": "abc...", "position": "left"}, ...]'
                value={manualProof}
                onChange={(e) => setManualProof(e.target.value)}
                required
              />
            </div>
            <button className="btn btn-primary">Verificar</button>
          </form>

          {manualResult && (
            <div className={`verify-result ${manualResult.is_valid ? "success" : "failure"} mt-md`}>
              <strong>
                {manualResult.is_valid
                  ? "✅ Proof válido"
                  : "❌ Proof inválido"}
              </strong>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
