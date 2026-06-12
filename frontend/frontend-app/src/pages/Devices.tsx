import { useState } from 'react';
import { DEVICES, FINDINGS, SCANS, fmtDate, /*fmtShort,*/ timeAgo } from '../data/mockData-v2';
import { Card, Btn, Badge } from '../components/ui';
import { Icon } from '../components/icons/Icon';
import type { Device } from '../types';

// Mapa de cores por estado da porta
const PORT_STATE_COLOR: Record<string, string> = {
  open:     'var(--ok)',
  filtered: 'var(--alto)',
  closed:   'var(--text3)',
};

export default function Devices() {
  const [detail, setDetail] = useState<Device | null>(null);

  // Detecta se o scan atual é full
  const latestScan = SCANS[0];
  const isFull = latestScan?.scan_mode === 'full';

  if (detail) {
    const devFindings = FINDINGS.filter(f => f.device_id === detail.device_id);
    // Em scan full mostra todas as portas com seu estado; em quick só as abertas
    const portsToShow = isFull
      ? detail.ports
      : detail.ports.filter(p => p.state === 'open');

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, animation: 'fadeIn 0.25s ease' }}>

        {/* Breadcrumb */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Btn variant="ghost" icon="back" size="sm" onClick={() => setDetail(null)}>Minha Rede</Btn>
          <span style={{ color: 'var(--text3)' }}>/</span>
          <span style={{ fontSize: 14, color: 'var(--text2)' }}>{detail.hostname}</span>
          {detail.highest_severity && <Badge sev={detail.highest_severity} />}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 14 }}>

          {/* Informações do dispositivo */}
          <Card>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>
              Informações do Dispositivo
            </div>
            {([
              ['Nome',             detail.hostname],
              ['Endereço IP',      detail.ip],
              ['Endereço MAC',     detail.mac || '—'],
              ['Fabricante',       detail.vendor || '—'],
              ['1ª detecção',      fmtDate(detail.first_seen_at)],
              ['Última detecção',  `${fmtDate(detail.last_seen_at)} (${timeAgo(detail.last_seen_at)})`],
            ] as [string, string][]).map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)', fontSize: 13, gap: 12 }}>
                <span style={{ color: 'var(--text3)', flexShrink: 0 }}>{k}</span>
                <span
                  title={v}
                  style={{
                    fontFamily: (k.includes('Endereço') || k.includes('IP')) ? 'var(--mono)' : 'var(--font)',
                    color: 'var(--text)',
                    maxWidth: '60%',
                    textAlign: 'right',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}>
                  {v}
                </span>
              </div>
            ))}
          </Card>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

            {/* Portas */}
            <Card>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
                Portas {isFull ? `detectadas (${detail.ports.length})` : `abertas (${detail.open_ports_count})`}
              </div>

              {portsToShow.length === 0 ? (
                <div style={{ fontSize: 13, color: 'var(--text3)', fontStyle: 'italic' }}>Nenhuma porta detectada.</div>
              ) : (
                portsToShow.map(p => (
                  <div key={`${p.port}-${p.protocol}`}
                    style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
                    {/* Número da porta */}
                    <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)', fontWeight: 600, minWidth: 44 }}>{p.port}</span>
                    {/* Serviço */}
                    <span style={{ color: 'var(--text2)', flex: 1 }}>{p.service}</span>
                    {/* Versão */}
                    {p.version && (
                      <span style={{ fontSize: 11, color: 'var(--text3)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={p.version}>
                        {p.version}
                      </span>
                    )}
                    {/* Estado — só em scan full, e só se não for 'open' (open é o default esperado) */}
                    {isFull && p.state !== 'open' && (
                      <span style={{ fontSize: 11, fontWeight: 600, color: PORT_STATE_COLOR[p.state] ?? 'var(--text3)', flexShrink: 0 }}>
                        {p.state}
                      </span>
                    )}
                  </div>
                ))
              )}
            </Card>

            {/* Problemas encontrados neste dispositivo */}
            {devFindings.length > 0 && (
              <Card>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
                  Problemas neste dispositivo ({devFindings.length})
                </div>
                {devFindings.slice(0, 5).map(f => (
                  <div key={f.finding_id}
                    style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
                    <Badge sev={f.severity} />
                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={f.title}>
                      {f.title}
                    </span>
                    {/* CVE inline — só em scan full */}
                    {isFull && f.cve_id && (
                      <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--urgente)', flexShrink: 0 }}>
                        {f.cve_id}
                      </span>
                    )}
                  </div>
                ))}
                {devFindings.length > 5 && (
                  <div style={{ fontSize: 12, color: 'var(--text3)', paddingTop: 8 }}>
                    + {devFindings.length - 5} problema{devFindings.length - 5 > 1 ? 's' : ''} — veja em "Problemas encontrados"
                  </div>
                )}
              </Card>
            )}

          </div>
        </div>
      </div>
    );
  }

  // ── Listagem ────────────────────────────────────────────────────────────
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
                {d.highest_severity
                  ? <Badge sev={d.highest_severity} />
                  : <span style={{ fontSize: 12, color: 'var(--ok)', fontWeight: 600 }}>✓ OK</span>}
              </div>

              {/* Vendor com tooltip nativo para texto longo */}
              <div
                title={d.vendor}
                style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 10, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {d.vendor || 'Fabricante desconhecido'}
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: 10, borderTop: '1px solid var(--border)', fontSize: 12 }}>
                <span style={{ color: 'var(--text3)' }}>{d.open_ports_count} porta{d.open_ports_count !== 1 ? 's' : ''} aberta{d.open_ports_count !== 1 ? 's' : ''}</span>
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