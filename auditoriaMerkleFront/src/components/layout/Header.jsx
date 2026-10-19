/**
 * Header — Barra superior con título de página y status.
 */
import { useLocation } from "react-router-dom";

const pageTitles = {
  "/": "Dashboard",
  "/logs": "Logs de Auditoría",
  "/batches": "Batches Merkle",
  "/verify": "Verificación",
  "/reports": "Reportes",
  "/tamper-demo": "Demo de Alteración",
  "/login": "Iniciar Sesión",
};

export default function Header() {
  const location = useLocation();

  const getTitle = () => {
    if (pageTitles[location.pathname]) return pageTitles[location.pathname];
    if (location.pathname.startsWith("/batches/")) return "Detalle del Batch";
    if (location.pathname.startsWith("/logs/")) return "Detalle del Log";
    return "Merkle Audit";
  };

  return (
    <header className="header">
      <div className="header-left">
        <h2>{getTitle()}</h2>
      </div>
      <div className="header-right">
        <div className="header-status">
          <span className="status-dot"></span>
          Backend conectado
        </div>
      </div>
    </header>
  );
}
