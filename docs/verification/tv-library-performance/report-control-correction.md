# Control-height mismatch resolved; later alignment gate stopped

2026-10-23, Africa/Cairo. **The 40px versus 36px mismatch is resolved without changing the UI.** Implementation remains incomplete because the resumed desktop run reached a different assertion failure in the same test. The application candidate is preserved and rolled back; the corrected test remains.

## Confirmed root cause and correction

Dante approved investigating/resolving the height mismatch and continuing the revised plan within the remaining 304.85 seconds, preserving behavior and prohibiting live restart/production data changes.

The approved, implemented [combined Library header plan](../../plans/2026-10-14-library-combined-header.md) explicitly specifies **36px embedded controls, 280px view-group width and 8px action gaps**. Its approval records Dante's “ok go” on October 14. The old TV parity test was last committed October 7 and still asserted 40px. Current `WorkspaceControls`/`WorkspaceViewActions` and `.workspace-controls-actions .library-view-switch` / `.library-rescan-button` CSS implement the later 36px contract.

Only the stale expected height in `tests/e2e/tv-parity.spec.js` changed, from 40 to 36, with a comment identifying the approved refinement. Movie/TV width/height equality, scan alignment, File View and all other assertions remain. No frontend production source/CSS or product contract changed. The original saved 40px failure supplies the RED evidence.

## Resumed verification and next failure

The exact saved compact repository/read-model/search candidate was reapplied after checking all three baseline and candidate SHA256 identities. Probe SHA256 remained `ff3df276d2bbb3fe43a2ad5b40e47f0f123f66c4335a3bd85d38bcbf795364cc`. Prior matching full-output, structural, focused/broader/Node and eight-observation memory evidence remains applicable to this identical candidate; those phases were not repeated.

Ran one full `compiled_desktop.ps1` phase through the cumulative runner, label `compiled-desktop-control-corrected`. The temporary build passed. The five named desktop spec files ran against a new synthetic fixture server on port 5127 with one worker, zero retries and fail-fast after one failure.

**Result: 21 passed, one failed, 22 did not run (35.7 seconds).** The runner also reports one non-test error with its early-stop message, as in the previous attempt. The real-backend card/nondefault Versions/saved-key/ordinary Play test passed again.

The corrected 36px height, Movie scan alignment and Movie/TV width/height parity assertions all passed. A later assertion failed:

```text
expect(tvSwitch.y).toBe(tvRescan.y)
Expected: 79
Received: 91
```

The test reads two bounding boxes in separate browser round trips immediately after switching/expanding TV controls. Saved trace API times: TV group read 35711.726–35718.501 ms; Refresh read 35719.284–35729.504 ms. The failure screenshot subsequently shows both controls aligned at the same top edge. This supports a hypothesis that layout moved between samples; it does not prove the exact cause or exclude an earlier transient misalignment. No application geometry change or relaxed alignment assertion was made. A suitable next investigation is a single browser evaluation that reads both rectangles together after loaded-state readiness, retaining exact 36px and alignment expectations. That correction/reverification has not run.

The new failed gate stopped verification. No retry, additional endpoint request, latency measurement or other test followed. Trace/screenshot inspection was offline only.

## Evidence, rollback and remaining budget

Evidence run remains `930057e1-4f6e-4758-82bc-3c28a263aaeb`; full phase log is `compiled-desktop-control-corrected.log` beneath its directory. Task root is recorded in `task-root.txt`.

New compiled root: `C:\Users\dante\AppData\Local\Temp\cp-tv-library-6c63f44b-c527-4646-8563-835031b1d28c\35749e7e-53ce-471e-96c2-3953f19d4e7c`. Failure artifacts are under `playwright-results\tv-parity-Discover-and-Lib-08ef6--View-shows-native-TV-files`: `test-failed-1.png`, `error-context.md`, `trace.zip`. Prior evidence/report remains unchanged: [previous complete gate report](report-desktop-stop.md).

After checking for concurrent source changes, restored the three application owners byte-for-byte to the saved pre-edit dirty baseline; all hashes verified. Candidate copies/hashes remain preserved under the existing run. Test/probe/harness/docs work remains. Prospective compact-context tests require the saved candidate and will not pass against restored application source; there is no green-current-checkout claim.

The temporary server's owned process tree was stopped; port 5127 is no longer listening. Live port 5000 remains PID 5264. No live request/restart, production data/configuration/dist change, native player launch, hardware test, commit or publication occurred.

This phase consumed **43.438 active seconds**. Original cumulative ledger: **338.5889602 / 600 consumed; 261.4110398 seconds remain**. Retained temp footprint: **247226151 bytes**, below 1 GiB. Optional latency remains unrun and separately requires express approval under the plan; no speedup claim is made. Further verification must address the new alignment gate and retain this same cumulative balance.
