# TV library import preview

Read-only inventory of `G:\TV` on 2026-09-27. The preview used a temporary TV database. It did not open or change the live catalog.

| Measure | Result |
|---|---:|
| Supported video files | 1,433 |
| Nonempty top-level folders | 48 |
| Filenames with episode numbering | 1,013 |
| Filenames with season only | 15 |
| Filenames needing numbering review | 405 |

These counts describe filename patterns, not verified show identities. The import UI lists every file and requires an approved TMDB TV identity before linking it. It permits individual file assignments for mixed folders. Files without a safe episode match remain in episode review.

Known review cases in this library include the two Hitchcock series in `Alfred Hitchcock - TV Collection` (268 Presents files, 93 Hour files, and 12 video extras), seven Sherlock files inside the Planet Earth folder, three films mixed into `Breaking Bad`, and same-title series such as Dark Matter and Lost in Space. The import UI exposes child-folder assignments for these cases. A parent assignment cannot silently claim a child folder whose title conflicts with the approved series. The background scan reads only approved paths and skips unchanged linked files.
