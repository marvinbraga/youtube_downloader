# Wireframes — Coleções de vídeo (v1)

**UI:** Bootstrap 5.3.3 + Icons · jQuery · `--yd-*` tokens · light + dark · accent `#E63946` · Inter
**Prefix:** `yd-collection-*` (do **not** apply `yd-album-*` to these nodes)
**Cover:** **16:9** (video). Álbuns stay **1:1**.
**Play:** existing `#videoPlayer` on Vídeos. CTA **Reproduzir** = first ready episode.
**No new tabs.**

Reuse Álbuns *metrics* (radius 0.75rem, hover lift, hero backdrop blur 28px) with collection class names so Álbuns CSS does not shift.

---

## Screen: Vídeos — grouped library

```yaml
screen: Videos Library Grouped
route: /#video-pane
layout: full-width
ui_library: bootstrap-5.3.3
styling: web_client/css/styles.css (--yd-* tokens)

ascii_prototype:
  default: |
    ┌─────────────────────────────────────────────────────────────────┐
    │  [ existing #videoPlayer 16:9 ]                                 │
    │  Selecione um vídeo para reproduzir                             │
    ├─────────────────────────────────────────────────────────────────┤
    │  [🔍 Buscar vídeos…                                    ] [↻]    │
    │                                                                 │
    │  Coleções                                                       │
    │  ┌──────────────┐  ┌──────────────┐                             │
    │  │ [capa 16:9]  │  │ [capa 16:9]  │                             │
    │  │ Coleção      │  │ Coleção      │                             │
    │  │ Documentários│  │ Outra série  │                             │
    │  │ 30 vídeos    │  │ 8 vídeos     │                             │
    │  └──────────────┘  └──────────────┘                             │
    │                                                                 │
    │  Avulsos                                                        │
    │  ┌────────────────────────────────────────────────────────────┐ │
    │  │ ▶  Como a CABALA…     720p  45:12     [Pronto] [▶] [🗑]   │ │
    │  │ ▶  BARSI REVELA…      720p  12:04     [Pronto] [▶] [🗑]   │ │
    │  └────────────────────────────────────────────────────────────┘ │
    └─────────────────────────────────────────────────────────────────┘

  loading: |
    ┌─────────────────────────────────────────────────────────────────┐
    │  [ player ]                                                     │
    │  Coleções    ░░░░░  ░░░░░  ░░░░░                                │
    │  Avulsos     spinner “Carregando vídeos…”                       │
    └─────────────────────────────────────────────────────────────────┘

  empty_no_collections: |
    ┌─────────────────────────────────────────────────────────────────┐
    │  [ player ]                                                     │
    │  (sem heading Coleções)                                         │
    │  lista plana yd-media-item — UI atual                           │
    └─────────────────────────────────────────────────────────────────┘

  empty_all: |
    ┌─────────────────────────────────────────────────────────────────┐
    │  [ camera-video icon ]                                          │
    │  Nenhum vídeo encontrado                                        │
    │  Faça o download de um vídeo na aba Download                    │
    └─────────────────────────────────────────────────────────────────┘

  error: |
    ┌─────────────────────────────────────────────────────────────────┐
    │  ⚠ Não foi possível carregar os vídeos            [ Tentar ]    │
    └─────────────────────────────────────────────────────────────────┘

  desktop: |
    Player full width; collection grid auto-fill minmax(160px).
    Avulsos = existing list-group card.

  mobile: |
    Stack. Grid minmax(140px) ≤575px. No horizontal scroll. Titles ellipsis.

component_validation:
  verified_components:
    - card: existing .card / player block — do not replace
    - input-group: #searchVideoInput
    - button: btn-outline-secondary refresh
    - yd-media-item: Avulsos rows unchanged
    - yd-empty-state / spinner-border text-danger
  missing_components:
    - yd-collection-grid: clone .yd-album-grid
    - yd-collection-card: clone .yd-album-card; 16:9 cover
    - yd-collection-cover--card: aspect-ratio 16/9 (not 1/1)
    - section headings “Coleções” / “Avulsos”: h5 + small muted

components:
  - type: video
    id: videoPlayer
    note: Unchanged; stays mounted when opening a collection
  - type: button
    class: yd-collection-card
    label: "{title}"
    meta: "Coleção · N vídeos"
    action: open-collection
  - type: list
    id: videoListAvulsos
    item: yd-media-item
    action: playVideo if ready

states:
  loading:
    description: Skeleton collection cards; Avulsos spinner as today
  empty:
    description: Omit Coleções if none; omit Avulsos if none; full empty-state if no videos at all
  error:
    description: Alert + Tentar novamente (refreshVideoBtn)
  success:
    description: Cards + Avulsos; click card → collection detail
```

**Grouping rule:** `folder.kind=playlist` → card. No `folder_id` or generic folder → Avulsos. **Never** show these cards on Álbuns.

---

## Screen: Collection detail (Vídeos) — hero + episodes

Same chrome is reused in Pastas (items column). On Vídeos the player stays above.

```yaml
screen: Collection Detail
route: /#video-pane (collection open) | /#folders-pane (playlist folder selected)
layout: full-width
ui_library: bootstrap-5.3.3
styling: web_client/css/styles.css

ascii_prototype:
  default: |
    ┌─────────────────────────────────────────────────────────────────┐
    │  [◀ Voltar aos vídeos]     ← Pastas: breadcrumb Raiz / Nome     │
    │                                                                 │
    │  ┌─ yd-collection-hero ───────────────────────────────────────┐ │
    │  │  ~~~~ capa blur ~~~~                                       │ │
    │  │  ┌──────────┐   COLEÇÃO                                    │ │
    │  │  │ 16:9     │   Documentários Importantes                  │ │
    │  │  │ capa     │   30 vídeos · 12 prontos                     │ │
    │  │  └──────────┘   [ ▶ Reproduzir ]                           │ │
    │  └────────────────────────────────────────────────────────────┘ │
    │                                                                 │
    │  ┌─ episódios (ordem da playlist) ────────────────────────────┐ │
    │  │  1  Introdução…                         18:02  [Pronto] ▶  │ │
    │  │  2  As Origens…                         22:11  [Pronto] ▶  │ │
    │  │  3  ▓▓▓ 42%                             —      [Baixando]  │ │
    │  │  4  Infiltrando…                        —      [Pendente]  │ │
    │  │  5  (Video unavailable)                 —      [Erro]      │ │
    │  └────────────────────────────────────────────────────────────┘ │
    └─────────────────────────────────────────────────────────────────┘

  loading: |
    ┌─────────────────────────────────────────────────────────────────┐
    │  [◀ Voltar]                                                     │
    │  ░░░ capa  ░░░ título                                           │
    │  spinner “Carregando coleção…”                                  │
    └─────────────────────────────────────────────────────────────────┘

  empty: |
    ┌─────────────────────────────────────────────────────────────────┐
    │  COLEÇÃO / título / 0 vídeos   [ Reproduzir disabled ]          │
    │                                                                 │
    │         [ collection-play icon ]                                │
    │         Nenhum vídeo nesta coleção                              │
    └─────────────────────────────────────────────────────────────────┘

  no_ready: |
    Hero meta “30 vídeos · 0 prontos”
    [ Reproduzir ] disabled  title="Nenhum vídeo pronto ainda"
    Rows show Pendente / Baixando / Erro only

  error: |
    ┌─────────────────────────────────────────────────────────────────┐
    │  ⚠ Não foi possível abrir a coleção              [ Tentar ]     │
    └─────────────────────────────────────────────────────────────────┘

  playing: |
    Row 2: background accent-muted; play icon → pause not required
    #currentVideoTitle = episode title
    #videoLoadingOverlay then native controls

  desktop: |
    Hero: cover left (max ~280px wide, 16:9), text + CTA right (flex-md-row).
    Episode rows: index 2rem | title | duration | status | play.

  mobile: |
    Cover above title (flex-column). CTA full width. Index + title wrap;
    actions stay on the right. 320px no horizontal scroll.

component_validation:
  verified_components:
    - btn btn-outline-secondary btn-sm: Voltar (mirror #albumBackBtn)
    - btn btn-danger: Reproduzir (mirror #albumPlayAllBtn, different label)
    - card: hero + list
    - badges / yd-ring: getStatusBadge()
    - list-group + yd-scroll-container
  missing_components:
    - yd-collection-hero / __backdrop / __body
    - yd-collection-cover--lg: 16:9, ~280×158 desktop, ~100% width mobile
    - yd-collection-episode: clone yd-album-track (index, title, status, play)
    - Eyebrow: text-uppercase small text-secondary → “Coleção”
  do_not_port:
    - Tocar tudo, Atualizar artistas, Remover erros
    - Artist line as primary chrome
    - Sticky yd-album-player bar
    - Shuffle / prev / next / repeat

components:
  - type: button
    id: collectionBackBtn
    label: "Voltar aos vídeos"  # Pastas: rely on breadcrumb + Voltar pasta
    variant: outline
    action: close-collection
  - type: heading
    level: 3
    text: "{folder.name}"
  - type: text
    variant: label
    content: "Coleção"
  - type: text
    variant: caption
    content: "{n} vídeos"  # append " · {m} prontos" if m < n
  - type: button
    id: collectionPlayBtn
    label: "Reproduzir"
    icon: bi-play-fill
    variant: primary
    action: play-first-ready
    disabled_when: no ready episode
  - type: list
    class: yd-collection-episode
    fields: [index, title, duration?, status, play]
    order: playlist position ascending

states:
  loading:
    description: Skeleton hero; spinner in list; Voltar enabled
  empty:
    description: "Nenhum vídeo nesta coleção"
  error:
    description: Inline alert + retry
  success:
    description: Play in #videoPlayer; row is-playing
  disabled:
    description: Reproduzir aria-disabled until first ready
```

### Pastas placement (same hero)

```
┌──────── folder list (col-lg-4) ──┬── items (col-lg-8) ──────────────┐
│ Documentários Importantes        │  COLEÇÃO hero + episode list     │
│   Playlist                       │  (not generic checkboxes/move)   │
│ Outra pasta                      │                                  │
└──────────────────────────────────┴──────────────────────────────────┘
```

Clicking `kind=playlist` **replaces** the generic “Itens na Pasta” list with collection chrome. Edit/delete on the folder row stay as today. **No** album play button on this row.

Play from Pastas: switch to Vídeos + open this collection + `playVideo` (see user-flows.md).

---

## Visual distinction vs Álbuns (do not blur)

| | Álbuns | Coleção |
|--|--------|---------|
| Classes | `yd-album-*` | `yd-collection-*` |
| Cover | 1:1 | **16:9** |
| Eyebrow | Álbum | **Coleção** |
| CTA | Tocar tudo | **Reproduzir** |
| Count | N faixas | **N vídeos** |
| Player | Sticky audio bar | Existing `#videoPlayer` only |
| Tab | Álbuns | Pastas + Vídeos |

---

## Interaction notes

- Collection **card** = `<button type="button">` (keyboard, no nested buttons).
- Episode **play** = `btn-sm` `aria-label="Reproduzir {title}"`; whole ready row clickable except the play control (stopPropagation same as album tracks).
- Downloading: existing `buildRingProgress` in the status slot; do not invent a new progress widget.
- Focus order: Voltar → Reproduzir → episode 1 play → …
- `Escape` is not required to close (no modal); Voltar is enough.
- Do not autoplay on open unless the user came from **Reproduzir**.
