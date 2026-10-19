import React, { useState } from 'react';
import { Shield, User, Lock, ChevronRight } from 'lucide-react';
import { USERS } from '../data/mockData';

export default function LoginPage({ onLogin }) {
  const [selectedUser, setSelectedUser] = useState(USERS[1]); // Cajero por defecto

  // Añadir los 3 perfiles de atacantes a la lista visual de login
  const loginOptions = [
    ...USERS,
    { id: "ATK-001", name: "DBA Corrupto (Interno)", role: "dba_hacker", username: "sys_admin_escalated" },
    { id: "ATK-002", name: "Hacker Externo (Inyección SQL)", role: "sql_hacker", username: "anon_hacker" },
    { id: "ATK-003", name: "Estafador (Phishing - Ana Torres)", role: "phishing_hacker", username: "ana.torres" }
  ];

  const handleLogin = (e) => {
    e.preventDefault();
    onLogin(selectedUser);
  };

  return (
    <div className="login-container" style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', backgroundColor: '#f0f2f5'
    }}>
      <div className="login-card" style={{
        backgroundColor: 'white', padding: '40px', borderRadius: '12px', boxShadow: '0 8px 24px rgba(0,0,0,0.1)', width: '100%', maxWidth: '400px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '24px' }}>
          <Shield size={48} color="#2563eb" strokeWidth={1.5} />
        </div>
        <h2 style={{ textAlign: 'center', marginBottom: '8px', color: '#1e293b' }}>Banco Simulado</h2>
        <p style={{ textAlign: 'center', marginBottom: '32px', color: '#64748b' }}>Acceso al Entorno de Simulación</p>

        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: '500', color: '#334155' }}>
              Selecciona tu Perfil de Prueba
            </label>
            <div className="select-wrapper" style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', top: '50%', left: '12px', transform: 'translateY(-50%)', color: '#94a3b8', pointerEvents: 'none' }}>
                <User size={18} />
              </div>
              <select
                value={selectedUser.id}
                onChange={(e) => setSelectedUser(loginOptions.find(u => u.id === e.target.value))}
                style={{
                  width: '100%', padding: '12px 12px 12px 40px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '15px', appearance: 'none', outline: 'none', backgroundColor: 'white'
                }}
              >
                {loginOptions.map(u => (
                  <option key={u.id} value={u.id}>
                    {u.name} ({u.role})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{
              marginTop: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '12px', fontSize: '16px', fontWeight: '600', backgroundColor: '#2563eb', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer'
            }}
          >
            Entrar a la Simulación <ChevronRight size={18} />
          </button>
        </form>

        <div style={{ marginTop: '24px', paddingTop: '24px', borderTop: '1px solid #e2e8f0', textAlign: 'center' }}>
          <p style={{ fontSize: '13px', color: '#94a3b8', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
            <Lock size={14} /> Entorno seguro de pruebas
          </p>
        </div>
      </div>
    </div>
  );
}
