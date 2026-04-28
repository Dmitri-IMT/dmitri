import { useState } from 'react';
import { Card, Btn, Field } from '../components/ui';
import { Icon } from '../components/icons/Icon';

export default function Settings() {
  const [apiUrl, setApiUrl] = useState('http://localhost:8000/api/v1');
  const [saved, setSaved]   = useState(false);
  const [showAdv, setShowAdv] = useState(false);

  const save = () => { 
    setSaved(true); 
    setTimeout(() => setSaved(false), 2000); 
  };

  const Toggle = ({ on, onToggle }: { on: boolean, onToggle: () => void }) => (
    <div onClick={onToggle} style={{ width: 40, height: 22, borderRadius: 11, background: on ? 'var(--accent)' : 'var(--surface3)', border: `1px solid ${on ? 'var(--accent)' : 'var(--border2)'}`, cursor: 'pointer', position: 'relative', transition: 'all 0.2s', flexShrink: 0 }}>
      <div style={{ position: 'absolute', top: 2, left: on ? 20 : 2, width: 16, height: 16, borderRadius: '50%', background: on ? 'var(--bg)' : 'var(--text3)', transition: 'left 0.2s' }} />
    </div>
  );

  const [notifs, setNotifs] = useState({ email: true, semanal: true, scan: false });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18, maxWidth: 560, animation: 'fadeIn 0.3s ease' }}>
      <h2 style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em' }}>Configurações</h2>

      <Card>
        <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 14 }}>Notificações</div>
        {(['email', 'semanal', 'scan'] as const).map((key) => {
          const labels = {
            email: { title: 'Alertas por e-mail', sub: 'Receber e-mail quando problemas urgentes forem encontrados' },
            semanal: { title: 'Relatório semanal', sub: 'Resumo semanal da saúde da sua rede por e-mail' },
            scan: { title: 'Notificar ao concluir verificação', sub: 'Receber aviso quando uma verificação terminar' }
          };
          
          return (
            <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 500 }}>{labels[key].title}</div>
                <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>{labels[key].sub}</div>
              </div>
              <Toggle on={notifs[key]} onToggle={() => setNotifs(p => ({ ...p, [key]: !p[key] }))} />
            </div>
          );
        })}
      </Card>

      <Card>
        <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>Sobre o Dispositivo Scanner</div>
        <p style={{ fontSize: 13, color: 'var(--text3)', marginBottom: 14 }}>O hardware do Dmitri está processando as requisições na rede local.</p>
        {[
          ['Versão do Software', '1.0.0'],
          ['Firmware do Agente', '0.2.1'],
          ['Última Sincronização', 'Hoje'],
          ['Status', 'Online e funcionando']
        ].map(([k, v]) => (
          <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
            <span style={{ color: 'var(--text3)' }}>{k}</span>
            <span style={{ color: 'var(--text)', fontWeight: 500 }}>{v}</span>
          </div>
        ))}
      </Card>

      <div>
        <button onClick={() => setShowAdv(!showAdv)}
          style={{ fontSize: 12, color: 'var(--text3)', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'var(--font)', padding: 0 }}>
          <Icon n={showAdv ? 'chevron_d' : 'chevron_r'} s={13} c="var(--text3)" />
          Configurações de Comunicação (Backend FastAPI)
        </button>
        {showAdv && (
          <Card style={{ marginTop: 10 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text3)', marginBottom: 12 }}>Conexão com o Backend</div>
            <Field 
              label="URL da API" 
              value={apiUrl} 
              onChange={setApiUrl} 
              mono 
              hint="Onde a interface React irá buscar os dados do hardware." 
            />
          </Card>
        )}
      </div>

      <div style={{ display: 'flex', gap: 10 }}>
        <Btn onClick={save} icon={saved ? 'check' : undefined}>{saved ? 'Salvo!' : 'Salvar'}</Btn>
        <Btn variant="secondary" size="md">Testar Conexão</Btn>
      </div>
    </div>
  );
}