import { useState } from 'react';
import { FINDINGS, DEVICES, SCANS } from '../data/mockData-v2';
import { Card, Btn, Badge } from '../components/ui';
import { Icon } from '../components/icons/Icon';
import type { Severity } from '../types';

const SEV_LABELS: Record<Severity, string> = {
  critical: 'Urgente',
  high:     'Importante',
  medium:   'Médio',
  low:      'Baixo',
};

// Cor do score CVSS
function cvssColor(score: number): string {
  if (score >= 9)   return 'var(--urgente)';
  if (score >= 7)   return 'var(--alto)';
  if (score >= 4)   return 'var(--medio)';
  return 'var(--text3)';
}

export default function Problems() {
  const [search,   setSearch]   = useState('');
  const [sevFilter, setSevFilter] = useState<Severity | 'all'>('all');
  const [expanded, setExpanded] = useState<string | null>(null);

  // Detecta se o scan atual é full
  const latestScan = SCANS[0];
  const isFull = latestScan?.scan_mode === 'full';

  const list = FINDINGS.filter(f => {
    if (sevFilter !== 'all' && f.severity !== sevFilter) return false;
    const dev = DEVICES.find(d => d.device_id === f.device_id);
    if (search) {
      const q = search.toLowerCase();
      const inTitle  = f.title.toLowerCase().includes(q);
      const inHost   = (dev?.hostname ?? '').toLowerCase().includes(q);
      const inCve    = (f.cve_id ?? '').toLowerCase().includes(q);
      if (!inTitle && !inHost && !inCve) return false;
    }
    return true;
  });

  const counts: Record<Severity | 'all', number> = {
    all:      FINDINGS.length,
    critical: FINDINGS.filter(f => f.severity === 'critical').length,
    high:     FINDINGS.filter(f => f.severity === 'high').length,
    medium:   FINDINGS.filter(f => f.severity === 'medium').length,
    low:      FINDINGS.filter(f => f.severity === 'low').length,
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, animation: 'fadeIn 0.3s ease' }}>

      {/* Cabeçalho */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em' }}>Problemas encontrados</h2>
          <p style={{ color: 'var(--text3)', fontSize: 13, marginTop: 2 }}>
            {FINDINGS.length} problemas identificados na última verificação
            {isFull && <span style={{ marginLeft: 8, fontSize: 11, background: 'var(--accent-dim)', color: 'var(--accent)', borderRadius: 4, padding: '2px 7px', fontWeight: 600 }}>Verificação completa</span>}
          </p>
        </div>
        {FINDINGS.length > 0 && <Btn variant="secondary" size="sm">Exportar relatório</Btn>}
      </div>

      {FINDINGS.length === 0 ? (
        <Card style={{ textAlign: 'center', padding: '60px 20px' }}>
          <Icon n="shield" s={48} c="var(--ok)" />
          <h3 style={{ marginTop: 16, fontSize: 18 }}>Nenhuma vulnerabilidade encontrada</h3>
          <p style={{ color: 'var(--text3)', marginTop: 8, fontSize: 14 }}>Sua rede está segura e não apresenta problemas conhecidos no momento.</p>
        </Card>
      ) : (
        <>
          {/* Filtros de severidade */}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {(['all', 'critical', 'high', 'medium', 'low'] as const).map(sev => {
              const active = sevFilter === sev;
              return (
                <button key={sev} onClick={() => setSevFilter(sev)}
                  style={{ fontSize: 12, fontWeight: 600, padding: '5px 12px', borderRadius: 20, border: `1px solid ${active ? 'var(--accent)' : 'var(--border2)'}`, background: active ? 'var(--accent-dim)' : 'var(--surface2)', color: active ? 'var(--accent)' : 'var(--text2)', cursor: 'pointer', fontFamily: 'var(--font)', transition: 'all 0.12s' }}>
                  {sev === 'all' ? 'Todos' : SEV_LABELS[sev]} ({counts[sev]})
                </button>
              );
            })}
          </div>

          {/* Busca */}
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder={isFull ? 'Buscar por problema, dispositivo ou CVE…' : 'Buscar por problema ou dispositivo…'}
            style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', borderRadius: 'var(--radius)', padding: '9px 14px', color: 'var(--text)', fontSize: 13, outline: 'none', fontFamily: 'var(--font)', width: '100%', boxSizing: 'border-box' }}
          />

          {/* Lista */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {list.map(f => {
              const dev    = DEVICES.find(d => d.device_id === f.device_id);
              const isOpen = expanded === f.finding_id;

              return (
                <div key={f.finding_id}>
                  {/* Linha resumo */}
                  <div onClick={() => setExpanded(isOpen ? null : f.finding_id)}
                    style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 18px', background: 'var(--surface)', border: `1px solid ${isOpen ? 'var(--border2)' : 'var(--border)'}`, borderRadius: isOpen ? '12px 12px 0 0' : 'var(--radius-lg)', cursor: 'pointer' }}>

                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span style={{ fontSize: 14, fontWeight: 600 }}>{f.title}</span>
                        {/* CVE badge — só em scan full */}
                        {isFull && f.cve_id && (
                          <a href={`https://nvd.nist.gov/vuln/detail/${f.cve_id}`} target="_blank" rel="noreferrer"
                            onClick={e => e.stopPropagation()}
                            style={{ fontSize: 11, fontFamily: 'var(--mono)', background: 'var(--urgente-dim)', color: 'var(--urgente)', borderRadius: 4, padding: '1px 6px', textDecoration: 'none', fontWeight: 700, flexShrink: 0 }}>
                            {f.cve_id}
                          </a>
                        )}
                        {/* CVSS score — só em scan full */}
                        {isFull && f.cvss_score != null && (
                          <span style={{ fontSize: 11, fontFamily: 'var(--mono)', fontWeight: 700, color: cvssColor(f.cvss_score), flexShrink: 0 }}>
                            CVSS {f.cvss_score.toFixed(1)}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 3 }}>
                        {dev?.hostname || f.device_ip}
                        {/* Script de origem — só em scan full */}
                        {isFull && f.source_scripts?.length && (
                          <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--text3)', fontFamily: 'var(--mono)' }}>
                            via {f.source_scripts.join(', ')}
                          </span>
                        )}
                      </div>
                    </div>

                    <Badge sev={f.severity} />
                    <Icon n={isOpen ? 'chevron_d' : 'chevron_r'} s={15} c="var(--text3)" />
                  </div>

                  {/* Painel expandido */}
                  {isOpen && (
                    <div style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', borderTop: 'none', borderRadius: '0 0 12px 12px', padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>

                      {/* Descrição */}
                      <p style={{ fontSize: 14, color: 'var(--text2)', lineHeight: 1.7, margin: 0 }}>{f.description}</p>

                      {/* Recomendação */}
                      <div style={{ padding: '12px', background: 'var(--surface3)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Recomendação</span>
                        <p style={{ marginTop: 4, fontSize: 13, color: 'var(--text2)', margin: '4px 0 0' }}>{f.recommendation}</p>
                      </div>

                      {/* Evidência técnica — só em scan full */}
                      {isFull && f.evidence && (
                        <div style={{ padding: '12px', background: 'var(--surface3)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Evidência técnica</span>
                          <pre style={{ marginTop: 6, fontSize: 12, color: 'var(--text2)', fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: '6px 0 0' }}>{f.evidence}</pre>
                        </div>
                      )}

                      {/* Rodapé: data + referências */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, paddingTop: 4 }}>
                        <span style={{ fontSize: 11, color: 'var(--text3)' }}>
                          Detectado em {new Date(f.detected_at).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                        </span>
                        {/* Referências — só em scan full */}
                        {isFull && f.references && f.references.length > 0 && (
                          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                            {f.references.map(ref => (
                              <a key={ref} href={ref} target="_blank" rel="noreferrer"
                                style={{ fontSize: 11, color: 'var(--accent)', textDecoration: 'none', fontFamily: 'var(--mono)' }}>
                                {ref.replace('https://vulners.com/cve/', 'vulners/')}
                              </a>
                            ))}
                          </div>
                        )}
                      </div>

                    </div>
                  )}
                </div>
              );
            })}

            {list.length === 0 && (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text3)', fontSize: 14 }}>
                Nenhum problema corresponde aos filtros aplicados.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}