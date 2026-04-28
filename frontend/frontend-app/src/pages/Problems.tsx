import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FINDINGS, DEVICES } from '../data/mockData';
import { Card, Btn, Badge } from '../components/ui';
import { Icon } from '../components/icons/Icon';
import type { Severity } from '../types';

export default function Problems() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Severity | 'all'>('all');
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);

  const list = FINDINGS.filter(f => {
    if (filter !== 'all' && f.severity !== filter) return false;
    const dev = DEVICES.find(d => d.device_id === f.device_id);
    if (search && !f.title.toLowerCase().includes(search.toLowerCase()) && !(dev?.hostname || '').toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, animation: 'fadeIn 0.3s ease' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em' }}>Problemas encontrados</h2>
          <p style={{ color: 'var(--text3)', fontSize: 13, marginTop: 2 }}>{FINDINGS.length} problemas identificados na última verificação</p>
        </div>
        {FINDINGS.length > 0 && <Btn variant="secondary" size="sm">Exportar relatório</Btn>}
      </div>

      {FINDINGS.length === 0 ? (
        <Card style={{ textAlign: 'center', padding: '60px 20px' }}>
          <Icon n="shield" s={48} c="var(--ok)" />
          <h3 style={{ marginTop: 16, fontSize: 18 }}>Nenhuma vulnerabilidade encontrada</h3>
          <p style={{ color: 'var(--text3)', marginTop: 8, fontSize: 14 }}>Sua rede está segura e não apresenta problemas de segurança conhecidos no momento.</p>
        </Card>
      ) : (
        <>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <input 
              value={search} 
              onChange={e => setSearch(e.target.value)} 
              placeholder="Buscar por problema ou dispositivo…"
              style={{ flex: 1, minWidth: 200, background: 'var(--surface2)', border: '1px solid var(--border2)', borderRadius: 'var(--radius)', padding: '9px 14px', color: 'var(--text)', fontSize: 13, outline: 'none', fontFamily: 'var(--font)' }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {list.map(f => {
              const dev = DEVICES.find(d => d.device_id === f.device_id);
              const isOpen = expanded === f.finding_id;
              
              return (
                <div key={f.finding_id}>
                  <div onClick={() => setExpanded(isOpen ? null : f.finding_id)}
                    style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 18px', background: 'var(--surface)', border: `1px solid ${isOpen ? 'var(--border2)' : 'var(--border)'}`, borderRadius: isOpen ? '12px 12px 0 0' : 'var(--radius-lg)', cursor: 'pointer' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>{f.title}</div>
                      <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>{dev?.hostname || f.device_ip}</div>
                    </div>
                    <Badge sev={f.severity} />
                    <Icon n={isOpen ? 'chevron_d' : 'chevron_r'} s={15} c="var(--text3)" />
                  </div>
                  {isOpen && (
                    <div style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', borderTop: 'none', borderRadius: '0 0 12px 12px', padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: 16 }}>
                      <p style={{ fontSize: 14, color: 'var(--text2)', lineHeight: 1.7 }}>{f.description}</p>
                      <div style={{ padding: '12px', background: 'var(--surface3)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase' }}>Recomendação</span>
                        <p style={{ marginTop: 4, fontSize: 13, color: 'var(--text2)' }}>{f.recommendation}</p>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}