# UX Acceptance Criteria — Coleções de vídeo (v1)

**Feature:** Collection/series view for `kind=playlist` folders (e.g. *Documentários Importantes*)
**Mode:** Gate 1 (UX validation)
**Stack:** vanilla JS + jQuery + Bootstrap 5.3.3 + Bootstrap Icons + `web_client/css/styles.css` tokens (`--yd-*`)
**Not in scope:** React, new tabs, Álbuns music player, sequential play-all queue

---

## UX RESEARCH SUMMARY

The user already downloaded a YouTube **video** playlist into a Pastas folder (`kind=playlist`, cover, ordered items). Today those episodes dump into a **flat Vídeos list**, while Álbuns is a **music** player (`kind=album`, faixas, Tocar tudo). Putting documentaries in Álbuns would be the wrong model (empty audio, wrong chrome). v1 treats the existing playlist folder as a **Coleção**: cover, episode order, open from Pastas, grouped on Vídeos — never in Álbuns.

## USER PROBLEM VALIDATION

### Problem Statement

- **Who:** The app owner (personal media library): downloads documentary/series playlists as video, and music playlists as albums.
- **What:** Video playlist items are a flat list; there is no series chrome (cover, order, play-from-folder). The only grouped player is Álbuns, which is audio-only.
- **When:** After `POST /video/playlist` (folder created immediately; episodes still downloading).
- **Impact:** Cannot browse *Documentários Importantes* as a series; risk of “open as album” which shows 0 faixas.

### Evidence

- Live download: folder **Documentários Importantes**, `kind=playlist`, ~30 videos queued; Álbuns (`GET /albums`) only returns `kind=album` and counts **audios**.
- Current UI: **Baixar Vídeo** playlist → Pastas + flat Vídeos. **Baixar Áudio** playlist → Álbuns.
- Pastas already lists the folder (`description` may be `Playlist`); click opens a generic item list, not a collection hero.
- Video `<video>` player lives on the Vídeos tab; `onended` only revokes the blob — **no sequential queue**.

### Validation Status

**VALIDATED** — problem is the current product behavior; success is grouping + collection chrome without touching Álbuns.

### Success metrics (v1)

| Metric | Target |
|--------|--------|
| Open collection + play a ready episode from Pastas | ≤ 3 clicks |
| Open collection + play a ready episode from Vídeos | ≤ 3 clicks |
| *Documentários Importantes* visible in Álbuns | **0** |
| Vídeos tab with no `kind=playlist` folders | Unchanged flat list (no extra chrome) |

---

## PERSONAS

### Persona 1: Arquivista

- **Role:** Sole user; downloads talks, documentaries, and music into one library.
- **Goals:** Keep **series** together with cover + order; keep **music** in Álbuns; play a ready episode without hunting the flat list.
- **Pain Points:** Playlist videos look like unrelated files; Álbuns is the only “grouped” UI and is the wrong place for video.
- **Quote:** “Isso é uma coleção de documentários, não um álbum.”

## JOBS TO BE DONE

### Job 1: Browse a video playlist as a series

**Statement:** When I have downloaded a YouTube video playlist, I want to open it as a **Coleção** with cover and episode order, so I can watch from the first ready episode without mixing it into Álbuns.

- **Functional:** See cover, count, ordered episodes, status, play.
- **Emotional:** Series feels curated, not dumped.

### Job 2: Keep music and video series apart

**Statement:** When I open Álbuns, I want only audio albums, so I never land on an empty music player for documentaries.

- **Functional:** `kind=playlist` never renders in Álbuns.
- **Emotional:** Trust that Álbuns stays a music player.

---

## UI CONFIGURATION (existing app — do not invent a new system)

| Token | Value |
|-------|--------|
| UI library | Bootstrap 5.3.3 + Bootstrap Icons 1.11 |
| Script | jQuery in `web_client/js/app.js` (not React) |
| Styling | `--yd-*` tokens, light + dark (`data-theme`) |
| Brand | `--yd-accent-primary: #E63946` |
| Type | Inter (UI) + JetBrains Mono (paths) |
| A11y | WCAG 2.1 AA |
| Layout | Desktop-first (existing Pastas 4+8 columns; albums grid `minmax(160px)`) |

**Semantic tokens only:** `var(--yd-bg-surface)`, `var(--yd-text-primary)`, `btn-danger` — not raw one-off hex in new collection CSS.

**Class prefix:** `yd-collection-*` (copy Álbuns *metrics* if useful). **Do not** reuse `yd-album-*` on collection nodes (Álbuns must not restyle).

---

## COPY RULES

| Surface | Word |
|---------|------|
| Collection chrome (eyebrow, cards, hero) | **Coleção** |
| Primary CTA | **Reproduzir** (not Tocar tudo) |
| Count | **N vídeo(s)** (not faixas) |
| Empty list | **Nenhum vídeo nesta coleção** |
| Ungrouped videos (Vídeos tab) | **Avulsos** |
| Pastas folder **meta** | May still show `Playlist` (folder `description`) |
| Álbuns | Unchanged; no playlist folder there |

Do not use **Álbum** or **Playlist** in the collection hero eyebrow.

---

## DATA CONTRACT (UX → implementers)

Client grouping needs these fields (join on the client if the API does not yet send `folder_kind`):

| Field | Use |
|-------|-----|
| `folder.kind === "playlist"` | Collection (not album, not generic folder) |
| `folder.cover_url` | Hero + card; fallback `i.ytimg.com/vi/{first_youtube_id}/hqdefault.jpg`; else `bi-collection-play` |
| `video.folder_id` | Membership |
| `folder_kind` or folder join | `playlist` → collection; missing/`folder` → **Avulsos** |
| Episode order | Playlist position (1-based). Videos have **no** `track_number` today — v1 UX still requires stable order (add `track_number` on videos **or** equivalent `episode_number`). Fallback: `created_date` only if position is unavailable, and show a note is **not** required in UI. |
| `download_status` / `download_progress` | Same badges/rings as Vídeos (`getStatusBadge`) |

`GET /albums` already filters `kind=album`. Keep the Pastas guard: `kind=playlist` must **not** get the album play button (legacy `icon === 'playlist'` heuristic already excludes `kind === 'playlist'`).

---

## UX ACCEPTANCE CRITERIA

### Functional (P0)

- [ ] No new top-level tab. Collection lives in **Pastas** and **Vídeos** only.
- [ ] `kind=playlist` folders **never** appear in Álbuns (grid, search, play-all).
- [ ] Clicking a `kind=playlist` folder in Pastas opens collection chrome: cover, title, **Coleção**, `N vídeos` (+ “M prontos” if M < N), **Reproduzir**, ordered episode list.
- [ ] **Reproduzir** plays the **first episode with `download_status=ready`** in the **existing** `#videoPlayer` on the Vídeos tab (switch tab if the user is on Pastas). Disabled when no ready episode.
- [ ] Clicking a ready episode (row or play control) plays that episode in `#videoPlayer`. Not-ready rows are not playable.
- [ ] v1 does **not** add shuffle, repeat, next/prev bar, or auto-advance (current `onended` has no queue).
- [ ] Vídeos tab: videos in `kind=playlist` folders are **grouped** into collection cards (cover + title + count). Clicking a card opens the **same** collection view (hero + episodes) under the existing player.
- [ ] Videos with no folder **or** a generic `kind=folder` stay in a flat **Avulsos** list below (existing `yd-media-item` row).
- [ ] If there are zero playlist collections, Vídeos looks as today (no Coleções heading).
- [ ] If there are zero avulsos, hide the Avulsos section (do not show an empty state for it).
- [ ] Empty collection body copy: **Nenhum vídeo nesta coleção**.
- [ ] Downloading/pending/error episodes use the same status treatment as the rest of the app (ring while in `activeDownloads`, badges Pronto / Baixando / Pendente / Erro).
- [ ] Play errors stay on the existing toast: “Erro ao reproduzir vídeo” / “Não autenticado”.
- [ ] Collection load failure: inline error + **Tentar novamente** (do not blank the whole app).

### Usability (P1)

- [ ] Primary action **Reproduzir** is `btn btn-danger` (same prominence as Tocar tudo / Baixar).
- [ ] Collection cards are full-card hit targets (`<button type="button">`), like `.yd-album-card`.
- [ ] Pastas breadcrumb still works (Raiz → folder name); **Voltar** returns to the folder list / Vídeos library, not Álbuns.
- [ ] Search on Vídeos: match collection **title** (show card) **or** episode title (still show parent card) **or** avulso fields (existing `SEARCH_FIELDS`). Empty search copy matches existing “Nenhum resultado para …”.
- [ ] User can complete “open *Documentários Importantes* and play first ready episode” in **3 steps or fewer** from Pastas or Vídeos.
- [ ] Loading feedback within 100ms of click (spinner/skeleton; disable **Reproduzir** while resolving the first ready id).
- [ ] No “ver como álbum”, convert-to-album, or kind editor.

### Accessibility (P1 — WCAG AA)

- [ ] Keyboard: tab to collection cards, **Reproduzir**, episode play, Voltar; Enter/Space activates.
- [ ] Visible focus (existing Bootstrap / `:focus-visible`).
- [ ] Focus order: Voltar → hero CTA → episode rows (play then title).
- [ ] Cover images: `alt="Capa da coleção {title}"`; decorative backdrop `alt=""`.
- [ ] Status not color-only (badge text + icon, same as today).
- [ ] Text contrast ≥ 4.5:1 (`--yd-text-primary` / `--yd-text-secondary` on `--yd-bg-surface`); large title ≥ 3:1.
- [ ] **Reproduzir** disabled has `aria-disabled="true"` and `title`/`aria-label` explaining why (e.g. “Nenhum vídeo pronto ainda”).
- [ ] Episode play buttons: `aria-label="Reproduzir {title}"`; disabled when not ready.
- [ ] Status / play start announced via existing toast (`aria-live`) and video title in `#currentVideoTitle`.
- [ ] Headings: pane keeps one `h4`/`h5` pattern; collection title is `h3` in hero (same as album detail).
- [ ] `lang="pt-BR"` unchanged.

### Responsive (P2) — desktop-first, must not break ~320px

- [ ] Pastas: existing `col-lg-4` / `col-lg-8` stack; hero cover stacks above title (`flex-column flex-md-row`), same as album hero.
- [ ] Collection grid: `repeat(auto-fill, minmax(160px, 1fr))`; at `≤575px` `minmax(140px)` like albums.
- [ ] **Cover aspect 16:9** (video), not 1:1 album square — this is the visual distinction from Álbuns.
- [ ] No horizontal scroll at 320px; titles truncate with `text-truncate` + `title` tooltip.
- [ ] Touch targets: **Reproduzir** and collection cards ≥ 44×44px; episode play may match existing `yd-action-btn` size.
- [ ] Existing `#videoPlayer` stays 16:9, full width of the Vídeos pane.

### Performance (P3)

- [ ] Collection cards use `cover_url` CSS background (same as albums); do not load every episode thumbnail in the library grid.
- [ ] Opening a collection does not remount a second `<video>`; reuse `#videoPlayer`.
- [ ] No layout jump of the player when switching library ↔ collection on Vídeos.

---

## UI STATES

### Collection card (Vídeos library)

| State | Trigger | Visual | Interaction |
|-------|---------|--------|-------------|
| Default | Playlist folder with ≥0 videos | 16:9 cover, title, `N vídeos`, eyebrow Coleção | Click → collection view |
| Loading | First paint of Vídeos | Skeleton cards (2–4) in `yd-collection-grid` | None |
| Empty library | No `kind=playlist` | Section omitted | — |
| Search miss | Query matches neither card nor avulso | Existing empty search state | Limpar busca |
| Error | Folders/videos fetch fail | Existing empty + toast; **Tentar novamente** via refresh | Refresh |

### Collection hero

| State | Trigger | Visual | Interaction |
|-------|---------|--------|-------------|
| Default | Folder loaded, ≥1 ready | Cover, **Coleção**, title, `N vídeos`, **Reproduzir** enabled | Reproduzir → first ready |
| Partial | Some downloading | Meta `N vídeos · M prontos`; rings on rows | Reproduzir uses first ready |
| No ready | All pending/downloading/error | **Reproduzir** disabled + tooltip | Wait / play later |
| Empty | 0 videos in folder | Hero + **Nenhum vídeo nesta coleção** | Voltar |
| Cover missing | No `cover_url` / youtube_id | `bi-collection-play` on `--yd-bg-overlay` | — |
| Loading | Opening folder | Spinner in episode list; hero title may show folder name from list cache | Voltar still works |
| Error | `/folders/{id}/items` fail | Alert + Tentar novamente | Retry |

### Episode row

| State | Trigger | Visual | Interaction |
|-------|---------|--------|-------------|
| Ready | `download_status=ready` | Index, title, duration optional, play enabled | Click / play → `#videoPlayer` |
| Downloading | In queue / `activeDownloads` | Ring progress (existing) | Play disabled |
| Pending | Queued, 0% | Badge Pendente | Play disabled |
| Error | Failed download | Badge Erro | Play disabled (no new delete chrome in v1) |
| Playing | `currentVideoId` matches | Row highlight (`--yd-accent-primary-muted`) | Same as Vídeos `active` |
| Empty list | 0 episodes | **Nenhum vídeo nesta coleção** | — |

### Play / player (existing)

| State | Trigger | Visual | Interaction |
|-------|---------|--------|-------------|
| Loading | `playVideo` | `#videoLoadingOverlay` | Wait |
| Playing | Stream OK | Title in `#currentVideoTitle` | Native controls |
| Error | HTTP / media error | Overlay off, toast | Retry play |
| Ended | `onended` | Stop; blob revoked | User picks another episode (no auto-next) |

---

## RECOMMENDATIONS

1. **Primary:** Shared collection chrome (hero + episode list) in Pastas (items column) and Vídeos (below the existing player). Play **always** uses `#videoPlayer` on the Vídeos tab.
2. **Pattern:** Visual language of Álbuns (hero backdrop blur, card hover lift, numbered rows) with **`yd-collection-*`**, **16:9 covers**, label **Coleção**, CTA **Reproduzir**.
3. **Risk:** Do not wire `kind=playlist` into `openAlbumById` / play-album-btn. Do not add a second audio-style queue. If episode order is missing on videos, treat ordered `track_number` as a **blocker for “episode order”**, not as “sort by date and ship”.
4. **Out of v1:** Play-all / auto-next, search inside collection, “Abrir coleção?” post-download confirm (Álbuns has an analog — nice-to-have only).
