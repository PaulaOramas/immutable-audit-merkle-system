/**
 * App — Punto de entrada con React Router y protección de rutas.
 *
 * Si el usuario no ha iniciado sesión, se muestra la página de login.
 * Una vez autenticado, se muestra el layout principal con las rutas protegidas.
 */
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import MainLayout from "./components/layout/MainLayout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import LogsPage from "./pages/LogsPage";
import LogDetailPage from "./pages/LogDetailPage";
import BatchesPage from "./pages/BatchesPage";
import BatchDetailPage from "./pages/BatchDetailPage";
import VerifyPage from "./pages/VerifyPage";
import ReportsPage from "./pages/ReportsPage";
import TamperDemoPage from "./pages/TamperDemoPage";
import ThreatAnalyticsPage from "./pages/ThreatAnalyticsPage";
import "./index.css";

/**
 * ProtectedRoutes — Renderiza el layout principal solo si
 * el usuario está autenticado. De lo contrario redirige a /login.
 */
function ProtectedRoutes() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="login-page">
        <div className="loading-spinner">
          <span className="spinner" />
          Verificando sesión...
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <MainLayout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/logs" element={<LogsPage />} />
        <Route path="/logs/:id" element={<LogDetailPage />} />
        <Route path="/batches" element={<BatchesPage />} />
        <Route path="/batches/:id" element={<BatchDetailPage />} />
        <Route path="/verify" element={<VerifyPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/tamper-demo" element={<TamperDemoPage />} />
        <Route path="/threats" element={<ThreatAnalyticsPage />} />
      </Routes>
    </MainLayout>
  );
}

/**
 * LoginRoute — Muestra login solo si NO está autenticado.
 */
function LoginRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="login-page">
        <div className="loading-spinner">
          <span className="spinner" />
          Cargando...
        </div>
      </div>
    );
  }

  if (user) {
    return <Navigate to="/" replace />;
  }

  return <LoginPage />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route path="/*" element={<ProtectedRoutes />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
