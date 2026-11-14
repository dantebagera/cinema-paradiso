# Advanced IPTV bulk prompt — 2026-11-06

Implemented in source and verified offline. Not live activated.

## Change

`services/chatgpt_skills.py` now supplies the exact advanced instructions Dante approved after the 100-title comparison. There is one authoritative bulk prompt. Output schema, batch size, model selection, verifier, retries, manual locks and application code are unchanged.

Prompt SHA-256: `a281c1445f51ccbeed985352df62fc8d7a080f3a75523942a0bc6a1185abaee4`.

Protocol SHA-256: `435ea3756a5d453cd5c3e3041385a856c194b5e732b867fc62f6a7f0f3c7c6ef`.

## Verification

- 19 baseline tests passed before edits.
- Three new tests first failed against the original prompt; subsequent focused run passed all 22 tests.
- All 138 core ChatGPT/job tests passed using Python's normal unittest entry point; see `core-tests.log`.
- All 19 IPTV bulk tests passed, including the 40,000-proposal and 25,001-source cases; see `bulk-tests.log`.
- The original combined 157-test invocation had one credential-test failure caused by launching multiprocessing from stdin. That failed run is preserved in `initial-broader-tests.log`. The complete core group was rerun, not merely the one failing test. The initial combined run is not a green full suite.
- The bulk request test captures the real transport payload. It verifies the approved prompt, that an already-resolved source skips GPT, that uncertain GPT output remains review, and that the scan does not apply proposals under the currently unchanged application code.
- A separate regression proves a paused job pinned to the old bulk protocol cannot issue a new request or lose its existing results on resume.
- Independent scoped review found no blocking issue. No live GPT requests were made during implementation; the exact prompt already has real-provider timing evidence.

## Timing evidence

The prior standalone 100-title experiment averaged 72.0875 seconds / 7,075 tokens for the old prompt and 73.13 seconds / 7,418 tokens for the approved advanced prompt, across two requests each. See `100-title-timing-summary.json` and `100-title-timing-result.txt`.

These measure GPT requests only, not full CP matching. They are not guarantees for future requests or match quality.

## Activation and remaining work

No restart, compiled frontend replacement, live matching, catalogue write, commit, push or release was performed. The running backend must reload before using the new prompt. Egysat was untouched.

Existing strict title/year verification can still reject correct GPT interpretations. This change does not implement the earlier decisions about improved independent verification, automatic recovery, or automatic application. Those decisions remain pending work, not reversed requirements.

Completed Lionz results remain available. An unfinished job explicitly pinned to the previous protocol will be rejected by the existing version guard after activation and requires a new job; no such unfinished F5 job was found at baseline.
