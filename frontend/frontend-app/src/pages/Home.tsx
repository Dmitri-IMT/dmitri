import { useNavigate } from 'react-router-dom';
import { SCANS, DEVICES, FINDINGS, timeAgo, fmtDate } from '../data/mockData';
import { Card, Btn, Badge } from '../components/ui';
import { Icon } from '../components/icons/Icon';

export default function Home() {
  const navigate = useNavigate();
  const latest = SCANS[0];
  const finds = FINDINGS.filter(f => f.scan_id === latest?.scan_id);
  const urgente = finds.filter(f => f.severity === 'critical').length;
  const importante = finds.filter(f => f.severity === 'high').length;
  const total = finds.length;

  const netStatus = urgente > 0 ? 'danger' : importante > 0 ? 'warning' : 'safe';
  
  const statusMap = {
    danger:  { label: 'Atenção urgente necessária', sub: 'Foram encontrados problemas críticos na sua rede.', color: 'var(--urgente)', bg: 'var(--urgente-dim)', icon: 'alert' as const },
    warning: { label: 'Sua rede tem pontos de melhoria', sub: 'Há problemas importantes que devem ser resolvidos em breve.', color: 'var(--alto)', bg: 'var(--alto-dim)', icon: 'alert' as const },
    safe:    { label: 'Sua rede está segura', sub: 'Nenhum problema crítico encontrado na última verificação.', color: 'var(--ok)', bg: 'var(--baixo-dim)', icon: 'shield' as const },
  };
  const st = statusMap[netStatus];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22, animation: 'fadeIn 0.35s ease' }}>
      {/* Banner de Status Principal */}
      <div style={{ background: `linear-gradient(135deg, ${st.bg} 0%, var(--surface) 100%)`, border: `1px solid ${st.color}33`, borderRadius: 'var(--radius-lg)', padding: '28px 24px', display: 'flex', alignItems: 'center', gap: 20 }}>
        <div style={{ width: 60, height: 60, borderRadius: '50%', background: st.bg, border: `2px solid ${st.color}44`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <Icon n={st.icon} s={28} c={st.color} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: st.color, letterSpacing: '-0.01em' }}>{st.label}</div>
          <div style={{ fontSize: 14, color: 'var(--text2)', marginTop: 4 }}>{st.sub}</div>
          {latest && (
            <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 6 }}>
              Última verificação: <strong style={{ color: 'var(--text2)' }}>{timeAgo(latest.timestamp)}</strong> · {fmtDate(latest.timestamp)}
            </div>
          )}
        </div>
        <Btn icon="scan" size="lg" onClick={() => navigate('/dashboard/scan')}>Verificar agora</Btn>
      </div>

      {/* Cards de Resumo */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 12 }}>
        {[
          { label: 'Dispositivos na rede', value: DEVICES.length, icon: 'network' as const, sub: 'computadores, câmeras, impressoras…', color: 'var(--text)' },
          { label: 'Problemas urgentes', value: urgente, icon: 'alert' as const, sub: urgente === 0 ? 'Nenhum encontrado' : 'Requerem ação imediata', color: urgente > 0 ? 'var(--urgente)' : 'var(--ok)' },
          { label: 'Problemas importantes', value: importante, icon: 'alert' as const, sub: importante === 0 ? 'Nenhum encontrado' : 'Devem ser resolvidos logo', color: importante > 0 ? 'var(--alto)' : 'var(--ok)' },
          { label: 'Total de problemas', value: total, icon: 'history' as const, sub: 'em todos os dispositivos', color: 'var(--text)' },
        ].map(({ label, value, icon, sub, color }) => (
          <Card key={label} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 13, color: 'var(--text2)', fontWeight: 500 }}>{label}</span>
              <Icon n={icon} s={15} c="var(--text3)" />
            </div>
            <div style={{ fontSize: 32, fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1, color }}>{value}</div>
            <div style={{ fontSize: 12, color: 'var(--text3)' }}>{sub}</div>
          </Card>
        ))}
      </div>

      {/* Lista Rápida de Dispositivos */}
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div style={{ fontSize: 16, fontWeight: 700 }}>Dispositivos na rede</div>
          <Btn variant="ghost" size="sm" onClick={() => navigate('/dashboard/devices')}>Ver todos →</Btn>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: 10 }}>
          {DEVICES.slice(0, 6).map(d => (
            <div key={d.device_id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', background: 'var(--surface2)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
              <div style={{ width: 36, height: 36, borderRadius: 8, background: 'var(--surface3)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <Icon n="devices" s={16} c="var(--text3)" />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{d.hostname}</div>
                <div style={{ fontSize: 11, color: 'var(--text3)' }}>{d.ip}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Detalhes da Última Verificação */}
      {latest && (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <Card style={{ flex: 1, minWidth: 200, padding: '14px 18px' }}>
            <div style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 4 }}>Última verificação</div>
            <div style={{ fontSize: 15, fontWeight: 600 }}>{fmtDate(latest.timestamp)}</div>
            <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>Modo: {latest.scan_mode === 'full' ? 'Completa' : 'Rápida'} · {latest.metadata.elapsed_seconds}s</div>
          </Card>
          <Card style={{ flex: 1, minWidth: 200, padding: '14px 18px' }}>
            <div style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 4 }}>Sub-rede verificada</div>
            <div style={{ fontSize: 15, fontWeight: 600, fontFamily: 'var(--mono)' }}>{latest.subnet}</div>
            <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>{latest.device_count} dispositivos encontrados</div>
          </Card>
          <Btn icon="scan" size="lg" onClick={() => navigate('/dashboard/scan')} style={{ alignSelf: 'stretch', flexShrink: 0 }}>
            Nova Verificação
          </Btn>
        </div>
      )}
    </div>
  );
}