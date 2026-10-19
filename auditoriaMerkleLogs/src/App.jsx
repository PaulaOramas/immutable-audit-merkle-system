/**
 * App — SecureBank: Simulador de Actividad para Auditoría Merkle.
 *
 * Genera eventos controlados que se envían al sistema de auditoría
 * como fuente de datos demostrable.
 */
import { useState, useCallback, useEffect } from "react";
import { EVENT_GENERATORS, generateRandomEvent } from "./services/eventGenerators";
import { sendLog, checkHealth } from "./services/auditApi";
import EventTimeline from "./components/EventTimeline";
import StatsBar from "./components/StatsBar";
import AutoSimulator from "./components/AutoSimulator";
import LoginPage from "./components/LoginPage";
import { Shield, Banknote, Users, Settings, MonitorPlay, Dices, LogOut, UserCircle } from "lucide-react";
import "./index.css";

const CATEGORIES = [
  { id: "auth", label: "Autenticación", icon: <Shield size={18} /> },
  { id: "transaction", label: "Transacciones", icon: <Banknote size={18} /> },
  { id: "user", label: "Usuarios", icon: <Users size={18} /> },
  { id: "system", label: "Sistema", icon: <Settings size={18} /> },
];

function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [events, setEvents] = useState([]);
  const [stats, setStats] = useState({
    total: 0, info: 0, warning: 0, error: 0, critical: 0, connected: false,
  });
  const [activeCategory, setActiveCategory] = useState("auth");
  const [sending, setSending] = useState(false);

  // Check API health on mount
  useEffect(() => {
    checkHealth()
      .then(() => setStats((s) => ({ ...s, connected: true })))
      .catch(() => setStats((s) => ({ ...s, connected: false })));
    const interval = setInterval(() => {
      checkHealth()
        .then(() => setStats((s) => ({ ...s, connected: true })))
        .catch(() => setStats((s) => ({ ...s, connected: false })));
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  const sendEvent = useCallback(async (eventType) => {
    const gen = EVENT_GENERATORS[eventType];
    if (!gen) return;
    const logData = gen.fn(currentUser);
    // Update source_app to banco_simulado
    logData.source_app = "banco_simulado";
    const localId = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const localEvent = {
      ...logData,
      _localId: localId,
      _icon: gen.icon,
      _label: gen.label,
      _status: "pending",
    };

    setEvents((prev) => [localEvent, ...prev].slice(0, 200));

    try {
      const result = await sendLog(logData);
      setEvents((prev) =>
        prev.map((e) =>
          e._localId === localId
            ? { ...e, _status: "sent", _hash: result.content_hash, _id: result.id }
            : e
        )
      );
      setStats((s) => ({
        ...s,
        total: s.total + 1,
        [logData.severity]: (s[logData.severity] || 0) + 1,
        connected: true,
      }));
    } catch {
      setEvents((prev) =>
        prev.map((e) =>
          e._localId === localId ? { ...e, _status: "error" } : e
        )
      );
      setStats((s) => ({ ...s, connected: false }));
    }
  }, [currentUser]);

  const sendRandomEvent = useCallback(async () => {
    const keys = Object.keys(EVENT_GENERATORS);
    const key = keys[Math.floor(Math.random() * keys.length)];
    await sendEvent(key);
  }, [sendEvent]);

  const sendBurst = useCallback(async (eventType, count = 5) => {
    setSending(true);
    for (let i = 0; i < count; i++) {
      await sendEvent(eventType);
      await new Promise((r) => setTimeout(r, 150));
    }
    setSending(false);
  }, [sendEvent]);

  const filteredGenerators = Object.entries(EVENT_GENERATORS).filter(
    ([, v]) => v.category === activeCategory
  );

  if (!currentUser) {
    return <LoginPage onLogin={setCurrentUser} />;
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <div className="header-brand">
          <span className="header-logo" style={{ display: 'flex', alignItems: 'center' }}>
            <MonitorPlay size={32} strokeWidth={2} />
          </span>
          <div>
            <h1 className="header-title">Banco Simulado</h1>
            <p className="header-subtitle">Simulador de Actividad — Sistema de Auditoría Merkle</p>
          </div>
        </div>
        <div className="header-actions" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 12px', backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: '20px', fontSize: '13px' }}>
            <UserCircle size={16} />
            <span>{currentUser.name} ({currentUser.role})</span>
          </div>
          <button
            className="btn btn-random"
            onClick={sendRandomEvent}
            disabled={sending}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <Dices size={18} /> Evento Aleatorio
          </button>
          <button
            className="btn"
            onClick={() => setCurrentUser(null)}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'transparent', border: '1px solid rgba(255,255,255,0.2)', color: 'white', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer' }}
            title="Cerrar Sesión"
          >
            <LogOut size={16} /> Salir
          </button>
        </div>
      </header>

      {/* Warning banner for attackers */}
      {currentUser?.role?.endsWith('_hacker') && (
        <div style={{
          backgroundColor: '#fee2e2', color: '#991b1b', padding: '12px 24px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', borderBottom: '1px solid #fecaca', fontWeight: '500', fontSize: '14px'
        }}>
          <Shield size={18} />
          MODO ATAQUE ACTIVO: Estás utilizando el perfil de simulación "{currentUser.name}".
          {currentUser.role === 'phishing_hacker' && " Genera transacciones normales rápido para simular Smurfing."}
          {currentUser.role === 'sql_hacker' && " Genera un evento normal y luego usa el botón de Inyección SQL en el log."}
          {currentUser.role === 'dba_hacker' && " Genera un evento normal y luego modifícalo directamente usando UPDATE SQL."}
        </div>
      )}

      {/* Stats */}
      <StatsBar stats={stats} />

      <div className="main-grid">
        {/* Left: Controls */}
        <div className="controls-panel">
          <h2 className="panel-title">Generador de Eventos</h2>

          {/* Category Tabs */}
          <div className="category-tabs">
            {CATEGORIES.map((cat) => (
              <button
                key={cat.id}
                className={`category-tab ${activeCategory === cat.id ? "active" : ""}`}
                onClick={() => setActiveCategory(cat.id)}
              >
                <span style={{ display: 'flex' }}>{cat.icon}</span>
                <span>{cat.label}</span>
              </button>
            ))}
          </div>

          {/* Event Buttons */}
          <div className="event-buttons">
            {filteredGenerators.map(([key, gen]) => {
              const IconComp = gen.icon;
              return (
                <div key={key} className="event-button-group">
                  <button
                    className="btn btn-event"
                    onClick={() => sendEvent(key)}
                    disabled={sending}
                  >
                    <span className="btn-icon" style={{ display: 'flex' }}><IconComp size={18} /></span>
                    <span className="btn-text">{gen.label}</span>
                  </button>
                  <button
                    className="btn btn-burst"
                    onClick={() => sendBurst(key, 5)}
                    disabled={sending}
                    title="Enviar 5 eventos"
                  >
                    ×5
                  </button>
                </div>
              );
            })}
          </div>

          {/* Auto Simulator */}
          <AutoSimulator onGenerate={sendRandomEvent} disabled={sending} />
        </div>

        {/* Right: Timeline */}
        <div className="timeline-panel">
          <div className="panel-header">
            <h2 className="panel-title">Timeline de Eventos</h2>
            <span className="event-count">{events.length} eventos</span>
          </div>
          <EventTimeline events={events} currentUser={currentUser} />
        </div>
      </div>

      {/* Footer */}
      <footer className="app-footer">
        <p>
          Banco Simulado Simulator • Los eventos generados se envían al API de Auditoría Merkle
          en <code>localhost:8000</code>
        </p>
      </footer>
    </div>
  );
}

export default App;
