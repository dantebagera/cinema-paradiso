"""One sequential command, cumulative hard budget, fresh isolated environment."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')

evidence = os.environ.get('CP_TV_PERF_TASK_ROOT') or Path(__file__).with_name('task-root.txt').read_text().strip()
root = Path(evidence)
run = json.loads(Path(os.environ.get('CP_TV_PERF_RUN_CONFIG') or Path(__file__).with_name('active-run.json')).read_text())
run_dir = Path(run['directory'])
budget_path = root/'budget.json'
budget = json.loads(budget_path.read_text())
remaining = budget['limit_seconds']-budget['active_seconds']
if remaining <= 10:
    raise SystemExit('Verification budget exhausted')
label, *command = sys.argv[1:]
env = dict(os.environ, CP_TEST_MODE='1', CP_TEST_QBT_MODE='embedded')
test_root = root/str(uuid.uuid4())
test_root.mkdir()
env.update(CP_TEST_ROOT=str(test_root), CP_TEST_DIST_DIR=str(test_root/'dist'),
           CP_TV_PERF_EVIDENCE=str(root), CP_TV_PERF_RUN_ID=run['id'],
           CP_TV_PERF_RUN_DIR=str(run_dir), CP_TV_PERF_BASELINE_SOURCE=run['baseline_source'],
           PYTHONIOENCODING='utf-8')
size = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
if size >= 1024**3: raise SystemExit('Temporary footprint limit reached')
print(f'{label}: {remaining:.2f}s remaining; {size} temporary bytes', flush=True)
started = time.monotonic()
code = 125
log_path = run_dir/f'{label}.log'
if log_path.exists(): raise SystemExit('Refusing to overwrite phase evidence')
try:
    with log_path.open('x', encoding='utf-8') as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=remaining-10)
        except subprocess.TimeoutExpired:
            # Only this phase's owned process tree; reserve time for cleanup.
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'], stdout=log, stderr=log, timeout=8)
            code = 124
finally:
    elapsed = time.monotonic()-started
    budget['active_seconds'] += elapsed
    budget.setdefault('phases', []).append({'label': label, 'seconds': elapsed, 'exit': code, 'test_root':str(test_root)})
    budget_path.write_text(json.dumps(budget, indent=2))
lines = log_path.read_text(encoding='utf-8').splitlines()
print('\n'.join(lines[-22:]))
print(f'EXIT={code} ACTIVE_TOTAL={budget["active_seconds"]:.3f}s')
raise SystemExit(code)
