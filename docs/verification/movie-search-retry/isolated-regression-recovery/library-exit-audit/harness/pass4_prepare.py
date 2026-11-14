import hashlib,json,subprocess
from pathlib import Path
R=Path(__file__).parent;BASE=Path(r'C:\Users\dante\Desktop\cinema paradiso');CODE=R/'checkout'
SAVED=Path(r'C:\Users\dante\Desktop\CP-Recovery\whole-checkout-2026-10-24-153619-e50288')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def seal(paths,root):return {n:{'sha256':digest(root/n),'bytes':(root/n).stat().st_size} for n in sorted(paths)}
names=set(load(R/'pass3-source-before.json'))
for folder in ['src','tests','tools','services','docs']:
    names.update(p.relative_to(BASE).as_posix() for p in (BASE/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.db','.sqlite','.sqlite3'})
(R/'pass4-source-before.json').write_text(json.dumps(seal(names,BASE),indent=2)+'\n')
status=subprocess.check_output(['git','status','--porcelain=v1','-uno'],cwd=BASE,text=True)
assert len(status.splitlines())==114
(R/'pass4-git-before.txt').write_text(status)
(R/'pass4-git-all-before.txt').write_text(subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'],cwd=BASE,text=True))
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=BASE,text=True).strip()=='be511f98846a67a182e5b371ad087938e9344362'
inputs=load(SAVED/'candidate-inputs.json');bundle=load(SAVED/'candidate-bundle.json')
assert len(inputs)==243 and len(bundle)==35
for n,v in inputs.items():assert digest(BASE/n)==digest(CODE/n)==v['sha256'],n
for n,v in bundle.items():assert digest(CODE/'dist'/n)==v['sha256'],n
prior=[p.relative_to(R).as_posix() for p in R.iterdir() if p.is_file() and not p.name.startswith(('pass4','budget-pass4','bounded-pass-4'))]
for folder in ['pass3-specs','pass3-browser-results']:
    prior.extend(p.relative_to(R).as_posix() for p in (R/folder).rglob('*') if p.is_file())
(R/'pass4-prior-evidence-seal.json').write_text(json.dumps(seal(prior,R),indent=2)+'\n')
print(json.dumps({'source_files':len(names),'tracked_dirty':114,'runtime_inputs':len(inputs),'bundle_files':len(bundle),'prior_evidence_files':len(prior)}))
