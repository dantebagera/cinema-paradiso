# Plex Rotten Tomatoes — main-folder application, 2026-11-14

Applied to `C:\Users\dante\Desktop\cinema paradiso` on branch master at117526b plus its existing dirty work. Dante approved the specific4px collapsed-card exception and application to main, then explicitly instructed: "apply it to the folder , dont test i will".

## Result

- Applied21feature product files and copied8regression files. Existing target files matched the preserved pre-feature baseline before replacement;255other source files were checked for preservation by file hashes.
- Built the current main source with `npm run build`; successful. Generated bundle: `/assets/index-BWbtuTmw.js`. The build includes current main IPTV/AI changes as well as RT.
- No tests were run during this application. No live requests, runtime behavior checks, restart, catalog refresh, commit or push were performed. The geometry test was updated to the explicitly approved4px exception but not rerun.
- Restart CP to load the new backend. A generated bundle is not proof that the running app has loaded the backend changes.
- Rollback backup of replaced files and prior dist: `C:\Users\dante\AppData\Local\Temp\cp-before-plex-rt-activation-_xsswp5j`. `manifest.json` records original existence and hashes; entries originally absent are new feature files.

## Final behavior

Collapsed Movie cards show RT beside TMDB at the bottom, with the compact vote count retained and the word votes removed. Expanded RT sits between awards and TMDB; long expanded titles wrap. Existing text/icon sizes remain. Up to4px extra collapsed height is approved only for crowded cards without both TMDB and awards.

RT remains optional and deferred behind cards/posters and browser idle. Saved locally captured owned scores remain eligible offline; unowned scores require Plex availability. Missing ratings do not produce a user-facing error.

Earlier isolated evidence and screenshots remain in the worktree at `C:\Users\dante\.codex\worktrees\plex-rt-ratings\cinema paradiso\docs\verification\plex-rotten-tomatoes-2026-11-14`. Those runs do not establish live behavior of the combined main checkout.
