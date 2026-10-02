# Reproduce the complete movie-awards seed

The pinned public inputs reproduce all 98 Oscar and 83 Golden Globe ceremonies through October 2, 2026. No provider credentials or network access are needed. Every ceremony passes the full independent category program, winning-film/eligible-recipient comparison and typed identity gates; the build reports zero unresolved identities, conflicts or source failures.

Run from the Cinema Paradiso checkout:

```powershell
$env:CP_TEST_MODE = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$awardsOutput = Join-Path $env:TEMP ('cp-awards-reproduce-' + [guid]::NewGuid().ToString('N'))
& .\.venv\Scripts\python.exe -m tools.build_movie_awards_snapshot --output-root $awardsOutput --sources-manifest docs/verification/movie-awards/reproduction/sources-manifest.json --identity-overrides docs/verification/movie-awards/reproduction/identity-overrides.json
```

`seed.json` must be byte-identical to `static/movie-awards/seed.json`, SHA-256 `d634b020c4f8410cc1b916eab6c38ab5b389cea749885347f2da51240da918b3`. It contains 181 ceremony contributions and 2,377 verified movie/person mappings. The store verifies this hash before installation. Reproduction writes only to OS-temp and does not install anything in the running app.

DLu's unchanged Oscar CSV is BSD 2-Clause; its complete notice is in `static/movie-awards/licenses/oscar-data-BSD-2-Clause.txt`. The unchanged historical Globe CSV is the pinned prasertcbs mirror of Unanimad's [CC0 Kaggle dataset](https://www.kaggle.com/datasets/unanimad/golden-globe-awards). Wikipedia contributors' exact ceremony/category/subject revisions and unchanged byte hashes are recorded in the manifest under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); each recorded URL provides attribution and access to revision history. Generated adaptations retain that attribution and license.

Primary category pages replace incomplete annual associations and incorrect CSV winners. Explicit source groups assign one category owner for each ceremony; overlap is rejected. Independent annual programs retain all other categories. The 118 sparse official facts supplement only explicitly reviewed historical category blocks; every record carries its original page, response hash, exact positive status and a hash bound to the transcribed fields. The CC0 dedication applies to this original factual compilation, not the Golden Globes website. Raw website HTML, prose, photographs and its full database are not distributed. The modern Mengting/IMDb scrape is not a bundled source.

An adaptation cannot verify the original record it transcribes. The identity owner checks each category's actual cited origin as well as adapter/revision identity. A failed byte hash, winner/recipient disagreement, missing category, unverified identity or source-license gate keeps the affected organization pending; no partial career total is published.

Reviewed source exceptions preserve the agreed counting rule: unassociated career honors remain excluded. Debbie Reynolds's 1951 New Star entry is a nominee; the original generic Gene Nelson award remains. Carolyn Jones's 1958 honor has no film association in the original CSV or official record; the category-page illustration of *Marjorie Morningstar* does not create a film win. Pia Zadora's 1982 award retains its generic historical category. The official Miracle Worker URL combines film and TV records; only its explicit 1963 movie-category win is transcribed, anchored to the 1962 Arthur Penn film identity. The 1974 theatrical *Scenes from a Marriage* uses IMDb `tt6725014` and TMDb movie 133919; the TV identity is excluded. Sallah's independently documented Samuel Goldwyn and foreign-language awards remain distinct.

Only entities and scoped identity overrides used by verified contributions remain. Removing unused mappings was checked against every film count and personal winning-film membership. Minimal typed identity facts are retained for local rendering; no credentials or catalog changes are part of reproduction.
