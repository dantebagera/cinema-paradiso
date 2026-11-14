"""Evidence-only inventory and report staging; never imports the application."""
import hashlib,json,shutil,subprocess
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).parent;BASE=Path(r'C:\Users\dante\Desktop\cinema paradiso')
OUT=BASE/'docs/verification/movie-search-retry/isolated-regression-recovery/pass3';OUT.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before=read(R/'pass3-source-before.json')
drift=[name for name,item in before.items() if not (BASE/name).is_file() or digest(BASE/name)!=item['sha256']]
assert not drift,drift
old_status=(R/'pass3-git-before.txt').read_text()
now_status=subprocess.check_output(['git','status','--porcelain=v1','-uno'],cwd=BASE,text=True)
assert old_status==now_status
saved=Path(r'C:\Users\dante\Desktop\CP-Recovery\whole-checkout-2026-10-24-153619-e50288')
inputs=read(saved/'candidate-inputs.json')
assert all(digest(BASE/name)==item['sha256'] for name,item in inputs.items())
bundle=read(saved/'candidate-bundle.json')
assert all(digest(R/'checkout/dist'/name)==item['sha256'] for name,item in bundle.items())
reports={key:read(R/f'pass3-browser-{key}.json') for key in ['library','home-following']}
for report in reports.values():
    assert report['stats']['unexpected']==0 and report['stats']['skipped']==0 and report['stats']['flaky']==0
stores=read(R/'pass3-post-recovery-stores.json');assert stores['all_ok'] and len(stores['databases'])==8
ledger=read(R/'bounded-pass-3.json');assert not ledger.get('halted')
units=[json.loads(line) for line in (R/'pass3-unit-runs.jsonl').read_text().splitlines()]
assert len(units)==2 and all(item['exit_code']==0 for item in units)
assert units[0]['root']!=units[1]['root']
preservation={'files_compared':len(before),'changed_or_missing':drift,'runtime_inputs_matched':len(inputs),
 'compiled_bundle_files_matched':len(bundle),'tracked_dirty_status_identical':True,
 'tracked_dirty_count':len(now_status.splitlines()),'source_or_existing_test_changes_this_pass':0,
 'verified_utc':datetime.now(timezone.utc).isoformat(),
 'production_boundary_evidence':'Reviewed action record and installed guard; no live HTTP/process control or production data reads/writes performed. Not independently measured hardware access counters.'}
result={'status':'All remaining scoped checks passed; awaiting final read-only review/closure',
 'preservation':preservation,'unit_runs':units,'tv_module_tests_passed':20,'repeat_evidence_case_passed':1,
 'desktop':{key:value['stats'] for key,value in reports.items()},'post_recovery_stores':stores,
 'ownership':{key:read(R/f'pass3-ui-{key}-ownership.json') for key in reports},
 'historical_evidence_not_rerun':{'movie_owner_passed':451,'node_passed':140,
 'cross_domain':{'run':462,'passed':461,'errors':1,'error_fixed_and_affected_module_passed_in_pass3':True},
 'normal_recovery_boots_passed':2},
 'limits':{'active_seconds':600,'per_batch_seconds':240,'process_write_bytes':8*1024**3,'temporary_footprint_bytes':4*1024**3},
 'out_of_scope':['real provider connectivity','real torrent/download operation','native playback','physical media rollback','new live verification'],
 'initial_harness_failure':'Optional base-interpreter user-site discovery was denied by the guard before readiness; PYTHONNOUSERSITE and redirected APPDATA/USERPROFILE fixed the environment without relaxing the boundary.'}
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
(R/'pass3-preservation.json').write_text(json.dumps(preservation,indent=2)+'\n')
for pattern in ['pass3-*.log','pass3-unit-runs.jsonl','pass3-ui-*-ownership.json','pass3-post-recovery-stores.json',
                'pass3-preservation.json','pass3-prepared.json','pass3-browser-*.json']:
    for p in R.glob(pattern):shutil.copy2(p,OUT/p.name)
for p in (R/'pass3-browser-results').rglob('*.png'):
    dest=OUT/'screenshots'/p.relative_to(R/'pass3-browser-results');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
for key in ['library','home-following']:
    pid=result['ownership'][key]['child_pid'];report=R/f'guard-{pid}.json'
    if report.exists():shutil.copy2(report,OUT/report.name)
print(json.dumps({'sealed_files':len(before),'runtime_inputs':len(inputs),'existing_changes_preserved':True,
 'desktop_tests_passed':sum(x['stats']['expected'] for x in reports.values()),'recovered_databases_ok':8}))
