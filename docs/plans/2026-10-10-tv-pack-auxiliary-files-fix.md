# TV season-pack auxiliary files: manifest repair

**Status:** Source repair approved by Dante's "so we need to fix" on 2026-10-10. This slice corrects the confirmed bonus-file rejection. Automatic stalled-source replacement remains a separate design: Dante chose zero-data automatic replacement and partial-download review; the complete timing/recovery design is not implemented by this repair. Dante separately permits stopping the live download and deleting files if useful; the observed transfer is progressing, so keep it.

## Problem and decision

- **Confirmed problem:** Louie's 13 season-2 episode filenames match its 2010 series identity. A fourteenth video under `Featurettes/`, `Fox Movie Channel Presents World Premiere - Louie Season 2.mkv`, is parsed as a season claim and rejected as another series. CP saves `validation_failed` and stops the torrent before payload downloading. Forcing the torrent bypasses its stop but not the saved CP failure.
- **Live evidence:** Hash `779e6621ec285663a2a577c2e338d857b24f3656`, acquisition `ed97dcd073564197a587348a6b3ce13c`, one intent shared by 13 Follow targets. After Dante's forced start the read-only sample shows 14.7% downloaded, 1.49 GB and seven connected seeds. No automatic source replacement is appropriate for that observation.
- **Desired result:** Clearly marked auxiliary directories below a torrent's package root do not contribute episode identity, coverage or payload selection. Actual episode files retain every identity, coverage, path, hash and quality check. Previously failed acquisitions require the existing explicit Retry; do not automatically revive saved validation failures.
- **Scope:** Shared filename-claim parser, manifest skipped-file output, known auxiliary-source cleanup in the existing verified move owner, and real transfer-validation/import regression tests. No UI, dependencies, profile/trust changes, task migration, automatic replacement, restart or production journal edits. Dante's explicit permission to delete staged files is recorded; this implementation only removes proved job-owned staged auxiliary copies after the selected episodes are safely published.
- **Unknown:** Future seed availability is not established by a current progress sample. The running job remains failed in CP until the corrected source is activated and existing Retry is used.

## Contracts affected and contract-change decision

| Contract/source | Current agreed behavior | Repair | Contract change? | Decision |
| --- | --- | --- | --- | --- |
| TV-BASE-04, docs/tv-contracts.md | Verify actual requested episode files; skip separate unselected files | Skip clearly named auxiliary directories before interpreting their contents as episode claims | No; restores established selection behavior | Source repair approved |
| TV-BASE-05/08 | Verified import and recovery retain ownership, identity and validation; completed staged copies are removed | Only valid selected episode mappings reach import; known auxiliary staging copies use the same checked cleanup; old failed job uses existing explicit Retry | No | Preserve; Dante explicitly permits file deletion when useful |
| TV-CHANGE-05 P1/P2 | One pack intent can cover several targets; source and transfer review differ | Keep the same intent and task associations on retry | No | Preserve |
| Follow stalled transfers | Associated transfers are not replaced automatically | Zero-data replacement, partial review | Separate behavior change | Dante chose this direction; excluded from this repair |

## Current design and ownership

| Responsibility | Owner/callers | Preserve | Obsolete branch |
| --- | --- | --- | --- |
| Episode claims and ignored auxiliary content | services/tv_filename_parser.py; TV acquisition, ingestion | Existing basename behavior and episode/daily/absolute parsing; ingestion passes basenames | Basename-only auxiliary recognition misses directory context |
| Manifest identity, coverage, skipped videos | TVAcquisition.validate_manifest | Genuine conflicting episode rejects, combined-file extra allowance, actual coverage | Ignored video omission from `skipped_files` |
| Metadata/file priority/resume | QBittorrentManager._process_pending_magnet_validation | Path/hash validation before domain checks; zero priority for unselected files, then resume | None |
| Failed-job recovery | TVAcquisition.manage('retry') | Explicit retry limits, ownership and blocklist; no new add or lost files | None |
| Verified publication/cleanup | Existing normal TV import owner | Only selected verified videos publish; cleanup after publication | None |
| Owned staging-source deletion | services/verified_import.py, finalize_verified_move | Hash/size/ownership checks, unknown-neighbor protection, per-source crash checkpoints | Reuse the existing cleanup loop for recorded auxiliary sources instead of creating a second deletion path |

Execution reuses attached worktree `C:\Users\dante\.codex\worktrees\tv-follow-season-packs\cinema paradiso` on `codex/tv-follow-season-packs`, based on `be511f98846a67a182e5b371ad087938e9344362`. Both worktree and main checkout contain the previous approved season-pack implementation. Preserve those dirty changes; capture source fingerprints before extending them. Running CP is a separate process (port 5000, observed PID 19084) with schema 4 and the earlier built frontend. No frontend amendment is needed.

## Exact behavior contract

Torrent file paths are relative paths rooted by their package folder. Normalize `/` and `\` when interpreting directory context. Below the first/root directory, exact case-insensitive components `sample`, `samples`, `trailer`, `trailers`, `extra`, `extras`, `featurette`, `featurettes` mark auxiliary content. Do not match substrings such as `Extras Season` or interpret the package root itself as an auxiliary directory: a show/package named `Extras` is valid. Basename-only callers keep their existing rules. Existing episode branches must preserve the directory-derived ignored flag instead of overwriting it.

The existing parser returns `ignored=true`; the manifest owner adds ignored video names to `skipped_files` and continues. Actual manifest mappings and claimed episode coverage exclude those videos. The transfer owner sets their priorities to zero before resuming. An auxiliary-only manifest cannot satisfy requested episodes. Unsafe paths still fail the upstream manifest checks before directory classification can skip anything.

No persisted schema, worker schedule, locks, retry limits or UI controls change. Explicit retry of the already failed job revalidates the current manifest under the same job and intent; it does not create a replacement torrent. Source rollback restores only this repair's files from their recorded fingerprints, preserving the previous approved implementation. No live data rollback or deletion is performed.

**Execution refinement: already-downloaded auxiliary files.** The complete-path test reproduced a second failure when a forced transfer had already written the bonus video: the existing move finalizer treats it as unknown staging material. At verified-import preparation, snapshot only existing ignored-video paths from the validated skipped manifest into `tv_auxiliary_files` (source, size and SHA-256). Reject escaped/symlink sources and changes during hashing. Persist this journal field with the selected video snapshot. The existing finalizer validates each auxiliary source against the skipped manifest, recorded staging root, saved size/hash and other jobs' references before deleting anything. It checks all selected and auxiliary sources and all neighboring files first. After committed publication and torrent removal, the same loop records unlinking/removed checkpoints for both kinds of source. An auxiliary path has no publication target and never becomes a library file. Unknown or shared neighbors, altered files and missing uncheckpointed sources remain review errors. Earlier jobs lacking this field retain conservative behavior. No broad directory deletion is added.

**Review correction: directory aliases.** A Windows junction below staging can resolve into another job's folder while the leaf is not a symbolic link. Preserve the original auxiliary manifest `name` with each snapshot. The shared verified-import owner inspects the lexical save path, all source ancestors and the leaf for symbolic links/reparse points before resolving them. Use that same guard before snapshotting, after hashing, during cleanup preflight and immediately before unlink. Revalidate the recorded save root before cleanup; do not resolve an aliased save root before checking it. Four permanent tests cover auxiliary-directory and save-root junctions present initially or substituted after the snapshot. Their unrelated targets remain untouched. A fifth test simulates a crash after auxiliary unlink and proves existing explicit Retry completes without another import/add.

## Implementation sequence

1. Record the current source fingerprints and run the existing parser/workflow/verified-acquisition tests in a unique disposable test root.
2. Add failing exact-path, directory-boundary, complete validation/import, genuine-conflict and explicit-retry tests. Capture the failures before correcting the owner.
3. Extend shared ignored classification and record skipped auxiliary videos in manifest output. Do not duplicate classification in the route or transfer manager.
4. Run focused and broader parser/TV/import checks, then the full Python command. Record known unrelated failures separately. No frontend source changes: retain the earlier compiled desktop proof and do not claim new live UI verification.
5. Deliver only changed source/test/docs files after checking that main checkout fingerprints still match their captured pre-repair values. Report activation/retry requirements explicitly.

## Acceptance matrix

| Scenario | Exact result | Evidence |
| --- | --- | --- |
| Actual Louie Featurettes path, both slash styles | Ignored auxiliary video, no episode ownership | Exact literal parser regression |
| Numbered video in auxiliary directory | Ignored flag survives SxxEyy and NxNN branches | Parser boundary test |
| Show/package root named Extras | Root alone does not ignore an episode | Negative boundary test |
| Similar ordinary folder name | No substring matching | Negative boundary test |
| Three episode files plus bonus video | Validated, bonus priority zero, one resume, only three files imported and bound | Actual manager/service/store/import owners with fixture network/probe |
| Forced-download bonus already exists | Known staging copy deleted only after committed episode publication and transfer removal; no bonus in library | Same complete-path test |
| Auxiliary source changes, is shared, or has an unknown neighbor | Cleanup stops before deleting any source; the bonus, episodes and unrelated neighbor are retained | Three adverse cleanup regressions |
| Directory/save-root alias exists or appears after snapshot | Review required, no unrelated file deletion | Four real Windows junction regressions |
| Crash after auxiliary unlink, before removed checkpoint | Explicit Retry completes cleanup with three library files and one original add | Recovery regression |
| Wrong-show episode in ordinary folder | validation_failed, no resume | Manifest negative test |
| Auxiliary-only pack | Missing coverage rejected | Manifest negative test |
| Saved validation_failed job with retained files | Explicit retry revalidates same hash/intent, resumes without a second add | Existing recovery owner regression |
| Existing wrong year, label, combined episodes, path traversal, manual/Follow/bulk | Existing rejection and lifecycle rules retained | Focused/broader suites |

## Verification and rollout

Use CP_TEST_MODE=1, a unique OS-temp CP_TEST_ROOT and temporary CP_TEST_DIST_DIR. Never use production TV roots or jobs for test writes. Focused command: `.venv\Scripts\python.exe -m unittest tests.test_tv_download_workflow tests.test_verified_tv_acquisition tests.test_tv_follow_season_planning tests.test_tv_catalog`. Broader command includes existing normal import, coverage, ingestion and destinations. Full command: `.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'`, with isolated compiled dist for route tests; retain its exact failures.

No source repair automatically clears a live saved validation failure. Live activation and Retry must be reported as separate from source verification. Keep the current progressing transfer and its partial files. No commits, pushes or release.

**Updated live observation:** A later read-only sample shows the Louie torrent at progress 1 (`forcedUP`), downloaded 10,278,791,570 bytes. CP's journal still says `validation_failed`. Preserve the completed payload for the corrected owner to verify/import; do not delete or replace this successful transfer.
