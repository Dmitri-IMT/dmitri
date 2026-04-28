import { useState } from 'react';
import { DEVICES, FINDINGS, fmtDate, fmtShort } from '../data/mockData';
import { Card, Btn, Badge } from '../components/ui';
import { Icon } from '../components/icons/Icon';
import type { Device } from '../types';

export default function Devices() {
  const [detail, setDetail] = useState<Device | null>(null);

  if (detail) {
    const devFinds = FINDINGS.filter(f => f.device_id === detail.device_id);
    
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, animation: 'fadeIn 0.25s ease' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Btn variant="ghost" icon="back" size="sm" onClick={() => setDetail(null)}>Minha Rede</Btn>
          <span style={{ color: 'var(--text3)' }}>/</span>
          <span style={{ fontSize: 14, color: 'var(--text2)' }}>{detail.hostname}</span>
          {detail.highest_severity && <Badge sev={detail.highest_severity} />}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 14 }}>
          <Card>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>Informações do Dispositivo</div>
            {[
              ['Nome', detail.hostname],
              ['Endereço IP', detail.ip],
              ['Endereço MAC', detail.mac],
              ['Fabricante', detail.vendor],
              ['Visto pela 1ª vez', fmtShort(detail.first_seen_at)],
              ['Última detecção', fmtDate(detail.last_seen_at)]
            ].map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
                <span style={{ color: 'var(--text3)' }}>{k}</span>
                <span style={{ fontFamily: k.includes('Endereço') || k.includes('IP') ? 'var(--mono)' : 'var(--font)', color: 'var(--text)', maxWidth: '60%', textAlign: 'right' }}>{v}</span>
              </div>
            ))}
          </Card>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Card>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>Portas Abertas ({detail.open_ports_count})</div>
              {detail.ports.filter(p => p.state === 'open').map(p => (
                <div key={p.port} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
                  <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)', fontWeight: 600, minWidth: 50 }}>{p.port}</span>
                  <span style={{ color: 'var(--text2)', flex: 1 }}>{p.service}</span>
                  {p.version && <span style={{ fontSize: 11, color: 'var(--text3)' }}>{p.version}</span>}
                </div>
              ))}
              {detail.open_ports_count === 0 && (
                <div style={{ fontSize: 13, color: 'var(--text3)', fontStyle: 'italic' }}>Nenhuma porta aberta detectada.</div>
              )}
            </Card>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, animation: 'fadeIn 0.3s ease' }}>
      <div>
        <h2 style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em' }}>Minha Rede</h2>
        <p style={{ color: 'var(--text3)', fontSize: 13, marginTop: 2 }}>{DEVICES.length} dispositivos detectados</p>
      </div>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(270px,1fr))', gap: 12 }}>
        {DEVICES.map(d => {
          const nFinds = FINDINGS.filter(f => f.device_id === d.device_id).length;
          return (
            <Card key={d.device_id} onClick={() => setDetail(d)}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 10, background: 'var(--surface3)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <Icon n="devices" s={18} c="var(--text3)" />
                  </div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>{d.hostname}</div>
                    <div style={{ fontSize: 11, color: 'var(--text3)', fontFamily: 'var(--mono)' }}>{d.ip}</div>
                  </div>
                </div>
                {d.highest_severity ? <Badge sev={d.highest_severity} /> : <span style={{ fontSize: 12, color: 'var(--ok)', fontWeight: 600 }}>✓ OK</span>}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 10, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{d.vendor}</div>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: 10, borderTop: '1px solid var(--border)', fontSize: 12 }}>
                <span style={{ color: 'var(--text3)' }}>{d.open_ports_count} portas abertas</span>
                <span style={{ color: nFinds > 0 ? 'var(--urgente)' : 'var(--ok)', fontWeight: 600 }}>
                  {nFinds === 0 ? 'Sem problemas' : `${nFinds} problema${nFinds > 1 ? 's' : ''}`}
                </span>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}