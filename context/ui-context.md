# UI Context

## Theme

Cinema Paradiso uses a dark cinematic archive-console visual language. The interface should feel private, precise, and powerful: near-black backgrounds, restrained dark panels, gold focus accents, and functional colors for state.

## Colors

Primary tokens live in `src/styles.css`.

| Role | CSS Variable | Value |
|---|---|---|
| Base background | `--archive-black` | `#0a0a0b` |
| Surface | `--surface` | `#121316` |
| Raised surface | `--surface-raised` | `#1a1c20` |
| Border | `--border` | `#26282d` |
| Primary text | `--text-primary` | `#e6e6e6` |
| Muted text | `--text-muted` | `#a3a6ad` |
| Focus accent | `--projector-gold` | `#d4af37` |
| Success/owned | `--success-green` | `#22c55e` |
| Warning/quality | `--archive-amber` | `#f59e0b` |
| AI | `--ai-violet` | `#8b5cf6` |
| Library/info | `--library-blue` | `#3b82f6` |
| Plex/system | `--plex-cyan` | `#06b6d4` |
| Danger/delete | `--danger-red` | `#ef4444` |

## Typography

- Font stack: Inter, Segoe UI, system UI, sans-serif.
- Body text should stay readable on dark surfaces.
- Do not use oversized hero text inside dense tool panels.
- Letter spacing should remain normal unless a specific styleguide component calls for uppercase labels.

## Border Radius

- Default panels and cards use 6-8px radius.
- Pills and status chips use rounded capsule shapes only when they behave like tags/status labels.
- Avoid nested decorative cards.

## Component Patterns

- Sidebar navigation is persistent, icon+label, and not duplicated inside page heroes.
- Home uses a command-center layout with health, release watchlist, discovery rail, and inspector.
- Library has Movie View and File View.
- Cleanup is a tabbed offline maintenance workspace.
- Discover is a tabbed online workspace: Explore Movies, Browse Indexers, Pick My Movie.
- Settings is a system/integrations console.

## Icons

Use Lucide React icons. Buttons should use icon+label when the action needs scanning speed. Icon-only buttons require clear labels/tooltips or `aria-label`.

## Motion

Use subtle transitions for hover, focus, active cards, loading, and notification state. Avoid noisy animation. Respect readability over spectacle.
