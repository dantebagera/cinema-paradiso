"""Final bounded metadata-only closeout. Budget wrapper closes after this returns."""
import json,runpy,shutil,sys
from pathlib import Path
R=Path(__file__).parent;BASE=Path(r'C:\Users\dante\Desktop\cinema paradiso')
OUT=BASE/'docs/verification/movie-search-retry/isolated-regression-recovery/library-exit-audit'
completion=json.loads((R/'pass4-qualified/completion.json').read_text())
assert completion['qualified'] and completion['server_exit_code']==0 and not completion['forced_pids']
assert completion['audit']['violations']==[]
assert 'Ran 21 tests' in (R/'pass4-review-fixes-green.log').read_text() and (R/'pass4-review-fixes-green.log').read_text().rstrip().endswith('OK')
runpy.run_path(str(R/'pass4_stage.py'),run_name='__main__')
plan=BASE/'docs/plans/2026-10-24-library-exit-audit-final.md'
text=plan.read_text(encoding='utf-8')
text=text.replace('**Status:** Approved for implementation in a new local task, 2026-10-24.',
 '**Status:** Implemented and verified in isolation, 2026-10-24. Evidence: [Library exit audit report](../verification/movie-search-retry/isolated-regression-recovery/library-exit-audit/README.md).')
text=text.replace('- [ ]','- [x]')
text+='\n## Execution outcome\n\nThe strict disposable controller and single audit validator are implemented. Final focused harness suite: **21 passed**, zero failures/errors/skips. Unchanged compiled Library scenarios: **5 passed**, zero unexpected/skipped/flaky cases and no report-level errors. Owned server PID 35676 stopped through its attested private endpoint, exited normally with code 0, and emitted a complete matching audit: `open=652`, `sqlite3.connect=917`, `violations=[]`. No forced cleanup in this qualification.\n\nOne earlier setup attempt failed before Chromium launched because the redirected profile changed browser-cache discovery; UTF-8 error-report reading also needed an explicit encoding. That failure and its forced cleanup remain retained and charged. The existing browser runtime was selected explicitly, with no installation. The successful run used separate artifacts and a fresh fixture; no Playwright retries were enabled.\n\nOne fresh read-only reviewer found two Important failure-path issues (original exception preservation and fail-closed budget accounting). Both were fixed in one RED-to-GREEN pass; the entire focused 21-test suite passed afterward, with no repeated browser run. Final preservation and exact closed resource totals are linked in the report. No product/live/native/provider/full-suite claim is added, and pass three\'s missing-audit history remains intact.\n'
plan.write_text(text,encoding='utf-8')
latest=BASE/'docs/verification/movie-search-retry/isolated-regression-recovery/README.md'
text=latest.read_text(encoding='utf-8');title,rest=text.split('\n',1)
latest.write_text(title+'\n\n**Latest:** [Library exit audit completion](library-exit-audit/README.md): five unchanged compiled Library cases passed, exact owned server exited normally with code 0, complete matching guard audit recorded zero violations, and the strict gate passed 21 focused controls. This closes the earlier missing Library exit report; failed setup and all earlier history remain retained. Product and live state are unchanged.\n'+rest,encoding='utf-8')
readme='''# Library exit audit completion — 2026-10-24

**Result: the remaining isolated Library exit audit is complete.** Five unchanged compiled desktop cases passed. The exact owned server exited normally with code 0 and emitted a complete matching guard audit with zero violations. Product source, tests and live state were preserved.

| Completion gate | Actual result |
| --- | --- |
| Final focused harness suite | 21 passed, zero failures/errors/skips |
| Existing compiled Library cases | 5 passed; unexpected=0, skipped=0, flaky=0; report-level errors=[] |
| Exact child identity | PID 35676, fresh UUID fixture, nonce/root/test-mode/held random port validated before HTTP/browser |
| Private stop and shutdown | Matching stop PID; normal exit 0 within the seven-second wait; no forced cleanup |
| Exit guard report | Valid complete JSON; exact PID, normalized isolation root and role `ui` |
| Workload counters | `open=652`, `sqlite3.connect=917` |
| Audit violations | `[]` |
| Preservation | 1,788 pre-existing safe files sealed; 243 runtime inputs, 35 bundle files, 161 historical evidence files and all 114 tracked dirty entries match; no source/test drift |
| Owned process cleanup | All four recorded owned root PIDs absent; successful Job Object tree drained; no owned process left |

The five scenarios cover serialized rapid typing with all 85 identities reachable, obsolete-response error/recovery and empty/repeat navigation, foreground typing during older poster loading, Movie → File → Movie during a pending read, and page-two quiet refresh through both catalog/library events. The quiet-refresh response marker proves commit while ordered cards, query, page, loading and notifications remain correct. Screenshots were captured from the unchanged compiled bundle at 1600 × 1000; page-two screenshot inspected. No UI edits, mobile work or frontend build.

The new disposable controller calls one strict audit validator. Missing, empty, malformed, mismatched or violating audits cannot qualify a run. Five passing browser results alone are insufficient: exact owned graceful shutdown, exit 0, complete positive workload counts and empty violations are mandatory. Forced termination is failure cleanup only. The guard, private server, fixture allocator, origin restriction and existing five assertions remain unchanged.

The original controller's actual finally body failed six adverse controls before correction. Initial strict controls passed 14/14; two setup regression controls expanded that to 16/16. One fresh read-only reviewer found two Important failure-path defects: outcome writing could replace the original failure, and wrapper exceptions could leave consumed allowance unrecorded. Four adverse controls then failed across five review controls; both fixes passed in the final complete 21-test suite. Budget accounting now persists halted/in-progress state before launch, records exceptional batches and blocks reuse when accounting is uncertain. Pending completion errors retain a secondary report-write-failure note. No second review or repeated browser execution was needed for these failure-path changes. No Critical or unresolved Important finding; provisional bookkeeping Minor resolved at closure.

One initial setup attempt failed: redirecting LOCALAPPDATA changed Playwright's browser-cache lookup, so all five reported launch errors before any browser assertion ran; report decoding also failed under Windows' default cp1252 encoding. The failed owned server was force-cleaned and its guard file is empty. That is a failed setup, not a clean audit. Raw files, failed controller version and costs are retained in `failed-setup/`, `guard-18512.json` and the disposable workspace. Explicit selection of the already installed Chromium cache and UTF-8 report reading corrected setup without installation or guard changes. The qualifying run used a new fixture and separate `qualified/` artifacts; retries remained zero. Two early setup-control development runs errored before explicit RED assertions; their raw logs and costs are also retained.

The source/dirty seals permit only this plan and the additive latest-report link to change among pre-existing files. New checkout files are confined to this verification folder. Existing source/test work and historical pass-three evidence were not overwritten. No commit, push, build, dependency installation, restart, production database access, real provider/torrent/native operation or new live-app interaction was performed.

This closes only the missing Library exit report. Prior pass-three TV/Home/Following/store results and recovered boots remain historical, and the earlier empty Library audit is still documented. Python guards cover trusted application execution, not an OS sandbox; the result does not establish real provider/native/media behavior or physical SSD write volume.

Fresh limits: 180 cumulative active seconds, 90 seconds per batch, 1 GiB process-reported writes, 4 GiB entire temporary-root logical footprint, one worker, zero retries. Setup, failed attempts and controls are charged in the single closed `bounded-pass-4.json`; older allowances remain closed. Exact final totals and all gate results are in [result.json](result.json). These are descendant-process counters and logical footprint, not physical SSD writes or hardware stress measurements.

Evidence: [raw guard audit](guard-35676.json), [strict completion result](qualified/completion.json), [browser report](qualified/browser.json), [final preservation](pass4-preservation-final.json), [fresh review and fixes](pass4-final-review.md), [execution ledger](pass4-progress.md). Reusable disposable helpers and unchanged dependencies are under `harness/`; the original execution root remains `C:\\Users\\dante\\AppData\\Local\\Temp\\cp-regression-recovery-30b40a41d572`.
'''
(OUT/'README.md').write_text(readme,encoding='utf-8')
sys.argv=['pass4_preserve.py','final'];runpy.run_path(str(R/'pass4_preserve.py'),run_name='__main__')
with (R/'pass4-progress.md').open('a',encoding='utf-8') as f:
    f.write('\nTask 2: complete. Final preservation passed; additive report staged and plan/latest link updated only after actual qualification and review fixes. All automated work finished; wrapper/resource ledger closure follows, no more tests.\n')
for name in ['pass4-preservation-final.json','pass4-progress.md']:shutil.copy2(R/name,OUT/name)
print(json.dumps({'metadata_closeout':True,'final_preservation':True,'report':str(OUT),'tests_after_closure':False}))
