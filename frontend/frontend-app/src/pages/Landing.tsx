import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Btn } from '../components/ui';
import { Icon } from '../components/icons/Icon';

// --- Componente do Fundo Animado (Canvas) ---
function NetworkBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let particles: Particle[] = [];
    let animationFrameId: number;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = Math.max(window.innerHeight, document.documentElement.scrollHeight);
    };

    window.addEventListener('resize', resize);
    resize();

    class Particle {
      x: number;
      y: number;
      vx: number;
      vy: number;
      size: number;

      constructor() {
        this.x = Math.random() * canvas!.width;
        this.y = Math.random() * canvas!.height;
        this.vx = Math.random() * 0.5 - 0.25;
        this.vy = Math.random() * 0.5 - 0.25;
        this.size = 2;
      }

      move() {
        this.x += this.vx;
        this.y += this.vy;
        if (this.x < 0 || this.x > canvas!.width) this.vx *= -1;
        if (this.y < 0 || this.y > canvas!.height) this.vy *= -1;
      }

      draw() {
        if (!ctx) return;
        ctx.fillStyle = "#ff7b2c";
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    const connectParticles = () => {
      for (let i = 0; i < particles.length; i++) {
        for (let j = i; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          if (distance < 120) {
            const opacity = 1 - (distance / 120);
            ctx.strokeStyle = `rgba(255, 123, 44, ${opacity * 0.15})`; 
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }
    };

    const init = () => {
      particles = [];
      const particleCount = Math.floor(window.innerWidth / 15);
      for (let i = 0; i < particleCount; i++) {
        particles.push(new Particle());
      }
    };

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach(p => {
        p.move();
        p.draw();
      });
      connectParticles();
      animationFrameId = requestAnimationFrame(animate);
    };

    init();
    animate();

    // Re-inicia o canvas se rolar muito a página para garantir cobertura
    const handleScroll = () => {
       if (canvas.height < document.documentElement.scrollHeight) {
           resize();
       }
    };
    window.addEventListener('scroll', handleScroll, true);

    return () => {
      window.removeEventListener('resize', resize);
      window.removeEventListener('scroll', handleScroll, true);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas 
      ref={canvasRef} 
      style={{ position: 'absolute', top: 0, left: 0, zIndex: 0, pointerEvents: 'none' }} 
    />
  );
}

// --- Componente Principal da Página ---
export default function Landing() {
  const navigate = useNavigate();

  return (
    <div style={{ height: '100vh', background: 'var(--bg)', color: 'var(--text)', display: 'flex', flexDirection: 'column', overflowX: 'hidden', overflowY: 'auto', position: 'relative' }}>
      
      <NetworkBackground />

      <div style={{ position: 'absolute', inset: 0, zIndex: 1, backgroundImage: 'linear-gradient(var(--border) 1px,transparent 1px),linear-gradient(90deg,var(--border) 1px,transparent 1px)', backgroundSize: '48px 48px', opacity: 0.3, pointerEvents: 'none' }} />
      
      <div style={{ position: 'absolute', top: '10%', left: '50%', transform: 'translateX(-50%)', width: 1200, height: 1200, background: 'radial-gradient(circle, rgba(255,123,44,0.15) 0%, transparent 55%)', pointerEvents: 'none', zIndex: 1 }} />

      <header style={{ position: 'relative', zIndex: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '24px 5%', borderBottom: '1px solid var(--border)', background: 'rgba(9, 13, 19, 0.6)', backdropFilter: 'blur(8px)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 40, height: 40, background: 'var(--accent-dim)', border: '1px solid var(--accent-glow)', borderRadius: 10 }}>
            {/* <Icon n="shield" s={20} c="var(--accent)" /> */}
            <img src="/Dmitri-logo.png" alt="Logo" style={{ maxWidth: "100%", height: "auto", objectFit: "contain" }} />
          </div>
          <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.02em' }}>Dmitri Vulnerability Scanner</span>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <Btn variant="ghost" onClick={() => navigate('/login')}>Entrar</Btn>
          <Btn onClick={() => navigate('/register')}>Criar Conta</Btn>
        </div>
      </header>

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '100px 20px', position: 'relative', zIndex: 10, textAlign: 'center', animation: 'fadeIn 0.6s ease' }}>
        
        <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 100, height: 100, background: 'var(--accent-dim)', border: '1px solid var(--accent-glow)', borderRadius: 24, marginBottom: 32, boxShadow: '0 0 60px var(--accent-glow)' }}>
          {/* <Icon n="shield" s={36} c="var(--accent)" /> */}
          <img src="/Dmitri-logo.png" alt="Logo" style={{ maxWidth: "100%", height: "auto", objectFit: "contain" }} />
        </div>
        
        <h1 style={{ fontSize: 'clamp(36px, 5vw, 56px)', fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1.1, maxWidth: 800, marginBottom: 24 }}>
          Segurança inteligente da rede, <br/>
          <span style={{ color: 'var(--accent)' }}>proteção contra ameaças.</span>
        </h1>
        
        <p style={{ fontSize: 'clamp(16px, 2vw, 18px)', color: 'var(--text2)', lineHeight: 1.6, maxWidth: 600, marginBottom: 40 }}>
          Dmitri é um agente de hardware plug-and-play que escaneia, identifica e protege a sua rede contra vulnerabilidades antes que elas sejam exploradas.
        </p>

        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', justifyContent: 'center' }}>
          <Btn size="lg" icon="scan" onClick={() => navigate('/register')} style={{ padding: '14px 28px', fontSize: 16 }}>
            Começar Agora
          </Btn>
          <Btn variant="secondary" size="lg" icon="terminal" onClick={() => navigate('/login')} style={{ padding: '14px 28px', fontSize: 16, background: 'rgba(21, 29, 43, 0.8)', backdropFilter: 'blur(8px)' }}>
            Acessar Painel
          </Btn>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 24, width: '100%', maxWidth: 1000, marginTop: 100 }}>
          {[
            { icon: 'network' as const, title: 'Mapeamento Automático', desc: 'Conecte o Dmitri à sua rede e ele listará instantaneamente todos os dispositivos conectados (IoT, servidores, computadores).' },
            { icon: 'alert' as const, title: 'Detecção de Vulnerabilidades', desc: 'Identifica portas abertas, serviços legados e senhas fracas expostas em sua infraestrutura local.' },
            { icon: 'history' as const, title: 'Relatórios Contínuos', desc: 'Mantenha um histórico completo de verificações e receba alertas caso novos dispositivos inseguros entrem na rede.' }
          ].map((feat, i) => (
            <div key={i} style={{ background: 'rgba(15, 21, 32, 0.7)', backdropFilter: 'blur(12px)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 32, textAlign: 'left', display: 'flex', flexDirection: 'column', gap: 16, transition: 'transform 0.2s', cursor: 'default' }}
                 onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-4px)'}
                 onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}>
              <div style={{ width: 48, height: 48, borderRadius: 12, background: 'var(--surface2)', border: '1px solid var(--border2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Icon n={feat.icon} s={24} c="var(--accent)" />
              </div>
              <h3 style={{ fontSize: 18, fontWeight: 600 }}>{feat.title}</h3>
              <p style={{ fontSize: 14, color: 'var(--text3)', lineHeight: 1.6 }}>{feat.desc}</p>
            </div>
          ))}
        </div>
      </main>

      {/* Footer */}
      <footer style={{ position: 'relative', zIndex: 10, padding: '32px 5%', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16, background: 'rgba(9, 13, 19, 0.8)', backdropFilter: 'blur(4px)', marginTop: 'auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon n="shield" s={16} c="var(--text3)" />
          <span style={{ fontSize: 13, color: 'var(--text3)', fontWeight: 600 }}>Dmitri Vulnerability Scanner</span>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text3)' }}>
          Instituto Mauá de Tecnologia · TCC 2026
        </div>
      </footer>
    </div>
  );
}