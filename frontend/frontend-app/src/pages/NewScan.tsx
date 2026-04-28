import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Btn } from '../components/ui';
import { Icon } from '../components/icons/Icon';

export default function NewScan() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<'full' | 'quick'>('full');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18, maxWidth: 580, animation: 'fadeIn 0.3s ease' }}>
      <div>
        <h2 style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em' }}>Nova Verificação</h2>
        <p style={{ color: 'var(--text3)', fontSize: 14, marginTop: 4 }}>
          O dispositivo Dmitri irá verificar todos os aparelhos conectados à sua rede e identificar possíveis problemas de segurança.
        </p>
      </div>

      <Card>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Tipo de verificação</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {[
            { id: 'quick' as const, label: 'Verificação Rápida', desc: 'Analisa as principais portas e serviços. Ideal para verificações frequentes. Dura cerca de 1 minuto.', icon: 'scan' as const },
            { id: 'full' as const,  label: 'Verificação Completa', desc: 'Análise detalhada de todos os serviços e versões. Mais precisa. Dura cerca de 5 minutos.', icon: 'shield' as const },
          ].map(m => (
            <div key={m.id} onClick={() => setMode(m.id)}
              style={{ padding: '16px', borderRadius: 'var(--radius)', cursor: 'pointer', border: `2px solid ${mode === m.id ? 'var(--accent)' : 'var(--border)'}`, background: mode === m.id ? 'var(--accent-dim)' : 'var(--surface2)', transition: 'all 0.13s' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <Icon n={m.icon} s={16} c={mode === m.id ? 'var(--accent)' : 'var(--text3)'} />
                <span style={{ fontSize: 14, fontWeight: 700, color: mode === m.id ? 'var(--accent)' : 'var(--text)' }}>{m.label}</span>
                {mode === m.id && <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--accent)' }}>✓ Selecionado</span>}
              </div>
              <p style={{ fontSize: 13, color: 'var(--text3)', lineHeight: 1.5 }}>{m.desc}</p>
            </div>
          ))}
        </div>
      </Card>

      <Card style={{ background: 'var(--accent-dim)', border: '1px solid var(--accent-glow)' }}>
        <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
          <Icon n="info" s={20} c="var(--accent)" style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent)', marginBottom: 4 }}>Como funciona?</div>
            <p style={{ fontSize: 13, color: 'var(--text2)', lineHeight: 1.6 }}>
              O scanner está conectado à sua rede e irá automaticamente identificar todos os aparelhos (computadores, câmeras, roteadores, etc.) e verificar se há configurações inseguras ou vulnerabilidades conhecidas.
            </p>
          </div>
        </div>
      </Card>

      <div style={{ display: 'flex', gap: 12 }}>
        <Btn icon="scan" size="lg" onClick={() => navigate('/dashboard/progress')}>Iniciar Verificação</Btn>
        <Btn variant="secondary" onClick={() => navigate('/dashboard')}>Cancelar</Btn>
      </div>
    </div>
  );
}