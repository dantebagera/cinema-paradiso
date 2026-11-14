# IPTV Filmography destination correction — 2026-11-13

Dante approved correcting the small Filmography button and activating the correction with "yes go". Portrait browsing remains provider-local; the small button opens the existing full Movie Discover filmography, including films absent from IPTV. Biography, design, and offline availability lookups are unchanged.

## Change and ownership

`IPTVPeopleCredits` now supplies separate portrait and Filmography callbacks through its existing context. `IPTVWorkspace` retains provider-local browsing and no longer accepts the obsolete full-filmography flag. `App.openPersonInDiscover` remains the shared Movie Discover owner, explicitly selects Movies, and captures the originating section before scheduling state updates. No new credits loader, database changes, or backend behavior was added.

## Verification

- Initial failing regression: three existing IPTV tests passed; both new actor/director cases failed because the small button stayed on `/iptv` ([red.log](red.log)).
- Initial correction: all 47 desktop IPTV, Movie relationships and TV parity cases passed ([green.log](green.log)). Mobile-only 390px cases were excluded as requested.
- Fresh independent review found a deferred state-update issue that could label the origin Library. Both new breadcrumb assertions reproduced it ([breadcrumb-red.log](breadcrumb-red.log)). The handler now captures origin before navigation; existing award origin uses the same captured section.
- Final compiled regression: 47/47 passed; bundle `index-rEoonoEd.js` ([final-green.log](final-green.log)).
- All 155 Node tests passed ([node.log](node.log)); focused Python IPTV UI/people suites passed 22/22 ([python.log](python.log)). These ran before the final origin-capture adjustment, which is covered by the final compiled suite.
- Browser cases assert the actual Discover destination, correct actor/director ID and role, a visible film absent from IPTV, Movie mode after previously selecting TV, correct IPTV breadcrumb, and preserved expanded IPTV card on return. Existing cases cover Biography, missing identity, portrait geometry, local filters and Back, and other Movie/TV navigation.

## Activation

Activated in the desktop main app after the final compiled regression passed. Candidate and desktop main existing activation targets were compared against their saved pre-correction baseline; all ten matched. The desktop checkout contains extensive unrelated dirty work that is preserved. Only the four corrected source/test files and related guides/evidence are included. No commit, push, package or release.


### Live activation result

- Main build passed and serves `index-rEoonoEd.js` with `index-D1BdEqO-.css`, matching the final isolated build.
- CP restarted through its normal `/api/power/actions` endpoint with qBittorrent left running. Port5000 listener changed from PID46308 to PID32136.
- All four corrected source/test files match the candidate. `config.json` remains byte-identical to the backup; `/api/app-data/config` still identifies the desktop `data` and `cache` directories.
- Recovery snapshot: `C:\Users\dante\.codex\backups\cp-filmography-correction-20261113-212851` (previous target files, full dist, config and activation manifest).
- Live served-bundle/API activation and the production browser interaction are verified. At desktop 1600x1000, opened Lionz CP View, expanded Heart of the Beast, and clicked Brad Pitt's small Filmography button. The live page navigated to `/discover`, selected Movies, displayed `IPTV > Actor: Brad Pitt`, and showed 115 credits across 3 pages. Lionz saved-catalog badges appeared on matching titles; other credits without a badge were also present. No playback was started. Native-window automation was previously blocked, so this check used the same live main app through localhost in the in-app browser. The temporary viewport override was reset.
