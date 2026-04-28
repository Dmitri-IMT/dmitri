import type { ReactNode, ButtonHTMLAttributes, InputHTMLAttributes } from 'react';
import { Icon, type IconName } from '../icons/Icon';
import type { Severity } from '../../types';

// --- BADGE ---
const SEV_LABEL: Record<Severity, string> = { critical: 'Urgente', high: 'Importante', medium: 'Moderado', low: 'Baixo risco' };
const SEV_COLOR: Record<Severity, string> = { critical: 'var(--urgente)', high: 'var(--alto)', medium: 'var(--medio)', low: 'var(--baixo)' };
const SEV_BG: Record<Severity, string>    = { critical: 'var(--urgente-dim)', high: 'var(--alto-dim)', medium: 'var(--medio-dim)', low: 'var(--baixo-dim)' };

export function Badge({ sev }: { sev: Severity }) {
  return (
    <span style={{ display: 'inline-block', padding: '3px 9px', borderRadius: 20, fontSize: 11, fontWeight: 700, color: SEV_COLOR[sev], background: SEV_BG[sev], border: `1px solid ${SEV_COLOR[sev]}33` }}>
      {SEV_LABEL[sev] || sev}
    </span>
  );
}

// --- CARD ---
interface CardProps {
  children: ReactNode;
  style?: React.CSSProperties;
  onClick?: () => void;
}

export function Card({ children, style = {}, onClick }: CardProps) {
  return (
    <div 
      onClick={onClick}
      className="custom-card"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 20, transition: 'all 0.15s', cursor: onClick ? 'pointer' : undefined, ...style }}
      onMouseEnter={(e) => onClick && (e.currentTarget.style.background = 'var(--surface2)', e.currentTarget.style.borderColor = 'var(--border2)')}
      onMouseLeave={(e) => onClick && (e.currentTarget.style.background = 'var(--surface)', e.currentTarget.style.borderColor = 'var(--border)')}
    >
      {children}
    </div>
  );
}

// --- BOTÃO ---
interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  icon?: IconName;
}

export function Btn({ children, variant = 'primary', size = 'md', icon, style = {}, disabled, ...props }: BtnProps) {
  const sz = { 
    sm: { fontSize: 12, padding: '6px 14px' }, 
    md: { fontSize: 14, padding: '10px 18px' }, 
    lg: { fontSize: 15, padding: '13px 24px' } 
  }[size];
  
  const vars = {
    primary:   { background: 'var(--accent)', color: '#080d13', borderColor: 'var(--accent)' },
    secondary: { background: 'var(--surface2)', color: 'var(--text)', borderColor: 'var(--border2)' },
    ghost:     { background: 'transparent', color: 'var(--text2)', borderColor: 'transparent' },
    danger:    { background: 'var(--urgente-dim)', color: 'var(--urgente)', borderColor: 'var(--urgente)44' },
  }[variant];

  return (
    <button 
      disabled={disabled}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 7, borderRadius: 'var(--radius)', fontWeight: 600, border: '1px solid transparent', transition: 'opacity 0.15s', opacity: disabled ? 0.45 : 1, cursor: disabled ? 'not-allowed' : 'pointer', fontFamily: 'var(--font)', ...sz, ...vars, ...style }}
      onMouseEnter={e => { if (!disabled) e.currentTarget.style.opacity = '0.8' }}
      onMouseLeave={e => { e.currentTarget.style.opacity = '1' }}
      {...props}
    >
      {icon && <Icon n={icon} s={14} />}
      {children}
    </button>
  );
}

// --- CAMPO DE TEXTO ---
interface FieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange'> {
  label?: string;
  value: string;
  onChange: (val: string) => void;
  mono?: boolean;
  hint?: string;
}

export function Field({ label, value, onChange, type = 'text', placeholder, mono, hint, ...props }: FieldProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      {label && <label style={{ fontSize: 12, color: 'var(--text2)', fontWeight: 600 }}>{label}</label>}
      <input 
        type={type} 
        value={value} 
        onChange={e => onChange(e.target.value)} 
        placeholder={placeholder}
        style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', borderRadius: 'var(--radius)', padding: '10px 14px', color: 'var(--text)', fontSize: 14, outline: 'none', fontFamily: mono ? 'var(--mono)' : 'var(--font)' }}
        onFocus={e => e.target.style.borderColor = 'var(--accent)'}
        onBlur={e => e.target.style.borderColor = 'var(--border2)'}
        {...props}
      />
      {hint && <span style={{ fontSize: 11, color: 'var(--text3)' }}>{hint}</span>}
    </div>
  );
}