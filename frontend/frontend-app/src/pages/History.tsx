import { useState } from 'react';
import { SCANS, FINDINGS, DEVICES, fmtDate, SEV_ORDER } from '../data/mockData';
import { Card, Btn, Badge } from '../components/ui';
import { Icon } from '../components/icons/Icon';
import type { Scan } from '../types';

export default function History() {
  const [detail, setDetail] = useState<Scan | null>(null);

  if (detail) {
    const finds = FINDINGS.filter(f => f.scan_id === detail.scan_id);
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, animation: 'fadeIn 0.25s ease' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Btn variant="ghost" icon="back" size="sm" onClick={() => setDetail(null)}>Histórico</Btn>
          <span style={{ color: 'var(--text3)' }}>/</span>
          <span style={{ fontSize: 13, color: 'var(--text2)' }}>{fmtDate(detail.timestamp)}</span>
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(130px,1fr))', gap: 10 }}>
          {[
            ['Modo', detail.scan_mode === 'full' ? 'Completa' : 'Rápida'],
            ['Dispositivos', detail.device_count],
            ['Problemas', detail.finding_count],
            ['Duração', `${detail.metadata.elapsed_seconds}s`]
          ].map(([k, v]) => (
            <Card key={k} style={{ padding: '14px 16px' }}>
              <div style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>{k}</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{v}</div>
            </Card>
          ))}
        </div>

        {finds.length > 0 ? (
          <Card>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>Problemas encontrados nesta verificação</div>
            {[...finds].sort((a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity]).map(f => (
              <div key={f.finding_id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', marginBottom: 6, background: 'var(--surface2)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <Badge sev={f.severity} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{f.title}</div>
                  <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 1 }}>
                    {DEVICES.find(d => d.device_id === f.device_id)?.hostname || f.device_ip}
                  </div>
                </div>
              </div>
            ))}
          </Card>
        ) : (
          <Card style={{ textAlign: 'center', padding: '40px 20px' }}>
            <Icon n="check" s={32} c="var(--ok)" />
            <div style={{ fontSize: 16, fontWeight: 600, marginTop: 12 }}>Nenhum problema encontrado</div>
            <div style={{ fontSize: 13, color: 'var(--text3)', marginTop: 4 }}>Esta verificação não retornou nenhuma vulnerabilidade.</div>
          </Card>
        )}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, animation: 'fadeIn 0.3s ease' }}>
      <div>
        <h2 style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em' }}>Histórico de Verificações</h2>
        <p style={{ color: 'var(--text3)', fontSize: 13, marginTop: 2 }}>{SCANS.length} verificações realizadas</p>
      </div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {SCANS.map(s => (
          <div key={s.scan_id} onClick={() => setDetail(s)}
            style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 18px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', cursor: 'pointer', transition: 'all 0.12s' }}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--surface2)'; e.currentTarget.style.borderColor = 'var(--border2)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'var(--surface)'; e.currentTarget.style.borderColor = 'var(--border)' }}>
            
            <div style={{ width: 40, height: 40, borderRadius: 10, background: s.status === 'completed' ? 'var(--baixo-dim)' : s.status === 'failed' ? 'var(--urgente-dim)' : 'var(--surface3)', border: `1px solid ${s.status === 'completed' ? 'rgba(82,200,160,0.2)' : s.status === 'failed' ? 'rgba(255,68,68,0.2)' : 'var(--border)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <Icon n={s.status === 'completed' ? 'check' : s.status === 'failed' ? 'alert' : 'scan'} s={18} c={s.status === 'completed' ? 'var(--ok)' : s.status === 'failed' ? 'var(--urgente)' : 'var(--text3)'} />
            </div>
            
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{s.scan_mode === 'full' ? 'Verificação Completa' : 'Verificação Rápida'} · {s.subnet}</div>
              <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>{fmtDate(s.timestamp)} · {s.metadata.elapsed_seconds}s</div>
            </div>
            
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              {s.finding_count > 0 ? (
                <span style={{ fontSize: 12, color: 'var(--alto)', fontWeight: 600 }}>{s.finding_count} problema{s.finding_count > 1 ? 's' : ''}</span>
              ) : (
                <span style={{ fontSize: 12, color: 'var(--ok)', fontWeight: 600 }}>Limpo</span>
              )}
              <Icon n="chevron_r" s={14} c="var(--text3)" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}