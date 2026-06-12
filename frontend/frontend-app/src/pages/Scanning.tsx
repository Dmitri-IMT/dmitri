import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Btn, Badge } from '../components/ui';
import type { Severity } from '../types';

export default function Scanning() {
  const navigate = useNavigate();
  const [progress, setProgress] = useState(0);
  const [stage, setStage]       = useState(0);
  const [done, setDone]         = useState(false);
  const [devices, setDevices]   = useState<{name: string, ip: string, sev: Severity | null}[]>([]);
  
  const STAGES = ['Procurando dispositivos', 'Analisando portas', 'Identificando serviços', 'Verificando problemas', 'Concluindo'];

  // IPs e Nomes baseados no seu payload real para dar uma sensação mais realista durante a simulação
  const SIMULATED_DEVICES = [
    { name: '192.168.1.1',   ip: '192.168.1.1',   sev: null },
    { name: '192.168.1.100', ip: '192.168.1.100', sev: null },
    { name: '192.168.1.103', ip: '192.168.1.103', sev: null },
    { name: '192.168.1.143', ip: '192.168.1.143', sev: null },
  ] as const;

  useEffect(() => {
    let i = 0;
    const iv = setInterval(() => {
      if (i >= 32) { clearInterval(iv); setDone(true); return; }
      i++;
      setProgress(Math.round((i / 32) * 100));
      setStage(Math.min(4, Math.floor((i / 32) * 5)));
      
      if (i % 8 === 0 && (i / 8) - 1 < SIMULATED_DEVICES.length) {
        setDevices(prev => [...prev, SIMULATED_DEVICES[(i / 8) - 1]]);
      }
    }, 200); // 200ms * 32 = ~6.4 segundos de simulação
    return () => clearInterval(iv);
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, animation: 'fadeIn 0.3s ease' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em' }}>{done ? 'Verificação concluída' : 'Verificando sua rede…'}</h2>
          <p style={{ color: 'var(--text3)', fontSize: 13, marginTop: 2 }}>Rede: 192.168.1.0/24</p>
        </div>
        {done && <Btn icon="alert" onClick={() => navigate('/dashboard/problems')}>Ver Resultados</Btn>}
      </div>

      <Card>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
          {STAGES.map((s, i) => (
            <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 22, height: 22, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, transition: 'all 0.3s', background: i < stage ? 'var(--ok)' : i === stage ? 'var(--accent)' : 'var(--surface3)', border: `1px solid ${i < stage ? 'var(--ok)' : i === stage ? 'var(--accent)' : 'var(--border)'}`, color: i <= stage ? 'var(--bg)' : 'var(--text3)' }}>
                {i < stage ? '✓' : i + 1}
              </div>
              <span style={{ fontSize: 12, color: i === stage ? 'var(--accent)' : i < stage ? 'var(--text2)' : 'var(--text3)', fontWeight: i === stage ? 600 : 400, whiteSpace: 'nowrap' }}>{s}</span>
              {i < STAGES.length - 1 && <div style={{ width: 16, height: 1, background: i < stage ? 'var(--ok)' : 'var(--border)', transition: 'background 0.3s' }} />}
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
          <span style={{ fontSize: 14, color: 'var(--text2)', fontWeight: 500 }}>{done ? 'Verificação finalizada!' : STAGES[stage] + '…'}</span>
          <span style={{ fontSize: 14, fontWeight: 700, color: done ? 'var(--ok)' : 'var(--accent)' }}>{progress}%</span>
        </div>
        <div style={{ height: 8, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
          <div style={{ width: `${progress}%`, height: '100%', background: done ? 'var(--ok)' : 'var(--accent)', borderRadius: 4, transition: 'width 0.2s linear', boxShadow: done ? '0 0 12px var(--ok)' : '0 0 12px var(--accent)' }} />
        </div>
      </Card>

      <Card>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Dispositivos encontrados</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {devices.map((d, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 10px', background: 'var(--surface2)', borderRadius: 'var(--radius)', border: '1px solid var(--border)', animation: 'fadeIn 0.3s ease' }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: d.sev ? 'var(--urgente)' : 'var(--ok)', flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{d.name}</div>
                <div style={{ fontSize: 11, color: 'var(--text3)', fontFamily: 'var(--mono)' }}>{d.ip}</div>
              </div>
              {d.sev ? <Badge sev={d.sev} /> : <span style={{ fontSize: 12, color: 'var(--ok)', fontWeight: 600 }}>✓ Limpo</span>}
            </div>
          ))}
          {!done && <div style={{ color: 'var(--text3)', fontSize: 12, padding: '6px 10px', animation: 'blink 1s infinite' }}>Procurando mais dispositivos…</div>}
        </div>
      </Card>
    </div>
  );
}
