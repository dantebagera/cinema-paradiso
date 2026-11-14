# ChatGPT across all CP AI features — implementation plan

**Status:** Updated 2026-11-02 for an explicitly requested implementation handoff. Dante authorized updating the plan, accepting any positive whole-number GPT recommendation target, moving the login check to the beginning, preserving Ollama, and creating a new task to implement it. The October 24 request authorized planning only; the November 2 instruction now authorizes implementation in the new task within the boundaries below. Unanswered product choices are identified separately; production activation, commits, packaging, and publication remain unapproved.

**Goal:** Add ChatGPT as a Settings-selectable provider for every current CP AI function, using separate GPT instructions, while preserving Ollama's skills, configuration, request contracts, and observable behavior.

**Architecture:** One provider-selection owner supplies an immutable selection to each AI operation. Provider-specific inference and instructions remain separate; existing Movie, TV, IPTV, catalogue, matching, acquisition, and review owners remain authoritative for product behavior. GPT receives validated, narrowly scoped tools and cannot execute a mutation by inventing a confirmation.

**Tech stack:** Existing Python/Flask, SQLite, React/Vite, and desktop Windows deployment. Direct documented ChatGPT OAuth and Responses API integration; no Codex installation, browser scraping, private ChatGPT endpoint, or separate API-billing fallback. Add `PyJWT[crypto]>=2.15.1,<3` for verified ID tokens. Windows DPAPI protects stored credentials; other operating systems require a separately reviewed secure-storage implementation before their ChatGPT option is enabled.

**Spec:** `docs/ai-skills/chatgpt/REVIEW.md`, both linked draft skills, and their capability catalogue. Current CP contracts and the preservation requirements below take precedence over draft wording.

**Execution:** Use the executing-plans workflow in the new implementation chat, starting with Task 0's isolated login/inference gate before general feature implementation. This plan does not authorize delegation or a new worktree. Reuse the current local project and preserve its dirty baseline; any later isolation must contain the intended working-tree changes and untracked skill/plan files, not just HEAD. No automatic commit steps.

**2026-11-02 amendment:** ChatGPT uses its configurable Settings count (15 only as the initial value), accepts any positive whole-number request target without an arbitrary movie-count maximum, and works through resumable batches. Real account login plus one minimal synthetic inference must succeed at the beginning, not after the rest of the feature is built. Ollama's settings, skills, limits and behavior remain unchanged. This is a planning amendment and implementation dispatch, not evidence that either login or implementation has already succeeded.

## Problem and decision

### What happens now

- Discover's Ask AI calls `/api/ollama/recommend`. Its simple movie prompt and post-processing use the configured candidate limit: default 15, allowed 1–50.
- AI Control uses `_ollama_chat_content` for interpretation and one repair attempt, then the existing four-action planning/execution owner. Its filters and person-filmography branch cannot fulfill arbitrary richer GPT commands merely by changing the prompt.
- Movie Smart Match uses a separate eight-file title/year/alias prompt and targeted repair, followed by deterministic TMDB/Plex search/ranking and explicit review/apply.
- IPTV has separate configuration and a separate `/api/generate` runner. It supports optional catalogue classification and ranking of real TMDB candidates. Its visible bulk-classification preview is currently deterministic/manual, not an AI call.
- No shared ChatGPT connection, account storage, provider selection, or GPT tool executor exists. Existing UI readiness checks often depend specifically on Ollama URL/model or IPTV's `ollama_enabled`.

### What Dante wants

1. Choose Ollama or ChatGPT from Settings.
2. Keep existing Ollama skills and operation intact, including Gemma/Nemotron-oriented instructions.
3. Use a separate set of GPT instructions when ChatGPT is selected.
4. Make every existing CP AI function capable of using ChatGPT, including the separate IPTV paths.
5. Support requested recommendation quantities and complete factual sets through batches and pagination.
6. Give GPT AI Control richer understanding, studio/company discovery, combined conditions, follow-ups, and an honest catalogue of CP functions.

### Confirmed, unknown, and proposed

**Confirmed:** The source paths and restrictions below exist; official documentation describes the local-personal-project sign-in route; earlier bounded TMDB reads found company search and company-based discovery usable. None of this proves Dante's ChatGPT account can complete inference through a new CP registration.

**Unknown:** Actual account admission, model availability, and provider-specific tool support for that account; end-to-end GPT behavior; baseline test results for this dirty checkout. Those require their distinct verification gates.

**Decision record for implementation:**

| ID | Exact proposal | Why it needs to be explicit |
| --- | --- | --- |
| P1 | **Approved 2026-11-02:** No automatic cross-provider fallback. A selected-provider failure is shown; switching provider is an explicit user choice. Existing deterministic/classic fallback inside a feature is retained and labelled. | Dante selected “Show failure; switch providers manually.” |
| P2 | **Approved 2026-11-02:** use GPT's saved Settings count when the request omits a quantity; 15 is only its initial value. Both the GPT setting and an explicit request accept any positive whole-number target with no arbitrary movie-count maximum. Explicit requests override the default for that request only; batches and Continue preserve the exact target. | Ollama's separate setting remains 1–50 and is not changed. A requested target does not guarantee enough eligible films exist or an uninterrupted plan allowance. |
| P3 | **Approved 2026-11-02:** The default for a factual studio list is released movies of at least 60 minutes, including long films and feature documentaries. Show unknown-runtime records as unresolved. Shorts, documentary exclusion, and upcoming inclusion are explicit scope options. | Dante selected this default with explicit shorts/upcoming options. Runtime scope does not prove official filmography membership. |
| P4 | **Approved 2026-11-02:** Selecting ChatGPT explains cloud use. Separate explicit Settings toggles authorize basename/folder/title hints for local identity matching and playlist/sample titles for IPTV assistance; both start off. | Dante selected separate opt-ins, initially off. No paths, stream URLs, credentials, or whole-library dumps are permitted. |
| P5 | Existing AI consumers must all work before the integration is called complete. New AI Control operations are enumerated below; high-impact administrative operations open their existing review/settings workflow rather than grant a generic execution tool. | A full CP capability catalogue is not permission to invent arbitrary backend operations. |

P1–P5 are now approved within the recorded scope. Dante explicitly answered the three remaining product questions in the implementation chat on November 2. Continue within this plan without repeated blanket permission. No agreed contract may be weakened through general implementation authorization.

### Scope and exclusions

In scope: all five current model consumers, connection and provider selection, GPT-specific skill loading, richer catalogue retrieval, recommendation continuation, GPT AI Control and its supported domain actions, desktop UI, isolated verification, and a separately authorized activation procedure.

Not included: changing or tuning Ollama, introducing API billing, automatically running AI during normal browsing/scanning/enrichment, importing ChatGPT histories/memories, mobile redesign, changing movie/TV identity ownership, changing torrent validation/trust/queue rules, arbitrary system administration, or executing the older TV bulk-identity proposal as though it were already shipped.

## Contracts affected and contract-change decision

| Contract and source | Agreed behavior and genuine exceptions | Affected surfaces/callers | Proposed behavior | Changes the contract? | Dante's explicit decision |
| --- | --- | --- | --- | --- | --- |
| Dante: "keep ollama and its skills untouched" | Preserve old prompts, repair prompts, settings, protocols, limits, validation, fallback, and user-visible outcomes when Ollama is selected. | All five AI consumers and Settings. | Add provider composition around existing owners; do not rewrite old Ollama inference functions. | No weakening permitted. | Explicit requirement, 2026-10-24. Implementation pending. |
| Provider choice | Current AI paths are tied to Ollama; IPTV has its own Ollama settings. | All AI entry points and readiness checks. | One global choice; GPT readiness is independent of Ollama settings. IPTV's existing Ollama configuration remains authoritative for its Ollama path. | Additive requested behavior. | Explicit request for all AI features; exact P1/P4 handling pending. |
| AI Control card-first complete-selection plan | Complete command scope starts selected, persists across pages, and is reviewed before writes. Plans are one-shot and expire. | AI Control, lists, download review, deletion. | Same semantics for GPT; truthful completeness and durable GPT session/job context. | No weakening. | Preserve. |
| Identity review and validation | AI proposes; provider evidence and deterministic validators decide eligibility; user explicitly applies. | Movie TMDB/Plex matching and IPTV matching/classification. | Same rules with GPT outputs normalized into existing domain contracts. | No weakening. | Preserve. |
| IPTV isolation and credential-free AI evidence | Provider data remains scoped; the Ollama endpoint remains credential-free localhost HTTP; no invented TMDB identity. | IPTV settings, matching, classification, metadata worker. | Keep the Ollama restriction unchanged. Add a separate GPT metadata-only channel behind explicit P4 consent. | New cloud channel; do not claim that a localhost Ollama endpoint guaranteed local inference, since its model may itself be cloud-backed. | Exact allowed evidence and P4 consent require review. |
| Watched and availability | Movie Watched requires owned Library content; IPTV/streaming availability is not ownership. | Lists, curation, recommendations, AI Control. | Existing rules enforced by owners, not GPT confidence. | No. | Preserve. |
| Movie eligibility and full catalogue | Curator excludes TV/shorts/unreleased; factual studio membership needs an explicit definition. | GPT curator and studio AI Control. | P3 scope, displayed exclusions, unresolved counts, no claim of official completeness beyond the query evidence. | New GPT scope definition. | P3 pending. Ollama unchanged. |
| Source selection and acquisition | Separate Movie/TV/AI Control trust selections, validated identities/manifests, explicit upgrades, existing quality/profile/queue rules. | Downloads and acquisition tools. | Reuse owners; unsupported quality is reported rather than silently changed. | No. | Preserve. |

**Contract-change gate:** No existing review, safety, domain, or eligibility rule is relaxed by this plan. If implementation or a test demands such a change, stop that part and send the prominent `## ⚠️ CONTRACT CHANGE — DANTE'S DECISION REQUIRED` notice required by `AGENTS.md`, with CURRENT RULE, PROPOSED RULE, WHAT DANTE WILL SEE, AFFECTED AREAS, REASON, COST OR RISK, ALTERNATIVE, and RECOMMENDATION. A proposed test that accepts the violation must be reported, not treated as a decision.

## Current design and ownership

### Baseline observed during planning

The following process/bundle/source observations are the **October 24 snapshot**, not a verified November 2 runtime. During the November 2 handoff the branch/HEAD remained the same, while the working tree had 121 changed tracked entries and 155 untracked entries; `app.py`, Settings and other files have changed since the old audit. The implementation task must refresh source, process, data, and served-bundle ownership before coding or claiming live parity, preserve all intervening work, and not reuse old source fingerprints as the current baseline.

- Checkout: `C:\Users\dante\Desktop\cinema paradiso`; branch `master`; HEAD `be511f98846a67a182e5b371ad087938e9344362`.
- Git status at the planning audit: 116 changed tracked entries and 151 untracked entries (including previously authored skill drafts). Counts are a snapshot, not a clean-state claim. Re-record exact paths and source fingerprints at implementation start; preserve unrelated concurrent work.
- Main configuration: checkout `config.json`; user data: checkout `data`; TMDB cache: checkout `cache`. IPTV metadata settings are owned separately under the user-data IPTV directory.
- Port 5000 owner: PID 51992, `C:\Program Files\Python312\python.exe`, command `python.exe app.py`, created 2026-10-24 22:10:31 Cairo. The command alone does not prove its working directory or loaded source revision; verify those before any live claim.
- Candidate frontend in this checkout: `dist/index.html`, modified 2026-10-24 22:10:28 Cairo, SHA-256 `695E94FC071215559545E280C896F3EDDD17016C23B6D64DADCE22F1651146FA`; references `/assets/index-CwW9dSyz.js` and `/assets/index-3_nuXu-W.css`. No HTTP/body comparison was performed in this planning turn; served-bundle identity remains a live gate.
- Package version: `3.0.0-beta.2`. Source version, process start time, runtime configuration, and served bundle are separate facts.
- No application tests, account connection, inference, scan, database query, download, or restart was performed to write this plan. Older passing results are not this checkout's baseline.

### Mandatory AI coverage map

| ID | Current model responsibility | Current owner/caller | GPT skill and integration | Completion proof |
| --- | --- | --- | --- | --- |
| F1 | Pick My Movie / Ask AI recommendations | `DiscoverWorkspace.askPickMyMovie`; `app.py::ollama_recommend` → `_ollama_api_json`. | `movie-curator/SKILL.md`; GPT recommendation jobs; same TMDB validation/card projection. | Works with Ollama absent, requested count >50, continuation, exclusions, cancellation, and valid cards. |
| F2 | AI Control interpretation and repair | `/api/ai-control/preview`; `services/ai_control.py::_parse_intent`, `_intent_messages`; `_ollama_chat_content`. | `ai-control/SKILL.md`; GPT tool loop and validated search/action preparation. | All existing four actions plus the explicitly registered additions work through domain owners; no GPT request uses Ollama's flat prompt. |
| F3 | Local movie identity hints and targeted repair | Movie Maintenance/Unmatched → Smart Match; `_smart_match_ai_batch` and `_process_smart_match_batch`; `services/smart_match.py`. TMDB and Plex database choices both use this inference. | New `movie-identity/SKILL.md`; typed title/year/alias output, existing parsing/ranking/review/apply. | Both TMDB and Plex paths, malformed/duplicate/missing IDs, accented/Arabic basenames, cancellation, and explicit apply. |
| F4 | Optional IPTV category assistance | `IPTVMovieService.classify_catalog(use_ollama=True)` → `_ollama_classification_decision` → runner. Visible `classification_preview` is deterministic/manual today. | New `iptv-classification/SKILL.md`; optional provider-aware category inference. Add an explicit GPT AI-classification preview, leaving current Classify/manual choices unchanged. | Bounded sanitized evidence, categories/exceptions validated, provider isolation/manual locks, uncertain result remains review. No background AI activation. |
| F5 | IPTV ranking of real movie candidates | IPTV Match selected with AI → `create_match_job` → `_proposal_for_source` → `ollama_runner`. | New `iptv-matching/SKILL.md`; rank only the supplied candidate set; same deterministic threshold and apply gates. | No Ollama prerequisite under GPT; out-of-set/low-score IDs rejected; no cross-provider IDs; user-selected apply only. |

All F1–F5 are release requirements. An intermediate phase may be useful but must be labelled incomplete. The final coverage report must include frontend entry, backend branch, readiness gate, selected provider, skill hash, output validator, error behavior, and test evidence for each row.

### TV history must not be misrepresented

`docs/plans/tv-user-action-corrections-implementation-plan.md` contains the folder-aware TV Bulk Identity Skill v1 specification. It is a CP-owned, versioned input/output contract, not an installed Codex skill. The current `TVLibraryDiscovery`, `TVIngestion`, `TVMetadata`, and episode parser have no model call, and the current TV routes expose no corresponding AI identity job.

Preserve that specification and its supplied-candidate/folder-evidence/review requirements. Do not quietly implement or change its Ollama skill in this project. TV discovery, coverage, lists, monitoring, acquisition preparation, and existing review actions are available to GPT AI Control through the TV owners below. A standalone TV bulk-identity implementation needs a separate explicitly approved scope; the final report must state this distinction rather than claim an existing AI consumer was migrated.

### Authoritative owner map and file boundaries

| Responsibility | Existing owner to reuse or extend | Planned files and exact responsibility |
| --- | --- | --- |
| Global configuration/save | `app.py::_load_config`, `_save_config`; existing runtime composition. | New `services/ai_provider.py`: typed provider configuration, readiness, immutable operation binding, redacted public state. Additive config keys only. |
| Credentials/authentication | No ChatGPT owner exists. | New `services/chatgpt_credentials.py`: DPAPI storage, atomic replacement, per-profile refresh lock. New `services/chatgpt_auth.py`: OAuth attempts, loopback listener, OIDC verification, account registration/revocation. |
| Inference | Existing Ollama helpers stay unchanged. | New `services/chatgpt_transport.py`: allowlisted public endpoints, account model list, SSE parser, complete/error/tool-call handling, bounded retries/cancellation. |
| GPT instructions | `docs/ai-skills/chatgpt/` drafts. | New `services/chatgpt_skills.py`: explicit feature→GPT resource mapping, required schema/version/hash. Promote reviewed GPT resources to `resources/ai/chatgpt/<skill>/SKILL.md`; docs remain the design/reference rather than the runtime dependency. |
| GPT jobs/sessions | Existing feature jobs remain with their owners. | New `services/ai_jobs.py`: GPT request/session/result persistence and lifecycle, not another catalogue or acquisition journal. |
| Movie query validation | `services/advanced_search.py`, `services/tmdb_advanced_search.py`, catalogue repository/read APIs. | Extend those owners for controlled company criteria. New `services/ai_catalog.py`: traversal, exact result-set handles, completion accounting, ownership intersection; no second query compiler or SQL membership rules. |
| AI Control plan/execution | `services/ai_control.py::PlanStore` and domain services. | Add a public resolved-plan seam to this owner. New `services/chatgpt_tools.py`: typed read/prepare operations bound to domain owners. New `services/chatgpt_agent.py`: bounded inference/tool-result loop, no independent persistence/mutation authority. |
| HTTP composition | `app.py`; existing feature route modules. | New `services/ai_routes.py`: generic config/auth/GPT jobs/session endpoints; `app.py` supplies real dependencies. Existing domain routes retain their purpose. |
| Movie Smart Match | `app.py`, `services/smart_match.py`, existing coordinator. | Pass a pinned AI binding into the existing job/batch boundary; retain classic matching, evidence/ranking, repair semantics and explicit apply. |
| IPTV inference | `services/iptv_provider_manager.py`, `iptv_movie_service.py`, `iptv_movie_classifier.py`, `iptv_routes.py`. | Inject the shared selected-provider owner; retain the existing `ollama_runner` seam for Ollama/tests. Add GPT dispatch and provenance at the inference boundary, not a second matching/classification service. |
| Desktop UI | Settings `IntegrationCard`/`ActionButton`; shared cards; Smart Match review; IPTV proposal panels; current TV/acquisition review components. | `src/api/ai.js`, `src/context/AIProviderContext.jsx`, `src/components/AIProviderStatus.jsx`, `src/components/AIJobProgress.jsx`; targeted changes to existing feature components. Reuse parent Settings card markup; do not clone its JSX/CSS. |

### Ollama preservation boundary

- Keep every `app.py::_ollama_*` helper, `ollama_recommend`, and `_smart_match_ai_batch` inference/repair body unchanged. Keep the Ollama config/model-list/scan/test routes and payloads unchanged.
- Keep the current text and behavior of `services/ai_control.py::_intent_messages`, `_parse_intent`, `_heuristic_intent`, and its legacy interpretation/normalization path. Do not pass GPT into an argument called `ollama_chat` or force GPT through this prompt/schema.
- Keep `IPTVMovieService._run_ollama`, existing Ollama evidence construction, and the public Ollama settings/localhost validation unchanged. Preserve `_ollama_classification_decision` results exactly; its provider-neutral category/threshold mapping may be extracted once for reuse by GPT, without changing its Ollama input, inference, output, error, or persistence behavior. `src/features/settings/ollamaModels.js` remains byte-identical.
- Existing Ollama UI fields, saved values, model access scans, test behavior, 1–50 candidate limit, repair count, classic fallback labels, and API results remain identical. Additional shared provider-status metadata must not alter the old route response contracts relied on by tests/callers.
- Shared non-inference owners may acquire neutral public seams or additive metadata only with old-result regression proof. If preserving a frozen body prevents a required integration, revise the plan with Dante; do not silently redefine "untouched."
- The legacy Ollama implementation is a deliberately retained, user-required provider contract, not an obsolete fallback to delete later. New GPT code must not copy catalogue, matching, acquisition, or confirmation business rules.

## Exact behavior contract

### Provider configuration, readiness, and operation binding

Add top-level `ai_provider` (`ollama` by default for old installations) and `chatgpt` with `active_account_id`, `model`, `recommendation_count` (initially 15, user-adjustable to any positive whole-number target), `allow_movie_identity_hints` (false), and `allow_iptv_titles` (false). These values are provider-specific; do not overwrite any `ollama_*`, `ai_control_ollama_curated_lists`, or IPTV Ollama settings. Preserve unrelated config fields on save.

The explicit requested quantity takes precedence over the saved GPT default for that job and does not silently rewrite Settings. Validate a positive whole number, reject zero/negative/fractional/non-numeric/boolean values, and impose no arbitrary 50/100/500/1000-movie ceiling. Keep the UI value as decimal text and accept decimal text or exact integer API inputs; canonicalize/persist large targets as decimal text so JavaScript's safe-integer limit does not silently round them. Requested quantity is separate from accepted/fetched counts. Ordinary HTTP payload limits and resource budgets remain in force; they must not be presented as a secretly reduced target.

`AIProviderService.snapshot(feature: str, *, domain_id: str | None = None) -> AISelection` returns an immutable object containing `provider`, `config_generation`, `account_id` or Ollama configuration reference, `model`, `skill_id`, `skill_version`, `skill_hash`, `feature`, and optional IPTV provider ID. Capture it once at operation creation and persist its safe provenance with GPT jobs and feature proposals. Never place tokens in it.

Provider choice is fixed when an operation starts; an existing operation never changes from Ollama to GPT or vice versa halfway through a batch. GPT model/account/skill choices are also fixed for that operation and its continuation. Preserve legacy Ollama model-setting semantics: its unchanged helper may read the current Ollama model at call time, as it does today; this project must not silently change that behavior to enforce a new GPT rule. Do not describe an initial Ollama model value as proof of every later call's model. Explicit GPT sign-out/revocation stops further calls using that account and cancels/pauses affected jobs with an account-disconnected reason. Switching the selected provider alone does not discard a reviewed plan.

GPT readiness is account permission + configured model + feature permission + feature dependencies, not the presence of Ollama. For F5, IPTV TMDB remains separately configured; the main Movie TMDB key is not substituted. Missing permissions/configuration are `integration_missing`/`consent_required`, not no matches. If Ollama is selected, retain every legacy per-feature enablement rule.

Explicit legacy `/api/ollama/*` routes remain Ollama-specific. Frontend recommendation dispatch uses them only when Ollama is selected; GPT uses the new job route. Existing generic AI Control/Smart Match/IPTV operations branch at their authoritative inference composition point according to the pinned global choice. No user-facing AI button may bypass this choice through a hardcoded Ollama check.

For old synchronous AI entry points that cannot represent GPT jobs (`/api/ai-control/preview` and IPTV's old AI matching request), first-party GPT clients use the new job routes. If an old request arrives while GPT is selected, return 409 `ai_job_endpoint_required` with the correct new route and make zero Ollama calls; do not silently execute the wrong provider. Under Ollama, keep the existing route behavior unchanged. Movie Smart Match already has a job owner and keeps its current route.

### OAuth and protected credentials

1. `ChatGPTAuth.start(*, account_id=None) -> {attempt_id, expires_at}` creates a 10-minute single-use attempt, starts an HTTP listener on `127.0.0.1:<available_port>/auth/callback`, and opens the system browser only after an explicit Continue with ChatGPT action. Keep scheme/host/path stable across registration; vary only the port. Do not use port 5000 as the OAuth listener or assume port 1455 is free.
2. Persist a random `urn:uuid:<UUIDv4>` host ID once for this installation. Start first registration with `dynamic_agent_client`, actual app name `Cinema Paradiso`, PKCE S256, fresh state/nonce, identity scopes and `offline_access resource.invoke chatgpt.tokens.use.direct`, and resource `https://api.openai.com/v1`. Reauthorization uses the issued client ID and the selected account's retained hints; never save `dynamic_agent_client` as an issued ID.
3. Validate state and error before consuming the callback. Reject unsolicited/duplicate/expired callbacks, wrong client IDs, or redirected host/path changes. Exchange once with the same URI/resource/verifier. A failed/denied attempt must not replace an active profile.
4. Verify ID-token signature using OIDC discovery/JWKS from the fixed OpenAI issuer, expected issued-client audience, expiry, nonce, and account identity. Choose allowed asymmetric algorithms from trusted provider configuration, not the token header. Require plan-use scope before inference. Use PyJWT with crypto dependencies; no handwritten JWT signature code.
5. Store each issued client/account registration separately, including same-email registrations. Use `<user_data_dir>/ai/chatgpt/host.json` for the opaque host ID and `<user_data_dir>/ai/chatgpt/profiles/<opaque_uuid>.bin` for each DPAPI-protected registration/token record. No email/client ID is used as a filename. Save profile mapping, tokens, scope and expiry together with owner-only ACLs and protected atomic replacement. Use a Windows named mutex derived from the installation/profile opaque IDs for each refresh lock; never put a credential in its name. Preserve the installation host ID and profile mapping on sign-out, clear that session's tokens, and leave other accounts intact.
6. Refresh 60 seconds before expiry under a per-profile cross-process lock, re-read the current record after acquiring it, and atomically replace the rotating refresh/access/ID token set. Temporary failures preserve the record. Terminal invalid-refresh/revocation marks the profile disconnected; do not loop OAuth or mix another profile's credentials.
7. On sign-out attempt the discovery-provided revocation endpoint, then clear local tokens. If remote revocation cannot be confirmed, report that fact and the Manage usage/disconnect option. No authentication endpoint, log, browser storage, support export, URL, or exception may expose token values. Retained ID-token hints are sent only to the OpenAI authorization endpoint and redacted from diagnostics.

Credential storage is machine/Windows-user-bound. A relocated/friend package must not include credentials or the host ID; it generates its own host and signs in. Do not auto-copy identity on a data-root relocation. Existing general relocation/package owners must explicitly exclude these records; a move affecting them requires a reviewed reauthentication outcome. No credential migration is performed in this implementation without approval.

Implementation detail verified November 2: changing the app-data root stops old-root AI jobs and pending auth attempts before changing the shared root, clears the active account/model selection, preserves the old encrypted records in place, and reports that reauthentication is required. No credential or host record is copied. Runtime skills ship under `resources`; the transferable catalogue backup excludes `ai/chatgpt`; recipient config retains only the count preference and resets account/model/evidence permissions.

### GPT transport and response contracts

`ChatGPTTransport.list_models(selection) -> list[{slug,display_name}]` uses the selected account's public `/v1/models` response, preserving display order and `visibility == list`. A listed model is not proof a request will be admitted. Do not hardcode a preferred model or silently replace an unavailable saved choice.

`ChatGPTTransport.run(selection, *, instructions, input_items, tools, cancel) -> CompletedResponse` calls `POST https://api.openai.com/v1/responses`, `store:false`, `stream:true`. Supply current task context in the input array and instructions/developer messages. Do not forward Ollama `format`, `options`, `temperature`, explicit system-message items, or the unsupported fields documented for this OAuth route. Namespace function tools according to the supported public contract; no hosted tool-search/MCP/computer-use dependency.

Assemble tool arguments by tool-call ID across SSE deltas; execute only after a complete terminal response and complete argument validation. Handle fragmented UTF-8/lines, multiple content items, errors after text starts, `response.failed`, `response.incomplete`, cancellation, and missing terminal events. Only `response.completed` counts as complete inference. Validate local schemas even if a model advertises structured outputs.

Typed final-result tools: curator returns `{recommendations:[{title,year,reason}]}`; movie identity returns `{matches:[{id,title,year,alternatives:[{title,year}]}]}`; IPTV category returns the existing six-field classification shape; IPTV ranking returns `{tmdb_id}` selected from supplied candidates. Schemas are generated/maintained in the transport/skill registry, not duplicated as handwritten JSON instructions. Do not expose mutation execution tools to the model.

Runtime constants: two concurrent GPT HTTP requests installation-wide; 15-second connection timeout; 60-second response-idle timeout; 180-second individual inference deadline; 2 MiB buffered inference limit; at most one transport retry with 1–5 second jitter before any inference output on a transient failure, honoring Retry-After up to 30 seconds. Never retry ineligible/invalid-schema/admission errors or restart a partially streamed response as if it were the same action. One structured repair per batch is permitted; then report invalid/unresolved output. These are request safeguards, not total-result limits.

Each GPT job may make at most 24 inference requests (including repair/retry) per explicitly started/continued run. On exhaustion retain exact accepted results and enter `paused_budget`; Continue grants the next run without losing the requested total. Show the limit and pause state; never present a paused request as complete. Catalogue pagination does not require an inference call per movie. No background model scan or automatic continuous inference is added.

### Persistence, jobs, sessions, and retry

Create `<user_data_dir>/ai/ai.sqlite` lazily on the first GPT operation, not during normal Ollama-only startup. Schema version 1: `sessions`, `jobs`, `result_items`, `events`, `action_receipts`, and `inference_leases`. Store opaque IDs, revisions, sanitized conversation references, pinned selection/skill provenance, counts, cursors, result identities, and lifecycle; do not duplicate media/catalogue/acquisition truth or store tokens here. `acquire_inference_slot(job_id, cancel)` and `release_inference_slot(lease_id)` use transactional leases so the two-request installation limit also covers multiple CP processes sharing this data root; reclaim only expired leases with no live owner, not another process's active slot.

Job states: `queued`, `running`, `awaiting_clarification`, `awaiting_confirmation`, `paused_budget`, `completed`, `partial`, `failed`, `cancelled`, `interrupted`. `coverage` is separate: `complete`, `partial`, `unknown`. Polling is read-only; it never resumes work or starts inference. Browser cancellation cancels the job explicitly; merely leaving a screen must not execute or confirm anything.

`request_key` deduplicates creation by session, feature, binding, and canonical request digest. Same key/body returns the same job; same key/different body is 409. Claims and receipts use SQLite transactions and expected revisions. On restart, mark in-flight inference interrupted and do not replay mutations. Resume read-only retrieval only after user continuation, rechecking provider/catalogue generations.

Persist only the last 20 conversation turns plus durable result-set references and explicit user constraints. Never compact away approved scope/exclusions/confirmation revisions. Displayed page size is 20 (up to 100 on explicit page requests), not a total-result ceiling. Results are keyed by domain and stable identity, preserving remakes and same-title films. A session expires after seven days of inactivity; expired context produces a clear new-session message, not a guessed reference. Prune expired GPT session data only through a separately approved cleanup operation, not an unannounced filesystem deletion job.

### Generic backend endpoints

All new mutation endpoints accept only JSON, reject unknown fields, enforce same-origin/local application checks, and never expose raw internal exceptions. Do not retrofit or weaken unrelated existing endpoint security as a side project.

| Endpoint | Input | Exact output/effect |
| --- | --- | --- |
| `GET /api/ai/config` | None. | Selected provider, config generation, redacted account options/active ID, configured model/count, evidence-consent flags, feature readiness and reason codes. No tokens or secret config. |
| `PUT /api/ai/config` | `expected_generation`, `provider`, optional `chatgpt_model`, `recommendation_count`, and explicit evidence-consent flags. | Validate all supplied values atomically; 409 on stale generation; preserve all Ollama and unrelated settings. Missing credentials may leave GPT selected-but-unavailable with a clear status; no fallback. |
| `POST /api/ai/auth/start` | Optional saved `account_id`. | Start one OAuth attempt/open browser; return attempt ID/expiry, not an authorization URL containing hints. |
| `GET /api/ai/auth/attempts/<attempt_id>`; `DELETE` same path | Attempt ID. | Redacted pending/complete/denied/expired/error state; DELETE cancels and closes listener. |
| `POST /api/ai/accounts/select` | `account_id`, `expected_generation`. | Validate saved registration, update only active selection/model readiness, increment generation. |
| `DELETE /api/ai/accounts/<account_id>/session` | Account ID. | Stop future calls/revoke/clear that session and report remote-revocation confirmation. |
| `GET /api/ai/models` | Active account only. | Account-specific `{models:[{slug,display_name}]}` or typed unavailable reason. |
| `POST /api/ai/test` | Active account and configured model; no arbitrary prompt. | One minimal typed inference, reported successful only at complete terminal output; count toward request budget. No library/IPTV evidence. |
| `GET /api/ai/features` | None. | F1–F5 manifest plus typed AI Control capability availability and reasons for current provider. |
| `POST /api/ai/recommendations` | `prompt`, optional positive whole-number `count` (decimal text or exact integer), optional `session_id`, `request_key`. | GPT job/session ID and initial status; exact requested target retained across batches/Continue. Omitted count uses saved GPT Settings value. Ollama UI continues its unchanged explicit provider route. |
| `POST /api/ai/control/turns` | `prompt`, optional `session_id`, `request_key`. | GPT job/session ID; eventual clarification or validated plan, not direct mutation. |
| `POST /api/iptv/providers/<provider_id>/movies/ai/classification-jobs`; `POST .../ai/match-jobs` | Existing explicit/all-filtered selection, filters, `request_key`; classification has no forced manual category. | GPT-only 202 response with `ai_job_id` and provider-scoped proposal/result reference. Snapshot the selection generation/provider binding. Resume/cancel through AI jobs; expose the existing review/apply envelope only when its complete proposal set is ready. |
| `GET /api/ai/jobs/<job_id>` | Optional event cursor, result page/page size. | State, progress, pinned provider/model/skill, paged results, total/accepted/excluded/unresolved counts, coverage and errors. |
| `POST /api/ai/jobs/<job_id>/cancel`; `POST .../continue` | `expected_revision`; Continue includes a new `request_key`. | Cooperative cancellation; or explicit continuation from checkpoint without duplicate accepted items. |
| `POST /api/ai/control/plans/<plan_id>/confirm` | `revision`, selected keys, required confirmation phrase, `request_key`. | Invoke the existing reviewed operation through the domain owner; return/persist its receipt. No model-authored confirmation is accepted. |

Extend existing Smart Match/IPTV route responses additively with `ai_provider`, `ai_model`, `ai_available`, `ai_unavailable_reason`, and skill provenance for the new generic/GPT view. Retain the old `ollama_available` and old explicit Ollama response contracts for legacy clients; migrate first-party readiness consumers to generic fields. The legacy field remains as provider-specific information, not an alternate readiness authority.

### Rich movie retrieval and requested counts

Extend `services/advanced_search.py` with repeatable controlled `company` criteria for Discover, AND/OR joins, exclusions, and validated TMDB identity/name/country. `services/tmdb_advanced_search.py` compiles these to `with_companies`/`without_companies`. Keep existing query versions/criteria accepted; unsupported combinations return a named validation error. For local-only company filtering where canonical company facts are absent, resolve the factual TMDB set then intersect authoritative owned IDs; never invent a SQL company column or classify studios from filenames.

`AICatalog.resolve_company(text, *, page=1) -> candidates` uses company search, details/alternative names as needed and paged resolution. Confidence is not a first-result shortcut. Ambiguous Disney/group/brand requests produce one clarification and store the selected scope. Company groups are explicit saved query members; parent/subsidiary/history membership is not inferred from a name substring. No hardcoded Ghibli/Disney production branch.

`AICatalog.collect(query, *, requested_count: int | None, cancel, checkpoint) -> ResultSet` reuses the shared compiler, TMDB transport, person-role evidence and catalogue ownership lookup. Apply every condition, including after person-filmography retrieval. Return a stable result-set handle plus query fingerprint, provider totals, fetched-page counts, exclusions/unresolved counts, ordering, and coverage. Apply global sort before truncating a requested top-N; page-local filtering/sorting must not claim complete global results.

Follow provider pages to the requested count/exhaustion, up to the provider's documented accessible page range. If a query exceeds that range, return `coverage:partial` and the reason; do not claim all results or silently select a prefix. Date partitioning is not an unreviewed automatic workaround. Required failed pages or missing post-filter facts keep coverage partial/unknown. A partial set cannot become an "all" mutation plan; let the user explicitly revise the scope to the visible partial set and create a new plan.

Curator batches target 20 raw candidates at a time, deduplicate by verified movie identity, verify through the existing movie metadata/eligibility owner, and top up rejected entries within the inference budget. Do not change `_ollama_enrich_with_tmdb` or its old path; expose/reuse the authoritative metadata resolution beneath it for GPT. Record seen IDs and user constraints on the server. Recommendation exhaustion is a reported shortfall, never fabricated padding.

The Settings target, per-request target and per-batch size are distinct: a saved default of 75 requests 75, a request for 1000 targets 1000, and a batch size of 20 is neither a result cap nor permission to stop at 20. Budget/usage interruption pauses with exact progress and continuation; insufficient verified matches produces an honest shortfall. Never advertise unlimited guaranteed results or fabricate films to satisfy the number.

### GPT skills beyond the two drafts

Promote the reviewed curator and AI Control instructions without loading editorial review notes into model context. Add three concise GPT-specific resources as part of implementation:

- `resources/ai/chatgpt/movie-identity/SKILL.md`: preserve supplied file IDs; infer title/year/aliases only; evidence may be malformed; no arbitrary paths, catalogue IDs, binding, or rename authority. Eight-file evidence limit and existing missing/duplicate-ID validator remain.
- `resources/ai/chatgpt/iptv-classification/SKILL.md`: supplied category vocabulary, bounded playlist/title evidence, mixed/uncertain/exceptions, and structured six-field output. Reuse category validation; the confidence ≥0.9 and ambiguity/manual-review rules remain domain decisions, not model-configurable thresholds.
- `resources/ai/chatgpt/iptv-matching/SKILL.md`: choose among at most eight supplied real TMDB candidate records or report unresolved. Never invent an ID. Preserve the current deterministic eligibility threshold (78), manual locks, provider generation and explicit apply.

Use `validate_ollama_classification` as the unchanged existing shape validator through a neutral shared seam, with GPT provenance applied by the caller rather than persisting its legacy `method:ollama` label. Do not copy its business validation or rewrite its Ollama return/error behavior. Additional GPT schema checks may reject out-of-input title exceptions before calling the shared validator.

Skill version/hash and model/provider are server-owned job provenance; reject model attempts to overwrite them. A missing skill/schema disables only its feature with an explicit diagnostic. The final release gate fails if any F1–F5 skill is absent.

### AI Control capabilities and action authority

`ChatGPTTools.available(selection, context) -> list[ToolDefinition]` exports narrowly typed namespaced read/preparation tools. `ChatGPTTools.call(name, arguments, context) -> ToolResult` validates declared schemas, domain IDs and permissions before owner invocation. The model can retrieve information and prepare actions; only the authenticated user confirmation endpoint can execute the stored mutation.

`services/ai_control.py` remains the authoritative Movie plan/selection/execution owner. Add `prepare_resolved(action, *, result_set, list_name, plan_store, provenance) -> plan` that accepts an immutable validated result-set handle and uses shared plan assembly, rather than pretending resolved GPT results are raw library items or creating a second selection schema. Extract only provider-neutral plan assembly if necessary; preserve the old Ollama producers' exact results. The old interpreter remains untouched, including its existing behavior; richer GPT filter handling uses the validated shared search model.

| Capability group | GPT callable reads/preparations | Execution/owner contract |
| --- | --- | --- |
| Movie catalogue | `search_movies(query,count)`, `suggest_movies(prompt,count)`, `resolve_people(text,role)`, `resolve_companies(text,page)`, `movie_details(ids)`, `collection_details(id)`, `movie_relationships(id)`. | Existing TMDB/catalogue/relationship/awards owners. `suggest_movies` invokes F1's verified curator within the same job budget and labels the result subjective, not an exhaustive factual set. Return bounded summaries and result-set references, not raw provider credentials or entire caches. |
| Movie lists/curation | `list_movie_lists()`, `prepare_movie_list(action,list_id,name,result_set)`, `prepare_movie_state(kind,active,result_set)`, `prepare_collection_override(collection_id,parts)`. | Actions are create/rename/delete/add/remove; state kinds watched/watchlist/followed. Curation owner validates IDs, watched ownership, list membership and saved results. Deleting a list never deletes media. |
| Movie acquisition/deletion | `prepare_movie_download(result_set,quality,profile_id)`, `prepare_movie_delete(result_set,whole_movie_folders)`, `download_status(ids)`. | Existing source review, AI Control executor, acquisition and library mutation owners; owned upgrade, source trust, profile/quality, root/active-file checks, Recycle Bin, and confirmation phrases remain. No arbitrary paths from tool arguments. |
| Metadata/maintenance | `maintenance_status(kind,filters,page)`, `prepare_movie_match(file_ids,database,method)`, `prepare_rename(proposal_ids)`, `metadata_job_status(id)`, `prepare_metadata_apply(job_id,proposal_ids)`. | Existing Smart Match/metadata/rename preview/apply owners. Resolve file IDs locally; GPT gets only consented basename hints. Existing job cancellation/status are used, not a second audit engine. |
| TV | `search_tv(query,page)`, `tv_coverage(series_id,scope)`, `tv_lists()`, `prepare_tv_list(action,list_id,series_ids,name)`, `prepare_tv_state(series_id,kind,active)`, `prepare_tv_task(series_id,scope,action,season,episode_ids,profile_id)`, `tv_task_status(id)`, `prepare_tv_task_cancel(task_id,mode)`, `prepare_tv_delete(series_ids)`. | Existing TV repository/read/ingestion/monitoring/acquisition/bulk owners and review UI. Do not bind episodes from model output, bypass missing-episode gates, equate complete season/series, or remove existing bulk limits. |
| IPTV | `search_iptv(provider_id,kind,filters,page)`, `iptv_details(provider_id,kind,item_id)`, `iptv_lists(provider_id)`, `prepare_iptv_list(provider_id,action,list_id,item_refs,name)`, `prepare_iptv_favorite(provider_id,item_ref,active)`, `prepare_iptv_match(provider_id,selection)`, `prepare_iptv_classification(provider_id,selection)`. | Existing provider-local stores/review/apply owners. Never reuse a Movie list ID as an IPTV list or expose a stream URL as a catalogue result. F4/F5 require title consent. |
| Playback/history/notifications | `continue_watching(domain)`, `playback_status()`, `prepare_play(media_ref,restart)`, `prepare_clear_progress(media_ref)`, `notifications(page)`, `prepare_mark_notifications_read(ids)`. | Existing validated player/TV identities and progress/notification owners. No invented pause/seek/volume API. Unsupported player controls report unavailable and point to the player. |
| Copy/configuration/admin | `copy_job_status(id)`, `redacted_integration_status(kind)`, `open_review(surface,target_ref)`. | Copy initiation, settings edits, credentials, provider removal, runtime updates, migrations, artwork cleanup, raw qBittorrent controls, power actions and subtitle session actions route to their existing dedicated UI. The catalogue describes them honestly; no general execute endpoint is created. |

Read/preparation argument schemas are defined in `chatgpt_tools.py` using the existing query/domain contracts, not arbitrary untyped dictionaries. Define enums for every `action`, `kind`, `scope`, and media reference (Movie key, TV typed ID, IPTV provider/kind/item tuple). Unknown arguments/actions fail before owner invocation. Register only tools whose owner and review path are implemented; catalogue records distinguish callable, review-UI-only, disabled integration, and not implemented. `open_review` is navigation/preselection only and cannot submit, start a scan, or apply a proposal.

Keep the existing `ai_control_ollama_curated_lists` flag and its interpretation untouched. GPT creative curation is available only for an explicit subjective recommendation/list request through `suggest_movies`; it must never substitute creative suggestions for an "all studio/actor/franchise" query or silently turn the old Ollama-specific setting into a global permission.

For new action types, existing domain previews may need a server-owned plan envelope before their existing confirm operation. The envelope stores selection/snapshot/token/revision; it does not duplicate action rules. On confirmation revalidate owner generation and target state. Existing preview helpers that cause work must be labelled as preparation with those effects; do not call them during a supposedly passive status query.

Multiple requested actions become an ordered plan with dependencies and separately visible effects. Initial full-set selection and subsequent subset selection remain exact. On uncertain write outcome inspect the owner/receipt; never blindly retry. A failed dependency blocks later steps. Success means actual persistence/submission returned by the owner, not GPT's last sentence.

### Desktop UI contract

1. **Settings:** Add an `AI provider` IntegrationCard immediately before the existing Ollama card, reusing `IntegrationCard`, `ActionButton`, `dialog-field`, `settings-field-stack`, existing spacing/status/button styles. Provider select: Ollama / ChatGPT. Include ChatGPT account picker, Continue with ChatGPT, model picker, Test connection, Manage usage, Disconnect, recommendation count, and the two P4 evidence toggles. Save provider settings separately; never include old Ollama fields in this payload. Keep the complete existing Ollama card/controls and settings hash intact.
2. **States:** loading; Ollama selected; GPT selected/disconnected; browser sign-in pending/cancelled/denied/expired; signed-in but plan permission absent; model loading/empty/stale choice; ready; transient failure; usage limit; evidence-consent required. Preserve entered choices on failure. No scan of all GPT models; Test sends one minimal request only when clicked.
3. **Account/usage copy:** Use official Continue with ChatGPT action/approved branding. After first successful plan-use connection show the existing CP modal pattern once per registration with "You're using your ChatGPT plan" and Got it. Show "Using ChatGPT plan" and Manage usage near GPT inputs/status. Do not add CP subscription tiers, API charges, fabricated quotas or reset times.
4. **Shared status:** `AIProviderContext` owns the single cached redacted config/features state and generation. Settings saves invalidate it for all screens. Feature components use readiness from this owner, not their own Ollama booleans. A failed refresh displays stale/unavailable state and prevents starting an operation with an unverified selection.
5. **Discover:** Retain Ask AI placement, current input/button/card geometry, ownership attachment and source/list controls. Under GPT add requested-count field, progress/cancel, Load more/Continue state and a compact follow-up input. Use existing `SharedMovieCards`/`DiscoverResultGrid` and expansion/navigation owners. Do not alter Ollama's submission/count UI behavior or its card results.
6. **AI Control:** Retain existing command form, examples, shared cards, all-results selection, Add to list, Find sources and Confirm action. Under GPT show clarification/follow-up and job progress; reuse current result/receipt/review structures. Domain-specific TV/IPTV results reuse their existing card/review components rather than casting everything as Movie cards.
7. **Movie Smart Match:** Keep database TMDB/Plex independent of AI provider. Change AI readiness/help text to selected-provider state while retaining Classic/Match by AI and proposal/apply/rename controls. Display the pinned provider/model on the job. Ollama wording/behavior remains as before when selected.
8. **IPTV:** Retain the existing Ollama assistance settings block and its localhost URL/model/enabled fields. Add selected-provider status and GPT title-consent link beside it. GPT readiness must not require `ollama_enabled`. Keep current deterministic/manual Classify operations; add explicit "Classify selected with AI" for GPT, using the current classification preview/apply panel. Match selected with AI uses the global provider and existing proposal review.
9. **Help:** Add ChatGPT connection/provider-specific explanations and the data scopes. Preserve Ollama setup instructions. Label unavailable/newly unconnected capabilities accurately.
10. **Verification:** Desktop 1600×1000, plus a narrower desktop 1280×800; loading/empty/error/populated/long-content states; rendered counts, cross-page selection, navigation, Back/Forward, refresh, reconnect and provider switch. No mobile screenshots, CSS redesign or mobile tests in this scope.

### Failure, migration, and rollback

- Normal Ollama-only installs create no GPT database/credential files and perform no OpenAI network calls. Absent new config keys behave exactly as today. Failed GPT setup never erases Ollama settings.
- New GPT stores have their own schema version and atomic transactions. Do not migrate the Movie/TV/IPTV catalogue schema simply to add a provider. If existing proposal provenance cannot be added without a schema change, submit the exact additive migration/backup/rollback amendment before that task; do not improvise a broad migration.
- Respect existing job formats. Store GPT-specific provenance in the AI job store keyed to domain job IDs if the domain owner cannot accept additive metadata. Do not overwrite older job history or pretend it has GPT provenance.
- Rolling back source leaves existing catalogues and Ollama config intact. Switch the new provider selection to Ollama only through explicit authorized Settings action; do not silently auto-switch on error. Old code ignores new additive config; restore only the backed-up keys if a live rollback is approved. Retain GPT records for recovery, stop workers, and reauthenticate if machine-bound records no longer decrypt. No deletion is a rollback default.

## Implementation sequence

Each task requires a focused failing regression, the minimal implementation in its named owner, and the same check passing. No task grants permission to touch production. Commands below are future isolated checks, not actions performed while drafting.

### Task 0 — Prove login and one minimal inference before general feature development

**Files:** Add `tools/chatgpt_login_preflight.py` as a thin isolated diagnostic entry point. Build only the necessary initial portions of `services/chatgpt_credentials.py`, `services/chatgpt_auth.py`, `services/chatgpt_transport.py`, and their focused tests; Tasks 3–4 complete these same owners later. Use a tiny injected selection value for the diagnostic; do not require the full application, five skills, job database, new Settings UI, or existing CP account store first.

**Interfaces:** Reuse the auth/credential/transport interfaces specified below, with explicit injected root/browser/HTTP/clock dependencies. The diagnostic requires an OS-temp root, creates its own host/profile, performs the documented browser OAuth, lists available models, and sends one minimal request for the fixed response `CP_CONNECTION_OK`. It reports only redacted success/error/request IDs. It is a composition client of the future shared owners, not a second OAuth or inference implementation.

- [x] Read `AGENTS.md`, refresh the dirty/source baseline and capture the protected Ollama fingerprints **before any implementation edit**. Verify that the diagnostic cannot import/start the live CP server, read its credential store, change config, or launch media/download services.
- [x] Add focused failing fixtures for callback state/nonce/client/signature validation, protected atomic storage, the public request shape, complete-terminal handling and secret redaction. Implement only the authentication/transport foundation needed to pass them. Recheck current official documentation before the real request; do not assume October 24 endpoint access still holds.
- [ ] Present the isolated sign-in flow and let Dante complete the official OpenAI login/consent himself. The instruction to put login verification first authorizes preparing this gate; it does not authorize reading another app's account tokens, automating account consent, or sharing Dante's login with recipients.
- [ ] Once Dante explicitly connects this isolated registration and chooses an available model, perform **one** minimal synthetic inference, with no library, filename, IPTV or production data. This is the first of the total six real-call qualification budget; no API-key billing fallback. Record account admission, permission, model and terminal completion as observed facts without recording tokens.
- [ ] **Pass gate:** verified account permission and the complete expected response. Only then proceed to the rest of Tasks 1–11. **Fail gate:** stop dependent feature work, preserve working Ollama and redacted diagnostic evidence, and resolve the concrete admission/transport problem first. If user interaction is pending, report that dependency; do not build the rest and later claim the login was verified.

This is the first executable milestone. Later tasks extend the tested foundation and do not repeat/reinvent the login check. Minimal preflight fixtures become part of the permanent auth/transport regression suites.

**Implementation progress, 2026-11-02:** **Task 0 passed.** Dante personally connected the isolated registration, chose GPT-6.1 Sol and sent the synthetic check; verified plan permission and completed expected response observed. 1/6 real inference calls spent, no retry. 30 focused offline checks pass; protected source/config/dist comparison unchanged at that gate. Task 1 is in progress. See `docs/verification/chatgpt/task-0-2026-11-02.md` and the execution ledger. No live CP activation.

### Task 1 — Capture preservation fixtures and create a safe offline harness

**Files:** Create `tests/test_ai_provider_preservation.py`, `tests/ai_provider_server.py`; extend `tools/run_playwright_e2e.ps1` with an explicit `-AIProviderOffline` mode; add `tests/e2e/ai-provider.spec.js` skeleton scenarios.

**Interfaces:** Preservation captures source/AST and full serialized Ollama request/response behavior. The server injects fake OpenAI/TMDB/Plex/IPTV/acquisition/player/power dependencies before app composition. Offline mode refuses external hosts and live ports, uses fake qBittorrent and an OS-temp build/data root, and has no production-manager startup.

- [ ] Record current dirty paths and hashes, source-exact frozen functions/prompt literals, old Settings fields, and legacy request/response fixtures including repair/failure cases. Pin clocks/UUIDs only where needed for deterministic comparisons.
- [ ] Add tests that fail if any F1–F5 GPT path tries an Ollama dependency or if a test can reach live qBittorrent/OpenAI/media roots.
- [ ] Implement the offline harness through existing composition seams; do not use the current wrapper unchanged: it sets `CP_TEST_QBT_MODE=system`, which is not proof of isolation.
- [ ] Run `python -m unittest tests.test_ai_provider_preservation -q` in the isolated environment. Existing baseline snapshots pass; missing GPT behavior remains explicitly unimplemented.

### Task 2 — Add additive configuration and a complete feature registry

**Files:** Create `services/ai_provider.py`, `tests/test_ai_provider.py`; modify `app.py` config/composition only, new `services/ai_routes.py`, and `tests/test_ai_routes.py`.

**Interfaces:** `AIProviderService.snapshot(...) -> AISelection`; `public_config() -> dict`; `features() -> list`; `update_config(payload, expected_generation) -> dict` with the fields defined above.

- [ ] Fail tests for absent-key legacy default, no new I/O under Ollama, invalid/stale config, independent IPTV dependencies, and each F1–F5 readiness branch.
- [ ] Implement config and feature registry with all five IDs, domain dependencies and evidence consent.
- [ ] Assert saving/selecting GPT does not change any Ollama key/file/prompt or readiness value for the Ollama snapshot.
- [ ] Run `python -m unittest tests.test_ai_provider tests.test_ai_routes tests.test_ai_provider_preservation -q`.

### Task 3 — Implement protected account registrations and OAuth

**Files:** Create `services/chatgpt_credentials.py`, `services/chatgpt_auth.py`, `tests/test_chatgpt_credentials.py`, `tests/test_chatgpt_auth.py`; extend `services/ai_routes.py`; modify `requirements.txt` only for the declared JWT dependency.

**Interfaces:** Auth start/status/cancel; account selection/sign-out; credential `load(profile_id)`, `replace(profile_id, record)`, `refresh_lock(profile_id)` and metadata-only listing. Inject clock, browser opener, HTTP/OIDC/JWKS and secure-storage backends for tests.

- [ ] Fail cases for wrong state/nonce/audience/issuer/signature, unsafe algorithm, expired code, mismatched issued client, denied plan scope, same-email profiles, failed replacement, concurrent token rotation and sign-out during work.
- [ ] Implement the exact public flow and DPAPI atomic storage/ACL protection; no real login in unit tests.
- [ ] Verify every public response/log/error/export is token-free and a failed new account cannot replace an active one.
- [ ] Run `python -m unittest tests.test_chatgpt_credentials tests.test_chatgpt_auth tests.test_ai_routes -q`.

### Task 4 — Implement transport and five GPT-specific instruction bindings

**Files:** Create `services/chatgpt_transport.py`, `services/chatgpt_skills.py`, `resources/ai/chatgpt/{movie-curator,ai-control,movie-identity,iptv-classification,iptv-matching}/SKILL.md`, `tests/test_chatgpt_transport.py`, `tests/test_chatgpt_skills.py`.

**Interfaces:** `list_models`, `run` and `CompletedResponse` above; `load(feature) -> {instructions, tool_schema, version, hash}`. One authoritative output schema per feature.

- [ ] Fail streaming fixtures for split characters/arguments, missing terminal events, post-delta usage errors, unsupported fields, malformed/out-of-schema tool calls, cancellation, and repeated transient failures.
- [ ] Promote/review the two drafts and author the three specialist skills without changing any Ollama prompt or parsing path.
- [ ] Implement transport, retry/budget limits, redaction and complete-only output delivery. Missing specialist instructions must fail feature readiness.
- [ ] Run `python -m unittest tests.test_chatgpt_transport tests.test_chatgpt_skills tests.test_ai_provider_preservation -q`.

### Task 5 — Add GPT job/session state and recommendation batching

**Files:** Create `services/ai_jobs.py`, `tests/test_ai_jobs.py`, `tests/test_chatgpt_recommendations.py`; extend `services/ai_routes.py`, `services/ai_provider.py`; add neutral metadata-resolution seams in the current owner only if required.

**Interfaces:** `AIJobStore.create(feature, selection, request, request_key)`, `snapshot(id,page,page_size,cursor)`, `cancel(id,revision)`, `continue_job(id,revision,request_key)`; result items and state defined above.

- [ ] Fail configurable saved counts of 15/75/1000, explicit-request override without Settings mutation, requested 120-result, duplicate/remake, post-validation top-up, no-padding, follow-up reference, exact large-target parsing/persistence, budget pause/continue, request-key conflict and interrupted-restart cases. Do not contact a model just to test numeric boundaries.
- [ ] Implement lazy SQLite state and finite concurrent batch workers. Verify accepted result identities and query constraints rather than raw model count.
- [ ] Test job provider/model pinning, sign-out stop, another account not inheriting conversation context, and no automatic replay.
- [ ] Run `python -m unittest tests.test_ai_jobs tests.test_chatgpt_recommendations tests.test_ollama_recommend -q`.

### Task 6 — Add company queries and complete combined-filter retrieval

**Files:** Extend `services/advanced_search.py`, `services/tmdb_advanced_search.py`; create `services/ai_catalog.py`, `tests/test_ai_catalog.py`, `tests/test_company_discovery.py`; extend `tests/test_advanced_search_model.py`.

**Interfaces:** `resolve_company` and `collect` above. Controlled query values identify type/ID/display name/country; result-set handles are domain-aware and immutable for a reviewed revision.

- [ ] Fail studio namesakes, company absent from first search page, explicit company union/intersection/exclusion, actor+year+owned, director-role filtering, sorting across pages, and missing runtime/ownership cases.
- [ ] Extend the existing query compiler and traverse its plans; do not change the old Ollama interpretation or repair its results incidentally.
- [ ] Test zero-result versus unavailable integration, failed required page, provider limit, partial-set mutation rejection, and P3 long-film inclusion.
- [ ] Run `python -m unittest tests.test_ai_catalog tests.test_company_discovery tests.test_advanced_search_model -q` plus existing advanced library/Discover tests.

### Task 7 — Add GPT AI Control using shared planning and domain tools

**Files:** Create `services/chatgpt_tools.py`, `services/chatgpt_agent.py`, `tests/test_chatgpt_tools.py`, `tests/test_chatgpt_control.py`; extend `services/ai_control.py` with the neutral resolved-plan seam, `services/ai_routes.py`, and `app.py` dependency composition.

**Interfaces:** `available`, `call`, and `prepare_resolved` above. Agent turns consume pinned selection, session context, schemas and validated tool results. Only user confirmation can call mutation execution.

- [ ] Fail studio-list, multi-step list/download, typed-domain confusion, untrusted provider text, stale scope/selection, unsupported quality, and uncertain-write retry cases.
- [ ] Implement read/prepare registry entries in the capability table and route review-UI-only operations through `open_review` without execution. Validate that every advertised callable entry has an actual handler and exact schema.
- [ ] Share existing Movie plan/selection/receipt owners; use TV/IPTV domain previews for their actions. Verify actual backend membership and saved outcomes, including failure/partial receipts.
- [ ] Run `python -m unittest tests.test_chatgpt_tools tests.test_chatgpt_control tests.test_ai_control_service tests.test_ai_control_api -q`. Preservation fixtures must still pass.

### Task 8 — Wire Movie Smart Match for both metadata databases

**Files:** Modify provider composition in `app.py::_process_smart_match_batch`, Smart Match start/readiness and coordinator binding; modify `services/smart_match.py` only for additive pinned context if needed; create `tests/test_chatgpt_smart_match.py`; extend existing Smart Match service/API tests.

**Interfaces:** Extend `SmartMatchCoordinator.start(paths, provider, method, background=True, *, ai_selection=None)` and `app.py::_process_smart_match_batch(paths, provider, method, *, ai_selection=None)`. A GPT start persists safe `ai_selection` context; `run_batch` forwards it as a keyword only when present. Missing context retains the original three-argument callbacks and means the legacy Ollama/classic path, including older saved jobs. Existing movie identity result is `{matches,errors}`; GPT normalized title/year/aliases pass `parse_ai_match_response` and the same downstream search/ranking owner. Frozen `_smart_match_ai_batch` remains the Ollama implementation. Provider is the metadata database in these existing signatures; `ai_selection.provider` is the separate inference-provider choice.

- [ ] Fail tests for GPT with no Ollama URL/model, TMDB versus Plex database selection, 8-item IDs with partial repair, unknown/duplicate/missing IDs, fabricated titles, changed files, and account/provider changes during a job.
- [ ] Wire GPT at the existing batch boundary and persist safe provider/model/skill provenance. Preserve deterministic/classic fallback policy and label it accurately.
- [ ] Verify proposal-only inference cannot apply metadata or rename; exact selected proposals and file checks govern apply.
- [ ] Run `python -m unittest tests.test_chatgpt_smart_match tests.test_smart_match_service tests.test_smart_match_api tests.test_smart_match_ui -q`.

### Task 9 — Wire both IPTV AI responsibilities and preserve automatic work

**Files:** Modify `services/iptv_provider_manager.py`, `services/iptv_movie_service.py`, `services/iptv_routes.py`; add neutral validator access without changing old classifier behavior; create `tests/test_chatgpt_iptv.py`; extend existing IPTV enrichment/gate/UI tests.

**Interfaces:** Add optional `ai_provider_service=None` to `IPTVMovieService.__init__` and the provider manager's composition, retaining the existing `ollama_runner` default/test injection. Extend `_proposal_for_source(source_key_value, client, *, method="tmdb", ai_selection=None)` to accept one pinned GPT selection. GPT requests use the new asynchronous AI-job routes and checkpoint the selected source keys/completed proposal references; the legacy synchronous Ollama route remains unchanged. Add `classification_ai_preview(payload, *, ai_selection)` to produce the existing classification-preview envelope through a shared category-decision mapping, rather than invoke the old catalogue-wide persistence method. Read all selected keys in bounded store queries, not the first-5000-row lookup in the current manual preview. Legacy `classify_catalog(use_ollama=True)` remains an explicit Ollama service API; it is not silently repurposed. GPT classification outputs the same normalized domain decision with truthful GPT provenance; GPT candidate ranking feeds the existing threshold/lock/apply checks. A paused/incomplete GPT job cannot mark its provider proposal set ready for apply.

- [ ] Fail tests for disabled Ollama but ready GPT, missing IPTV TMDB, absent title consent, wrong provider/generation, out-of-set candidate IDs, low deterministic scores, mixed/uncertain classification, and manual locks.
- [ ] Add explicit GPT classification-preview dispatch and GPT matching dispatch. Preserve manual/deterministic classification and background `classify_catalog_batch`; no normal sync/enrichment begins model calls.
- [ ] Verify F4 bounded 25-title evidence and selections beyond row 5000, F5 at most eight candidate summaries, no credential/stream/path leakage, no cross-provider data, no auto-apply, pinned settings, cancellation, pause/continue without duplicate proposals, and failure reporting.
- [ ] Run `python -m unittest tests.test_chatgpt_iptv tests.test_iptv_movie_enrichment tests.test_iptv_movie_gates_0_5 -q`.

### Task 10 — Integrate desktop Settings, provider status, and all entry points

Verification refinement November 2: the first isolated compiled bundle passed the six initial scenarios plus separately selected native Movie Smart Match/TV card scenarios. A discovered ordered IPTV preparation gap required an explicit next-step progress/review UI, and a browser `ERR_NO_BUFFER_SPACE` read failure exposed the missing explicit Settings reload control. These new source changes require one further bounded isolated compilation and final desktop run; all earlier repeat checks reused the original compiled bytes. Production `dist` remains excluded. No additional model inference is authorized by these offline checks.

Final verification refinement November 2: a subsequent affected-scenario rerun reproduced immediate Cancel failing with `stale_job_revision` because live progress advanced between GET and POST. Cancellation now identifies the current run number atomically in the existing store, preserving strict action confirmation and rejecting a Cancel from before a later explicit Continue. The new store regression failed before the fix and passes after it. This UI correction required a third isolated compilation (3.12 seconds). Its full 12 desktop scenarios passed in 1.3 minutes. No production bundle was rebuilt.

Ordered IPTV review: a matching preparation that depends on a not-yet-confirmed classification is a deferred action. Confirming classification does not run matching. The user explicitly chooses **Prepare next step**, which starts a fresh saved F5 run (same pinned account/model, its own 24-call budget) on the earlier confirmed subset. Polling/refresh is read-only; **Load prepared review** explicitly replaces the deferred review after completion. A separate Apply commits proposals. Continue/Cancel use the shared job owner, and cancelling the action/control request cancels its unfinished child preparation. No automatic inference or write occurs after a receipt or page reload.

**Files:** Create `src/api/ai.js`, `src/context/AIProviderContext.jsx`, `src/components/AIProviderStatus.jsx`, `src/components/AIJobProgress.jsx`; modify `src/App.jsx`, `src/features/settings/SettingsWorkspace.jsx`, `src/features/discover/DiscoverWorkspace.jsx`, `src/features/ai-control/AIControlWorkspace.jsx`, `src/features/cleanup/CleanupWorkspace.jsx`, `src/components/SmartMatchPanel.jsx`, `src/features/iptv/IPTVWorkspace.jsx`, `src/features/help/HelpWorkspace.jsx`, and `src/api/iptv.js` where required by the new explicit action.

**Interfaces:** One redacted config generation/readiness context; generic progress/result paging; existing domain cards/review components. The original Ollama card, exact-model helper and API actions retain their behavior.

- [ ] Add failing desktop/API-consumer checks for all five routes with missing Ollama, save/reload/switch, sign-in states, consent gates, stale jobs and error preservation.
- [ ] Implement only the desktop changes specified above; keep existing layouts and Back/Forward/context ownership.
- [ ] Assert the compiled rendered count/selection, persisted list membership, provider/model label, missing-integration state, usage error, cancellation and sign-out behavior. Verify loaded resources and HTTP payloads actually use the selected provider.
- [ ] Run focused UI/unit checks, build once to the isolated output, then `-AIProviderOffline` Playwright at both desktop viewports. Do not test mobile or rebuild production `dist`.

### Task 11 — Whole-feature qualification and plan comparison

**Files:** Create `tests/test_ai_feature_matrix.py`; complete `tests/e2e/ai-provider.spec.js` and `tests/e2e/chatgpt-control.spec.js`; update the GPT resource catalogue/help and documentation to the implemented callable/review-only statuses.

- [ ] Require one passing end-to-end fixture row per F1–F5 for both selected providers, including dependencies and errors. Legacy Ollama payload/prompt fingerprints and golden outcomes must match.
- [ ] Exercise the complete action result, not just interpretation: returned IDs/cards, full rendered/scrollable counts, selections, persisted list contents, review tokens, receipts, domain isolation and no duplicated writes.
- [ ] Run relevant existing broader suites under the finite budgets below. Record pre-existing failures separately; do not weaken them or call focused results a green full suite.
- [ ] Compare every approved contract and proposal against source and rendered behavior; stop on any mismatch. No existing AI consumer may be deferred behind a successful movie-picker demo.

### Task 12 — Whole-feature account qualification and separately authorized live activation

- [ ] Require the recorded successful **Task 0** user-driven OAuth/account/model gate; it must already have happened before general feature development. Complete one synthetic qualification request for each of F1–F5. The budget is **six real inference calls total across the project**: Task 0's one connection request plus these five feature requests, including any repairs/retries. Do not spend another six here or repeat login proof for appearance's sake. Use synthetic evidence and temporary catalogues only; no real media, production catalogue mutation, download submission or IPTV credentials in model context. Exact evidence permissions must already have been decided before the affected feature is implemented.
- [ ] If access/required tool format is unsupported, stop with request IDs and the exact limitation; retain working Ollama and request a design decision. Do not switch to private endpoints/API billing.
- [ ] After explicit activation approval, back up only the affected configuration/new stores, verify process/data/served-bundle ownership, build through the authorized CP launch owner, and verify every selected-provider surface. Running `run.bat`, changing live provider/config, account login, restart, and live data actions are separate named actions.
- [ ] Report source changes, isolated passes/failures/skips, actual account verification and live activation separately. Do not commit/push/package/tag/release without explicit authorization.

## Acceptance matrix

| Scenario and starting state | Action | Exact expected result | Surface/owner | Automated check or observed evidence |
| --- | --- | --- | --- | --- |
| Old install; no new config, GPT files or account. | Browse/use Ollama. | Same prompts, payloads, limits, settings/results; no OpenAI calls or new GPT store. | All legacy owners. | Preservation fixtures and filesystem/network spy. |
| GPT ready; Ollama URL/model absent and IPTV Ollama disabled. | Use F1–F5. | Every feature reaches its GPT skill; only its actual domain dependencies/consent can block. | Feature registry and all entries. | `test_ai_feature_matrix` plus desktop network assertions. |
| Separate GPT accounts with same email. | Switch/reauthorize/sign out. | Client IDs/tokens/context never mixed; correct account selected; other account preserved. | Auth/credentials. | Signed token fixtures and profile-state assertions. |
| Concurrent expiry/refresh. | Two operations request a token. | One serialized refresh; newest rotating token persists; no lost replacement. | Credential owner. | Cross-process lock/race test. |
| Wrong state/nonce/signature/audience or missing plan scope. | Complete callback. | Rejected or signed-in/no-plan state; no inference; active profile unchanged. | Auth. | Negative token/callback fixtures. |
| Stream starts then usage/error/incomplete event occurs. | Read response. | Failure/partial shown, never success or mutation; quota message/Manage usage preserved. | Transport/UI. | Fragmented SSE fixtures and compiled UI. |
| GPT model/account/provider changes during an operation. | Continue current batch then start another. | Existing pinned identity retained; next operation uses new choice; sign-out stops old-account calls. | Selection/jobs/domain jobs. | Concurrency and desktop switch tests. |
| User requests 120 valid films. | Ask AI. | 120 accepted unique eligible IDs when fixtures supply enough; >50 reachable; top-up and global count correct. | Curator/jobs/cards. | Backend set assertion plus rendered page traversal. |
| GPT Settings count is 75 or 1000; prompt omits a count. | Ask AI. | Exact saved default becomes the job target; 15 is not forced; no 50-result validation ceiling. | Settings/config/curator. | Config/API roundtrip and job-target assertions. |
| Saved GPT default is 75; prompt requests 1000. | Ask AI, then pause/Continue. | Target remains 1000 across all batches/continuations; saved default remains 75; final completion or shortfall is honest. | Session/jobs/Settings. | Offline batch fixtures, persisted target and rendered progress. |
| Very large valid decimal target such as `9007199254740993`. | Validate/store request without fetching movies. | Target is retained exactly without JavaScript rounding, hidden count clamp or a giant one-shot output attempt. Invalid zero/fraction/boolean inputs are rejected. | UI/API/job numeric boundary. | Pure numeric/serialization fixtures; zero inference calls. |
| Only 11 valid recommendations exist. | Request 20. | 11 verified results and honest shortfall, no duplicate/padding or relaxed criteria. | Curator. | Candidate rejection/exhaustion test. |
| User says "more like the third, less violent." | Follow up. | Actual third result used; constraints preserved; previous IDs excluded; context loss prompts clarification. | Session/curator. | Session and rendered follow-up tests. |
| Ghibli factual set spans five fixture pages. | Create all-feature-films list. | All scoped eligible IDs retrieved; long films retained, unknown runtime unresolved; exact review before persistence. | Company queries/control/curation. | Query request assertions, set equality, saved membership. |
| Ambiguous Disney/duplicate company names or target absent from page 1. | Request a list. | Appropriate candidate resolution/clarification; no first-result or substring group shortcut. | Company resolver. | Multi-page/company-country fixture. |
| Actor/director + date + ownership + sorting. | Search/create list. | Every condition applied after filmography resolution; acting-only credits do not satisfy director. | Shared search/AI catalogue. | Adverse combined-constraint fixtures. |
| Required page fails or provider page ceiling is reached. | Request all. | Coverage partial; exact counts/reason; no "all" mutation plan until explicit revised scope. | Catalogue/jobs/control. | Partial traversal and UI state tests. |
| User customizes cross-page selection. | Confirm. | Same requested action on exactly selected stored IDs; unknown/empty/stale keys rejected. | Shared plan/domain executor. | Service/API and card selection tests. |
| Write times out after persistence. | Repeat same request key. | Inspect/return existing receipt; no duplicate list/download/deletion. | Job/action/domain owner. | Fault injection around persisted result. |
| Movie Smart Match includes eight IDs; GPT omits/duplicates one. | Match by AI under TMDB and Plex. | Targeted one repair; correct context→ID mapping; residual uncertainty/classic fallback labelled; no auto-apply. | F3 and match review. | Parser/API/UI evidence and proposal IDs. |
| Movie match contains Arabic/accented basenames. | Match and review. | Unicode survives; only consented hints sent; arbitrary paths absent; selection/apply still guarded. | F3/context redaction. | UTF-8 transport fixture and exact payload inspection. |
| IPTV manual lock/non-Film item/out-of-set or score<78 candidate. | GPT matching. | Existing deterministic rejection/lock survives; no identity invented/applied. | F5. | Provider-scoped proposal/apply fixture. |
| Mixed IPTV sample or GPT title exception not in input. | GPT classification preview. | Unknown exception rejected; mixed/uncertain remains review; no manual lock overwritten. | F4. | Shape validator plus evidence-membership test. |
| Normal IPTV sync/enrichment/manual Classify. | Run existing workflow. | Same deterministic path and worker behavior; zero unsolicited GPT calls. | IPTV workers/manual preview. | Model call-count zero, existing regression suites. |
| Missing Movie/TV/IPTV integration. | Request related operation. | Clear integration_missing/disabled state, never no-matches/not-owned or another domain's credentials. | Tools/domain owner. | Failure and cross-domain tests. |
| Unowned movie watched / unsupported 4K direct policy. | Prepare action. | Existing ownership restriction/quality limits enforced; no silent 1080p or watched write. | Curation/acquisition. | Backend result and receipt assertions. |
| TV missing-episode task and IPTV list with similar IDs. | Prepare/confirm. | Correct typed owners, episode/proposal gates, provider-local list; no Movie-ID coercion. | TV/IPTV tools/reviews. | Domain isolation and task/list persistence. |
| Prompt injection in filename/plot/provider text. | Retrieve/use evidence. | Data treated as evidence; no tool privilege, action, secret request or confirmation escalation. | Agent/tools. | Adversarial tool trace and zero mutation assertion. |
| Delete plan targets changed/out-of-root/active file. | Confirm. | Rejected by existing owner; no replacement target chosen. | Mutation/selection owner. | Safe temp fixtures, no production paths. |
| User asks for unsupported player control/admin operation. | GPT responds. | Honest unavailability or existing review/settings navigation; zero arbitrary execution. | Tool catalogue/frontend. | Callable-handler consistency and side-effect spies. |
| Repeated navigation, Back/Forward, reload, empty/error/long results. | Use desktop UI. | Existing geometry/state preserved; no duplicate request or stale result overwrites; counts are observed. | Compiled React UI. | 1600×1000 and 1280×800 Playwright. |
| Restart while GPT work awaits confirmation. | Reopen session. | Interrupted work visible; no automatic mutation/replay; stale plans refreshed before confirmation. | Jobs/domain plans. | Restart fixture and receipt replay test. |

## Verification and rollout

### Gates and resource budgets

1. **Planning gate (this deliverable):** Verify plan structure, source references and scope coverage only. No app tests or runtime changes.
2. **Initial implementation baseline:** Record the November 2 implementation handoff and approved P2/P5 scope, current checkout/dirty baseline and protected fingerprints before Task 0 edits. P1/P3/P4 decisions are needed before their dependent behavior, not as a reason to avoid independent login-foundation work. Resolve any contract-change notice before its affected work. Tests use OS-temp isolation with external effects mocked.
3. **Early real-login gate (Task 0):** Before broad feature development, obtain user-driven consent in the isolated registration and verify one minimal synthetic response. No existing account-token reuse, paid API fallback, library/IPTV data or live CP/config changes. Failure blocks dependent feature work. Count the call inside the six-call total.
4. **Focused tests:** One worker, maximum five minutes per task group. Stop on budget exhaustion or an isolation failure; report the failed/incomplete gate rather than repeatedly rerunning.
5. **Broader regression:** One Python worker and one Node test process, serially, maximum 15 minutes per language group. Do not run stress tests, disk benchmarks, hardware polling or scans of real libraries. Existing large fixture suites that exceed the budget require a reviewed narrower partition, not an unbounded retry.
6. **Compiled desktop:** One isolated build and at most ten minutes of focused provider/control desktop tests per viewport. Rerun only failures or behavior affected by a subsequent fix. No production `dist` writes.
7. **Whole-feature account qualification (Task 12):** Synthetic OS-temp evidence, the remaining five calls for F1–F5 within the total six-call budget; no paid API fallback, real downloads, production lists, library scans or apply actions. This is not where first login is attempted.
8. **Live activation gate:** Separate approval naming the restart/build/config/account actions. Verify process, data/config, served index/bundle and visible feature behavior. Until then report source-only/isolated.

### Future verification commands

Run from the approved implementation checkout. First create a unique test root and set isolation before importing CP:

```powershell
$aiTestRoot = Join-Path ([IO.Path]::GetTempPath()) ('cp-chatgpt-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $aiTestRoot | Out-Null
$env:CP_TEST_MODE = '1'
$env:CP_TEST_ROOT = $aiTestRoot
$env:CP_TEST_DIST_DIR = Join-Path $aiTestRoot 'dist'
```

Task commands use `\.venv\Scripts\python.exe` (written as `python` above for brevity). All new integration tests install the offline dependency guards before any route can start a manager or contact a network. Do not treat `CP_TEST_QBT_MODE` alone as isolation.

Focused final groups:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ai_provider_preservation tests.test_ai_provider tests.test_ai_routes tests.test_chatgpt_credentials tests.test_chatgpt_auth tests.test_chatgpt_transport tests.test_chatgpt_skills tests.test_ai_jobs -q
.\.venv\Scripts\python.exe -m unittest tests.test_chatgpt_recommendations tests.test_ai_catalog tests.test_company_discovery tests.test_chatgpt_tools tests.test_chatgpt_control tests.test_chatgpt_smart_match tests.test_chatgpt_iptv tests.test_ai_feature_matrix -q
.\.venv\Scripts\python.exe -m unittest tests.test_ollama_recommend tests.test_ai_control_service tests.test_ai_control_api tests.test_smart_match_service tests.test_smart_match_api tests.test_iptv_movie_enrichment tests.test_iptv_movie_gates_0_5 tests.test_advanced_search_model -q
```

Then run the relevant existing catalogue/advanced-search, curation/list/selection, source/acquisition, TV, player and UI regressions selected by the final touched-owner map. Before claiming a complete Python suite, run discovery under the approved budget and report every skip/failure, or explicitly label it incomplete. Never substitute a selected group for full-suite evidence.

For Node, enumerate and run every existing `.test.mjs`, rather than rely on the single package script:

```powershell
$aiNodeTests = @(rg --files tests -g '*.test.mjs')
node --test @aiNodeTests
```

After Task 1 implements/validates the offline mode, the following wrapper performs the single build with `npm.cmd run build -- --outDir <its verified temporary dist>` before starting its isolated server. Do not perform another standalone production or test build first:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/run_playwright_e2e.ps1 -AIProviderOffline tests/e2e/ai-provider.spec.js tests/e2e/chatgpt-control.spec.js --workers=1
```

Do not use that new switch before it exists and its network/process containment test passes. Use a free isolated port; refuse a port conflict and do not kill its owner. Preserve failure artifacts under the verified temporary root; no recursive deletion outside an explicitly verified test root. Clear/restore test environment values after the approved verification session.

### Final evidence and rollback report

Record approved scope/choices, protected Ollama comparison, changed files/owners, F1–F5 coverage, executed test commands/counts/skips/failures and budget usage, compiled UI result, account admission result, and whether anything is live. Compare returned IDs, rendered counts, saved membership, confirmations, and receipts to the approved contracts. State unresolved differences plainly even if tests pass.

For activation, preserve config/new-store backups and the previous served bundle through CP's existing recovery procedure. On a material mismatch stop new GPT work, preserve job receipts, and use the approved rollback; do not change catalogues, discard Ollama settings, silently replay actions, or delete evidence. No commit, push, tag, release or private package is implied.

## Review focus

- Same-email accounts, rotating refresh tokens and sign-out during a job must not mix credentials or context: Tasks 3/5, account-race tests.
- A movie list that combines person/company/date/ownership must retain every condition through retrieval and persistence: Tasks 6/7, combined-filter and saved-set assertions.
- Model output after a partial stream, stale confirmation or unknown write result must never become a second action: Tasks 4/5/7, terminal-event and receipt tests.
- IPTV's independent Ollama switches, manual locks and provider IDs must not leave GPT disabled or weaken candidate validation: Task 9, both independent AI paths and zero-background-call tests.
- Existing Ollama wire prompts/results and desktop behavior must remain unchanged despite shared composition edits: Tasks 1/2/8/10/11, exact preservation fixtures and side-by-side compiled UI.

## Source references checked for this plan

- CP: `AGENTS.md`; `docs/plans/_template.md`; `docs/plans/ai-control-card-first-complete-actions-zero-regression-plan.md`; `docs/plans/tv-user-action-corrections-implementation-plan.md`; `docs/tv-contracts.md`; the owners and draft package linked above.
- [OpenAI registration/sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in), [accounts/sessions](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions), [models/inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference), [preview restrictions](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations), [error recovery](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery), [UI/UX](https://developers.openai.com/siwc/ui-ux-guidelines), and [local-project cookbook](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt). Recheck the request/schema contract before implementation/account preflight; account access is not established by documentation.
- [TMDB company search](https://developer.themoviedb.org/reference/search-company), [movie discovery](https://developer.themoviedb.org/reference/discover-movie), [errors/page limits](https://developer.themoviedb.org/docs/errors), and [rate limits](https://developer.themoviedb.org/docs/rate-limiting).
- [PyJWT crypto installation](https://pyjwt.readthedocs.io/en/latest/installation.html) and [verified decode API](https://pyjwt.readthedocs.io/en/latest/api.html). No dependency is installed as part of planning.

## Approval and completion record

- **Planning authorization:** Dante asked for the full implementation plan and explicitly required unchanged Ollama/skills and ChatGPT coverage for all CP AI features.
- **Implementation handoff, 2026-11-02:** Dante: "ok lam3y update the plan with this and move the login check to the beginning , keep ollama untouched, after plan updates open new task and hand over the plan for implementation". This authorizes the new local implementation task, the P2 configurable/unrestricted positive-count requirement, and the early login-first sequence. Start Task 0 and independent foundation work without asking again for that same authorization.
- **Product choices settled in implementation chat, 2026-11-02:** P1 manual provider switching on failure; P3 released ≥60-minute studio default with explicit scope options; P4 separate evidence opt-ins initially off. Dante explicitly selected each recommended option.
- **Contract-change decisions:** None granted through this draft. Preserve current contracts; use the required prominent notice if a change becomes necessary.
- **Account interaction:** The early gate is part of the requested sequence, but Dante must explicitly complete OpenAI sign-in/consent for the isolated registration. This is not authority to extract existing credentials or autonomously consent. The one minimal connection response follows that explicit connection; full F1–F5 qualification retains the declared synthetic-data and six-call budget.
- **Production/live/commit/publication authorization:** Pending and separate; no production restart/build/config/data change, commit, push, package, tag or release is included.
- **Original planning-chat outcome:** Plan/skill authoring and handoff. The completion record below supersedes the original planning-only status for the implementation continuation.
- **Implementation continuation complete, November 2:** Tasks 0–11 source implementation and isolated verification are complete, with exact scope, owner map, passing checks and remaining broad-suite failures recorded in `docs/verification/chatgpt/implementation-2026-11-02.md`. Historical task checklists above are the original execution instructions; this record and its evidence are the current status. No assertion of a green whole Python suite is made.
- **Task 12 bounded account result:** User-driven OAuth/model/connection passed before general development. Six of six real calls used: connection plus one per F1–F5. F2–F5 single-response synthetic protocol checks passed. F1 produced a valid scope, then the qualification-only one-call guard blocked its normal next request; original failed record preserved, no real recommendations or retained response ID claimed. No additional request was sent. Full F1 product behavior passed offline; real multi-step quality qualification remains outside the exhausted budget. Details: `docs/verification/chatgpt/account-qualification-2026-11-02.json`.
- **Live activation remains unperformed:** Production configuration and served dist hashes match the baseline. Credentials remain in the isolated diagnostic root. No live restart/build/provider change, commit, push, package, tag or release.
- **Shutdown instruction:** Dante explicitly requested continued work followed by PC shutdown. After final evidence is saved, request orderly Windows shutdown without forcing unsaved applications closed. This is separate from CP activation.
