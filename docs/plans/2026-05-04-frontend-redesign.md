# Plano de Atualização do Frontend — Design System Consolidado

**Data:** 2026-05-04
**Origem:** Análise de `new_design/` (loop-proposal.html, design-canvas.jsx, tweaks-panel.jsx, components/, styles/)
**Escopo:** Apenas `web_client/` — HTML, CSS, JS
**Restrição crítica:** Stack permanece jQuery + Bootstrap 5.3.3. Sem migração para React.

---

## Decisões Pendentes (Responder Antes de Implementar)

| # | Decisão | Opção A | Opção B |
|---|---------|---------|---------|
| 1 | **Accent color** | Manter vermelho atual `#E63946` (branding YouTube) | Adotar roxo 264° (`oklch(0.66 0.18 264)` → `#7C5CDB`) como no new_design |
| 2 | **Tipografia** | Manter Inter + JetBrains Mono (já carregadas, zero HTTP extra) | Adotar Geist + Instrument Serif (2 webfonts novas, verificar licença) |
| 3 | **Backdrop-filter** | Aplicar `blur(28px)` em todos os cards (GPU pesado em listas longas) | Limitar a containers fixos (navbar, modais, progress card) |

> **Não prosseguir para implementação sem essas três respostas.**

---

## Fonte de Design Consolidada

### Tokens adotados do `new_design/`

| Token | new_design | Equivalente atual | Ação |
|-------|-----------|-------------------|------|
| Espaçamento base | `--s-1: 4px` … `--s-10: 72px` | `--yd-space-1` … `--yd-space-12` | Unificar escala |
| Border radius | `--r-xs: 6px` … `--r-xl: 28px` | `--yd-radius-sm: 6px` … `--yd-radius-xl: 20px` | Adicionar `--r-xl: 28px` |
| Transição | `180ms cubic-bezier(.2,.8,.2,1)` | `250ms cubic-bezier(0.4,0,0.2,1)` | Adotar curva do new_design |
| Shadow SM | `0 1px 2px` + inset white | Sem inset | Adicionar inset `0 1px 0 rgba(255,255,255,0.5)` |
| Shadow MD | `0 8px 24px -8px` blur | `box-shadow` simples | Substituir |
| Glass blur | `28px` | Não implementado | Implementar em containers fixos |
| Grain overlay | SVG noise, opacity 0.04 | Não implementado | Adicionar em `.yd-bg-base` |
| Aurora background | 3 radial-gradients animados | Não implementado | Aplicar em `.main-container` |

### Cores (mantendo hex — não misturar com oklch)

| Token | Light (hex) | Dark (hex) |
|-------|------------|-----------|
| `--yd-bg-base` | `#F5F6FA` | `#0D0F12` |
| `--yd-bg-surface` | `#FAFBFC` | `#141619` |
| `--yd-surface-glass` | `rgba(255,255,255,0.55)` | `rgba(255,255,255,0.04)` |
| `--yd-surface-glass-strong` | `rgba(255,255,255,0.75)` | `rgba(255,255,255,0.07)` |
| `--yd-border` | `rgba(80,70,110,0.12)` | `rgba(255,255,255,0.08)` |
| `--yd-border-strong` | `rgba(80,70,110,0.22)` | `rgba(255,255,255,0.14)` |
| `--yd-shadow-inset` | `rgba(255,255,255,0.5)` | `rgba(255,255,255,0.06)` |
| Aurora 1 | `#D4BEF0` (purple tint) | `#7B3FD4` (purple glow) |
| Aurora 2 | `#B8CCEF` (blue tint) | `#3B5FBE` (blue glow) |
| Aurora 3 | `#EFD8C8` (warm tint) | `#A83B7E` (pink glow) |

---

## Fases de Implementação

### Fase 1 — Tokens CSS (Baixo risco, alto impacto visual)

**Arquivo:** `web_client/css/styles.css`
**Sem tocar:** HTML, JS, IDs, classes existentes.

Substituições no `:root` e `[data-theme]`:

1. **Escala de espaçamento** — unificar `--yd-space-*` com escala 4px do new_design; adicionar `--yd-space-10: 2.5rem`, `--yd-space-12: 3rem`
2. **Border radius** — adicionar `--yd-radius-2xl: 28px`; atualizar `--yd-radius-xl: 20px → 20px` (sem mudança), confirmar consistência
3. **Sombras** — substituir por 3 níveis (sm/md/lg) com inset branco para efeito de elevação
4. **Transição** — trocar curva `cubic-bezier(0.4,0,0.2,1)` por `cubic-bezier(.2,.8,.2,1)` (mais snappy); `--yd-transition-spring` mantém `.34,1.56,.64,1`
5. **Variáveis de glass** — adicionar `--yd-glass-blur: 28px`, `--yd-surface-glass`, `--yd-surface-glass-strong`
6. **Variáveis de aurora** — adicionar `--yd-aurora-1`, `--yd-aurora-2`, `--yd-aurora-3` por tema

**Critério de aceite:** `ruff check` passa (sem arquivos Python alterados). Visual já deve parecer levemente mais refinado sem quebrar layout.

---

### Fase 2 — Surfaces e Background (Médio risco)

**Arquivo:** `web_client/css/styles.css` + pequenas adições em `web_client/index.html`

#### 2a. Aurora background

Adicionar pseudo-elementos ao `.main-container` (ou wrapper equivalente):

```css
.yd-aurora-stage {
  position: relative;
  isolation: isolate;
}
.yd-aurora-stage::before {
  content: '';
  position: fixed; inset: 0;
  background:
    radial-gradient(50% 50% at 25% 30%, var(--yd-aurora-1) / 0.6, transparent),
    radial-gradient(50% 50% at 80% 70%, var(--yd-aurora-2) / 0.5, transparent),
    radial-gradient(40% 40% at 60% 20%, var(--yd-aurora-3) / 0.4, transparent);
  filter: blur(80px) saturate(1.3);
  opacity: 0.85;
  z-index: -1;
  pointer-events: none;
}
```

> Adicionar classe `yd-aurora-stage` ao `<main>` no HTML — 1 linha de mudança.

#### 2b. Grain texture

```css
.yd-grain::after {
  content: '';
  position: fixed; inset: 0;
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4'/><feColorMatrix type='saturate' values='0'/></filter><rect width='200' height='200' filter='url(%23n)' opacity='0.4'/></svg>");
  opacity: 0.04;
  mix-blend-mode: overlay;
  pointer-events: none;
  z-index: 9999;
}
```

#### 2c. Classes glass

```css
.yd-glass {
  background: var(--yd-surface-glass);
  backdrop-filter: blur(var(--yd-glass-blur));
  -webkit-backdrop-filter: blur(var(--yd-glass-blur));
  border: 1px solid var(--yd-border);
}
.yd-glass-strong {
  background: var(--yd-surface-glass-strong);
  backdrop-filter: blur(var(--yd-glass-blur));
  -webkit-backdrop-filter: blur(var(--yd-glass-blur));
  border: 1px solid var(--yd-border-strong);
}
```

Aplicar `.yd-glass` em:
- `.navbar` → substituir background sólido
- `.card` (download cards, progress card) → substituir `background: var(--yd-bg-raised)`
- Modais (`.modal-content`) — cuidado com legibilidade

Não aplicar em:
- `.yd-scroll-container` com listas longas (custo GPU)
- `.yd-media-item` (muitos elementos simultâneos)

**Critério de aceite:** Aurora visível no fundo; navbar com glassmorphism; sem scroll jank em listas de 50+ itens.

---

### Fase 3 — Componentes (Médio risco, sem tocar JS)

**Arquivo:** `web_client/css/styles.css`
**Regra:** Nenhum ID ou handler JS é alterado. Apenas estilos.

#### 3a. `.yd-media-item`

Adotar estilo de card elevado em vez de item plano:

```css
.yd-media-item {
  border-radius: var(--yd-radius-lg);
  box-shadow: var(--yd-shadow-sm);
  transition: transform var(--yd-transition-fast), box-shadow var(--yd-transition-fast);
}
.yd-media-item:hover {
  transform: translateY(-1px);
  box-shadow: var(--yd-shadow-md);
}
.yd-media-item.active {
  box-shadow: 0 0 0 2px var(--yd-accent-primary), var(--yd-shadow-sm);
}
```

#### 3b. Botões

```css
.btn-primary, .btn-danger {
  transition: all 180ms cubic-bezier(.2,.8,.2,1);
}
.btn-primary:hover, .btn-danger:hover {
  transform: translateY(-1px);
  filter: brightness(1.07);
  box-shadow: var(--yd-shadow-md);
}
```

#### 3c. `.yd-badge` — adicionar dot indicator estilo new_design

Adicionar dot colorido antes do texto:

```css
.yd-badge--ready::before,
.yd-badge--downloading::before,
.yd-badge--error::before {
  content: '';
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  margin-right: 5px;
  vertical-align: middle;
}
.yd-badge--ready::before { background: var(--yd-success); box-shadow: 0 0 6px var(--yd-success); }
.yd-badge--downloading::before { background: var(--yd-warning); box-shadow: 0 0 6px var(--yd-warning); }
.yd-badge--error::before { background: var(--yd-error); box-shadow: 0 0 6px var(--yd-error); }
```

#### 3d. `.yd-progress-bar__fill`

Adicionar glow no fill ativo:

```css
.yd-progress-bar__fill--active {
  box-shadow: 0 0 12px var(--yd-accent-primary);
}
```

#### 3e. Inputs `.form-control`, `.form-select`

```css
.form-control:focus, .form-select:focus {
  border-color: var(--yd-accent-primary);
  box-shadow: 0 0 0 4px var(--yd-accent-primary-muted);
  transition: border-color 160ms;
}
```

#### 3f. `.yd-nav` segmented control

Adicionar transição no indicador de aba ativa:

```css
.yd-nav .nav-link {
  transition: all 180ms cubic-bezier(.2,.8,.2,1);
}
.yd-nav .nav-link.active {
  box-shadow: var(--yd-shadow-sm);
}
```

**Critério de aceite:** Todos os componentes existentes visualmente refinados. Zero quebra de funcionalidade (testar download, player, transcrição, pastas).

---

### Fase 4 — Animações e Microinterações

**Arquivo:** `web_client/css/styles.css`

1. **Trocar curva de easing** em todos os `@keyframes` existentes — substituir `ease-out` por `cubic-bezier(.2,.8,.2,1)`
2. **`itemEnter`** — adicionar `scale(0.97) → scale(1)` além do translate para entrada mais orgânica
3. **Modal** — adicionar `backdrop-filter: blur(8px)` no `.modal-backdrop` (leveza de fundo)
4. **Toast** — adicionar sombra `var(--yd-shadow-md)` + borda colorida esquerda já existente com `box-shadow` em vez de `border-left`

**Critério de aceite:** `prefers-reduced-motion` continua removendo transformações.

---

### Fase 5 — Abas Sem Referência no New Design (Extrapolação)

As abas **Transcrições** e **Pastas** não têm correspondência no `new_design/`. Aplicar a mesma linguagem visual das fases 1–4 adaptada:

#### Transcrições
- `.transcription-viewer` → adicionar `.yd-glass` + `box-shadow: var(--yd-shadow-md)`
- Botões de ação (copy, download, delete) → adotar estilo `.btn-ghost` equivalente (background transparente, hover com surface)
- Provider/Language selects → estilos da Fase 3e

#### Pastas
- `.yd-folder-item` → mesma elevação de `.yd-media-item` (Fase 3a)
- Breadcrumb → estilo de chips estilo new_design (`.tag`-like, border-radius pill)
- Checkboxes de seleção → accent-color com `var(--yd-accent-primary)` via CSS

---

## Arquivos Impactados

| Arquivo | Fases | Tipo de mudança |
|---------|-------|----------------|
| `web_client/css/styles.css` | 1, 2, 3, 4, 5 | Adições e substituições CSS |
| `web_client/index.html` | 2a, 2b | Adicionar classe `yd-aurora-stage` e `yd-grain` em `<main>` |
| `web_client/js/app.js` | — | **Sem alterações** |

---

## O que NÃO será feito

- Migração para React, Vite, ou qualquer bundler
- Adoção de `oklch()` (manter hex para consistência dark mode)
- Remoção ou renomeação de IDs usados pelo JS
- Mudança em endpoints ou lógica de polling
- Implementação do TweaksPanel (componente de design tool, não de produto)
- Implementação do DesignCanvas (idem)
- Mudança de estrutura de abas ou fluxos de usuário

---

## Dependências e Ordem de Execução

```
Fase 1 (Tokens)
    └── Fase 2 (Surfaces) — depende das variáveis de aurora e glass
          └── Fase 3 (Componentes) — depende de tokens e glass classes
                └── Fase 4 (Animações) — depende de tokens de transição
                      └── Fase 5 (Orphan tabs) — depende de todas as anteriores
```

Cada fase é deployável independentemente. Fase 1 sozinha já entrega valor visual.

---

## Riscos

| Risco | Probabilidade | Mitigação |
|-------|--------------|-----------|
| `backdrop-filter` causa jank em listas longas | Média | Limitar a containers fixos (Fase 2c) |
| Aurora visível demais em tema claro | Baixa | Reduzir opacity de 0.85 para 0.6 no light theme |
| Glass torna texto ilegível sobre aurora | Média | Aumentar `--yd-surface-glass-strong` para 0.85 no light |
| Inset shadow conflita com Bootstrap borders | Baixa | Testar em `.form-control` com `:focus` |
| oklch não suportado em browser antigo | N/A | Não será usado — sistema fica em hex |
