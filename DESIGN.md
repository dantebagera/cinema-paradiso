---
name: Cinema Paradiso
description: Local-first cinematic command center for managing, cleaning, discovering, and watching a personal movie archive.
colors:
  archive-black: "#0a0a10"
  panel-black: "#0d0d0d"
  surface: "#1a1a1a"
  surface-raised: "#252525"
  surface-ink: "#10101e"
  border: "#1c1c28"
  border-strong: "#333333"
  text-primary: "#e5e5e5"
  text-strong: "#ffffff"
  text-soft: "#cccccc"
  text-muted: "#888888"
  text-faint: "#555555"
  projector-gold: "#fdcb6e"
  archive-amber: "#e5a00d"
  ai-violet: "#a29bfe"
  library-blue: "#74b9ff"
  success-green: "#2ecc71"
  danger-red: "#e74c3c"
  dashboard-pink: "#fd79a8"
  plex-cyan: "#00cec9"
typography:
  display:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "2.5rem"
    fontWeight: 800
    lineHeight: 1.12
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "1.3rem"
    fontWeight: 700
    lineHeight: 1.25
  title:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 700
    lineHeight: 1.2
  body:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "0.88rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "0.72rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.05em"
rounded:
  xs: "3px"
  sm: "4px"
  md: "6px"
  lg: "8px"
  xl: "10px"
  modal: "12px"
  panel: "14px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  xxl: "28px"
  page: "48px"
components:
  button-primary:
    backgroundColor: "{colors.projector-gold}"
    textColor: "{colors.archive-black}"
    rounded: "{rounded.md}"
    padding: "7px 18px"
    typography: "{typography.body}"
  button-danger:
    backgroundColor: "{colors.danger-red}"
    textColor: "{colors.text-strong}"
    rounded: "{rounded.md}"
    padding: "9px 18px"
    typography: "{typography.body}"
  button-ghost:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.text-soft}"
    rounded: "{rounded.md}"
    padding: "7px 14px"
    typography: "{typography.body}"
  input-default:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    padding: "8px 14px"
    typography: "{typography.body}"
  card-default:
    backgroundColor: "{colors.surface-ink}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.xl}"
    padding: "18px 20px"
  poster-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.xl}"
    padding: "0"
---

# Design System: Cinema Paradiso

## 1. Overview

**Creative North Star: "The Cinematic Archive Console"**

Cinema Paradiso should feel like a powerful local archive console with cinematic taste: dark, focused, fast, and quietly premium. The surface is not a theater lounge, not an awards-show poster, and not a generic entertainment website. It is a working command center for thousands of local movie files, with enough atmosphere to make library management feel pleasurable.

The default workspace is near-black. Gold is the projector light: rare, directional, and used to focus attention. Feature colors remain functional, not decorative. Violet belongs to AI and matching flows, blue to library inspection, green to owned or safe actions, amber to quality warnings, pink to dashboard analysis, cyan to Plex/system sync, and red to destructive actions.

This system rejects generic SaaS dashboards, cheap Plex clones, purple AI-gradient apps, glassy crypto-style interfaces, beige premium templates, cluttered torrent-indexer tables, and anything that makes dense workflows slower or harder to trust.

**Key Characteristics:**
- Near-black shell with layered charcoal panels.
- Gold used as a rare cinematic signal, never as a full costume.
- Compact product typography, not landing-page drama.
- Poster imagery earns cinematic richness; tables stay operational.
- Motion is tasteful, short, and tied to state.

## 2. Colors

The palette is black and gold at the identity level, with functional accent colors preserved for fast scanning across tools and statuses.

### Primary
- **Archive Black**: The page and sidebar canvas. It anchors the app and should own most of every screen.
- **Projector Gold**: The primary cinematic accent. Use for hero emphasis, Explore, Scan, primary archive actions, ratings, and focus moments. Its rarity is what makes it feel premium.
- **Archive Amber**: A rougher operational gold for warnings, low-quality files, unmatched notices, and cleanup attention.

### Secondary
- **AI Violet**: AI recommendations, Pick My Movie, unmatched matching, and Prowlarr result emphasis. Use as a functional category color, not as a purple-gradient identity.
- **Library Blue**: Library browser navigation, sorted table state, filters, and file inspection.
- **Success Green**: In-library badges, safe cleanup states, stream/play affordances, and confirmed positive status.

### Tertiary
- **Dashboard Pink**: Analytics and chart surfaces only. Do not spread it into general actions.
- **Plex Cyan**: Plex sync, genre metadata, and system integration status.
- **Danger Red**: Delete, permanent removal, error, and destructive confirmation only.

### Neutral
- **Panel Black**: Full-screen overlays and active panels.
- **Surface**: Modal bodies, field backgrounds, table bands, and panel interiors.
- **Surface Raised**: Cards, filters, rows, and hoverable containers.
- **Surface Ink**: Home feature cards and cinematic card panels.
- **Border**: Sidebar separators and quiet structural lines.
- **Border Strong**: Inputs, table controls, modal edges, and elevated panel outlines.
- **Text Primary**: Default readable text on dark surfaces.
- **Text Strong**: Titles, key values, and table names.
- **Text Soft**: Secondary table text and modal copy.
- **Text Muted**: Descriptions, subtitles, and support copy.
- **Text Faint**: Path text, disabled labels, empty-state hints, and helper copy.

### Named Rules

**The Projector Light Rule.** Gold is the focus beam, not the wallpaper. If more than one major region is gold, the screen is overdressed.

**The Functional Accent Rule.** Purple, blue, green, pink, cyan, amber, and red must describe product meaning. Do not use them as random decoration.

**The No Oscars Costume Rule.** Keep the confidence of black and gold, but never add red-carpet, trophy, velvet-curtain, or awards-show visual language.

## 3. Typography

**Display Font:** Segoe UI, system-ui, sans-serif
**Body Font:** Segoe UI, system-ui, sans-serif
**Label/Mono Font:** Segoe UI, system-ui, sans-serif

**Character:** One compact system sans carries the product. It should feel crisp, familiar, and fast, with weight and spacing doing the hierarchy work.

### Hierarchy
- **Display** (800, 2.5rem, 1.12): Home hero and rare screen-leading statements only. Do not use display scale inside dense panels.
- **Headline** (700, 1.2rem to 1.3rem, 1.25): Panel titles, dashboard headings, and modal headings.
- **Title** (700, 0.95rem, 1.2): Feature cards, movie titles, table title cells, and compact section headers.
- **Body** (400, 0.82rem to 0.95rem, 1.5 to 1.75): Form text, modal copy, card descriptions, table cells, and workflow explanations.
- **Label** (700, 0.68rem to 0.78rem, 0.05em to 0.16em): Short metadata labels, table headers, badges, and dashboard labels. Uppercase is allowed only for compact labels.

### Named Rules

**The Product First Type Rule.** Use a fixed compact type scale. Do not use fluid landing-page typography inside the app.

**The No Display Labels Rule.** Buttons, filters, tabs, badges, inputs, and table headers must stay in the product sans vocabulary.

## 4. Elevation

The system is hybrid: flat and tonal by default, with lift reserved for poster cards, home feature cards, dropdowns, and active overlays. Most depth comes from black surface changes, borders, and stateful hover response. Shadows should feel like dark-room depth, not floating glass.

### Shadow Vocabulary
- **Card Hover** (`box-shadow: 0 10px 36px #00000099`): Home feature cards and large clickable cards.
- **Poster Hover** (`box-shadow: 0 12px 32px #00000088`): Movie poster cards that lift and scale on hover.
- **Dropdown Ambient** (`box-shadow: 0 8px 32px #0008`): Settings dropdowns, compact popovers, and floating utility panels.

### Named Rules

**The Flat Until Invited Rule.** Surfaces are flat at rest. Lift appears on hover, selection, modal focus, or poster interactions.

**The No Glass Rule.** Do not use backdrop blur or translucent glass cards as the visual system. Dark overlays are allowed for modal focus.

## 5. Components

### Buttons

Buttons are compact, confident, and action-specific.

- **Shape:** Gently squared product controls (5px to 6px radius), with larger 8px only when the button is embedded in a card or full-width poster action.
- **Primary:** Gold or the feature color, dark text only when the filled color is bright enough. Padding usually sits between 6px 14px and 9px 18px.
- **Hover / Focus:** Increase fill opacity, brighten border, or translate only when the component is card-like. Focus must be visible with border color, outline, or glow.
- **Secondary / Ghost / Tertiary:** Charcoal fill, strong border, and muted text. Hover should move toward text white or the feature accent.
- **Danger:** Filled red for irreversible confirmation, outlined red for row-level delete actions.

### Chips

Chips are metadata, not decoration.

- **Style:** Small text, compact padding, tinted background, one-pixel border, and exact status color.
- **State:** Selected chips use a stronger border and clearer text. Disabled chips reduce opacity and cursor affordance.
- **Use:** Resolution, rip source, genre, Plex state, in-library status, AI reason tags, and torrent quality variants.

### Cards / Containers

Cards carry either feature choices or movie posters. Do not turn every layout block into a card.

- **Corner Style:** 8px to 10px for cards, 12px to 14px for modals and large panels.
- **Background:** Use Surface Ink for home feature cards, Surface for modals, Surface Raised for dashboard cards and table containers.
- **Shadow Strategy:** Cards lift only on hover or active interaction. Static dense panels use borders and tonal layering.
- **Border:** One-pixel charcoal borders are standard. Accent bars may be used on feature cards, but not as generic side stripes.
- **Internal Padding:** 18px to 20px for cards, 24px to 28px for modals and large panels.

### Inputs / Fields

Inputs should feel like command-console controls without looking terminal-themed.

- **Style:** Charcoal fill, one-pixel border, 6px to 8px radius, light text, muted placeholder text.
- **Focus:** Border shifts to the current feature color. No heavy glow unless the field belongs to the AI recommendation surface.
- **Error / Disabled:** Error uses red border and red text. Disabled uses low contrast, reduced opacity, and clear cursor change.

### Navigation

The sidebar is the product spine.

- **Style:** Fixed 220px sidebar, near-black background, one-pixel right border, compact icon plus label rows.
- **Typography:** 0.86rem, 600 weight, muted by default.
- **Default / Hover / Active:** Default labels are quiet. Hover reveals the feature color with a tinted background and left-edge selection. Active state should be explicit, not color-only.
- **Mobile Treatment:** Collapse into a compact top or drawer navigation rather than shrinking labels until they become unreadable.

### Poster Cards

Poster cards are where the app can be most cinematic.

- **Image:** 2:3 poster ratio, object-fit cover, charcoal placeholder.
- **Motion:** Hover may lift the card and scale poster imagery slightly, around 180ms to 300ms.
- **Metadata:** Title, year, genres, rating, plot, language, ownership, and actions stay compact. Do not let poster romance bury the action buttons.

### Tables

Tables are the archive working surface.

- **Style:** Dense rows, clear hover state, strong title cells, muted paths, sortable headers, and compact metadata badges.
- **Spacing:** 7px to 10px cell padding. Dense is allowed when scanning hundreds of files.
- **State:** Selection, unmatched, deleted, disabled, sorted, and loading states must use both color and text/icon/structure.

### Toasts and Loading

Feedback should be visible, short, and calm.

- **Toast:** Bottom-right, 8px radius, bright semantic fill, translate plus opacity entrance.
- **Loading:** Prefer skeleton shimmer or inline progress for content areas. Spinners are acceptable for sync or blocking operations.
- **Reduced Motion:** Replace shimmer, poster scale, card lift, and toast travel with simple opacity or instant state when requested by the system.

## 6. Do's and Don'ts

### Do:

- **Do** make the app feel like "The Cinematic Archive Console": serious, dark, cinematic, and operational.
- **Do** use Archive Black as the dominant canvas and Projector Gold as a rare focus signal.
- **Do** keep feature colors functional: violet for AI, blue for library, green for safe/in-library, amber for quality warnings, pink for analytics, cyan for Plex, red for danger.
- **Do** keep dense workflows fast, scannable, and calm.
- **Do** use tasteful motion for hover, state change, loading, and reveal. Keep most transitions between 150ms and 250ms, with poster imagery allowed up to 300ms.
- **Do** include reduced-motion fallbacks for poster scale, card lift, shimmer, and toast movement.
- **Do** make delete, rename, and cleanup actions explicit and controlled.
- **Do** keep gold accents scarce enough that they feel intentional.

### Don't:

- **Don't** make the app look like a generic SaaS dashboard.
- **Don't** make it a cheap Plex clone.
- **Don't** use purple AI-gradient app styling.
- **Don't** use glassy or blurred crypto-style interfaces.
- **Don't** use beige premium templates.
- **Don't** ship cluttered torrent-indexer tables without hierarchy.
- **Don't** use decorative gradient text.
- **Don't** use glassmorphism as a theme.
- **Don't** repeat identical icon-card grids everywhere.
- **Don't** put tiny uppercase eyebrows above every section.
- **Don't** use oversized metric blocks as a default design move.
- **Don't** use visual effects that make library management harder to read.
- **Don't** literalize black and gold into Oscars imagery: no red carpet, trophies, velvet curtains, or ceremony language.
