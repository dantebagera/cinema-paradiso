"""Additive evidence staging, after review; no application execution."""
import json,shutil
from pathlib import Path
R=Path(__file__).parent;BASE=Path(r'C:\Users\dante\Desktop\cinema paradiso')
OUT=BASE/'docs/verification/movie-search-retry/isolated-regression-recovery/library-exit-audit'
OUT.mkdir(exist_ok=False)
for name in ['pass4-source-before.json','pass4-prior-evidence-seal.json','pass4-git-before.txt','pass4-git-all-before.txt',
 'pass4-preservation-preclose.json','pass4-progress.md','guard-35676.json','guard-18512.json','pass4-final-review.md']:
    shutil.copy2(R/name,OUT/name)
for p in R.glob('pass4*.log'):shutil.copy2(p,OUT/p.name)
failed=OUT/'failed-setup';failed.mkdir()
for name in ['pass4-browser-library.json','pass4-browser-library.log','pass4-ownership.json','pass4-owned-cleanup.json','pass4-ui-library-server.log']:
    shutil.copy2(R/name,failed/name)
shutil.copytree(R/'pass4-browser-results',failed/'browser-results')
shutil.copytree(R/'pass4-qualified',OUT/'qualified')
harness=OUT/'harness';harness.mkdir()
for p in R.glob('pass4*.py'):shutil.copy2(p,harness/p.name)
for name in ['pass4-playwright.config.cjs','budget-pass4.py','budget-pass3.py','budget-pass2.py','pass3_behavior.py','pass3_support.py','pass3_ui_server.py','guard.py','sitecustomize.py']:
    shutil.copy2(R/name,harness/name)
# Same frozen spec/fixture; copied as evidence, never edited or executed from this folder.
for name in ['library-search-performance.spec.js','pass3-browser-fixture.cjs']:
    shutil.copy2(R/'pass3-specs'/name,harness/name)
print(json.dumps({'staged':str(OUT),'prior_history_unchanged':True}))
