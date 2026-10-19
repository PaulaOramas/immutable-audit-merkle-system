/**
 * Generadores de eventos para cada módulo de simulación.
 * Cada función retorna un objeto con la estructura que espera el API de auditoría.
 */
import { USERS, ACCOUNTS, CONFIG_KEYS, randomItem, randomAmount, randomIp } from "../data/mockData";

// ====== AUTENTICACIÓN ======
export function generateLoginSuccess(currentUser) {
  const user = currentUser || randomItem(USERS);
  return {
    source_app: "secure_bank",
    event_type: "login_success",
    severity: "info",
    payload: {
      user_id: user.id,
      username: user.username,
      role: user.role,
      ip: randomIp(),
      user_agent: "Mozilla/5.0 (SecureBank Dashboard)",
      timestamp: new Date().toISOString(),
    },
  };
}

export function generateLoginFailed(currentUser) {
  const user = currentUser || randomItem(USERS);
  return {
    source_app: "secure_bank",
    event_type: "login_failed",
    severity: "warning",
    payload: {
      username: user.username,
      reason: randomItem(["invalid_password", "account_locked", "expired_session"]),
      ip: randomIp(),
      attempts: Math.floor(Math.random() * 5) + 1,
      timestamp: new Date().toISOString(),
    },
  };
}

export function generateLogout(currentUser) {
  const user = currentUser || randomItem(USERS);
  return {
    source_app: "secure_bank",
    event_type: "logout",
    severity: "info",
    payload: {
      user_id: user.id,
      username: user.username,
      session_duration_min: Math.floor(Math.random() * 120) + 1,
      ip: randomIp(),
      timestamp: new Date().toISOString(),
    },
  };
}

export function generatePasswordChange(currentUser) {
  const user = currentUser || randomItem(USERS);
  return {
    source_app: "secure_bank",
    event_type: "password_change",
    severity: "info",
    payload: {
      user_id: user.id,
      username: user.username,
      initiated_by: currentUser ? currentUser.username : randomItem(["user", "admin", "policy"]),
      ip: randomIp(),
      timestamp: new Date().toISOString(),
    },
  };
}

// ====== TRANSACCIONES ======
export function generateTransfer(currentUser) {
  const from = randomItem(ACCOUNTS);
  let to = randomItem(ACCOUNTS);
  while (to.id === from.id) to = randomItem(ACCOUNTS);
  const amount = randomAmount(50, 10000);
  return {
    source_app: "secure_bank",
    event_type: "transfer",
    severity: amount > 5000 ? "warning" : "info",
    payload: {
      from_account: from.id,
      to_account: to.id,
      amount,
      currency: "USD",
      initiated_by: currentUser?.username || randomItem(USERS).username,
      ip: randomIp(),
      reference: `TXN-${Date.now().toString(36).toUpperCase()}`,
      timestamp: new Date().toISOString(),
    },
  };
}

export function generateDeposit(currentUser) {
  const account = randomItem(ACCOUNTS);
  const amount = randomAmount(100, 20000);
  return {
    source_app: "secure_bank",
    event_type: "deposit",
    severity: amount > 10000 ? "warning" : "info",
    payload: {
      account_id: account.id,
      amount,
      currency: "USD",
      method: randomItem(["cash", "check", "wire", "ach"]),
      teller: currentUser?.username || randomItem(USERS).username,
      ip: randomIp(),
      reference: `DEP-${Date.now().toString(36).toUpperCase()}`,
      timestamp: new Date().toISOString(),
    },
  };
}

export function generateWithdrawal(currentUser) {
  const account = randomItem(ACCOUNTS);
  const amount = randomAmount(20, 5000);
  return {
    source_app: "secure_bank",
    event_type: "withdrawal",
    severity: amount > 3000 ? "warning" : "info",
    payload: {
      account_id: account.id,
      amount,
      currency: "USD",
      method: randomItem(["atm", "counter", "online"]),
      initiated_by: currentUser?.username || "unknown",
      ip: randomIp(),
      reference: `WDR-${Date.now().toString(36).toUpperCase()}`,
      timestamp: new Date().toISOString(),
    },
  };
}

// ====== GESTIÓN DE USUARIOS ======
export function generateUserCreated(currentUser) {
  const creator = currentUser || randomItem(USERS.filter((u) => u.role === "admin" || u.role === "gerente"));
  const newId = `U${String(Math.floor(Math.random() * 900) + 100)}`;
  return {
    source_app: "secure_bank",
    event_type: "user_created",
    severity: "info",
    payload: {
      new_user_id: newId,
      new_username: `user_${newId.toLowerCase()}`,
      role_assigned: randomItem(["cajero", "auditor", "viewer"]),
      created_by: creator.username,
      ip: randomIp(),
      timestamp: new Date().toISOString(),
    },
  };
}

export function generateRoleChanged(currentUser) {
  const target = randomItem(USERS);
  const admin = currentUser || randomItem(USERS.filter((u) => u.role === "admin"));
  const newRole = randomItem(["admin", "cajero", "gerente", "auditor", "viewer"]);
  return {
    source_app: "secure_bank",
    event_type: "role_changed",
    severity: newRole === "admin" ? "critical" : "warning",
    payload: {
      user_id: target.id,
      username: target.username,
      old_role: target.role,
      new_role: newRole,
      changed_by: admin.username,
      ip: randomIp(),
      timestamp: new Date().toISOString(),
    },
  };
}

export function generateUserDeleted(currentUser) {
  const target = randomItem(USERS);
  const admin = currentUser || randomItem(USERS.filter((u) => u.role === "admin"));
  return {
    source_app: "secure_bank",
    event_type: "user_deleted",
    severity: "warning",
    payload: {
      user_id: target.id,
      username: target.username,
      deleted_by: admin.username,
      reason: randomItem(["terminated", "policy_violation", "inactive", "request"]),
      ip: randomIp(),
      timestamp: new Date().toISOString(),
    },
  };
}

// ====== CAMBIOS DE ESTADO ======
export function generateConfigChanged(currentUser) {
  const config = randomItem(CONFIG_KEYS);
  const admin = currentUser || randomItem(USERS.filter((u) => u.role === "admin" || u.role === "gerente"));
  return {
    source_app: "secure_bank",
    event_type: "config_changed",
    severity: "warning",
    payload: {
      config_key: config.key,
      config_label: config.label,
      old_value: `old_${Math.floor(Math.random() * 100)}`,
      new_value: `new_${Math.floor(Math.random() * 100)}`,
      changed_by: admin.username,
      ip: randomIp(),
      timestamp: new Date().toISOString(),
    },
  };
}

export function generateServiceStatus(currentUser) {
  const services = ["payment_gateway", "auth_service", "notification_service", "report_engine", "backup_service"];
  const svc = randomItem(services);
  const newStatus = randomItem(["online", "offline", "degraded", "maintenance"]);
  return {
    source_app: "secure_bank",
    event_type: "service_status",
    severity: newStatus === "offline" ? "critical" : newStatus === "degraded" ? "error" : "info",
    payload: {
      service_name: svc,
      new_status: newStatus,
      previous_status: randomItem(["online", "offline", "degraded"]),
      reported_by: currentUser?.username || "system_monitor",
      timestamp: new Date().toISOString(),
    },
  };
}

// ====== MAPA DE GENERADORES ======
import { LogIn, Lock, LogOut, KeyRound, Send, ArrowDownToLine, Landmark, UserPlus, UserCog, UserMinus, FileCog, Activity } from "lucide-react";

export const EVENT_GENERATORS = {
  login_success: { fn: (user) => generateLoginSuccess(user), label: "Login Exitoso", icon: LogIn, category: "auth" },
  login_failed: { fn: (user) => generateLoginFailed(user), label: "Login Fallido", icon: Lock, category: "auth" },
  logout: { fn: (user) => generateLogout(user), label: "Cierre de Sesión", icon: LogOut, category: "auth" },
  password_change: { fn: (user) => generatePasswordChange(user), label: "Cambio de Contraseña", icon: KeyRound, category: "auth" },
  transfer: { fn: (user) => generateTransfer(user), label: "Transferencia", icon: Send, category: "transaction" },
  deposit: { fn: (user) => generateDeposit(user), label: "Depósito", icon: ArrowDownToLine, category: "transaction" },
  withdrawal: { fn: (user) => generateWithdrawal(user), label: "Retiro", icon: Landmark, category: "transaction" },
  user_created: { fn: (user) => generateUserCreated(user), label: "Crear Usuario", icon: UserPlus, category: "user" },
  role_changed: { fn: (user) => generateRoleChanged(user), label: "Cambiar Rol", icon: UserCog, category: "user" },
  user_deleted: { fn: (user) => generateUserDeleted(user), label: "Eliminar Usuario", icon: UserMinus, category: "user" },
  config_changed: { fn: (user) => generateConfigChanged(user), label: "Cambiar Configuración", icon: FileCog, category: "system" },
  service_status: { fn: (user) => generateServiceStatus(user), label: "Estado de Servicio", icon: Activity, category: "system" },
};

export function generateRandomEvent(currentUser) {
  const keys = Object.keys(EVENT_GENERATORS);
  const key = randomItem(keys);
  return { type: key, ...EVENT_GENERATORS[key].fn(currentUser) };
}
