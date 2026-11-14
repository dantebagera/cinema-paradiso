# Movie and TV streaming provider choice

**Status:** Implemented and verified in isolation, 2026-10-24; not activated live. Dante: “add this as a second streaming option in cp for movies and tv, keep streamimdb and let me choose between them in settings and keep streamimdb the default”.

## Problem and decision

- Settings currently exposes editable movie/TV URL templates, but no named provider choice. The selected templates already drive all movie and episode Stream actions through the shared player.
- Add StreamIMDB (default) and VSEmbed choices in Settings > Streaming Link. Preserve Custom URL for existing custom configurations. One choice applies to movies and TV, saved only through Save Streaming.
- VSEmbed URLs: `https://vsembed.ru/embed/movie/{tmdb_id}/` and `https://vsembed.ru/embed/tv/{tmdb_id}/{season_number}-{episode_number}`.
- Earlier provider playback proof was limited to short isolated sessions on 2026-10-06; availability and interruption-free playback on 2026-10-24 are not established. Do not add a sandbox, advertising scripts, CAPTCHA automation, automatic fallback, or a second player.
- Open product decisions: none for the requested scope. Implementation choice: retain the saved URL pair as the source of truth; derive the named selection from it instead of adding a competing saved provider flag.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and exceptions | Affected callers | Proposed behavior | Changes contract? | Decision |
| --- | --- | --- | --- | --- | --- |
| Dante's streaming request, 2026-10-24 | StreamIMDB remains available and default | Settings, Movies, TV | Add an explicitly saved second provider | Requested extension | Explicit request above |
| Existing custom URL configuration | Preserve custom movie URLs, IMDb resolution, explicit TV overrides and disabled state | Streaming API/settings | Keep Custom URL and legacy template-only API requests | No | Preserve |
| TV identity and progress | Exact series TMDB ID, season/episode; unreleased/reconciliation guards; Stream does not mark watched | TV streaming callers | Same shared URL builder/player | No | Preserve |
| Stream-player interaction/loading | Shared iframe, Close/Escape/focus return; page load is not proof of playback | All streaming surfaces | No modal changes | No | Preserve |

## Current design and ownership

| Responsibility | Owner | Preserve / retire |
| --- | --- | --- |
| Provider definitions, known-provider TV derivation, TV validation | `services/streaming_templates.py` | One catalogue for the two built-ins; preserve explicit overrides and unknown-provider behavior |
| Config input/output and persistence | `app.py`, `/api/streaming/config`, `_all_config`, `_save_config` | Validate before changing state; same saved URL fields; no GET writes |
| Settings fields/save feedback | `src/features/settings/SettingsWorkspace.jsx`, existing `IntegrationCard`, `dialog-field` select and `ActionButton` | Reuse layout and callback; retire manual editing for built-in templates only, retain through Custom URL |
| Movie/TV URL expansion and player | `src/utils/appUtils.js`, `src/App.jsx` | Unchanged shared consumers |

Baseline: Desktop checkout, `master`, `be511f98846a67a182e5b371ad087938e9344362`. Many unrelated dirty/untracked files, including `app.py` and `src/App.jsx`. Relevant originals and full status saved to OS-temp `cp-streaming-options-6c0d29810f3149b1ae4754b758dc89de`. Work in this checkout to preserve and build against Dante's current integrated source; no checkout reset or branch change. Test data and builds are isolated.

Runtime observed before changes: localhost:5000, Python PID 51992 (`app.py`), repository `config.json`, data selected by `_user_data_dir`; API currently returns StreamIMDB movie and TV URLs. Served JS `index-CwW9dSyz.js`, CSS `index-3_nuXu-W.css`. These identify the live baseline, not a future deployment. No live config or dist changes authorized by this source implementation scope.

## Exact behavior contract

### Frontend

- Add a `Streaming provider` select inside existing Streaming Link card, above URL fields, using existing `dialog-field` markup. Server supplies built-in IDs, labels and URL pairs; frontend does not own a second catalogue.
- Options: StreamIMDB (default), VSEmbed, Custom URL. Existing custom pairs select Custom URL. Preset selection previews both URLs, read-only; Custom URL allows both to be edited with existing placeholder help.
- Save Streaming submits selection, enabled state, label, and templates. Success uses returned effective config and existing `onStreamingConfigChanged` callback so both Movies and TV immediately use the saved choice. Unsaved changes do not alter playback. Error leaves saved playback config intact.
- Preserve enable checkbox, button label, sizing/spacing/control style, and all unrelated settings. Desktop only.

### Backend

- Extend GET/POST response additively with `provider` and `providers`; preserve existing fields, including conditional TV field behavior.
- POST accepts optional `provider`: built-in IDs select canonical movie+TV pair, `custom` uses submitted templates, absent keeps legacy template behavior. Unknown IDs/non-object requests return 400 before mutation or saving.
- Derive `provider` from actual effective movie+TV URLs. Explicit TV overrides that differ from a preset remain Custom URL. No new saved provider flag, schema migration, background work, provider network calls, or retry logic.
- Save both selected URLs through existing atomic configuration writer; GET never writes. Restart reads the same fields as before. Existing known-host TV inference is extended to VSEmbed through the same provider catalogue, preserving StreamIMDB http/www/port behavior and explicit overrides.

## Implementation sequence

1. Add API regressions, run them RED, then implement catalogue and config selection in the existing owners.
2. Add real-settings browser regression, observe failure before frontend changes, then extend Settings and verify save/reload/default/custom/error behavior.
3. Test the full Settings -> real backend -> movie/episode iframe path using an isolated TV fixture server and intercepted external player pages. Verify exact URLs, same modal, disabled/unreleased handling, unchanged watched state, switch-back and reload.
4. Run focused Python, broader related Python/Node suites, isolated compiled desktop tests; inspect screenshots and review changes against saved originals. No commit, live activation, restart, package, or release.

## Acceptance matrix

| Scenario | Action | Expected result | Evidence |
| --- | --- | --- | --- |
| Default installation | GET config / open Settings | StreamIMDB selected, original URLs | API + compiled desktop |
| Existing custom URL/TV override | GET/save legacy payload | Preserved; Custom URL selected | API + desktop |
| VSEmbed selection | Save in Settings | Both canonical VSEmbed URLs persisted/returned | Real API + desktop |
| Movie stream | Navigate from Settings to Discover and Stream | Selected provider's movie TMDB URL in shared iframe | Desktop interception |
| Episode stream | Open released S01E02 and Stream | Series 900001, season 1, episode 2, correct provider syntax | Real TV API + desktop |
| Progress guard | Compare episode before/after streaming | Watched/completed unchanged | Desktop real API |
| Reload / switch back | Reload Settings, select StreamIMDB, save | Saved choice restored; both URLs switch back | API + desktop |
| Invalid provider/template | POST invalid inputs | 400, no runtime/persistence mutation | API |
| Disabled streaming | Save disabled with preset | URLs retained, Stream actions unavailable | API + desktop |
| Delayed/unavailable player | Existing modal regressions | Truthful load status, Close/focus behavior intact | Existing stream-player suite |

## Verification and outcome

- Baseline focused API/default suite: 5 tests passed before changes.
- Test-first evidence: provider API checks failed before the backend change; compiled desktop selector test failed before the frontend change. Visual check caught a 19px native select; the new control now reuses the shared dialog input styling at 42px with keyboard focus styling.
- Final focused Python: **54 passed**, including real configuration-file persistence across two fresh backend processes, both provider choices, custom/override preservation, invalid provider IDs, malformed URLs and non-object JSON rejection without saves.
- Node: **140 passed**.
- Full Python discovery: **1,848 tests; 4 failures, 12 errors, 5 skipped**. Three environment-dependent test methods pass when supplied their required embedded-QBT and existing TV-baseline environment. Remaining catalogue fixture errors and obsolete trailer-source assertion reproduce using saved pre-change source. Full-suite details are in `docs/verification/streaming-provider-choice/verification.md`; no full-suite-green claim.
- Final compiled desktop run: **14 passed** (3 provider-settings, 4 shared stream-modal, 7 native-TV scenarios). Tests use real config/TV APIs; provider pages are intercepted. Same-session sidebar navigation proves saved provider changes reach both movie and episode streaming without a document reload; unsaved Settings drafts leave the active provider unchanged. Reload separately proves saved selection persistence. Episode watched state is unchanged.
- Two intermediate desktop runs hit Windows `UNKNOWN` file-open errors while the older native-TV tests wrote generated screenshots under the repo. Running the same 14 tests with the working directory/output artifacts in OS-temp passed; no native-TV test assertions were weakened.
- Independent review identified falsey non-object requests and malformed custom movie URLs; both were reproduced RED and fixed before the final checks. The reviewer also requested same-session coverage, added above.
- Live boundary rechecked after implementation: PID 51992, served JS `index-CwW9dSyz.js` and CSS `index-3_nuXu-W.css`, and StreamIMDB movie/TV settings remain as before. No live config/dist replacement or restart performed.
- Python: `CP_TEST_MODE=1`, unique OS-temp `CP_TEST_ROOT`, `.venv/Scripts/python.exe -m unittest ...`.
- Node: `node --test tests/*.test.mjs` (existing relevant appUtils/TV builders included).
- Desktop: `CP_TV_E2E=1 npm.cmd run test:e2e -- tests/e2e/streaming-providers.spec.js tests/e2e/stream-player.spec.js tests/e2e/native-tv.spec.js`, with separate OS-temp build/data; external embed interception is routing/UI proof, not new provider playback proof.
- Build outside live `dist`; live served bundle/config must remain unchanged. Report baseline failures and unavailable checks separately.
- Recovery: source comparison/backups in OS-temp; no live migration is required. User can select StreamIMDB and save after any future activation.
