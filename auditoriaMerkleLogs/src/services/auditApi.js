/**
 * Cliente API para enviar logs al sistema de auditoría Merkle.
 */
const AUDIT_API = import.meta.env.VITE_AUDIT_API_URL || "http://localhost:8000";
const API_KEY = import.meta.env.VITE_AUDIT_API_KEY || "";

export async function sendLog(log) {
  const res = await fetch(`${AUDIT_API}/api/v1/logs`, {
    method: "POST",
    headers: { 
      "Content-Type": "application/json",
      "X-API-Key": API_KEY 
    },
    body: JSON.stringify(log),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || `Error ${res.status}`);
  }
  return res.json();
}

export async function sendLogsBatch(logs) {
  const res = await fetch(`${AUDIT_API}/api/v1/logs/batch`, {
    method: "POST",
    headers: { 
      "Content-Type": "application/json",
      "X-API-Key": API_KEY 
    },
    body: JSON.stringify({ logs }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || `Error ${res.status}`);
  }
  return res.json();
}

export async function checkHealth() {
  const res = await fetch(`${AUDIT_API}/health`);
  return res.json();
}
