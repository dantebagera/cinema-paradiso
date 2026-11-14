# Library combined header — 2026-10-14

Implemented in the Desktop checkout; verified using compiled assets in an isolated test-mode server. Production frontend and backend process are unchanged.

## Result

- Movies/TV Shows navigation followed immediately by one filter/actions header.
- Reused Media View/File View/scan buttons sit inside the shared filter header, along with the existing TV Maintenance action.
- Independent buttons preserve the filter disclosure state. Existing Movie scan, TV refresh, per-view preferences, sticky behavior and shared Discover/Lists behavior are preserved.
- At desktop widths 1280/1600/2048, controls stay aligned and inside the panel. Long TV File queries stay compact with ellipsis; complete text remains in the hover title and search input.

## Verification

| Gate | Result |
| --- | --- |
| Initial existing sticky/per-view baseline | 3 passed |
| New initial layout regression on old build | 7 failed as intended; actions 55px above filter heading |
| Initial focused corrected build | 10 passed |
| Initial full shared-controls browser suite | 71 passed |
| Long-query regression before correction | Failed as intended; header 120px tall |
| Corrected focused combined-header checks | 8 passed |
| Final full shared-controls browser suite | 72 passed |
| Final Python workspace/library UI checks | 70 passed |
| Vite compiled build | Passed |
| Targeted diff whitespace check | Passed |
| Independent review | No remaining findings; corrected filename-query header 52px with no overlap |

Logs and desktop screenshots are beside this report. Tests used port 5138, CP_TEST_MODE=1, a unique OS-temp CP_TEST_ROOT, CP_TEST_QBT_MODE=embedded, and CP_TEST_DIST_DIR under that root. Browser fixtures isolated scans and external-provider behavior. Backend integration suites were not run because no backend behavior changed.

Production port 5000 was still PID 45076 and checkout dist still referenced index-kgvXGbPC.js / index-CQEVD-Zn.css after testing. No production scan, data/config edit, activation, restart, commit, push or publication was performed. Snapshot of the seven pre-edit source files is retained in the isolated test root.
