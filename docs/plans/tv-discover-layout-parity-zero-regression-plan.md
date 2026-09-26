# TV Discover layout parity

Status: implemented in the isolated 0870 worktree on 2026-09-23.

## Problem and owner

Movie Discover uses the centered `discover-workspace` shell and `discover-search-panel`. TV Discover rendered outside that shell and forced fourteen controls into one toolbar row, clipping both year fields at desktop widths. The owners are `TVWorkspace.jsx`, `TVSearchControls.jsx`, and `tv.css`; the movie Discover styles remain the visual reference.

## Change

- Use the movie Discover shell, header treatment, search dimensions, and content width for TV Discover.
- Keep the TV advanced-search button inside its search field, as previously requested.
- Arrange the existing TV feed, ownership, genre, language, country, viewing, year, rating, votes, sorting, refresh, and reset controls in two readable rows.
- Use the movie Discover grid minimum card width on TV Discover so series cards do not become narrow at 1366px.
- Preserve TV Library layout, query behavior, series navigation, streaming, and download actions.

Movie-only Browse Indexers, Pick My Movie, and bulk movie actions have separate owners and no equivalent TV workflow in this layout change. A distinct product decision is needed to define their TV behavior rather than displaying controls that cannot work.

## Verification

- Isolated frontend production build passed.
- 12 TV parity and expanded-page browser checks passed after the layout change.
- 9 TV Library, streaming, acquisition, and stabilization browser checks passed.
- New desktop comparisons at 1366px and 1920px checked equal Movie/TV header and search widths, readable year fields, a minimum 460px TV card, and no horizontal page overflow.
- All browser checks used the disposable fixture server and an isolated built bundle.
