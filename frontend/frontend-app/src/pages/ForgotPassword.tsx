import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Btn, Field } from '../components/ui';
import { Icon } from '../components/icons/Icon';

export default function ForgotPassword() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState('');

  const submit = async () => {
    if (!email) { 
      setErr('Preencha seu e-mail.'); 
      return; 
    }
    setErr('');
    setLoading(true);

    // TODO: Integração com FastAPI para redefinição de senha
    /*
    try {
      const res = await fetch('http://localhost:8000/api/v1/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      // Mesmo se der erro (ex: e-mail não existe), por segurança, não avisar o usuário
      // para evitar vazamento de dados de quem está cadastrado na plataforma.
      setSent(true);
    } catch (error) {
      setErr('Erro de conexão com o servidor.');
    } finally {
      setLoading(false);
    }
    */

    // Mock temporário
    setTimeout(() => {
      setLoading(false);
      setSent(true);
    }, 1200);
  };

  return (
    <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg)', position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(var(--border) 1px,transparent 1px),linear-gradient(90deg,var(--border) 1px,transparent 1px)', backgroundSize: '48px 48px', opacity: 0.3 }} />
      <div style={{ position: 'absolute', top: '15%', left: '50%', transform: 'translateX(-50%)', width: 700, height: 700, background: 'radial-gradient(circle,rgba(255,123,44,0.05) 0%,transparent 65%)', pointerEvents: 'none' }} />
      
      <div style={{ position: 'relative', width: '100%', maxWidth: 380, margin: '0 20px', animation: 'fadeIn 0.4s ease' }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 60, height: 60, background: 'var(--accent-dim)', border: '1px solid var(--accent-glow)', borderRadius: 16, marginBottom: 16, boxShadow: '0 0 40px var(--accent-glow)' }}>
            <Icon n="lock" s={28} c="var(--accent)" />
          </div>
          <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.02em' }}>Recuperar Senha</h1>
          <p style={{ color: 'var(--text3)', fontSize: 14, marginTop: 4 }}>Enviaremos um link para o seu e-mail</p>
        </div>

        <Card style={{ padding: 28 }}>
          {!sent ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <Field label="E-mail cadastrado" value={email} onChange={setEmail} placeholder="exemplo@email.com" />
              
              {err && <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--urgente)' }}><Icon n="alert" s={14} c="var(--urgente)" />{err}</div>}
              
              <Btn onClick={submit} disabled={loading} style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}>
                {loading ? 'Enviando…' : 'Enviar link de recuperação'}
              </Btn>
            </div>
          ) : (
            <div style={{ textAlign: 'center', animation: 'fadeIn 0.4s ease' }}>
              <div style={{ display: 'inline-flex', alignItems: 'center', justifyItems: 'center', width: 48, height: 48, borderRadius: '50%', background: 'var(--baixo-dim)', border: '1px solid rgba(82,200,160,0.3)', marginBottom: 16 }}>
                <Icon n="check" s={24} c="var(--ok)" />
              </div>
              <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>E-mail enviado!</h3>
              <p style={{ fontSize: 13, color: 'var(--text2)', lineHeight: 1.5 }}>Se o e-mail <strong>{email}</strong> estiver cadastrado em nossa base, você receberá um link para criar uma nova senha em instantes.</p>
            </div>
          )}
        </Card>

        <p style={{ textAlign: 'center', color: 'var(--text3)', fontSize: 13, marginTop: 24 }}>
          Lembrou a senha? <span onClick={() => navigate('/login')} style={{ color: 'var(--accent)', cursor: 'pointer', fontWeight: 600 }}>Voltar para o login</span>
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