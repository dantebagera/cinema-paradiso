# Match hybrid torrent IDs during import

**Status** · Live verified on 2026-11-09. Dante asked to “fix the torrent ID mismatch and get CP to import The Odyssey without redownloading it,” then separately approved the backend restart.

## Problem and decision

The Odyssey is complete in CP staging. Its saved job uses the torrent's v1 ID and qBittorrent uses its v2-based ID for commands. Both IDs are present on the same live row. The completion monitor looked up only qBittorrent's primary ID, so the saved job timed out. The 5.9 GiB staged file still exists. The repair keeps the saved job and imports that file through the existing Movie move and Library handoff.

## Contracts affected and contract-change decision

| Contract and source | Affected callers | Behavior to preserve |
| --- | --- | --- |
| [Selected-release identity and recovery](../second-brain/movie-downloads-and-import.md) | Movie submission, validation, and completion | Match an ID reported on the torrent itself. Validate its manifest before accepting the payload. Retain the existing journal key, staging containment, conflict rules, move, cleanup, and catalog handoff. |
| [TV download and import rules](../second-brain/tv-downloads-and-import.md) | Shared transfer monitor and TV acquisition | Retain acquisition identity, explicit TV retry policy, file selection, and verified publication. Send client commands to its primary ID when a matched live row is available. |

The fix changes how the service identifies the same release. The existing verification and publication rules apply. No product contract decision is open.

## Current design and ownership

`QBittorrentManager` owns submission, validation, and dispatch from the download monitor. `QBittorrentJobStore` owns the persisted key and move checkpoints. `TVAcquisition` owns TV episode selection, publication, and cleanup. Flask's completed-download handoff owns Movie Library publication.

Baseline was the dirty `master` checkout at `be511f9`, Flask PID 28376 on port 5000, and embedded qBittorrent 5.3.0 on port 8686. Data is under the checkout's `data` directory. The served frontend is `index-B-nPNaZj.js`. There is no frontend change.

## Exact behavior contract

Index each live client row by its primary ID and its reported v1 and v2 identities. Resolve an alias only when it identifies one live row. Use the existing journal key for persistence and the client's primary ID for commands. Validate the manifest against the expected identity using the observed row's IDs. A previously timed-out Movie magnet with an exact alternate-ID match to a complete torrent can enter that validation path once. Other failed validations remain failed. Complete torrents proceed through the existing completion path without starting them again.

## Implementation sequence

1. Reproduce a pending hybrid magnet and a previously timed-out complete Movie magnet in isolated tests.
2. Update the transfer manager's identity lookup and validation, then use the client's primary ID for completion commands in the Movie and TV owners.
3. Run the transfer, monitor, API, and TV regression suites. Verify the live staged file, job transition, target file, and Library handoff after authorized activation.

## Acceptance matrix

| Starting state | Expected result |
| --- | --- |
| Hybrid magnet with v1 job key and v2-based client ID | Resolve the same torrent and validate using the reported identities. |
| Completed staged Movie with a timed-out alias job | Import under the same job key and remove the torrent after the move. No add or resume. |
| Same-ID or unmatched metadata timeout | Keep the existing timeout behavior. |
| Unsafe manifest or destination conflict | Existing checks reject the payload or hold the move for review. |
| TV job with a client ID different from its saved key | Verify the correct files and send client actions to the matched row while preserving acquisition and publication state. |

## Verification and rollout

The baseline qBittorrent suite passed 97 tests in an isolated temporary data root. Run the targeted red and green regression tests, then the qBittorrent, download monitor, TV acquisition, and TV import suites with `CP_TEST_MODE=1` and a temporary `CP_TEST_ROOT`. Before any live activation, verify the file, both IDs, free destination space, and current activity. Keep a backup of the journal outside the workspace. The live acceptance check is the existing job's imported path on disk, torrent cleanup, and Movie Library publication.

The three regression tests reproduced the defect before the fix and passed afterward. The broader transfer, API, monitor, TV, and power-action run passed all 192 tests.

After the approved restart, Flask PID 3008 served the same frontend bundle. qBittorrent PID 8408 stayed running. The original job validated the live torrent, moved the staged file to `E:\Movies`, removed the torrent from the client, and completed Movie Library publication. The Library details endpoint returned The Odyssey (2026) with TMDB ID 1368337 at the imported path. The destination file's SHA-256 matched the staged file's checksum.
