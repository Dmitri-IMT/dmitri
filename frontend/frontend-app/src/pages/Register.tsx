import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Btn, Field } from '../components/ui';
import { Icon } from '../components/icons/Icon';

interface RegisterProps {
  onRegister: () => void;
}

export default function Register({ onRegister }: RegisterProps) {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [pass, setPass] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  const submit = async () => {
    if (!name || !email || !pass) { 
      setErr('Preencha todos os campos.'); 
      return; 
    }
    setErr('');
    setLoading(true);

    // TODO: Integração com FastAPI para criar usuário
    /*
    try {
      const res = await fetch('http://localhost:8000/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password: pass })
      });
      if (!res.ok) throw new Error('Erro ao criar conta');
      
      // Se a API não logar automaticamente após cadastro, navegue pro login
      // ou chame onRegister() para logar direto.
      onRegister();
    } catch (error) {
      setErr('Não foi possível criar a conta. Tente novamente.');
      setLoading(false);
    }
    */

    // Mock temporário: Cadastra e loga direto
    setTimeout(() => {
      setLoading(false);
      onRegister(); 
    }, 1200);
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
          <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.02em' }}>Criar Conta</h1>
          <p style={{ color: 'var(--text3)', fontSize: 14, marginTop: 4 }}>Configure seu acesso ao Dmitri</p>
        </div>

        <Card style={{ padding: 28 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Field label="Nome Completo" value={name} onChange={setName} placeholder="Seu nome" />
            <Field label="E-mail" value={email} onChange={setEmail} placeholder="exemplo@email.com" />
            <Field label="Senha" value={pass} onChange={setPass} type="password" placeholder="••••••••" />
            
            {err && <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--urgente)' }}><Icon n="alert" s={14} c="var(--urgente)" />{err}</div>}
            
            <Btn onClick={submit} disabled={loading} style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}>
              {loading ? 'Criando conta…' : 'Cadastrar'}
            </Btn>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '4px 0' }}>
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
              <span style={{ fontSize: 11, color: 'var(--text3)' }}>OU</span>
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            </div>

            <Btn variant="secondary" style={{ width: '100%', justifyContent: 'center', background: 'white', color: 'black' }} onClick={() => console.log('Cadastro Google')}>
              Cadastrar com Google
            </Btn>
          </div>
        </Card>

        <p style={{ textAlign: 'center', color: 'var(--text3)', fontSize: 13, marginTop: 24 }}>
          Já tem uma conta? <span onClick={() => navigate('/login')} style={{ color: 'var(--accent)', cursor: 'pointer', fontWeight: 600 }}>Faça login</span>
        </p>
      </div>

      <div style={{ display: 'flex', justifyContent: 'center', marginTop: 32 }}>
        <Btn variant="ghost" size="sm" icon="back" onClick={() => navigate('/')}>
          Voltar para o início
        </Btn>
      </div>

    </div>
  );
}