# TV download contracts implementation evidence

Plan: `docs/plans/2026-10-08-tv-download-contracts-implementation.md`.
Scope: approved source/tests and disposable compiled desktop verification only.
Baseline: master, `78c60069bfec1184e43ec20ed01fa55bd2215f86`; only the plan and contract files untracked. Live port 5000 remains PID 48136. No production mutations authorized.

Ruling: implement in the explicitly named checkout. The handoff names this master checkout and forbids further agents; this takes precedence over optional worktree/reviewer skill workflow. No commits.
Pre-flight: Task 1's independent TV policy feeds Task 4 readiness and automatic preparation; Task 2 destinations feed search, multi-season review and Follow; Task 3 composes existing per-season decisions. Tokens must recheck source trust and destinations at preparation/submission.

## Implemented source behavior

1. `app.py` owns independent stored/effective Movie and TV trust, enabled-ID validation, explicit-empty and omitted-field behavior, atomic config publication and rollback on failed save. Settings uses one draft selector for both domains, release watchlist and AI Control. Loading gates, unavailable IDs, errors, Cancel, Escape, focus restoration and Tab containment are implemented. Movie legacy mode decoding remains only until an explicit Movie selection is saved; TV does not consume it. No live source selection was changed.
2. TV schema 6 adds `tv_import_homes.origin`. The repository proposes safe canonical `Title (YYYY)/Season NN` homes only for genuinely unowned collections with one unambiguous root. Validated Download/Start reserves ownership transactionally; verified publication creates directories and records their creation in the existing job journal. Established homes/padding remain authoritative. Flat, ambiguous, excluded, externally colliding, unsafe-name and missing-date cases remain blocked. The numeric repair tool's existing-home insert now names its columns; the tool was tested only with disposable fixtures.
3. The lower all/checked-season controls compose regular released missing targets through existing per-season review, grouped destinations and the existing batch submitter. Stable composite episode keys prevent preview-ID collisions. Preparation retains multi-season identity. Approved-home selection is shared with the single-season dialog. Reviewing/checking seasons creates no job/task; partial provider failures remain visible.
4. Follow and one-shot bulk share bounded automatic preparation (five supported candidates per pass), with identity/hash/source/quality/coverage checks intact. Follow readiness blocks activation without setup while permitting drafts. Missing/Future source retries are 18,000 elapsed seconds; Future eligibility is midnight Africa/Cairo on the date-only air date. Six-hour metadata refresh, other retry intervals, one-shot completion, cancellation and legacy job policy remain unchanged. UI polls every 15 seconds and exposes returned counts/times/errors.
5. A lost submission acknowledgement now retains the durable intent in Follow. Retry uses that same intent/token; the qBittorrent magnet owner can reconcile a present TV transfer on an explicit submission retry, pause it and continue ordinary file verification without another add. Movie handling is unchanged. Ready intent state alone does not count as acquired without verified episode availability; Upgrade additionally checks the job's imported coverage.

## Isolation and review

- Test environment: OS-temp `C:\Users\dante\AppData\Local\Temp\cp-tv-contracts-1414d92b78cc4bf9950a23b5a1742bd0`; tzdata 2026.5 installed only into `python-deps`. Production roots are not used by tests.
- The existing E2E runner compiles to a fresh OS-temp `dist` and serves the native TV fixture on port 5117. Prowlarr/TMDB/qBittorrent are fixtures; no provider probes or real transfers occurred. The real search, submit, manifest, publication, catalog and cleanup owners are exercised against synthetic media.
- Per Dante's no-agent handoff, review was performed in this chat. Findings corrected: Settings opening before selections loaded; old schema insert in numeric repair; stale multi-season preparation identity; queued/partial import incorrectly implying acquisition; source-list disk failure leaving memory changed; lost acknowledgement losing Follow's durable intent. This is a self-review, not an independent reviewer sign-off.
- All new folder creation remains exclusive. A crash between creating a directory and persisting its ownership journal leaves an unexplained directory blocked for review; the resolver never adopts an unknown external folder. Closing a multi-season UI aborts its request; server composition also has a cancellation callback and bounded search work. An in-flight upstream request can finish before that work bound is observed.

## Verification ledger

Logs are under the OS-temp test root above. The baseline source commit was exported read-only into `baseline` for comparison; no checkout reset was performed.

| Gate | Result | Evidence |
| --- | --- | --- |
| Pre-edit focused baseline | 126 passed, 70.912 s | `baseline.log` |
| Regression-first policy, destination, scope, scheduling, import-truth and acknowledgement checks | Observed failing behavior before corrections; subsequent relevant groups passed | `recovery.log`, earlier focused/red logs in the test root |
| Final focused Python including destinations, lifecycle, Follow, source search, batch, curation and numeric repair | 172 passed, 109.660 s | `focused-final.log` |
| Full Python suite | 1,667 run, 1,666 passed, one baseline failure, 361.812 s | `python-final.log`; exact failure classified below |
| Full Node suite | 119 passed, zero failed/skipped, 342.8918 ms | `node-final.log` |
| Compiled desktop combined suite | 39/40 passed, 1.6 min; all nine new scenarios passed | `desktop-final-40.log`; one existing Library toolbar measurement failed, classified below |
| Targeted desktop final rerun | 3/3 passed, 20.4 s | `desktop-final-targeted.log`: final polling fixture plus Library filter parity at 1366 and 2048 pixels |
| Original-commit streaming test | Same failure reproduced at HEAD `78c60069` | `baseline-streaming-HEAD.log`: `test_streaming_modal_shows_loading_feedback_until_iframe_loads`; source assertion expects obsolete `streamLoaded` |
| Patch formatting and live port | Formatting check clean; port 5000 still PID 48136 | Read-only Git/port check |

The combined desktop run is **not claimed as green**. `TV Library filters keep the movie grid and readable year fields at 1366px` failed its existing toolbar-coordinate comparison (13.96875 pixels versus less than 2). The unchanged scenario passed earlier combined runs and the final targeted rerun at both widths. This is intermittent; its underlying cause is unconfirmed. No Library layout/CSS change or relaxed assertion was introduced. All nine new contract scenarios passed, including actual multi-season submission, selector errors, new verified publication and blocked flat destinations. The polling fixture was then tightened to use three consistent episode states/counts and reverified; its final screenshot shows 0/3 acquired, one queued, one waiting and one needing review.

Final read-only live check: `/` still serves `/assets/index-BL38s9_4.js`, matching `dist/index.html`; port 5000 remains PID 48136. This confirms the old served bundle remains installed, not that source edits are live.

The first broad run exposed five numeric-repair errors from a two-column insert, and three Settings source-shape assertions. The schema caller was corrected. Tests asserting duplicate selector component names/callback syntax were updated to the shared owner; AI's visible default-source description was preserved. The streaming-overlay assertion was left unchanged and reproduced on the original commit. Full-suite status must report that failure explicitly.

Earlier desktop failures were traced to the Settings loading race (corrected), a case-sensitive test expecting `available` instead of rendered `Available locally` (test corrected), a fixture spy reading `indexers` instead of the real `indexer_ids` argument (fixture corrected), an unavailable-ID test waiting for a checkbox after its removal (test now clicks and asserts removal), and one transient screenshot file-open error. Final combined results supersede these runs, not the failure history.

## Approved contract comparison

| Rule / acceptance scenario | Observed source or isolated result |
| --- | --- |
| Independent Movie YTS and TV Lime/1337x selections | Config API tests preserve independent trust; desktop save/read and provider-call capture check the same effective TV IDs. IDs 2/7/9 belong only to the fixture. |
| Explicit empty / omission / unavailable / save failure | No TV fallback; failed save preserves old effective state; draft Start is blocked. Shared dialog retains draft on error and Cancel discards it. |
| New unsaved Louie-shaped collection | Desktop review leaves show untracked and folder absent; explicit Download tracks/reserves without creating folder; actual verified fixture import binds the original filename under `Louie Fixture (2010)/Season 01` and cleans staging. |
| Established South Park style / old jobs | Destination and import regressions preserve existing homes/padding and legacy recorded policies. No live collection was changed. |
| Existing flat Lucifer-shaped collection | Repository, submission and compiled readiness remain blocked; existing file binding/media preserved. This limitation is intentionally deferred. |
| Unsafe title / missing first-air date / roots / exclusions / external collision | Actionable blocked result with no transfer claim/add; external content is preserved. |
| Reservation migration, reopening and concurrent owners | Schema 5->6/restore and simultaneous repository tests pass; stable same-series home and other-series conflicts are asserted. |
| All/checked seasons / duplicate provisional IDs | Regular released missing targets only; groups/coverage use composite keys; actual desktop explicit batch queues two season destinations with no Follow task; existing single-season/episode upgrade path preserved. |
| Partial provider failure / overlap / batch retry | Remaining available groups visible; overlap rejected; idempotent batch retries unfinished members only. |
| Cairo eligibility / five-hour retry / offline restart | Injected clocks cover an ordinary midnight and both 2026 DST boundaries; retry is exactly 18,000 elapsed seconds, persisted and not replayed. Missing timezone data blocks Start/worker acquisition. |
| Automatic supported links / hash swap / wrong identity / untrusted quality | Shared prepare is used without manual confirmation; bounded attempts and rejection/error distinctions asserted; trust removal invalidates stale automatic submission. |
| Queued/acquired / acknowledgement loss | No second add during monitoring or retry; acquired requires verified episode availability. Restart recovers the same durable intent. |
| Ended Missing / Future / one-shot bulk | Existing targeting/completion and cancellation tests retained; Missing stays a fixed snapshot, ended Future remains unavailable, Library bulk finishes without persistent retries. |
| Polling / profile/scope changes / repeated navigation | Abort/sequence protection and keyed controls; desktop Back/Forward and existing creator/related navigation checks retain correct series/season content. |
| Movie/watchlist/AI/IPTV boundaries | Existing full suites and shared Settings source checks run; release-watchlist and AI trust remain separate; no Movie/IPTV destination or scheduling rules changed. |

## Handback boundary

Source and isolated verification only. Live config/catalog/jobs/library, shared interpreter, served `dist`, process and Lucifer task were not modified. No commit, push, restart, deployment, package or release. Actual source availability and live playback/download behavior are not proven by these fixtures. Live activation requires separate authorization and installation of the declared timezone dependency before restart/schema activation.
