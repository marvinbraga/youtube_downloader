/* =========================================================
   Loop — Shared components & icons
   Exposes: Icon, Logo, TopNav, MobileTopBar, MobileTabBar,
            QualityChip, FormatChip, ProgressBar, Avatar,
            StatPill, Tooltip, Section, ScreenShell, MobileShell
   ========================================================= */

/* ---------- Icons (all 16-24 stroke, currentColor) ---------- */
const Icon = ({ name, size = 18, stroke = 1.6, ...rest }) => {
  const paths = {
    download: <><path d="M12 4v12"/><path d="m6 11 6 6 6-6"/><path d="M5 21h14"/></>,
    play: <path d="M6 4l14 8-14 8z" fill="currentColor" stroke="none"/>,
    pause: <><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></>,
    plus: <><path d="M12 5v14"/><path d="M5 12h14"/></>,
    link: <><path d="M10 14a4 4 0 0 0 5.66 0l3.34-3.34a4 4 0 0 0-5.66-5.66l-1.4 1.4"/><path d="M14 10a4 4 0 0 0-5.66 0l-3.34 3.34a4 4 0 0 0 5.66 5.66l1.4-1.4"/></>,
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></>,
    home: <><path d="m3 11 9-7 9 7v9a2 2 0 0 1-2 2h-4v-7h-6v7H5a2 2 0 0 1-2-2z"/></>,
    library: <><path d="M4 6h16"/><path d="M4 12h16"/><path d="M4 18h10"/></>,
    queue: <><rect x="3" y="4" width="18" height="4" rx="1"/><rect x="3" y="11" width="18" height="4" rx="1"/><rect x="3" y="18" width="12" height="2" rx="1"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></>,
    bell: <><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></>,
    check: <path d="m5 12 5 5L20 7"/>,
    close: <><path d="M6 6l12 12"/><path d="M18 6 6 18"/></>,
    chevronRight: <path d="m9 6 6 6-6 6"/>,
    chevronDown: <path d="m6 9 6 6 6-6"/>,
    arrowRight: <><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></>,
    moreHorizontal: <><circle cx="5" cy="12" r="1.5" fill="currentColor"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/><circle cx="19" cy="12" r="1.5" fill="currentColor"/></>,
    user: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
    sparkles: <><path d="M12 3v4"/><path d="M12 17v4"/><path d="M3 12h4"/><path d="M17 12h4"/><path d="m6 6 2 2"/><path d="m16 16 2 2"/><path d="m6 18 2-2"/><path d="m16 8 2-2"/></>,
    folder: <><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></>,
    music: <><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></>,
    film: <><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 8h18"/><path d="M3 16h18"/><path d="M8 3v18"/><path d="M16 3v18"/></>,
    captions: <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 12h3"/><path d="M14 12h3"/><path d="M7 15h2"/><path d="M14 15h3"/></>,
    list: <><path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><circle cx="4" cy="6" r="1" fill="currentColor"/><circle cx="4" cy="12" r="1" fill="currentColor"/><circle cx="4" cy="18" r="1" fill="currentColor"/></>,
    scissors: <><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="m20 4-12 12"/><path d="m8 8 12 12"/></>,
    sun: <><circle cx="12" cy="12" r="4"/><path d="M12 3v2"/><path d="M12 19v2"/><path d="m5 5 1.4 1.4"/><path d="m17.6 17.6 1.4 1.4"/><path d="M3 12h2"/><path d="M19 12h2"/><path d="m5 19 1.4-1.4"/><path d="m17.6 6.4 1.4-1.4"/></>,
    moon: <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>,
    cloud: <path d="M17 18a4 4 0 1 0-1-7.9 6 6 0 1 0-11 2.9A4 4 0 0 0 6 18z"/>,
    grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    trash: <><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></>,
    refresh: <><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 4v4h-4"/><path d="M3 20v-4h4"/></>,
    alert: <><path d="M12 2 1 22h22z"/><path d="M12 9v5"/><circle cx="12" cy="18" r="0.8" fill="currentColor"/></>,
    zap: <path d="M13 2 3 14h7l-1 8 10-12h-7z"/>,
    wifi: <><path d="M5 12a10 10 0 0 1 14 0"/><path d="M8.5 15.5a5 5 0 0 1 7 0"/><circle cx="12" cy="19" r="1" fill="currentColor"/></>,
    speaker: <><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" fill="currentColor" stroke="none"/><path d="M19 12c0-2-1-4-3-5"/><path d="M16 8a8 8 0 0 1 0 8"/></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth={stroke}
      strokeLinecap="round" strokeLinejoin="round" {...rest}>
      {paths[name] || null}
    </svg>
  );
};

/* ---------- Logo ---------- */
const Logo = ({ name = 'Loop', size = 20 }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
    <div style={{
      width: size + 8, height: size + 8,
      borderRadius: 10,
      background: 'linear-gradient(135deg, var(--accent), oklch(0.7 0.18 calc(var(--accent-h) + 60)))',
      display: 'grid', placeItems: 'center',
      boxShadow: '0 4px 12px -4px var(--accent), inset 0 1px 0 oklch(1 0 0 / 0.3)',
    }}>
      <svg width={size - 2} height={size - 2} viewBox="0 0 24 24" fill="none">
        <path d="M5 12a7 7 0 1 1 11.5 5.4" stroke="white" strokeWidth="2.4" strokeLinecap="round" />
        <path d="m13 14 4 4-4 4" stroke="white" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
    <div style={{ fontWeight: 600, fontSize: 16, letterSpacing: '-0.02em' }}>{name}</div>
  </div>
);

/* ---------- Avatar ---------- */
const Avatar = ({ initials = 'AM', size = 32, hue = 264 }) => (
  <div style={{
    width: size, height: size, borderRadius: '50%',
    background: `linear-gradient(135deg, oklch(0.7 0.14 ${hue}), oklch(0.55 0.18 ${hue + 40}))`,
    color: 'white', display: 'grid', placeItems: 'center',
    fontSize: size * 0.36, fontWeight: 600, letterSpacing: '-0.02em',
    boxShadow: '0 2px 8px -2px oklch(0 0 0 / 0.2), inset 0 1px 0 oklch(1 0 0 / 0.3)',
  }}>{initials}</div>
);

/* ---------- Top nav (desktop) ---------- */
const TopNav = ({ active = 'home', brandName = 'Loop' }) => {
  const items = [
    { id: 'home', label: 'Home', icon: 'home' },
    { id: 'queue', label: 'Queue', icon: 'queue' },
    { id: 'library', label: 'Library', icon: 'library' },
    { id: 'pricing', label: 'Pricing', icon: 'sparkles' },
  ];
  return (
    <header className="glass" style={{
      display: 'flex', alignItems: 'center',
      padding: '10px 14px',
      borderRadius: 'var(--r-pill)',
      gap: 12,
    }}>
      <Logo name={brandName} />
      <div style={{ width: 1, height: 22, background: 'var(--border)', margin: '0 6px' }} />
      <nav style={{ display: 'flex', gap: 2, flex: 1 }}>
        {items.map(it => (
          <button key={it.id} className={active === it.id ? 'btn btn-sm btn-glass' : 'btn btn-sm btn-ghost'}
            style={{
              borderRadius: 'var(--r-pill)',
              color: active === it.id ? 'var(--fg)' : 'var(--fg-muted)',
              background: active === it.id ? 'var(--surface-strong)' : 'transparent',
            }}>
            <Icon name={it.icon} size={15} />
            {it.label}
          </button>
        ))}
      </nav>
      <button className="btn btn-sm btn-ghost" aria-label="Notifications">
        <Icon name="bell" size={16} />
      </button>
      <Avatar initials="AM" size={30} />
    </header>
  );
};

/* ---------- Mobile top bar ---------- */
const MobileTopBar = ({ title, brandName = 'Loop', back = false, action = null }) => (
  <div style={{
    display: 'flex', alignItems: 'center',
    padding: '60px 16px 14px',
    gap: 12,
  }}>
    {back ? (
      <button className="btn btn-sm btn-ghost" style={{ width: 36, padding: 0, borderRadius: 12 }}>
        <Icon name="chevronRight" size={18} style={{ transform: 'rotate(180deg)' }} />
      </button>
    ) : <Logo name={brandName} size={18} />}
    <div style={{ flex: 1, textAlign: 'center', fontSize: 15, fontWeight: 500 }}>
      {title}
    </div>
    {action || <button className="btn btn-sm btn-ghost" style={{ width: 36, padding: 0, borderRadius: 12 }}>
      <Icon name="bell" size={17} />
    </button>}
  </div>
);

/* ---------- Mobile tab bar ---------- */
const MobileTabBar = ({ active = 'home' }) => {
  const items = [
    { id: 'home', icon: 'home', label: 'Home' },
    { id: 'queue', icon: 'queue', label: 'Queue' },
    { id: 'library', icon: 'library', label: 'Library' },
    { id: 'settings', icon: 'settings', label: 'Settings' },
  ];
  return (
    <div className="glass-strong" style={{
      position: 'absolute', bottom: 18, left: 16, right: 16,
      display: 'flex', justifyContent: 'space-around',
      padding: '8px 6px',
      borderRadius: 'var(--r-pill)',
    }}>
      {items.map(it => (
        <button key={it.id} className="btn btn-sm btn-ghost" style={{
          flex: 1, flexDirection: 'column', height: 48, gap: 2,
          color: active === it.id ? 'var(--fg)' : 'var(--fg-subtle)',
          background: active === it.id ? 'var(--surface)' : 'transparent',
          borderRadius: 18,
        }}>
          <Icon name={it.icon} size={18} />
          <span style={{ fontSize: 10, letterSpacing: 0 }}>{it.label}</span>
        </button>
      ))}
    </div>
  );
};

/* ---------- Quality / format chips ---------- */
const Chip = ({ active, children, onClick }) => (
  <button onClick={onClick} style={{
    display: 'inline-flex', alignItems: 'center', gap: 6,
    height: 36, padding: '0 14px',
    borderRadius: 'var(--r-pill)',
    background: active ? 'var(--fg)' : 'var(--surface)',
    color: active ? 'var(--bg-base)' : 'var(--fg)',
    border: `1px solid ${active ? 'var(--fg)' : 'var(--border)'}`,
    fontSize: 13, fontWeight: 500,
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.02em',
    cursor: 'pointer',
    transition: 'all 160ms',
  }}>{children}</button>
);

/* ---------- Progress bar ---------- */
const ProgressBar = ({ value = 0, indeterminate = false, color }) => (
  <div style={{
    height: 6, width: '100%',
    background: 'var(--surface-sunk)',
    borderRadius: 999,
    overflow: 'hidden',
    border: '1px solid var(--border)',
  }}>
    <div style={{
      height: '100%',
      width: indeterminate ? '40%' : `${value}%`,
      background: color || 'linear-gradient(90deg, var(--accent), oklch(0.7 0.18 calc(var(--accent-h) + 60)))',
      borderRadius: 999,
      transition: 'width 400ms cubic-bezier(.2,.8,.2,1)',
      boxShadow: '0 0 12px var(--accent)',
    }}/>
  </div>
);

/* ---------- Stat pill ---------- */
const StatPill = ({ label, value, mono = true }) => (
  <div className="glass-sunk" style={{
    padding: '10px 14px',
    display: 'flex', flexDirection: 'column', gap: 2,
  }}>
    <div className="eyebrow" style={{ fontSize: 10 }}>{label}</div>
    <div style={{
      fontFamily: mono ? 'var(--font-mono)' : 'var(--font-sans)',
      fontSize: 16, fontWeight: 500, letterSpacing: '-0.01em',
    }}>{value}</div>
  </div>
);

/* ---------- Screen shells ---------- */
const ScreenShell = ({ children, label, width = 1280, height = 820 }) => (
  <div data-screen-label={label} className="aurora-stage grain" style={{
    width, height,
    padding: '20px 24px 24px',
    display: 'flex', flexDirection: 'column',
    gap: 20,
    overflow: 'hidden',
  }}>
    <div className="aurora-3rd" />
    {children}
  </div>
);

const MobileShell = ({ children, label, dark = false }) => (
  <div data-screen-label={label} data-theme={dark ? 'dark' : 'light'} className="phone-frame">
    <div className="phone-screen aurora-stage grain">
      <div className="aurora-3rd" />
      <div className="phone-notch" />
      {children}
    </div>
  </div>
);

Object.assign(window, {
  Icon, Logo, Avatar, TopNav, MobileTopBar, MobileTabBar,
  Chip, ProgressBar, StatPill, ScreenShell, MobileShell,
});
