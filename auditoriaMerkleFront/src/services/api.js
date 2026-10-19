/**
 * API Client — Conexión con el backend FastAPI.
 *
 * Centraliza todas las llamadas HTTP al backend:
 * - Auth (login, register, API keys)
 * - Logs (listar, detalle, ingestar)
 * - Batches (listar, detalle, anclar, verificar)
 * - Verify (proof, verificación on-chain)
 */

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

class ApiClient {
  constructor() {
    this.baseUrl = API_BASE;
    this.token = localStorage.getItem("jwt_token");
  }

  // Headers
  _headers(isJson = true) {
    const headers = {};
    if (isJson) headers["Content-Type"] = "application/json";
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
    return headers;
  }

  setToken(token) {
    this.token = token;
    localStorage.setItem("jwt_token", token);
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem("jwt_token");
  }

  // Generic fetch
  async _fetch(path, options = {}) {
    const res = await fetch(`${this.baseUrl}${path}`, {
      headers: this._headers(),
      ...options,
    });
    if (res.status === 401 && !path.includes("/auth/login")) {
      this.clearToken();
      window.location.href = "/login";
      throw new Error("No autorizado");
    }
    return res;
  }

  // ====== Auth ======
  async login(username, password) {
    const res = await this._fetch("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err?.detail?.message || "Credenciales inválidas");
    }
    return res.json();
  }

  async getMe() {
    const res = await this._fetch("/api/v1/auth/me");
    return res.json();
  }

  // ====== Logs ======
  async getLogs(params = {}) {
    const query = new URLSearchParams(params).toString();
    const res = await this._fetch(`/api/v1/logs?${query}`);
    return res.json();
  }

  async getLog(id) {
    const res = await this._fetch(`/api/v1/logs/${id}`);
    return res.json();
  }

  // ====== Batches ======
  async getBatches(params = {}) {
    const query = new URLSearchParams(params).toString();
    const res = await this._fetch(`/api/v1/batches?${query}`);
    return res.json();
  }

  async getBatch(id) {
    const res = await this._fetch(`/api/v1/batches/${id}`);
    return res.json();
  }

  async anchorBatch(id) {
    const res = await this._fetch(`/api/v1/batches/${id}/anchor`, {
      method: "POST",
    });
    return res.json();
  }

  async closeBatch(id) {
    const res = await this._fetch(`/api/v1/batches/${id}/close`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Error cerrando batch");
    return res.json();
  }

  async crossVerifyBatch(id) {
    const res = await this._fetch(`/api/v1/batches/${id}/cross-verify`);
    return res.json();
  }

  async timestampBatch(id) {
    const res = await this._fetch(`/api/v1/batches/${id}/timestamp`, {
      method: "POST",
    });
    return res.json();
  }

  async getBatchTree(id) {
    const res = await this._fetch(`/api/v1/batches/${id}/tree`);
    return res.json();
  }

  // ====== Verify ======
  async getProof(logId) {
    const res = await this._fetch(`/api/v1/logs/${logId}/proof`);
    return res.json();
  }

  async verifyProof(data) {
    const res = await this._fetch("/api/v1/verify", {
      method: "POST",
      body: JSON.stringify(data),
    });
    return res.json();
  }

  // ====== Health ======
  async getHealth() {
    const res = await fetch(`${this.baseUrl}/health`);
    return res.json();
  }
}

export const api = new ApiClient();
export default api;
