import { useState } from 'react';
import { SCANS, FINDINGS, DEVICES, fmtDate, SEV_ORDER, shortId } from '../data/mockData-v2';
import { Card, Btn, Badge } from '../components/ui';
import { Icon } from '../components/icons/Icon';
import type { Scan } from '../types';

export default function History() {
  const [detail,   setDetail]   = useState<Scan | null>(null);
  const [showArgs, setShowArgs] = useState(false);

  if (detail) {
    const finds  = FINDINGS.filter(f => f.scan_id === detail.scan_id);
    const isFull = detail.scan_mode === 'full';

    // Contagem por severidade
    const sevCounts = {
      critical: finds.filter(f => f.severity === 'critical').length,
      high:     finds.filter(f => f.severity === 'high').length,
      medium:   finds.filter(f => f.severity === 'medium').length,
      low:      finds.filter(f => f.severity === 'low').length,
    };

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, animation: 'fadeIn 0.25s ease' }}>

        {/* Breadcrumb */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Btn variant="ghost" icon="back" size="sm" onClick={() => { setDetail(null); setShowArgs(false); }}>Histórico</Btn>
          <span style={{ color: 'var(--text3)' }}>/</span>
          <span style={{ fontSize: 13, color: 'var(--text2)' }}>{fmtDate(detail.timestamp)}</span>
          {detail.highest_severity && <Badge sev={detail.highest_severity} />}
        </div>

        {/* Cards resumo */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(130px,1fr))', gap: 10 }}>
          {([
            ['Modo',        detail.scan_mode === 'full' ? 'Completa' : 'Rápida'],
            ['Dispositivos', detail.device_count],
            ['Problemas',    detail.finding_count],
            ['Duração',      `${detail.metadata.elapsed_seconds}s`],
          ] as [string, string | number][]).map(([k, v]) => (
            <Card key={k} style={{ padding: '14px 16px' }}>
              <div style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>{k}</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{v}</div>
            </Card>
          ))}
        </div>

        {/* Breakdown por severidade — só em scan full e quando há findings */}
        {isFull && finds.length > 0 && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {(['critical', 'high', 'medium', 'low'] as const).map(sev => {
              const n = sevCounts[sev];
              if (n === 0) return null;
              return (
                <div key={sev} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 20, fontSize: 12 }}>
                  <Badge sev={sev} />
                  <span style={{ fontWeight: 600, color: 'var(--text2)' }}>{n}</span>
                </div>
              );
            })}
          </div>
        )}

        {/* Metadados técnicos — só em scan full */}
        {isFull && (
          <Card style={{ padding: '14px 18px' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
              Detalhes técnicos
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {([
                ['ID do scan',       shortId(detail.scan_id) + '…'],
                ['Agente',           detail.metadata.agent_version],
                ['Sub-rede',         detail.subnet],
              ] as [string, string][]).map(([k, v]) => (
                <div key={k} style={{ display: 'flex', gap: 12, fontSize: 13 }}>
                  <span style={{ color: 'var(--text3)', minWidth: 110, flexShrink: 0 }}>{k}</span>
                  <span style={{ color: 'var(--text2)', fontFamily: 'var(--mono)', fontSize: 12 }} title={k === 'ID do scan' ? detail.scan_id : undefined}>{v}</span>
                </div>
              ))}
              {/* Argumentos nmap — colapsáveis */}
              <div style={{ fontSize: 13 }}>
                <button onClick={() => setShowArgs(p => !p)}
                  style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: 'var(--text3)', fontFamily: 'var(--font)', fontSize: 13, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Icon n={showArgs ? 'chevron_d' : 'chevron_r'} s={12} c="var(--text3)" />
                  Argumentos nmap
                </button>
                {showArgs && (
                  <pre style={{ marginTop: 6, fontSize: 11, color: 'var(--text2)', fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap', wordBreak: 'break-all', background: 'var(--surface3)', borderRadius: 6, padding: '8px 10px', border: '1px solid var(--border)' }}>
                    {detail.metadata.nmap_arguments}
                  </pre>
                )}
              </div>
            </div>
          </Card>
        )}

        {/* Lista de findings */}
        {finds.length > 0 ? (
          <Card>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>Problemas encontrados nesta verificação</div>
            {[...finds].sort((a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity]).map(f => (
              <div key={f.finding_id}
                style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', marginBottom: 6, background: 'var(--surface2)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <Badge sev={f.severity} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.title}</span>
                    {/* CVE inline — só em scan full */}
                    {isFull && f.cve_id && (
                      <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--urgente)', flexShrink: 0 }}>
                        {f.cve_id}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 1 }}>
                    {DEVICES.find(d => d.device_id === f.device_id)?.hostname || f.device_ip}
                  </div>
                </div>
                {/* CVSS score — só em scan full */}
                {isFull && f.cvss_score != null && (
                  <span style={{ fontSize: 11, fontFamily: 'var(--mono)', fontWeight: 700, color: 'var(--text3)', flexShrink: 0 }}>
                    {f.cvss_score.toFixed(1)}
                  </span>
                )}
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

  // ── Listagem de scans ───────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, animation: 'fadeIn 0.3s ease' }}>
      <div>
        <h2 style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em' }}>Histórico de Verificações</h2>
        <p style={{ color: 'var(--text3)', fontSize: 13, marginTop: 2 }}>{SCANS.length} verificação{SCANS.length !== 1 ? 'ões' : ''} realizada{SCANS.length !== 1 ? 's' : ''}</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {SCANS.map(s => {
          const isFull = s.scan_mode === 'full';
          return (
            <div key={s.scan_id} onClick={() => setDetail(s)}
              style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 18px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', cursor: 'pointer', transition: 'all 0.12s' }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--surface2)'; e.currentTarget.style.borderColor = 'var(--border2)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'var(--surface)';  e.currentTarget.style.borderColor = 'var(--border)'; }}>

              {/* Ícone de status */}
              <div style={{ width: 40, height: 40, borderRadius: 10, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: s.status === 'completed' ? 'var(--baixo-dim)' : s.status === 'failed' ? 'var(--urgente-dim)' : 'var(--surface3)',
                border: `1px solid ${s.status === 'completed' ? 'rgba(82,200,160,0.2)' : s.status === 'failed' ? 'rgba(255,68,68,0.2)' : 'var(--border)'}` }}>
                <Icon n={s.status === 'completed' ? 'check' : s.status === 'failed' ? 'alert' : 'scan'} s={18}
                  c={s.status === 'completed' ? 'var(--ok)' : s.status === 'failed' ? 'var(--urgente)' : 'var(--text3)'} />
              </div>

              {/* Texto principal */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  {isFull ? 'Verificação Completa' : 'Verificação Rápida'}
                  <span style={{ color: 'var(--text3)', fontWeight: 400 }}>·</span>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--text2)' }}>{s.subnet}</span>
                  {/* Agente — só em scan full */}
                  {isFull && (
                    <span style={{ fontSize: 11, color: 'var(--text3)', fontFamily: 'var(--mono)' }}>v{s.metadata.agent_version}</span>
                  )}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>
                  {fmtDate(s.timestamp)} · {s.metadata.elapsed_seconds}s · {s.device_count} dispositivo{s.device_count !== 1 ? 's' : ''}
                </div>
              </div>

              {/* Severidade + contagem */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                {s.highest_severity && <Badge sev={s.highest_severity} />}
                {s.finding_count > 0 ? (
                  <span style={{ fontSize: 12, color: 'var(--alto)', fontWeight: 600 }}>
                    {s.finding_count} problema{s.finding_count > 1 ? 's' : ''}
                  </span>
                ) : (
                  <span style={{ fontSize: 12, color: 'var(--ok)', fontWeight: 600 }}>Limpo</span>
                )}
                <Icon n="chevron_r" s={14} c="var(--text3)" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}