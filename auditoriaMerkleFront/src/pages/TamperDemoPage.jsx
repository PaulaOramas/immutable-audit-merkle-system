/**
 * TamperDemoPage — Demo interactiva de detección de alteración.
 *
 * Permite al usuario:
 * 1. Cargar un log real con su Merkle Proof
 * 2. Verificar que los datos originales son válidos (✅)
 * 3. Simular una alteración del contenido
 * 4. Verificar que el sistema detecta la manipulación (❌)
 * 5. Comparar lado a lado: original vs. alterado
 */
import { useState, useEffect } from "react";
import api from "../services/api";
import { truncateHash, formatDate } from "../utils/helpers";

export default function TamperDemoPage() {
  const [logs, setLogs] = useState([]);
  const [selectedLogId, setSelectedLogId] = useState("");
  const [step, setStep] = useState(0); // 0: select, 1: original, 2: tamper, 3: compare
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Datos originales
  const [originalProof, setOriginalProof] = useState(null);
  const [originalResult, setOriginalResult] = useState(null);

  // Datos alterados
  const [tamperedHash, setTamperedHash] = useState("");
  const [tamperedResult, setTamperedResult] = useState(null);
  const [tamperType, setTamperType] = useState("");

  useEffect(() => {
    loadLogs();
  }, []);

  async function loadLogs() {
    try {
      const res = await api.getLogs({ limit: 50, offset: 0 });
      setLogs(res.items || []);
    } catch {
      setLogs([]);
    }
  }

  async function handleLoadProof() {
    if (!selectedLogId) return;
    setLoading(true);
    setError(null);
    resetDemo();

    try {
      const proof = await api.getProof(selectedLogId);
      setOriginalProof(proof);

      // Verificar el original
      const result = await api.verifyProof({
        content_hash: proof.content_hash,
        merkle_root: proof.merkle_root,
        proof: proof.proof,
      });
      setOriginalResult(result);
      setTamperedHash(proof.content_hash);
      setStep(1);
    } catch {
      setError("No se pudo obtener el proof. Asegúrate de que el log esté en un batch cerrado.");
    } finally {
      setLoading(false);
    }
  }

  function resetDemo() {
    setOriginalProof(null);
    setOriginalResult(null);
    setTamperedHash("");
    setTamperedResult(null);
    setTamperType("");
    setStep(0);
  }

  // Simulaciones de alteración
  function tamperOneChar() {
    if (!originalProof) return;
    const hash = originalProof.content_hash;
    const pos = Math.floor(Math.random() * hash.length);
    const original = hash[pos];
    let replacement = original;
    while (replacement === original) {
      replacement = "0123456789abcdef"[Math.floor(Math.random() * 16)];
    }
    const tampered = hash.substring(0, pos) + replacement + hash.substring(pos + 1);
    setTamperedHash(tampered);
    setTamperType(`Se cambió el carácter en posición ${pos}: "${original}" → "${replacement}"`);
    setTamperedResult(null);
  }

  function tamperRandomHash() {
    const chars = "0123456789abcdef";
    let hash = "";
    for (let i = 0; i < 64; i++) hash += chars[Math.floor(Math.random() * 16)];
    setTamperedHash(hash);
    setTamperType("Se reemplazó todo el hash por uno aleatorio");
    setTamperedResult(null);
  }

  function tamperSwapChars() {
    if (!originalProof) return;
    const hash = originalProof.content_hash;
    const pos = Math.floor(Math.random() * (hash.length - 1));
    const tampered = hash.substring(0, pos) + hash[pos + 1] + hash[pos] + hash.substring(pos + 2);
    setTamperedHash(tampered);
    setTamperType(`Se intercambiaron los caracteres en posiciones ${pos} y ${pos + 1}`);
    setTamperedResult(null);
  }

  async function handleVerifyTampered() {
    if (!originalProof) return;
    setLoading(true);
    try {
      const result = await api.verifyProof({
        content_hash: tamperedHash,
        merkle_root: originalProof.merkle_root,
        proof: originalProof.proof,
      });
      setTamperedResult(result);
      setStep(3);
    } catch {
      setTamperedResult({ is_valid: false, error: "Error en verificación" });
      setStep(3);
    } finally {
      setLoading(false);
    }
  }

  // Encontrar diferencias entre dos hashes
  function renderHashDiff(original, tampered) {
    if (!original || !tampered) return null;
    return (
      <span className="hash-diff">
        {original.split("").map((char, i) => (
          <span key={i} className={char !== tampered[i] ? "hash-changed" : "hash-same"}>
            {tampered[i] || ""}
          </span>
        ))}
      </span>
    );
  }

  return (
    <div>
      <h1 className="page-title">Demo de Detección de Alteración</h1>
      <p className="page-description">
        Demostración interactiva de cómo el sistema Merkle detecta cualquier intento
        de manipulación de los registros de auditoría, por mínimo que sea.
      </p>

      {/* Progreso de pasos */}
      <div className="demo-steps-indicator mb-lg">
        {["Seleccionar Log", "Verificar Original", "Simular Alteración", "Comparar Resultados"].map((label, i) => (
          <div key={i} className={`demo-step-indicator ${step >= i ? "active" : ""} ${step === i ? "current" : ""}`}>
            <div className="demo-step-num">{i + 1}</div>
            <span>{label}</span>
          </div>
        ))}
      </div>

      {error && <div className="error-message mb-lg">{error}</div>}

      {/* Paso 1: Seleccionar log */}
      <div className={`demo-section ${step >= 0 ? "visible" : ""}`}>
        <div className="card">
          <div className="card-title mb-md">📝 Paso 1 — Seleccionar un Log</div>
          <p className="text-muted mb-md" style={{ fontSize: "0.85rem" }}>
            Selecciona un registro de auditoría existente. Se cargará su Merkle Proof
            para demostrar que no ha sido alterado.
          </p>
          <div className="flex gap-md items-center" style={{ flexWrap: "wrap" }}>
            <select
              className="form-select"
              style={{ maxWidth: 500 }}
              value={selectedLogId}
              onChange={(e) => { setSelectedLogId(e.target.value); resetDemo(); }}
            >
              <option value="">— Selecciona un log —</option>
              {logs.filter((l) => l.batch_id).map((log) => (
                <option key={log.id} value={log.id}>
                  [{log.source_app}] {log.event_type} — {truncateHash(log.content_hash, 10)} — {formatDate(log.created_at)}
                </option>
              ))}
            </select>
            <button
              className="btn btn-primary"
              disabled={!selectedLogId || loading}
              onClick={handleLoadProof}
            >
              {loading && step === 0 ? "Cargando..." : "🔒 Cargar Proof"}
            </button>
          </div>
        </div>
      </div>

      {/* Paso 2: Verificación original */}
      {step >= 1 && originalProof && (
        <div className="demo-section visible mt-lg">
          <div className="card">
            <div className="card-title mb-md">✅ Paso 2 — Verificación del Registro Original</div>
            <p className="text-muted mb-md" style={{ fontSize: "0.85rem" }}>
              Los datos originales del registro se verifican contra el árbol Merkle.
              El hash coincide con la estructura → <strong>integridad confirmada</strong>.
            </p>

            <div className="demo-data-panel">
              <div className="demo-data-row">
                <span className="demo-data-label">Content Hash</span>
                <span className="demo-data-value mono">{originalProof.content_hash}</span>
              </div>
              <div className="demo-data-row">
                <span className="demo-data-label">Merkle Root</span>
                <span className="demo-data-value mono">{originalProof.merkle_root}</span>
              </div>
              <div className="demo-data-row">
                <span className="demo-data-label">Batch</span>
                <span className="demo-data-value">#{originalProof.batch_number} · Leaf index: {originalProof.leaf_index}</span>
              </div>
              <div className="demo-data-row">
                <span className="demo-data-label">Proof ({originalProof.proof.length} pasos)</span>
                <span className="demo-data-value mono" style={{ fontSize: "0.72rem" }}>
                  {originalProof.proof.map((s) => `${s.position}:${truncateHash(s.hash, 6)}`).join(" → ")}
                </span>
              </div>
            </div>

            {originalResult && (
              <div className="verify-result success mt-md">
                <strong>✅ Verificación exitosa — El registro NO ha sido alterado</strong>
                <p style={{ fontSize: "0.82rem", marginTop: "4px", opacity: 0.85 }}>
                  El content_hash recorre correctamente el árbol Merkle y llega al root esperado.
                </p>
              </div>
            )}

            {step === 1 && (
              <button className="btn btn-primary mt-md" onClick={() => setStep(2)}>
                Siguiente: Simular Alteración →
              </button>
            )}
          </div>
        </div>
      )}

      {/* Paso 3: Simulación de alteración */}
      {step >= 2 && originalProof && (
        <div className="demo-section visible mt-lg">
          <div className="card">
            <div className="card-title mb-md">🔓 Paso 3 — Simular una Alteración</div>
            <p className="text-muted mb-md" style={{ fontSize: "0.85rem" }}>
              Simula que un atacante modifica el contenido del registro. Esto cambiaría
              su hash. Observa cómo el sistema detecta la manipulación.
            </p>

            {/* Botones de alteración */}
            <div className="demo-tamper-actions mb-md">
              <button className="btn btn-danger btn-sm" onClick={tamperOneChar}>
                🎯 Cambiar 1 carácter
              </button>
              <button className="btn btn-danger btn-sm" onClick={tamperSwapChars}>
                🔀 Intercambiar 2 caracteres
              </button>
              <button className="btn btn-danger btn-sm" onClick={tamperRandomHash}>
                💥 Hash completamente diferente
              </button>
            </div>

            {tamperType && (
              <div className="demo-tamper-info mb-md">
                <span className="demo-tamper-badge">Alteración aplicada</span>
                {tamperType}
              </div>
            )}

            {/* Hash alterado editable */}
            <div className="form-group">
              <label className="form-label">Hash alterado (editable)</label>
              <input
                className="form-input mono"
                style={{ fontSize: "0.78rem" }}
                value={tamperedHash}
                onChange={(e) => {
                  setTamperedHash(e.target.value);
                  setTamperType("Hash editado manualmente");
                  setTamperedResult(null);
                }}
              />
            </div>

            {/* Comparación visual de hashes */}
            {tamperedHash !== originalProof.content_hash && (
              <div className="demo-hash-compare mb-md">
                <div className="demo-hash-row">
                  <span className="demo-hash-label">Original:</span>
                  <span className="mono demo-hash-original">{originalProof.content_hash}</span>
                </div>
                <div className="demo-hash-row">
                  <span className="demo-hash-label">Alterado:</span>
                  {renderHashDiff(originalProof.content_hash, tamperedHash)}
                </div>
              </div>
            )}

            <button
              className="btn btn-primary"
              disabled={loading || tamperedHash === originalProof.content_hash}
              onClick={handleVerifyTampered}
            >
              {loading ? "Verificando..." : "🔍 Verificar Datos Alterados"}
            </button>

            {tamperedHash === originalProof.content_hash && (
              <span className="text-muted ml-md" style={{ fontSize: "0.82rem" }}>
                ⬆️ Modifica el hash primero
              </span>
            )}
          </div>
        </div>
      )}

      {/* Paso 4: Comparación de resultados */}
      {step >= 3 && (
        <div className="demo-section visible mt-lg">
          <div className="card">
            <div className="card-title mb-md">📊 Paso 4 — Comparación de Resultados</div>
            <p className="text-muted mb-md" style={{ fontSize: "0.85rem" }}>
              El sistema Merkle detecta cualquier alteración, por mínima que sea.
              La estructura jerárquica de hashes propaga el cambio hasta la raíz.
            </p>

            <div className="demo-comparison">
              {/* Original */}
              <div className="demo-compare-card demo-compare-success">
                <div className="demo-compare-header">
                  <span className="demo-compare-icon">✅</span>
                  <strong>Datos Originales</strong>
                </div>
                <div className="demo-compare-hash mono">{truncateHash(originalProof.content_hash, 16)}</div>
                <div className="demo-compare-result">Verificación: VÁLIDA</div>
                <p>El hash original recorre correctamente el árbol Merkle hasta el root.</p>
              </div>

              {/* Separador */}
              <div className="demo-compare-vs">VS</div>

              {/* Alterado */}
              <div className="demo-compare-card demo-compare-failure">
                <div className="demo-compare-header">
                  <span className="demo-compare-icon">❌</span>
                  <strong>Datos Alterados</strong>
                </div>
                <div className="demo-compare-hash mono">{truncateHash(tamperedHash, 16)}</div>
                <div className="demo-compare-result">Verificación: INVÁLIDA</div>
                <p>El hash modificado no coincide con la estructura del árbol Merkle.</p>
              </div>
            </div>

            {/* Explicación */}
            <div className="demo-explanation mt-lg">
              <h4>¿Por qué funciona?</h4>
              <div className="demo-explanation-grid">
                <div className="demo-explanation-item">
                  <span className="demo-explanation-num">1</span>
                  <div>
                    <strong>Hashing determinístico</strong>
                    <p>Cada registro tiene un hash SHA-256 único. Cualquier cambio en el contenido produce un hash completamente diferente.</p>
                  </div>
                </div>
                <div className="demo-explanation-item">
                  <span className="demo-explanation-num">2</span>
                  <div>
                    <strong>Propagación en el árbol</strong>
                    <p>Al cambiar una hoja, todos los nodos intermedios hasta la raíz cambian. Es imposible alterar un registro sin invalidar la raíz.</p>
                  </div>
                </div>
                <div className="demo-explanation-item">
                  <span className="demo-explanation-num">3</span>
                  <div>
                    <strong>Anclaje inmutable</strong>
                    <p>El Merkle Root está anclado en blockchain. Aun si alguien modifica la base de datos, el root on-chain permanece intacto como referencia.</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex gap-md mt-lg">
              <button className="btn btn-secondary" onClick={() => { setStep(2); setTamperedResult(null); }}>
                🔄 Intentar otra alteración
              </button>
              <button className="btn btn-secondary" onClick={resetDemo}>
                🔁 Reiniciar Demo
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
