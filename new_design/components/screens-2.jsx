/* =========================================================
   Loop — Screens part 2: Settings, Login, Pricing, Error,
   plus mobile mockups (Home, Analyze, Library)
   ========================================================= */

/* ============================================================
   5. SETTINGS — desktop
   ============================================================ */
const SettingsDesktop = ({ brandName = 'Loop' }) => (
  <ScreenShell label="05 Settings — Desktop" width={1280} height={820}>
    <TopNav active="settings" brandName={brandName} />

    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16 }}>
      <div>
        <div className="eyebrow">Preferences</div>
        <h2 className="serif" style={{ margin: '6px 0 0', fontSize: 36, fontWeight: 400, letterSpacing: '-0.02em' }}>
          Settings
        </h2>
      </div>
    </div>

    <main style={{ flex: 1, display: 'grid', gridTemplateColumns: '220px 1fr', gap: 20, minHeight: 0 }}>
      {/* Side nav */}
      <nav className="glass" style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {[
          { id: 'account', label: 'Account', icon: 'user', active: true },
          { id: 'downloads', label: 'Downloads', icon: 'download' },
          { id: 'storage', label: 'Storage', icon: 'folder' },
          { id: 'network', label: 'Network', icon: 'wifi' },
          { id: 'audio', label: 'Audio', icon: 'speaker' },
          { id: 'appearance', label: 'Appearance', icon: 'sun' },
          { id: 'shortcuts', label: 'Shortcuts', icon: 'zap' },
          { id: 'about', label: 'About', icon: 'sparkles' },
        ].map(it => (
          <button key={it.id} style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 12px',
            background: it.active ? 'var(--surface-strong)' : 'transparent',
            border: 'none', cursor: 'pointer',
            borderRadius: 10, color: it.active ? 'var(--fg)' : 'var(--fg-muted)',
            fontSize: 13, textAlign: 'left', fontFamily: 'inherit',
          }}>
            <Icon name={it.icon} size={15} />
            <span style={{ flex: 1 }}>{it.label}</span>
            {it.active && <Icon name="chevronRight" size={13} />}
          </button>
        ))}
      </nav>

      {/* Content */}
      <section style={{ display: 'flex', flexDirection: 'column', gap: 16, overflow: 'auto', paddingRight: 4 }} className="scroll-y">
        {/* Profile card */}
        <div className="glass-strong" style={{ padding: 24, display: 'flex', alignItems: 'center', gap: 18 }}>
          <Avatar initials="AM" size={64} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 20, fontWeight: 500, letterSpacing: '-0.01em' }}>Ana Martins</div>
            <div style={{ fontSize: 13, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)' }}>ana@field.studio · Pro plan</div>
          </div>
          <button className="btn btn-glass btn-sm">Edit profile</button>
          <button className="btn btn-ghost btn-sm">Sign out</button>
        </div>

        {/* Settings groups */}
        {[
          {
            title: 'Default download',
            rows: [
              { l: 'Default quality', s: 'Best available up to 2160p', val: '2160p ▾' },
              { l: 'Default format', s: 'Choose what fits your workflow', val: 'MP4 ▾' },
              { l: 'Save location', s: '~/Movies/Loop', val: 'Change' },
              { l: 'Subfolder per channel', s: 'Auto-organize by source', toggle: true },
            ],
          },
          {
            title: 'Network',
            rows: [
              { l: 'Concurrent downloads', s: 'Higher uses more bandwidth', val: '4 ▾' },
              { l: 'Bandwidth limit', s: 'Cap so other apps stay snappy', val: 'Unlimited ▾' },
              { l: 'Use system VPN', s: 'Route traffic through active VPN', toggle: false },
            ],
          },
          {
            title: 'Appearance',
            rows: [
              { l: 'Theme', s: 'Light, dark, or follow system', val: 'System ▾' },
              { l: 'Density', s: 'Compact spacing on lists', toggle: false },
              { l: 'Reduce motion', s: 'Subtle transitions only', toggle: false },
            ],
          },
        ].map(group => (
          <div key={group.title} className="glass" style={{ padding: 0 }}>
            <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)' }}>
              <div className="eyebrow">{group.title}</div>
            </div>
            <div>
              {group.rows.map((r, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 16,
                  padding: '14px 20px',
                  borderBottom: i < group.rows.length - 1 ? '1px solid var(--border)' : 'none',
                }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 500 }}>{r.l}</div>
                    <div style={{ fontSize: 12, color: 'var(--fg-subtle)', marginTop: 2 }}>{r.s}</div>
                  </div>
                  {r.toggle !== undefined ? (
                    <div style={{
                      width: 38, height: 22, borderRadius: 999,
                      background: r.toggle ? 'var(--accent)' : 'var(--surface-sunk)',
                      border: '1px solid var(--border)', position: 'relative',
                    }}>
                      <div style={{
                        position: 'absolute', top: 2, left: r.toggle ? 18 : 2,
                        width: 16, height: 16, borderRadius: '50%',
                        background: 'white', boxShadow: '0 1px 3px oklch(0 0 0 / 0.2)',
                      }} />
                    </div>
                  ) : (
                    <button className="btn btn-sm btn-glass" style={{ minWidth: 110, justifyContent: 'space-between' }}>
                      {r.val}
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </section>
    </main>
  </ScreenShell>
);

/* ============================================================
   6. LOGIN — desktop (split layout)
   ============================================================ */
const LoginDesktop = ({ brandName = 'Loop' }) => (
  <ScreenShell label="06 Sign in — Desktop" width={1280} height={820}>
    <main style={{
      flex: 1, display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 20, minHeight: 0,
    }}>
      {/* LEFT — brand */}
      <section className="glass-strong" style={{
        padding: 48, display: 'flex', flexDirection: 'column',
        position: 'relative', overflow: 'hidden',
      }}>
        <Logo name={brandName} size={22} />

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 24 }}>
          <div className="eyebrow">A quieter way to save</div>
          <h1 className="serif" style={{
            margin: 0, fontSize: 72, lineHeight: 1, fontWeight: 400, letterSpacing: '-0.03em',
          }}>
            Welcome<br />
            <em style={{ fontStyle: 'italic', color: 'var(--accent)' }}>back.</em>
          </h1>
          <p style={{ margin: 0, fontSize: 16, lineHeight: 1.5, color: 'var(--fg-muted)', maxWidth: 380 }}>
            Pick up where you left off — your queue, library, and preferences sync across every device.
          </p>
        </div>

        {/* Decorative quote */}
        <div className="glass" style={{ padding: 20, maxWidth: 360 }}>
          <div className="serif" style={{ fontSize: 17, lineHeight: 1.4, fontStyle: 'italic' }}>
            "It's the only downloader that doesn't make me feel like I need to take a shower afterwards."
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12 }}>
            <Avatar initials="JR" size={28} hue={30} />
            <div style={{ fontSize: 12 }}>
              <div style={{ fontWeight: 500 }}>Jules R.</div>
              <div style={{ color: 'var(--fg-subtle)' }}>Documentary editor</div>
            </div>
          </div>
        </div>
      </section>

      {/* RIGHT — form */}
      <section style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '0 60px' }}>
        <div className="glass-strong" style={{ padding: 36, display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div>
            <h2 className="serif" style={{ margin: 0, fontSize: 32, fontWeight: 400, letterSpacing: '-0.02em' }}>Sign in</h2>
            <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--fg-muted)' }}>
              New here? <a style={{ color: 'var(--accent)', textDecoration: 'none' }}>Create an account →</a>
            </p>
          </div>

          {/* Social */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <button className="btn btn-glass" style={{ height: 44 }}>Continue with Apple</button>
            <button className="btn btn-glass" style={{ height: 44 }}>Continue with Google</button>
          </div>

          {/* Divider */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: 'var(--fg-subtle)', fontSize: 11 }}>
            <hr className="divider" style={{ flex: 1 }} />
            <span style={{ fontFamily: 'var(--font-mono)', letterSpacing: '0.15em' }}>OR</span>
            <hr className="divider" style={{ flex: 1 }} />
          </div>

          {/* Inputs */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>Email</label>
              <input className="input" style={{ marginTop: 6 }} defaultValue="ana@field.studio" />
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label style={{ fontSize: 11, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>Password</label>
                <a style={{ fontSize: 11, color: 'var(--fg-muted)', textDecoration: 'none' }}>Forgot?</a>
              </div>
              <input className="input" type="password" style={{ marginTop: 6 }} defaultValue="••••••••••" />
            </div>
          </div>

          <button className="btn btn-accent btn-lg">Sign in <Icon name="arrowRight" size={15} /></button>

          <div style={{ fontSize: 11, color: 'var(--fg-subtle)', textAlign: 'center' }}>
            By continuing you agree to our <a style={{ color: 'var(--fg-muted)' }}>Terms</a> and <a style={{ color: 'var(--fg-muted)' }}>Privacy Policy</a>.
          </div>
        </div>
      </section>
    </main>
  </ScreenShell>
);

/* ============================================================
   7. PRICING — desktop
   ============================================================ */
const PricingDesktop = ({ brandName = 'Loop' }) => {
  const plans = [
    {
      name: 'Free', price: '0', sub: 'forever',
      tagline: 'For casual use and trying things out.',
      features: ['5 downloads / day', 'Up to 1080p', 'MP4 / MP3 only', 'Basic captions', 'Local storage only'],
      cta: 'Get started', highlight: false,
    },
    {
      name: 'Pro', price: '8', sub: 'per month',
      tagline: 'Most chosen. Built for makers and archivists.',
      features: ['Unlimited downloads', 'Up to 8K HDR', 'All formats incl. WAV/FLAC', 'Captions in 40+ languages', 'Cloud sync (50 GB)', 'Bulk & playlists', 'Priority queue'],
      cta: 'Start 7-day trial', highlight: true,
    },
    {
      name: 'Studio', price: '24', sub: 'per month',
      tagline: 'Teams, agencies, and serious workflows.',
      features: ['Everything in Pro', 'Up to 5 seats', 'Shared collections', '500 GB cloud sync', 'API access', 'SSO & audit log', 'Priority support'],
      cta: 'Talk to us', highlight: false,
    },
  ];
  return (
    <ScreenShell label="07 Pricing — Desktop" width={1280} height={820}>
      <TopNav active="pricing" brandName={brandName} />

      <header style={{ textAlign: 'center', marginTop: 12 }}>
        <div className="eyebrow">Pricing</div>
        <h1 className="serif" style={{ margin: '8px 0 0', fontSize: 56, lineHeight: 1.05, fontWeight: 400, letterSpacing: '-0.03em' }}>
          Pay for the <em style={{ color: 'var(--accent)' }}>workflow,</em><br />
          not the file count.
        </h1>
        <div style={{ display: 'inline-flex', gap: 4, padding: 4, marginTop: 18, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 999 }}>
          <button className="btn btn-sm" style={{ background: 'var(--fg)', color: 'var(--bg-base)' }}>Monthly</button>
          <button className="btn btn-sm btn-ghost">Yearly <span className="tag" style={{ marginLeft: 6, height: 18, fontSize: 10 }}>−20%</span></button>
        </div>
      </header>

      <main style={{ flex: 1, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {plans.map(p => (
          <div key={p.name} className={p.highlight ? 'glass-strong' : 'glass'} style={{
            padding: 28, display: 'flex', flexDirection: 'column', gap: 16,
            position: 'relative',
            border: p.highlight ? '1px solid var(--accent)' : undefined,
            boxShadow: p.highlight ? '0 30px 60px -20px var(--accent), var(--shadow-lg)' : undefined,
          }}>
            {p.highlight && (
              <span style={{
                position: 'absolute', top: -12, left: 24,
                background: 'var(--accent)', color: 'var(--accent-fg)',
                padding: '4px 10px', borderRadius: 999,
                fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', textTransform: 'uppercase',
              }}>Most chosen</span>
            )}
            <div>
              <div style={{ fontSize: 14, fontWeight: 500, letterSpacing: '-0.01em' }}>{p.name}</div>
              <div style={{ fontSize: 12, color: 'var(--fg-muted)', marginTop: 4 }}>{p.tagline}</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <span className="serif" style={{ fontSize: 56, fontWeight: 400, letterSpacing: '-0.03em' }}>${p.price}</span>
              <span style={{ fontSize: 13, color: 'var(--fg-muted)' }}>{p.sub}</span>
            </div>
            <button className={p.highlight ? 'btn btn-accent btn-lg' : 'btn btn-glass btn-lg'}>
              {p.cta} {p.highlight && <Icon name="arrowRight" size={15} />}
            </button>
            <hr className="divider" />
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10, fontSize: 13 }}>
              {p.features.map(f => (
                <li key={f} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                  <span style={{
                    width: 16, height: 16, borderRadius: '50%',
                    background: p.highlight ? 'var(--accent-soft)' : 'var(--surface-sunk)',
                    color: p.highlight ? 'var(--accent)' : 'var(--fg)',
                    display: 'grid', placeItems: 'center', flexShrink: 0,
                  }}>
                    <Icon name="check" size={10} stroke={2.5} />
                  </span>
                  {f}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </main>
    </ScreenShell>
  );
};

/* ============================================================
   8. ERROR — desktop
   ============================================================ */
const ErrorDesktop = ({ brandName = 'Loop' }) => (
  <ScreenShell label="08 Error — Desktop" width={1280} height={820}>
    <TopNav active="home" brandName={brandName} />

    <main style={{ flex: 1, display: 'grid', placeItems: 'center' }}>
      <div className="glass-strong" style={{ padding: 48, maxWidth: 560, textAlign: 'center', position: 'relative', overflow: 'hidden' }}>
        {/* Decorative ring */}
        <div style={{
          width: 88, height: 88, borderRadius: '50%',
          background: 'linear-gradient(135deg, oklch(0.7 0.18 25), oklch(0.55 0.2 15))',
          margin: '0 auto 20px', display: 'grid', placeItems: 'center',
          color: 'white',
          boxShadow: '0 12px 32px -8px oklch(0.6 0.2 15 / 0.5), inset 0 1px 0 oklch(1 0 0 / 0.3)',
        }}>
          <Icon name="alert" size={32} stroke={1.6} />
        </div>

        <div className="eyebrow" style={{ color: 'oklch(0.65 0.18 25)' }}>Error 4012</div>
        <h1 className="serif" style={{ margin: '8px 0 12px', fontSize: 40, fontWeight: 400, letterSpacing: '-0.02em' }}>
          We couldn't reach that video.
        </h1>
        <p style={{ margin: 0, fontSize: 15, lineHeight: 1.55, color: 'var(--fg-muted)' }}>
          The source returned a 403, which usually means the upload is private,
          age-gated, or region-locked. Try signing in to the source, or paste a different link.
        </p>

        <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 24 }}>
          <button className="btn btn-glass btn-lg">Try a different URL</button>
          <button className="btn btn-accent btn-lg"><Icon name="refresh" size={15} /> Retry</button>
        </div>

        <div className="glass-sunk" style={{
          marginTop: 24, padding: '12px 16px',
          fontFamily: 'var(--font-mono)', fontSize: 11,
          textAlign: 'left', color: 'var(--fg-muted)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12,
        }}>
          <span>req_id: 8f3a-2b21-c0de-9911 · 2026-05-04T14:22:18Z</span>
          <button className="btn btn-sm btn-ghost" style={{ height: 24, fontSize: 11 }}>Copy</button>
        </div>
      </div>
    </main>
  </ScreenShell>
);

/* ============================================================
   MOBILE — Home
   ============================================================ */
const HomeMobile = ({ brandName = 'Loop' }) => (
  <MobileShell label="09 Home — Mobile">
    <MobileTopBar brandName={brandName} title="" />
    <div style={{ padding: '8px 16px', display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <div className="eyebrow">Universal video downloader</div>
        <h1 className="serif" style={{
          margin: '6px 0 0', fontSize: 38, lineHeight: 1.05, fontWeight: 400, letterSpacing: '-0.03em',
        }}>
          Save anything<br />
          <em style={{ color: 'var(--accent)' }}>worth keeping.</em>
        </h1>
      </div>

      <div className="glass" style={{
        padding: 6, display: 'flex', alignItems: 'center', gap: 6,
        borderRadius: 'var(--r-pill)',
      }}>
        <div style={{ paddingLeft: 12, color: 'var(--fg-subtle)' }}>
          <Icon name="link" size={15} />
        </div>
        <input className="input" style={{ border: 'none', background: 'transparent', height: 38, fontSize: 13, padding: '0 4px', flex: 1 }}
          placeholder="Paste a URL…" defaultValue="example.video/...aurora-4k" />
        <button className="btn btn-accent btn-sm" style={{ height: 38, padding: '0 12px' }}>
          <Icon name="sparkles" size={13} />
        </button>
      </div>

      <div className="glass" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--accent)', boxShadow: '0 0 8px var(--accent)' }} />
          <span style={{ fontSize: 12, fontWeight: 500 }}>Downloading now</span>
          <span style={{ flex: 1 }} />
          <span className="mono" style={{ fontSize: 11, color: 'var(--fg-muted)' }}>64%</span>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <div className="placeholder-img" style={{ width: 56, height: 36, flexShrink: 0 }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              Northern Lights — Iceland 4K
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--fg-subtle)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>2160p · 38s left</div>
          </div>
        </div>
        <ProgressBar value={64} />
      </div>

      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
          <div className="eyebrow">Recent</div>
          <a style={{ fontSize: 11, color: 'var(--fg-muted)', textDecoration: 'none' }}>All →</a>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[
            { t: 'Patagonian winds — field session', m: 'WAV · 42 min' },
            { t: 'Stoic morning — full talk', m: '1080p · 1h 12m' },
            { t: 'Lo-fi study mix — autumn 2026', m: 'MP3 · 2h 04m' },
          ].map((r, i) => (
            <div key={i} className="glass" style={{ padding: 10, display: 'flex', gap: 10, alignItems: 'center' }}>
              <div className="placeholder-img" style={{ width: 44, height: 30, flexShrink: 0 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.t}</div>
                <div style={{ fontSize: 10.5, color: 'var(--fg-subtle)', fontFamily: 'var(--font-mono)' }}>{r.m}</div>
              </div>
              <Icon name="play" size={14} />
            </div>
          ))}
        </div>
      </div>
    </div>
    <MobileTabBar active="home" />
  </MobileShell>
);

/* ============================================================
   MOBILE — Analyze
   ============================================================ */
const AnalyzeMobile = ({ brandName = 'Loop' }) => (
  <MobileShell label="10 Analyze — Mobile" dark>
    <MobileTopBar brandName={brandName} title="Preview" back />
    <div style={{ padding: '4px 16px 100px', display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div className="placeholder-img" style={{
        aspectRatio: '16/9', borderRadius: 16,
        background: 'linear-gradient(135deg, oklch(0.45 0.15 280), oklch(0.55 0.18 220))',
        border: 'none', position: 'relative',
      }}>
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>
          <button className="glass-strong" style={{
            width: 52, height: 52, borderRadius: '50%',
            display: 'grid', placeItems: 'center',
            color: 'var(--fg)', border: 'none',
          }}>
            <Icon name="play" size={18} />
          </button>
        </div>
        <span style={{
          position: 'absolute', bottom: 8, right: 8,
          padding: '3px 8px', borderRadius: 4,
          background: 'oklch(0 0 0 / 0.6)', color: 'white',
          fontSize: 11, fontFamily: 'var(--font-mono)',
        }}>12:48</span>
      </div>

      <div>
        <h2 className="serif" style={{ margin: 0, fontSize: 22, lineHeight: 1.2, fontWeight: 400, letterSpacing: '-0.02em' }}>
          Northern Lights — Iceland in 4K HDR
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, fontSize: 12, color: 'var(--fg-muted)' }}>
          <Avatar initials="AF" size={18} hue={200} />
          <span>Aurora Field Notes · 1.2M views</span>
        </div>
      </div>

      <div className="glass" style={{ padding: 14 }}>
        <div className="eyebrow" style={{ marginBottom: 10 }}>Quality</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {['2160p', '1440p', '1080p', '720p'].map((q, i) => (
            <Chip key={q} active={i === 0}>{q}</Chip>
          ))}
        </div>
      </div>

      <div className="glass" style={{ padding: 14 }}>
        <div className="eyebrow" style={{ marginBottom: 10 }}>Format</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 6 }}>
          {[
            { id: 'mp4', label: 'MP4' }, { id: 'mp3', label: 'MP3' },
            { id: 'wav', label: 'WAV' }, { id: 'gif', label: 'GIF' },
          ].map((f, i) => (
            <button key={f.id} style={{
              padding: '10px 0', textAlign: 'center',
              background: i === 0 ? 'var(--surface-strong)' : 'var(--surface-sunk)',
              border: `1px solid ${i === 0 ? 'var(--accent)' : 'var(--border)'}`,
              borderRadius: 10, fontSize: 12, fontFamily: 'var(--font-mono)',
              color: 'inherit',
            }}>{f.label}</button>
          ))}
        </div>
      </div>

      <div className="glass-strong" style={{ padding: 14, display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 500 }}>1.2 GB</div>
          <div style={{ fontSize: 10.5, color: 'var(--fg-subtle)' }}>~ 8s on Pro</div>
        </div>
        <button className="btn btn-accent" style={{ flex: 2 }}>
          <Icon name="download" size={14} /> Download
        </button>
      </div>
    </div>
    <MobileTabBar active="home" />
  </MobileShell>
);

/* ============================================================
   MOBILE — Library
   ============================================================ */
const LibraryMobile = ({ brandName = 'Loop' }) => (
  <MobileShell label="11 Library — Mobile">
    <MobileTopBar brandName={brandName} title="Library" />
    <div style={{ padding: '4px 16px 100px', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="glass" style={{ padding: '6px 8px 6px 14px', display: 'flex', alignItems: 'center', gap: 8, borderRadius: 999 }}>
        <Icon name="search" size={14} />
        <input style={{ background: 'transparent', border: 'none', outline: 'none', color: 'inherit', flex: 1, fontSize: 13 }} placeholder="Search 142 items…" />
      </div>

      <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 4 }}>
        {['All', 'Video', 'Audio', '4K+', 'Recent'].map((c, i) => (
          <Chip key={c} active={i === 0}>{c}</Chip>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        {[
          { t: 'Aurora over Reykjavík', m: '4K · 12:48' },
          { t: 'Patagonian winds', m: 'WAV · 42:10' },
          { t: 'Stoic morning', m: '1080p · 1h 12m' },
          { t: 'Lo-fi autumn 2026', m: 'MP3 · 2h 04m' },
          { t: 'How to film aurora', m: '1080p · 18:22' },
          { t: 'Tycho — Red Rocks', m: '1080p · 58:12' },
        ].map((it, i) => (
          <div key={i} className="glass" style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div className="placeholder-img" style={{
              aspectRatio: '16/10',
              background: `linear-gradient(${135 + i * 33}deg, oklch(0.55 0.14 ${(i * 60) % 360}), oklch(0.4 0.18 ${(i * 80 + 40) % 360}))`,
              border: 'none', borderRadius: 10,
            }} />
            <div style={{ fontSize: 11.5, fontWeight: 500, lineHeight: 1.25, display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{it.t}</div>
            <div style={{ fontSize: 10, color: 'var(--fg-subtle)', fontFamily: 'var(--font-mono)' }}>{it.m}</div>
          </div>
        ))}
      </div>
    </div>
    <MobileTabBar active="library" />
  </MobileShell>
);

Object.assign(window, {
  SettingsDesktop, LoginDesktop, PricingDesktop, ErrorDesktop,
  HomeMobile, AnalyzeMobile, LibraryMobile,
});
