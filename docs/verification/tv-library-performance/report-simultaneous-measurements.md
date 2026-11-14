# Simultaneous alignment checks passed; isolated artwork fixture blocked completion

2026-10-23, Africa/Cairo. **Alignment test timing is fixed without changing the UI.** The full control/File View test now passes. The continued desktop run stopped later at a poster-loading assertion, so implementation remains incomplete and the application candidate has again been preserved and rolled back.

## Approved change and actual verification

Dante explicitly approved simultaneous measurements and continuation within the remaining 261.41 seconds, preserving existing behavior with no live restart or production data changes.

Added test-only `measureLibraryActions(page, label)`: one synchronous locator evaluation reads the shared header's view group and refresh sibling using `getBoundingClientRect()`. Missing refresh control fails explicitly. Movie and TV are each measured as one pair; exact 36px height, same width/height across media and exact alignment expectations remain unchanged. No sleeps, tolerance increase, assertion deletion, application CSS or product behavior change.

Reapplied only the identical saved compact repository/read-model/search candidate after baseline/candidate SHA256 guards. The prior valid exact-output, structural and eight-observation memory evidence applies to this identical application/probe. No repeated observations or timing claim were added.

Ran cumulative phase `compiled-desktop-simultaneous` once. Temporary build passed. Five named desktop specs used one worker, zero retries and fail-fast after one failure.

**Desktop: 29 passed, one failed, 14 did not run (1.1 minutes).** The runner also reports one non-test error alongside its early-stop message. The previously failing full case, `Discover and Library use the in-page media rows and TV File View shows native TV files`, passed, including same-evaluation alignment and actual File View interactions. The real-backend Library cards/nondefault version/saved exact key/later Play case also passed again. Discover gutters/year fields at 1366/1920/2048, quick bars/status, Library filters at 1366/2048 and advanced-search explanations passed beyond the previous stopping point.

## Next failed gate: image isolation fixture

`TV desktop parity and uncropped Dark Matter poster at 1920x1080` timed out after 15 seconds at:

```javascript
await expect.poll(() => card.locator('img').first()
  .evaluate(img => img.complete && img.naturalWidth > 0)).toBeTruthy();
```

Saved network evidence shows unsuccessful external requests to:

- `https://image.tmdb.org/t/p/w342/2DPmTlv8F0V1TQBPmlsGOVOhtWk.jpg`
- `https://image.tmdb.org/t/p/w1280/iBc82qaA05ntzSnrVndw8scv4Bn.jpg`

The isolated desktop harness explicitly aborts every non-local HTTP(S) request. This existing fixture still supplies CDN artwork and has no local replacement for that image dependency. The failed image requests and guard explain why this isolated setup cannot satisfy the image-loaded assertion; they do not demonstrate an application image regression. The assertion and external-network restriction were both retained. The next correction should supply deterministic test-only artwork locally (or fulfill those image requests from fixture bytes), preserving the natural-width and uncropped-poster geometry checks without real CDN access. No such correction or rerun has occurred.

After this failed gate, no further test, endpoint request or latency measurement ran. Only saved logs/network trace were read. While the desktop phase was still running, an additional prospective catalog assertion was added for a stored-unavailable version whose physical file still exists, through standalone and compact playback adapters. It is **unrun**, not an additional passing test; the previously reported focused count remains 49. This closes a planned coverage gap only after later verification.

## Evidence and rollback

Evidence run: `930057e1-4f6e-4758-82bc-3c28a263aaeb`; log `compiled-desktop-simultaneous.log` in the run directory under the task root from `task-root.txt`.

Compiled root: `C:\Users\dante\AppData\Local\Temp\cp-tv-library-6c63f44b-c527-4646-8563-835031b1d28c\d1adcf22-9a85-4096-a094-ec511cfea5c2`. Failure screenshot, error context and trace are under `playwright-results\tv-parity-TV-desktop-parit-3e3a6--Matter-poster-at-1920x1080`.

After checking for concurrent changes, the three application owners were restored byte-for-byte to their pre-edit dirty baseline and hashes verified. The compact candidate/hashes remain preserved. Simultaneous measurement, corrected 36px expectation, prospective regression tests, probe, isolation harness and docs remain. Compact-context assertions require the preserved candidate; no green-current-checkout claim is made. Existing dirty work and `tv_playback.py` remain untouched by rollback.

The owned temporary server tree was stopped. Port 5127 no longer listens; live port 5000 remains PID 5264. No live app request/restart, production data/config/dist change, real player, hardware test, commit or publication occurred.

This phase: **69.875 active seconds**. Cumulative original ledger: **408.4639602 / 600 consumed; 191.5360398 seconds remain**. Retained temp footprint: **298015750 bytes**, below 1 GiB. Exact response/query/memory results remain in [the earlier gate report](report-desktop-stop.md); all stops are retained separately. Whole-request latency remains unmeasured and no live speedup is claimed. Next execution must explicitly address the stopped artwork fixture gate, retain the original budget and verify the added stored-unavailable assertion before claiming it passes.
