/**
 * Datos ficticios para la simulación de SecureBank.
 */

export const USERS = [
  { id: "U001", name: "Carlos Méndez", role: "admin", username: "carlos.mendez" },
  { id: "U002", name: "Ana Torres", role: "cajero", username: "ana.torres" },
  { id: "U003", name: "Luis Herrera", role: "gerente", username: "luis.herrera" },
  { id: "U004", name: "María López", role: "auditor", username: "maria.lopez" },
  { id: "U005", name: "Pedro Sánchez", role: "cajero", username: "pedro.sanchez" },
];

export const ACCOUNTS = [
  { id: "CTA-1001", owner: "U001", balance: 15200.50, type: "Corriente" },
  { id: "CTA-1002", owner: "U002", balance: 8340.00, type: "Ahorros" },
  { id: "CTA-1003", owner: "U003", balance: 42100.75, type: "Corriente" },
  { id: "CTA-1004", owner: "U004", balance: 3200.00, type: "Ahorros" },
  { id: "CTA-1005", owner: "U005", balance: 950.25, type: "Corriente" },
];

export const IPS = [
  "192.168.1.10", "192.168.1.25", "10.0.0.5", "172.16.0.100",
  "192.168.2.45", "10.0.1.12", "192.168.1.88",
];

export const CONFIG_KEYS = [
  { key: "max_transfer_limit", label: "Límite máximo de transferencia" },
  { key: "session_timeout", label: "Tiempo de expiración de sesión" },
  { key: "two_factor_auth", label: "Autenticación de dos factores" },
  { key: "daily_withdrawal_limit", label: "Límite diario de retiro" },
  { key: "password_policy", label: "Política de contraseñas" },
  { key: "audit_retention_days", label: "Días de retención de auditoría" },
];

export const SEVERITIES = ["info", "warning", "error", "critical"];

export function randomItem(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

export function randomAmount(min = 10, max = 5000) {
  return Math.round((Math.random() * (max - min) + min) * 100) / 100;
}

export function randomIp() {
  const ip = randomItem(IPS);
  const port = Math.floor(Math.random() * (65535 - 1024 + 1)) + 1024;
  return `${ip}:${port}`;
}
