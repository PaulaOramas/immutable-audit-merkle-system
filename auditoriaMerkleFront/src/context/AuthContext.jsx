/**
 * AuthContext — Contexto global de autenticación.
 *
 * Provee login, logout y el usuario actual a toda la aplicación.
 * El token JWT se persiste en localStorage.
 */
import { createContext, useContext, useState, useEffect } from "react";
import api from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // On mount: check for existing token and validate it
  useEffect(() => {
    const token = localStorage.getItem("jwt_token");
    if (token) {
      api.setToken(token);
      api
        .getMe()
        .then((userData) => setUser(userData))
        .catch(() => {
          api.clearToken();
          setUser(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (username, password) => {
    const data = await api.login(username, password);

    // The backend returns { access_token, token_type, username, role, expires_in_minutes }
    if (data.detail) {
      // Error response from backend
      throw new Error(data.detail.message || "Credenciales inválidas");
    }

    api.setToken(data.access_token);

    // Fetch the full user profile (includes id, full_name, etc.)
    const profile = await api.getMe();
    setUser(profile);
    return data;
  };

  const logout = () => {
    api.clearToken();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
