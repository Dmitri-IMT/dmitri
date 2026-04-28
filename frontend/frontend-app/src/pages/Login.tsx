import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Btn, Field } from '../components/ui';
import { Icon } from '../components/icons/Icon';

interface LoginProps {
  onLogin: () => void;
}

export default function Login({ onLogin }: LoginProps) {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [pass, setPass] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  const submit = async () => {
    if (!email || !pass) { 
      setErr('Preencha e-mail e senha.'); 
      return; 
    }
    setErr('');
    setLoading(true);

    // TODO: Integração com FastAPI
    /*
    try {
      const res = await fetch('http://localhost:8000/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password: pass })
      });
      if (!res.ok) throw new Error('Credenciais inválidas');
      const data = await res.json();
      // Salvar token (ex: sessionStorage.setItem('token', data.access_token))
      onLogin();
    } catch (error) {
      setErr('E-mail ou senha incorretos.');
      setLoading(false);
    }
    */

    // Mock temporário
    setTimeout(() => {
      setLoading(false);
      if (email === 'admin' && pass === 'admin') {
        onLogin();
      } else {
        setErr('Acesso negado. (Dica: use admin / admin)');
      }
    }, 1000);
  };

  return (
    <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg)', position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(var(--border) 1px,transparent 1px),linear-gradient(90deg,var(--border) 1px,transparent 1px)', backgroundSize: '48px 48px', opacity: 0.3 }} />
      <div style={{ position: 'absolute', top: '15%', left: '50%', transform: 'translateX(-50%)', width: 700, height: 700, background: 'radial-gradient(circle,rgba(255,123,44,0.05) 0%,transparent 65%)', pointerEvents: 'none' }} />
      
      <div style={{ position: 'relative', width: '100%', maxWidth: 380, margin: '0 20px', animation: 'fadeIn 0.4s ease' }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 60, height: 60, background: 'var(--accent-dim)', border: '1px solid var(--accent-glow)', borderRadius: 16, marginBottom: 16, boxShadow: '0 0 40px var(--accent-glow)' }}>
            <Icon n="shield" s={28} c="var(--accent)" />
          </div>
          <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.02em' }}>Dmitri</h1>
          <p style={{ color: 'var(--text3)', fontSize: 14, marginTop: 4 }}>Acesse o painel do seu scanner</p>
        </div>

        <Card style={{ padding: 28 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Field label="E-mail ou Usuário" value={email} onChange={setEmail} placeholder="admin" />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label style={{ fontSize: 12, color: 'var(--text2)', fontWeight: 600 }}>Senha</label>
                <span onClick={() => navigate('/forgot-password')} style={{ fontSize: 11, color: 'var(--accent)', cursor: 'pointer' }}>Esqueceu a senha?</span>
              </div>
              <input 
                type="password" 
                value={pass} 
                onChange={e => setPass(e.target.value)} 
                placeholder="••••••••"
                style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', borderRadius: 'var(--radius)', padding: '10px 14px', color: 'var(--text)', fontSize: 14, outline: 'none', fontFamily: 'var(--font)' }}
                onFocus={e => e.target.style.borderColor = 'var(--accent)'}
                onBlur={e => e.target.style.borderColor = 'var(--border2)'}
              />
            </div>
            
            {err && <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--urgente)' }}><Icon n="alert" s={14} c="var(--urgente)" />{err}</div>}
            
            <Btn onClick={submit} disabled={loading} icon={loading ? undefined : 'lock'} style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}>
              {loading ? 'Entrando…' : 'Entrar'}
            </Btn>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '4px 0' }}>
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
              <span style={{ fontSize: 11, color: 'var(--text3)' }}>OU</span>
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            </div>

            <Btn variant="secondary" style={{ width: '100%', justifyContent: 'center', background: 'white', color: 'black' }} onClick={() => alert("Funcionalidade ainda não implementada.")}>
              Continuar com Google
            </Btn>
          </div>
        </Card>

        <p style={{ textAlign: 'center', color: 'var(--text3)', fontSize: 13, marginTop: 24 }}>
          Não tem uma conta? <span onClick={() => navigate('/register')} style={{ color: 'var(--accent)', cursor: 'pointer', fontWeight: 600 }}>Cadastre-se</span>
        </p>

        <div style={{ display: 'flex', justifyContent: 'center', marginTop: 32 }}>
          <Btn variant="ghost" size="sm" icon="back" onClick={() => navigate('/')}>
            Voltar para o início
          </Btn>
        </div>

      </div>
    </div>
  );
}