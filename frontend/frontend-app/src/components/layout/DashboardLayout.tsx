import { NavLink, Outlet } from 'react-router-dom';
import { Icon, type IconName } from '../icons/Icon';

interface NavItem {
  path: string;
  label: string;
  icon: IconName;
}

const NAV: NavItem[] = [
  { path: '/dashboard', label: 'Início', icon: 'home' },
  { path: '/dashboard/my-devices', label: 'Meus dispositivos', icon: 'devices'},
  { path: '/dashboard/problems', label: 'Problemas', icon: 'alert' },
  { path: '/dashboard/devices', label: 'Minha Rede', icon: 'network' },
  { path: '/dashboard/scan', label: 'Nova Verificação', icon: 'scan' },
  { path: '/dashboard/progress', label: 'Verificando…', icon: 'terminal' },
  { path: '/dashboard/history', label: 'Histórico', icon: 'history' },
  { path: '/dashboard/settings', label: 'Configurações', icon: 'settings' },
];

interface DashboardLayoutProps {
  onLogout: () => void;
}

export default function DashboardLayout({ onLogout }: DashboardLayoutProps) {
  // Simulando o estado do dispositivo da mock
  const deviceOnline = true;

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* SIDEBAR */ }
      <aside className="sidebar" style={{ height: '100%', background: 'var(--surface)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', padding: '0 10px', flexShrink: 0 }}>
        
        {/* Header - Versão Expandida */ }
        <div className="sidebar-header-expanded" style={{ padding: '18px 6px 14px', borderBottom: '1px solid var(--border)', marginBottom: 8, whiteSpace: 'nowrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 36, height: 36, background: 'var(--accent-dim)', border: '1px solid var(--accent-glow)', borderRadius: 9, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              {/* <Icon n="shield" s={19} c="var(--accent)" /> */}
              <img src="/Dmitri-logo.png" alt="Logo" style={{ maxWidth: "100%", height: "auto", objectFit: "contain" }} />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16, letterSpacing: '-0.01em' }}>Dmitri</div>
              <div style={{ fontSize: 10, color: 'var(--text3)', letterSpacing: '0.04em' }}>Proteção de Rede</div>
            </div>
          </div>
        </div>

        {/* Header - Versão Colapsada (Mobile) */ }
        <div className="sidebar-header-collapsed" style={{ padding: '18px 0 14px', borderBottom: '1px solid var(--border)', marginBottom: 8, display:'flex', justifyContent:'center' }}>
           <div style={{ width: 36, height: 36, background: 'var(--accent-dim)', border: '1px solid var(--accent-glow)', borderRadius: 9, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {/* <Icon n="shield" s={19} c="var(--accent)" /> */}
              <img src="/Dmitri-logo.png" alt="Logo" style={{ maxWidth: "100%", height: "auto", objectFit: "contain" }} />
            </div>
        </div>

        {/* Status do Scanner */ }
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px', marginBottom: 8, background: deviceOnline ? 'rgba(82,200,160,0.08)' : 'rgba(255,68,68,0.08)', border: `1px solid ${deviceOnline ? 'rgba(82,200,160,0.2)' : 'rgba(255,68,68,0.2)'}`, borderRadius: 'var(--radius)', whiteSpace: 'nowrap', overflow: 'hidden' }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: deviceOnline ? 'var(--ok)' : 'var(--urgente)', boxShadow: `0 0 8px ${deviceOnline ? 'var(--ok)' : 'var(--urgente)'}`, flexShrink: 0 }} />
          <div className="sidebar-text">
            <div style={{ fontSize: 11, fontWeight: 600, color: deviceOnline ? 'var(--ok)' : 'var(--urgente)' }}>{deviceOnline ? 'Conectado' : 'Offline'}</div>
          </div>
        </div>

        {/* Links de Navegação */ }
        <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2, overflowY: 'auto', overflowX: 'hidden' }}>
          {NAV.map((n) => (
            <NavLink
              key={n.path}
              to={n.path}
              end={n.path === '/dashboard'}
              style={({ isActive }) => ({
                display: 'flex', alignItems: 'center', gap: 9, padding: '10px', borderRadius: 'var(--radius)', textDecoration: 'none',
                fontSize: 13, fontWeight: isActive ? 600 : 500, color: isActive ? 'var(--accent)' : 'var(--text2)',
                background: isActive ? 'var(--accent-dim)' : 'transparent',
                border: `1px solid ${isActive ? 'rgba(255,123,44,0.18)' : 'transparent'}`,
                transition: 'all 0.12s', userSelect: 'none', whiteSpace: 'nowrap'
              })}
            >
              {({ isActive }) => (
                <>
                  <div style={{ display:'flex', justifyContent:'center', width: 24, flexShrink: 0 }}>
                    <Icon n={n.icon} s={15} c={isActive ? 'var(--accent)' : 'var(--text3)'} />
                  </div>
                  <span className="sidebar-text">{n.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Perfil / Logout */ }
        <div style={{ borderTop: '1px solid var(--border)', padding: '10px 4px 14px', marginTop: 6, cursor: 'pointer' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, padding: '6px 4px', whiteSpace: 'nowrap' }}>
            <div style={{ width: 30, height: 30, borderRadius: '50%', background: 'var(--surface3)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700, flexShrink: 0 }}>
               A
            </div>
            <div className="sidebar-text">
              <div style={{ fontSize: 13, fontWeight: 600 }}>Administrador</div>
            </div>

            <div className="logout-button" onClick={onLogout}>Sair</div>

          </div>
        </div>
      </aside>

      {/* ÁREA PRINCIPAL DA TELA */ }
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        <div style={{ flex: 1, overflowY: 'auto', padding: '22px 28px', paddingBottom: 40 }}>
          <Outlet /> {/* Aqui o React Router vai injetar o Home, Problems, Devices, etc */ }
        </div>
      </main>
    </div>
  );
}