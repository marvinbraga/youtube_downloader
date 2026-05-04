/* =========================================================
   Loop — Screens part 1: Home, Analyze, Queue, Library
   ========================================================= */

const sampleVideo = {
  title: 'Northern Lights — Iceland in 4K HDR (Time-lapse Edition)',
  channel: 'Aurora Field Notes',
  duration: '12:48',
  views: '1.2M',
  thumb: 'gradient-1',
};

/* ============================================================
   1. HOME — desktop
   The first thing users see: paste URL, recent items, formats
   ============================================================ */
const HomeDesktop = ({ brandName = 'Loop', accent = 'Sources' }) => (
  <ScreenShell label="01 Home — Desktop" width={1280} height={820}>
    <TopNav active="home" brandName={brandName} />

    <main style={{
      flex: 1, display: 'grid',
      gridTemplateColumns: '1.4fr 1fr',
      gap: 20, minHeight: 0,
    }}>
      {/* LEFT — paste URL hero */}
      <section className="glass-strong" style={{
        padding: '48px 48px 32px',
        display: 'flex', flexDirection: 'column',
        gap: 28, position: 'relative', overflow: 'hidden',
      }}>
        <div className="eyebrow">Universal video downloader</div>
        <h1 className="serif" style={{
          margin: 0, fontSize: 64, lineHeight: 1.02,
          fontWeight: 400, letterSpacing: '-0.03em',
        }}>
          Save anything<br />
          <em style={{ fontStyle: 'italic', color: 'var(--accent)' }}>worth keeping.</em>
        </h1>
        <p style={{
          margin: 0, fontSize: 16, lineHeight: 1.5,
          color: 'var(--fg-muted)', maxWidth: 460,
        }}>
          Paste a link from any of 1,200+ supported sources.
          We'll handle quality, format, captions, and playlists.
        </p>

        {/* URL paste card */}
        <div className="glass" style={{
          padding: 8, display: 'flex', alignItems: 'center', gap: 8,
          borderRadius: 'var(--r-pill)',
          marginTop: 8,
        }}>
          <div style={{ paddingLeft: 16, color: 'var(--fg-subtle)' }}>
            <Icon name="link" size={18} />
          </div>
          <input className="input" style={{
            border: 'none', background: 'transparent', height: 48,
            fontSize: 15, padding: '0 8px', flex: 1,
          }} placeholder="Paste a video, channel, or playlist URL…" defaultValue="https://example.video/watch?v=aurora-iceland-4k" />
          <button className="btn btn-accent btn-lg" style={{ height: 48 }}>
            <Icon name="sparkles" size={16} /> Analyze
          </button>
        </div>

        {/* clipboard hint + supported sources */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: 'var(--fg-muted)', fontSize: 13 }}>
          <span className="tag"><kbd style={{ fontFamily: 'inherit' }}>⌘V</kbd> from clipboard</span>
          <span>·</span>
          <span>{accent}: video platforms, social, podcasts, live VODs</span>
        </div>

        {/* feature row */}
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 12, marginTop: 'auto',
        }}>
          {[
            { icon: 'film', label: 'Up to 8K', sub: 'HDR · 60fps' },
            { icon: 'music', label: 'Audio extract', sub: 'MP3 · WAV · FLAC' },
            { icon: 'list', label: 'Playlists', sub: 'Bulk · Channel' },
            { icon: 'captions', label: 'Captions', sub: '40+ languages' },
          ].map(f => (
            <div key={f.label} className="glass-sunk" style={{ padding: 14 }}>
              <Icon name={f.icon} size={18} stroke={1.4} />
              <div style={{ marginTop: 8, fontSize: 13, fontWeight: 500 }}>{f.label}</div>
              <div style={{ fontSize: 11, color: 'var(--fg-subtle)', marginTop: 2, fontFamily: 'var(--font-mono)' }}>{f.sub}</div>
            </div>
          ))}
        </div>
      </section>

      {/* RIGHT — recent + queue */}
      <aside style={{ display: 'flex', flexDirection: 'column', gap: 16, minHeight: 0 }}>
        {/* Quick stats */}
        <div className="glass" style={{ padding: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14 }}>
            <div className="eyebrow">This month</div>
            <a style={{ fontSize: 12, color: 'var(--fg-muted)', textDecoration: 'none' }}>View all →</a>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8 }}>
            <StatPill label="Saved" value="142" />
            <StatPill label="Storage" value="38.4 GB" />
            <StatPill label="Hours" value="22:14" />
          </div>
        </div>

        {/* Active queue */}
        <div className="glass" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)', boxShadow: '0 0 10px var(--accent)' }} />
              <span style={{ fontSize: 13, fontWeight: 500 }}>2 in progress</span>
            </div>
            <button className="btn btn-sm btn-ghost" style={{ fontSize: 12, padding: '0 8px' }}>Pause all</button>
          </div>
          {[
            { title: 'Northern Lights — Iceland 4K HDR', q: '2160p · MP4', pct: 64, eta: '00:38 left' },
            { title: 'Tycho — Live at Red Rocks 2024', q: '1080p · MP4', pct: 22, eta: '03:12 left' },
          ].map((d, i) => (
            <div key={i} className="glass-sunk" style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', gap: 10 }}>
                <div className="placeholder-img" style={{ width: 64, height: 40, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{d.title}</div>
                  <div style={{ fontSize: 11, color: 'var(--fg-subtle)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                    {d.q} · {d.eta}
                  </div>
                </div>
                <span className="mono" style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{d.pct}%</span>
              </div>
              <ProgressBar value={d.pct} />
            </div>
          ))}
        </div>

        {/* Recent */}
        <div className="glass" style={{ padding: 18, flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <div className="eyebrow">Recent saves</div>
            <a style={{ fontSize: 12, color: 'var(--fg-muted)', textDecoration: 'none' }}>Library →</a>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, overflow: 'auto' }} className="scroll-y">
            {[
              { t: 'How to film aurora — gear & settings', m: '2160p · 18 min', d: 'Yesterday' },
              { t: 'Field recording: Patagonian winds', m: 'WAV · 42 min', d: '2 days ago' },
              { t: 'Stoic morning routine — full talk', m: '1080p · 1h 12m', d: '4 days ago' },
              { t: 'Lo-fi study mix — autumn 2026', m: 'MP3 · 2h 04m', d: '1 week ago' },
            ].map((r, i) => (
              <div key={i} style={{
                display: 'flex', gap: 10, alignItems: 'center', padding: '8px 4px',
                borderBottom: i < 3 ? '1px solid var(--border)' : 'none',
              }}>
                <div className="placeholder-img" style={{ width: 44, height: 28, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.t}</div>
                  <div style={{ fontSize: 11, color: 'var(--fg-subtle)', fontFamily: 'var(--font-mono)' }}>{r.m}</div>
                </div>
                <span style={{ fontSize: 11, color: 'var(--fg-subtle)' }}>{r.d}</span>
              </div>
            ))}
          </div>
        </div>
      </aside>
    </main>
  </ScreenShell>
);

/* ============================================================
   2. ANALYZE — desktop
   After URL paste: video preview, choose quality/format/range
   ============================================================ */
const AnalyzeDesktop = ({ brandName = 'Loop' }) => {
  const [quality, setQuality] = React.useState('2160p');
  const [format, setFormat] = React.useState('mp4');

  return (
    <ScreenShell label="02 Analyze — Desktop" width={1280} height={820}>
      <TopNav active="home" brandName={brandName} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: 'var(--fg-muted)', fontSize: 13 }}>
        <Icon name="link" size={14} />
        <span className="mono" style={{ fontSize: 12 }}>example.video/watch?v=aurora-iceland-4k</span>
        <span style={{ flex: 1 }} />
        <button className="btn btn-sm btn-ghost"><Icon name="refresh" size={14} /> Re-analyze</button>
        <button className="btn btn-sm btn-ghost"><Icon name="close" size={14} /> Cancel</button>
      </div>

      <main style={{
        flex: 1, display: 'grid',
        gridTemplateColumns: '1.5fr 1fr',
        gap: 20, minHeight: 0,
      }}>
        {/* LEFT — preview + meta */}
        <section className="glass-strong" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 18 }}>
          {/* Preview */}
          <div className="placeholder-img" style={{
            aspectRatio: '16/9',
            background: 'linear-gradient(135deg, oklch(0.45 0.15 280), oklch(0.55 0.18 220), oklch(0.5 0.12 320))',
            border: '1px solid var(--border)',
            position: 'relative',
            color: 'oklch(1 0 0 / 0.6)',
          }}>
            <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>
              <button className="glass-strong" style={{
                width: 64, height: 64, borderRadius: '50%',
                display: 'grid', placeItems: 'center',
                color: 'var(--fg)', border: 'none', cursor: 'pointer',
              }}>
                <Icon name="play" size={22} />
              </button>
            </div>
            <div style={{
              position: 'absolute', bottom: 12, right: 12,
              padding: '4px 10px', borderRadius: 6,
              background: 'oklch(0 0 0 / 0.6)', backdropFilter: 'blur(8px)',
              color: 'white', fontSize: 12, fontFamily: 'var(--font-mono)',
            }}>{sampleVideo.duration}</div>
          </div>

          {/* Title */}
          <div>
            <h2 className="serif" style={{ margin: 0, fontSize: 28, lineHeight: 1.15, letterSpacing: '-0.02em', fontWeight: 400 }}>
              {sampleVideo.title}
            </h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8, fontSize: 13, color: 'var(--fg-muted)' }}>
              <Avatar initials="AF" size={22} hue={200} />
              <span style={{ color: 'var(--fg)' }}>{sampleVideo.channel}</span>
              <span className="dot" />
              <span>{sampleVideo.views} views</span>
              <span className="dot" />
              <span>Uploaded Mar 12, 2026</span>
            </div>
          </div>

          {/* Trim */}
          <div className="glass-sunk" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 500 }}>
                <Icon name="scissors" size={14} /> Trim range
              </div>
              <span className="tag" style={{ height: 22 }}>full · 12:48</span>
            </div>
            <div style={{ position: 'relative', height: 36 }}>
              <div style={{
                position: 'absolute', inset: 0,
                background: `repeating-linear-gradient(90deg,
                  var(--surface-strong) 0 2px,
                  transparent 2px 5px)`,
                borderRadius: 6,
                opacity: 0.5,
              }} />
              <div style={{
                position: 'absolute', top: 0, bottom: 0, left: '8%', right: '12%',
                background: 'linear-gradient(90deg, var(--accent), oklch(0.7 0.18 calc(var(--accent-h) + 60)))',
                opacity: 0.3,
                borderRadius: 6,
                border: '1px solid var(--accent)',
              }} />
              {['8%', '88%'].map(left => (
                <div key={left} style={{
                  position: 'absolute', top: -4, bottom: -4, left,
                  width: 4, background: 'var(--fg)', borderRadius: 2,
                }} />
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--fg-muted)' }}>
              <span>00:00</span>
              <span style={{ color: 'var(--fg)' }}>01:02 → 11:16</span>
              <span>12:48</span>
            </div>
          </div>
        </section>

        {/* RIGHT — options */}
        <aside style={{ display: 'flex', flexDirection: 'column', gap: 14, minHeight: 0, overflow: 'auto' }} className="scroll-y">
          <div className="glass" style={{ padding: 18 }}>
            <div className="eyebrow" style={{ marginBottom: 12 }}>Quality</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {['4320p', '2160p', '1440p', '1080p', '720p', '480p'].map(q => (
                <Chip key={q} active={quality === q} onClick={() => setQuality(q)}>{q}</Chip>
              ))}
            </div>
          </div>

          <div className="glass" style={{ padding: 18 }}>
            <div className="eyebrow" style={{ marginBottom: 12 }}>Format</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
              {[
                { id: 'mp4', label: 'MP4', sub: 'Video · H.264', icon: 'film' },
                { id: 'mp3', label: 'MP3', sub: 'Audio · 320kbps', icon: 'music' },
                { id: 'wav', label: 'WAV', sub: 'Audio · lossless', icon: 'music' },
                { id: 'gif', label: 'GIF', sub: 'Loop · max 30s', icon: 'film' },
              ].map(f => (
                <button key={f.id} onClick={() => setFormat(f.id)} style={{
                  textAlign: 'left', padding: 12,
                  background: format === f.id ? 'var(--surface-strong)' : 'var(--surface-sunk)',
                  border: `1px solid ${format === f.id ? 'var(--accent)' : 'var(--border)'}`,
                  borderRadius: 12, cursor: 'pointer',
                  color: 'inherit',
                }}>
                  <Icon name={f.icon} size={15} />
                  <div style={{ fontSize: 13, fontWeight: 500, marginTop: 6 }}>{f.label}</div>
                  <div style={{ fontSize: 10.5, color: 'var(--fg-subtle)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>{f.sub}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="glass" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div className="eyebrow">Extras</div>
            {[
              { l: 'Embed captions', s: 'EN, PT-BR, ES, FR', on: true },
              { l: 'Save thumbnail', s: 'Highest resolution', on: true },
              { l: 'Save metadata', s: '.json sidecar', on: false },
              { l: 'Loudness normalize', s: '−14 LUFS', on: false },
            ].map((t, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderTop: i ? '1px solid var(--border)' : 'none' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13 }}>{t.l}</div>
                  <div style={{ fontSize: 11, color: 'var(--fg-subtle)', fontFamily: 'var(--font-mono)', marginTop: 1 }}>{t.s}</div>
                </div>
                <div style={{
                  width: 36, height: 22, borderRadius: 999,
                  background: t.on ? 'var(--accent)' : 'var(--surface-sunk)',
                  border: '1px solid var(--border)', position: 'relative',
                  transition: 'background 200ms',
                }}>
                  <div style={{
                    position: 'absolute', top: 2, left: t.on ? 16 : 2,
                    width: 16, height: 16, borderRadius: '50%',
                    background: 'white', boxShadow: '0 1px 3px oklch(0 0 0 / 0.2)',
                    transition: 'left 200ms',
                  }} />
                </div>
              </div>
            ))}
          </div>

          {/* Estimate + action */}
          <div className="glass-strong" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <div className="eyebrow">Estimated</div>
              <span className="tag" style={{ height: 22 }}>~ 8s on Pro</span>
            </div>
            <div style={{ display: 'flex', gap: 16 }}>
              <div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 22, fontWeight: 500 }}>1.2 GB</div>
                <div style={{ fontSize: 11, color: 'var(--fg-subtle)' }}>file size</div>
              </div>
              <div style={{ width: 1, background: 'var(--border)' }} />
              <div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 22, fontWeight: 500 }}>2160p</div>
                <div style={{ fontSize: 11, color: 'var(--fg-subtle)' }}>HDR · 60fps</div>
              </div>
            </div>
            <button className="btn btn-accent btn-lg" style={{ marginTop: 4 }}>
              <Icon name="download" size={16} /> Add to queue
            </button>
          </div>
        </aside>
      </main>
    </ScreenShell>
  );
};

/* ============================================================
   3. QUEUE — desktop
   ============================================================ */
const QueueDesktop = ({ brandName = 'Loop' }) => (
  <ScreenShell label="03 Queue — Desktop" width={1280} height={820}>
    <TopNav active="queue" brandName={brandName} />

    {/* Header strip */}
    <div className="glass" style={{ padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 16 }}>
      <div>
        <h2 className="serif" style={{ margin: 0, fontSize: 26, fontWeight: 400 }}>Download queue</h2>
        <div style={{ fontSize: 12, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
          2 active · 3 queued · 1 failed
        </div>
      </div>
      <div style={{ flex: 1 }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', borderRadius: 999, background: 'var(--surface-sunk)', border: '1px solid var(--border)' }}>
        <Icon name="zap" size={14} stroke={2} />
        <span style={{ fontSize: 12 }}>Network</span>
        <span className="mono" style={{ fontSize: 12, color: 'var(--fg)' }}>84 Mb/s</span>
      </div>
      <button className="btn btn-sm btn-glass"><Icon name="pause" size={13} /> Pause all</button>
      <button className="btn btn-sm btn-glass"><Icon name="trash" size={13} /> Clear done</button>
      <button className="btn btn-sm btn-accent"><Icon name="plus" size={13} /> Add</button>
    </div>

    <main className="glass-strong" style={{ flex: 1, padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* Table head */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '60px 1.6fr 0.8fr 0.6fr 1fr 0.5fr 40px',
        padding: '12px 20px',
        borderBottom: '1px solid var(--border)',
        fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase',
        color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)',
      }}>
        <span></span>
        <span>Title</span>
        <span>Format</span>
        <span>Size</span>
        <span>Progress</span>
        <span>Status</span>
        <span></span>
      </div>

      {/* Rows */}
      <div style={{ flex: 1, overflow: 'auto' }} className="scroll-y">
        {[
          { t: 'Northern Lights — Iceland 4K HDR', c: 'Aurora Field Notes', q: '2160p MP4', size: '1.2 GB', pct: 64, status: 'downloading', eta: '00:38' },
          { t: 'Tycho — Live at Red Rocks 2024', c: 'Tycho Music', q: '1080p MP4', size: '840 MB', pct: 22, status: 'downloading', eta: '03:12' },
          { t: 'Field recording — Atlas storm cell', c: 'Solitary Wave', q: 'WAV 24bit', size: '720 MB', pct: 0, status: 'queued', eta: '—' },
          { t: 'How I edit cinematic b-roll (full course)', c: 'Frame & Form', q: '1440p MP4', size: '3.4 GB', pct: 0, status: 'queued', eta: '—' },
          { t: 'Tiny Desk — Kelsey Lu (audio)', c: 'NPR Music', q: 'MP3 320', size: '52 MB', pct: 100, status: 'done', eta: '—' },
          { t: 'Why dolphins sleep with one eye open', c: 'Wildlife Atlas', q: '1080p MP4', size: '—', pct: 12, status: 'failed', eta: '—' },
          { t: 'Building a Faraday cage from scratch', c: 'EE Lab', q: '720p MP4', size: '184 MB', pct: 100, status: 'done', eta: '—' },
        ].map((r, i) => {
          const statusColor = {
            downloading: 'var(--accent)', queued: 'var(--fg-muted)',
            done: 'oklch(0.65 0.16 150)', failed: 'oklch(0.65 0.18 25)',
          }[r.status];
          return (
            <div key={i} style={{
              display: 'grid',
              gridTemplateColumns: '60px 1.6fr 0.8fr 0.6fr 1fr 0.5fr 40px',
              padding: '14px 20px',
              borderBottom: '1px solid var(--border)',
              alignItems: 'center', gap: 12,
              fontSize: 13,
            }}>
              <div className="placeholder-img" style={{ width: 48, height: 30 }} />
              <div style={{ minWidth: 0 }}>
                <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontWeight: 500 }}>{r.t}</div>
                <div style={{ fontSize: 11, color: 'var(--fg-subtle)' }}>{r.c}</div>
              </div>
              <span className="mono" style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{r.q}</span>
              <span className="mono" style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{r.size}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <ProgressBar value={r.pct} color={r.status === 'failed' ? 'oklch(0.65 0.18 25)' : undefined} />
                <span className="mono" style={{ fontSize: 11, color: 'var(--fg-muted)', width: 40 }}>{r.pct}%</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: statusColor, boxShadow: r.status === 'downloading' ? `0 0 8px ${statusColor}` : 'none' }} />
                <span style={{ fontSize: 12, textTransform: 'capitalize' }}>{r.status}</span>
              </div>
              <button className="btn btn-sm btn-ghost" style={{ width: 32, padding: 0 }}>
                <Icon name="moreHorizontal" size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </main>
  </ScreenShell>
);

/* ============================================================
   4. LIBRARY — desktop
   ============================================================ */
const LibraryDesktop = ({ brandName = 'Loop' }) => {
  const items = [
    { t: 'Aurora over Reykjavík', c: 'Aurora Field Notes', d: '12:48', size: '1.2 GB', tag: '4K' },
    { t: 'Patagonian winds — field session', c: 'Solitary Wave', d: '42:10', size: '720 MB', tag: 'WAV' },
    { t: 'Stoic morning — full talk', c: 'Modern Stoa', d: '1:12:04', size: '480 MB', tag: '1080p' },
    { t: 'Lo-fi study mix — autumn 2026', c: 'Hush Hour', d: '2:04:30', size: '210 MB', tag: 'MP3' },
    { t: 'How to film aurora — gear & settings', c: 'Aurora Field Notes', d: '18:22', size: '640 MB', tag: '1080p' },
    { t: 'Tycho — Live at Red Rocks 2024', c: 'Tycho Music', d: '58:12', size: '840 MB', tag: '1080p' },
    { t: 'Tiny Desk — Kelsey Lu', c: 'NPR Music', d: '15:48', size: '52 MB', tag: 'MP3' },
    { t: 'Why dolphins sleep with one eye open', c: 'Wildlife Atlas', d: '08:14', size: '184 MB', tag: '1080p' },
    { t: 'Building a Faraday cage', c: 'EE Lab', d: '22:18', size: '210 MB', tag: '720p' },
    { t: 'Late-night Tokyo drive', c: 'Neon Drift', d: '46:00', size: '1.6 GB', tag: '4K' },
  ];
  return (
    <ScreenShell label="04 Library — Desktop" width={1280} height={820}>
      <TopNav active="library" brandName={brandName} />

      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16 }}>
        <div>
          <div className="eyebrow">Your collection</div>
          <h2 className="serif" style={{ margin: '6px 0 0', fontSize: 36, fontWeight: 400, letterSpacing: '-0.02em' }}>
            Library
          </h2>
        </div>
        <div style={{ flex: 1 }} />
        <div className="glass" style={{ padding: '6px 8px 6px 14px', display: 'flex', alignItems: 'center', gap: 8, borderRadius: 999, width: 280 }}>
          <Icon name="search" size={14} />
          <input style={{ background: 'transparent', border: 'none', outline: 'none', color: 'inherit', flex: 1, fontSize: 13 }} placeholder="Search 142 items…" />
        </div>
        <button className="btn btn-sm btn-glass"><Icon name="grid" size={13} /> Grid</button>
        <button className="btn btn-sm btn-glass"><Icon name="folder" size={13} /> Collections</button>
      </div>

      {/* Filter chips */}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        {['All', 'Video', 'Audio', '4K+', 'Recent', 'Long-form', 'Music', 'Field recordings'].map((c, i) => (
          <Chip key={c} active={i === 0}>{c}</Chip>
        ))}
        <span style={{ flex: 1 }} />
        <span className="tag">142 items · 38.4 GB</span>
      </div>

      {/* Grid */}
      <div style={{
        flex: 1, display: 'grid',
        gridTemplateColumns: 'repeat(5, 1fr)',
        gap: 14, overflow: 'auto', paddingRight: 4,
      }} className="scroll-y">
        {items.map((it, i) => (
          <div key={i} className="glass" style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 8, cursor: 'pointer' }}>
            <div className="placeholder-img" style={{
              aspectRatio: '16/10',
              background: `linear-gradient(${135 + i * 23}deg, oklch(0.55 0.14 ${(i * 50) % 360}), oklch(0.4 0.18 ${(i * 70 + 40) % 360}))`,
              border: 'none',
              position: 'relative',
            }}>
              <span style={{
                position: 'absolute', bottom: 6, right: 6,
                fontFamily: 'var(--font-mono)', fontSize: 10,
                background: 'oklch(0 0 0 / 0.55)', color: 'white',
                padding: '2px 6px', borderRadius: 4,
              }}>{it.d}</span>
              <span style={{
                position: 'absolute', top: 6, left: 6,
                fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '0.1em',
                background: 'oklch(1 0 0 / 0.18)', backdropFilter: 'blur(6px)',
                color: 'white', padding: '2px 6px', borderRadius: 4, border: '1px solid oklch(1 0 0 / 0.2)',
              }}>{it.tag}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <div style={{ fontSize: 13, fontWeight: 500, lineHeight: 1.25, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                {it.t}
              </div>
              <div style={{ fontSize: 11, color: 'var(--fg-subtle)', display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)' }}>
                <span>{it.c}</span>
                <span>{it.size}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </ScreenShell>
  );
};

Object.assign(window, {
  HomeDesktop, AnalyzeDesktop, QueueDesktop, LibraryDesktop,
});
