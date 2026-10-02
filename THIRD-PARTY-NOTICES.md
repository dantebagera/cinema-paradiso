# Third-party notices

## Watchdog

Cinema Paradiso uses Watchdog 6.0.0 for native filesystem change notifications.

- Project: https://github.com/gorakhargosh/watchdog
- License: Apache License 2.0
- License text: https://www.apache.org/licenses/LICENSE-2.0

The installed Python distribution also carries its upstream `LICENSE` file in package metadata.

## Movie awards source fixtures and taxonomy

The bundled movie-awards seed contains independently verified Oscar ceremonies 1–98 and Golden Globe ceremonies 1–83. Both organizations pass complete independent historical coverage, identity and redistribution gates. The seed contains aggregate film/personal wins and verified identities, not a category ledger.

- DLu Oscar data: https://github.com/DLu/oscar_data, revision `c5e9716b7e020e70205d6b95f5a5678526c1b45f`. BSD 2-Clause; the full notice is retained in `static/movie-awards/licenses/oscar-data-BSD-2-Clause.txt`. The test fixture contains selected winning records, with selection and hashes in `tests/fixtures/movie_awards/dataset-provenance.json`.
- Golden Globe Awards 1944–2020 by Unanimad: https://www.kaggle.com/datasets/unanimad/golden-globe-awards. Kaggle metadata identifies the license as CC0/Public Domain. The inspected mirror is pinned at `prasertcbs/basic-dataset` revision `8415fd4eedd124d739d75430853796e13ded1009`; fixture provenance retains both origins.
- Minimal annual-page layout fixtures are adapted from Wikipedia contributors' pages for the 97th and 98th Academy Awards and the 82nd and 83rd Golden Globes. Each fixture's adjacent `.provenance.json` records its original URL and exact revision. These adaptations retain only selected category headers and winning list entries and are licensed under CC BY-SA 4.0: https://creativecommons.org/licenses/by-sa/4.0/. Wikipedia contributors' history and attribution are available through each recorded page and revision.
- Reproducible source evidence is retained in `docs/verification/movie-awards/reproduction/`: the pinned DLu CSV, Unanimad's CC0 historical Globe CSV, and Wikipedia contributors' unchanged ceremony/category/subject bytes. `sources-manifest.json` records each original URL, exact revision and byte hash. Wikipedia material and its adapted factual records retain CC BY-SA 4.0 attribution; the generated counts are independently compared with different records for every category. The runtime manifest records the seed hash; the reproduction README explains the offline build.
- The original compilation of 118 sparse official historical facts is dedicated under CC0 1.0: https://creativecommons.org/publicdomain/zero/1.0/. This dedication applies only to the original factual transcription, never the Golden Globes website. Each row retains its original page URL, exact response SHA-256, positive status/category/associated subject and a hash bound to its transcribed fields. No website prose, HTML, photographs or full database is distributed. Golden Globe names/designs remain the property of their respective owners.
- The MengtingWan mixed-event dataset was inspected as source and identity evidence. Its repository has an Apache 2.0 license, while the README identifies the data as IMDb-derived. Data-specific redistribution terms are not established in this implementation; the raw dataset and its extracted rows are not bundled. No historical readiness claim depends on a repository license alone.
