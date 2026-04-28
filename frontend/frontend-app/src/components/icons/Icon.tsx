import type { JSX, SVGProps } from 'react';

export type IconName = 'home' | 'shield' | 'devices' | 'alert' | 'scan' | 'history' | 'settings' | 'check' | 'back' | 'chevron_r' | 'chevron_d' | 'plus' | 'lock' | 'menu' | 'terminal' | 'info' | 'network';

interface IconProps extends SVGProps<SVGSVGElement> {
  n: IconName;
  s?: number;
  c?: string;
}

export function Icon({ n, s = 16, c = 'currentColor', style = {}, ...props }: IconProps) {
  const paths: Record<IconName, JSX.Element> = {
    home: <><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" fill="none" stroke={c} strokeWidth="1.7" strokeLinejoin="round"/><polyline points="9 22 9 12 15 12 15 22" fill="none" stroke={c} strokeWidth="1.7" strokeLinejoin="round"/></>,
    shield: <><path d="M12 2L3 6v6c0 5.5 3.8 10.7 9 12 5.2-1.3 9-6.5 9-12V6L12 2z" fill="none" stroke={c} strokeWidth="1.8" strokeLinejoin="round"/></>,
    devices: <><rect x="2" y="3" width="20" height="14" rx="2" fill="none" stroke={c} strokeWidth="1.7"/><path d="M8 21h8M12 17v4" stroke={c} strokeWidth="1.7" strokeLinecap="round"/></>,
    alert: <><path d="M10.3 3.9L2 20h20L13.7 3.9a2 2 0 00-3.4 0z" fill="none" stroke={c} strokeWidth="1.7" strokeLinejoin="round"/><line x1="12" y1="10" x2="12" y2="14" stroke={c} strokeWidth="1.8" strokeLinecap="round"/><circle cx="12" cy="17.5" r="0.7" fill={c}/></>,
    scan: <><circle cx="11" cy="11" r="7" fill="none" stroke={c} strokeWidth="1.8"/><line x1="16.5" y1="16.5" x2="21" y2="21" stroke={c} strokeWidth="2" strokeLinecap="round"/></>,
    history: <><polyline points="12 8 12 12 14 14" fill="none" stroke={c} strokeWidth="1.7" strokeLinecap="round"/><path d="M3.05 11a9 9 0 1 0 .5-3" fill="none" stroke={c} strokeWidth="1.7" strokeLinecap="round"/><polyline points="3 4 3 11 10 11" fill="none" stroke={c} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></>,
    settings: <><circle cx="12" cy="12" r="3" fill="none" stroke={c} strokeWidth="1.7"/><path d="M12 1v3M12 20v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M1 12h3M20 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" stroke={c} strokeWidth="1.7" strokeLinecap="round"/></>,
    check: <polyline points="20 6 9 17 4 12" fill="none" stroke={c} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>,
    back: <><line x1="19" y1="12" x2="5" y2="12" stroke={c} strokeWidth="2" strokeLinecap="round"/><polyline points="12 19 5 12 12 5" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></>,
    chevron_r: <polyline points="9 18 15 12 9 6" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>,
    chevron_d: <polyline points="6 9 12 15 18 9" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>,
    plus: <><line x1="12" y1="5" x2="12" y2="19" stroke={c} strokeWidth="2" strokeLinecap="round"/><line x1="5" y1="12" x2="19" y2="12" stroke={c} strokeWidth="2" strokeLinecap="round"/></>,
    lock: <><rect x="3" y="11" width="18" height="11" rx="2" fill="none" stroke={c} strokeWidth="1.7"/><path d="M7 11V7a5 5 0 0110 0v4" fill="none" stroke={c} strokeWidth="1.7" strokeLinecap="round"/></>,
    menu: <><line x1="3" y1="6" x2="21" y2="6" stroke={c} strokeWidth="2" strokeLinecap="round"/><line x1="3" y1="12" x2="21" y2="12" stroke={c} strokeWidth="2" strokeLinecap="round"/><line x1="3" y1="18" x2="21" y2="18" stroke={c} strokeWidth="2" strokeLinecap="round"/></>,
    terminal: <><polyline points="4 17 10 11 4 5" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/><line x1="12" y1="19" x2="20" y2="19" stroke={c} strokeWidth="2" strokeLinecap="round"/></>,
    info: <><circle cx="12" cy="12" r="10" fill="none" stroke={c} strokeWidth="1.7"/><line x1="12" y1="8" x2="12" y2="12" stroke={c} strokeWidth="2" strokeLinecap="round"/><circle cx="12" cy="16" r="0.8" fill={c}/></>,
    network: <><circle cx="12" cy="5" r="2" fill="none" stroke={c} strokeWidth="1.7"/><circle cx="5" cy="19" r="2" fill="none" stroke={c} strokeWidth="1.7"/><circle cx="19" cy="19" r="2" fill="none" stroke={c} strokeWidth="1.7"/><line x1="12" y1="7" x2="5" y2="17" stroke={c} strokeWidth="1.5"/><line x1="12" y1="7" x2="19" y2="17" stroke={c} strokeWidth="1.5"/></>,
  };

  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" style={{ display: 'inline-block', flexShrink: 0, ...style }} {...props}>
      {paths[n] || null}
    </svg>
  );
}