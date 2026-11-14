# YouTube Movie streaming implementation plan

**Status:** Implemented and verified in isolation, 2026-11-14. Dante said “go” after agreeing the rules below. No activation, restart, commit, push, or live catalog modification is authorized. See [verification report](../verification/youtube-stream-2026-11-14/report.md).

## Problem and decision

Movie Stream offers IPTV and web embeds but cannot find full movies on YouTube. Add YouTube to the shared Movie source chooser. Normal searches never invoke GPT. Require actual video duration within the movie runtime ±5%, inclusive. Search Arabic-language films using Arabic titles, not English translations. Always expose Search more and explicit Use GPT. Do not filter or rank by uploader legitimacy.

Approaches discussed: simple title search; trusted channels; broader title/runtime matching with optional GPT. Dante chose the last approach and explicitly removed uploader checks. GPT proposes additional queries only; CP executes real searches and enforces duration itself. Missing runtime or missing Arabic title is an explicit metadata error, never a reason to silently widen the rule. TV is outside scope.

## Contracts affected and contract-change decision

| Contract/source | Existing behavior | Proposed behavior | Change? | Decision |
| --- | --- | --- | --- | --- |
| Conversation, 2026-11-14 | No YouTube Movie source | Exact rules above | Additive | Explicit “go” |
| 2026-11-13 Movie chooser | Opens immediately, user chooses source | Preserve; search only after selecting YouTube | No | Preserve |
| Streaming configuration | Disabled web streaming hides web sources | YouTube follows the existing web enabled flag | No | Preserve |
| TV stream | Saved provider, exact episode | Unchanged | No | Preserve |
| AI jobs/account | Selected account/model, admission, cancellation and durable jobs | Register F6 in existing owners | Additive | Optional GPT requested |
| Stream progress | Web playback does not update owned progress/watched | Preserve | No | Preserve |

## Current design and ownership

Baseline desktop: dirty master 117526b; extensive tracked/untracked changes preserved. Managed worktree at C:/Users/dante/.codex/worktrees/youtube-movie-stream/cinema paradiso has the current source overlaid; baseline.json records source backup location. Live backend PID 52396 on port 5000 serves index-hjeN8MRq.js; YouTube key is configured, region EG. No credential copied. Existing config remains owned by app.py/YouTubeService. Live process/data are not used for tests.

| Responsibility | Owner | Callers / preservation |
| --- | --- | --- |
| Movie chooser and IPTV cleanup | StreamPlayerModal.jsx | Discover/Home/Library/Lists; TV direct mode |
| YouTube HTTP/config | services/youtube_playlist.py::YouTubeService | Preserve trailers/feed and configured key |
| Movie search orchestration | new services/youtube_movies.py | Uses existing YouTube HTTP owner; owns movie query/session/runtime logic only |
| Movie metadata fetch | app.py::_ai_tmdb_provider_get | Reuse existing TMDB HTTP owner with alternative titles/translations |
| GPT selection/jobs | ai_provider.py, ai_jobs.py, chatgpt_skills.py | Add F6, bounded worker, no alternate credentials or transport |
| Result UI | new YouTubeMovieSource.jsx | Reuse source list/button/player styles; separate component because asynchronous movie search differs from IPTV version selection |

## Exact behavior contract

### Frontend

Add YouTube after existing web providers. Selecting it opens a search stage in the same dialog. Show title, runtime and ±5% range, query/status, accumulated candidate rows with title/channel/duration and Open on YouTube. User selects playback; no autoplay of a guessed match. Use the existing WebStreamPlayer and embed URL utility. Back to results retains the current search; Change source restores the chooser. Controls remain visible in loading/empty/error/populated states, temporarily disabled during an operation; exhausted Search more reports exhaustion. Use GPT is explicit and displays setup guidance when unavailable. Cancellation uses existing AI jobs. Abort local requests on unmount; late responses cannot replace a different movie. Desktop only.

### Backend

POST /api/youtube/movie-search accepts tmdb_id for a new session or search_id for the next page. No client-supplied runtime. Resolve metadata and Arabic aliases, validate finite positive runtime, then search one 50-result page per click. Batch videos.list for actual duration. Include exact 95% and 105% boundaries. Unknown duration is ineligible. No channel/license/official filters; non-embeddable candidates remain available via YouTube. Title similarity and duration proximity order possible matches; never claim completeness. Each session has an opaque ID, bounded in-memory lifetime/size, accumulated deduplicated results and queued query/page pairs. Serialize a session's mutations. Failure leaves query/page pending for retry and preserves prior results. No catalog writes or migration.

POST /api/ai/youtube/movie-search accepts search_id and request_key, checks F6/account readiness, creates an existing durable AI job. Worker sends public movie metadata, attempted queries and bounded candidate titles to the selected account/model. One model call proposes up to three Arabic-only queries for Arabic films (otherwise appropriate titles), with an explanation. Only schema-validated queries are searched. Every result passes the same runtime gate. Output includes the accumulated search snapshot. Cancellation checked before inference and each network search. No automatic GPT call or hidden retries. Session expiry yields an explicit restart instruction.

## Implementation sequence

- [x] Task 1: Add failing backend tests, implement search/session owner and routes, verify actual returned candidates and adverse cases.
- [x] Task 2: Add F6 schema/worker and job route with failing tests for explicit use, permission, malformed output, Arabic query enforcement, cancellation and runtime preservation.
- [x] Task 3: Integrate shared dialog, add compiled desktop tests for chooser, results, pagination, GPT, errors and playback navigation; preserve IPTV/TV flows.
- [x] Task 4: Run focused and broader affected suites, build isolated dist, inspect rendered desktop UI, independent review, update knowledge pages/report.

### Execution ledger and review decisions

- Current source, including ignored frontend dependencies/assets needed to build, was preserved in the isolated worktree. Tests use temporary data roots; no live credentials are copied.
- `StreamSourceList` now owns reusable selection-row markup. IPTVSourceList only maps provider fields into that shared component; existing CSS/geometry and unavailable behavior are preserved.
- Runtime missing or non-finite: report a metadata error. No hidden inference or duration relaxation. Missing Arabic title: explicit metadata error. Mixed Arabic/Latin title suffixes are removed before querying.
- Additive F6 registration required updating existing feature enumeration assertions from five to the explicit six feature IDs. No existing feature was removed or weakened.
- Independent reviewer found failed GPT query retry loss, hidden partial results, and mixed Arabic/English aliases. Reproduction tests failed before the corrections and passed afterward. Validated GPT queries now enter the same retry queue before network work. Failed jobs return accumulated results with the error. Cancellation uses read-only POST `/api/youtube/movie-search/status` to recover already found matches and suppresses late result commits.
- No commits or live integration performed. Baseline source-string assertions that already fail on desktop were left intact; see report.

## Acceptance matrix

| Scenario | Expected result | Verification |
| --- | --- | --- |
| 100-minute movie; 5699/5700/6300/6301-second videos | Only 5700 and 6300 accepted | Service + API tests |
| Arabic film with English display title | Every deterministic/GPT query uses Arabic name | Service/worker tests |
| Any uploader, official words/license | Same eligibility/ranking | Service tests |
| Missing/NaN runtime, missing Arabic title | Metadata error; no unfiltered search | Service/API tests |
| Search more repeats video; later page | Append once; retain original rows | Service + desktop |
| Upstream error | Explicit error, retain rows and retry same page | Service + desktop |
| Empty/exhausted | Honest status; Search more/Use GPT visible | Desktop |
| Normal source/search more | Zero GPT requests | API/desktop |
| Explicit GPT | Real validated search results, ±5% unchanged | Worker + desktop |
| GPT malformed/cancelled/English Arabic query | No invalid searches; visible error | Worker tests |
| Source switch/close/late response | No stale playback/results, IPTV cleanup preserved | Desktop regression |
| Disabled web/TV/other Movie surfaces | Existing behavior preserved | Existing regression suites |

## Verification and rollout

Use desktop .venv Python with CP_TEST_MODE=1 and a new temporary CP_TEST_ROOT. Build using existing dependencies into worktree dist. Run unittest modules for YouTube, streaming config, AI provider/skills/jobs/routes and new worker. Run Playwright desktop Movie chooser, streaming providers/player and new YouTube scenarios against disposable backend. External API behavior is fixture-tested; live account/key usage is not implied by those tests. No commit/restart/activation. Record failures and exact limitations in docs/verification/youtube-stream-2026-11-14/report.md.

## Installation authorization and result

2026-11-14: Dante approved applying the feature to the main CP installation and will restart CP himself. Incremental sources and rebuilt frontend are installed; 72 focused tests passed in the main checkout. Backend restart is pending. This does not authorize commits, pushes, packaging, or catalog changes. See the installation update in the verification report.
