/**
 * Sidebar — Navegación principal del dashboard.
 */
import { NavLink, useLocation } from "react-router-dom";
import { LayoutDashboard, FileText, Package, Search, FileBarChart, ShieldAlert, Network, Crosshair } from "lucide-react";

export default function Sidebar() {
  const location = useLocation();

  const links = [
    { to: "/", icon: <LayoutDashboard size={18} />, label: "Dashboard" },
    { to: "/logs", icon: <FileText size={18} />, label: "Logs" },
    { to: "/batches", icon: <Package size={18} />, label: "Batches" },
    { to: "/verify", icon: <Search size={18} />, label: "Verificar" },
    { to: "/reports", icon: <FileBarChart size={18} />, label: "Reportes" },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="logo">M</div>
        <h1>Merkle Audit</h1>
      </div>

      <nav className="sidebar-nav">
        <div className="sidebar-section">
          <div className="sidebar-section-title">Principal</div>
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === "/"}
              className={({ isActive }) =>
                `sidebar-link${isActive ? " active" : ""}`
              }
            >
              <span className="icon" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {link.icon}
              </span>
              {link.label}
            </NavLink>
          ))}
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-title">Seguridad</div>
          <NavLink
            to="/threats"
            className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
          >
            <span className="icon" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Crosshair size={18} />
            </span>
            Amenazas (SOC)
          </NavLink>
          <NavLink
            to="/tamper-demo"
            className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
          >
            <span className="icon" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <ShieldAlert size={18} />
            </span>
            Demo Alteración
          </NavLink>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-title">Sistema</div>
          <div className="sidebar-link" style={{ cursor: "default" }}>
            <span className="icon" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Network size={18} />
            </span>
            <span style={{ fontSize: "0.8rem" }}>Ganache: 1337</span>
          </div>
        </div>
      </nav>
    </aside>
  );
}
