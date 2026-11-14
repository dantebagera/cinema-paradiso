import json,os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parent
env={**os.environ,'CP_ISOLATION_ROOT':str(root),'CP_ISOLATION_ROLE':'probe',
 'PYTHONPATH':str(root)+os.pathsep+str(root/'checkout'),'PYTHONDONTWRITEBYTECODE':'1',
 'TEMP':str(root/'tmp'),'TMP':str(root/'tmp'),'PYTHONIOENCODING':'utf-8'}
assert subprocess.run([sys.executable,str(root/'guard_probe.py')],cwd=root/'checkout',env=env).returncode==0
code="""import os,subprocess;from pathlib import Path;from guard import TOOL_READ,BoundaryViolation
p=next(iter(TOOL_READ));assert os.stat(p).st_size>0
blocked=0
for operation in [lambda:open(p,'wb'),lambda:subprocess.run([p,'-version'])]:
 try:operation()
 except BoundaryViolation:blocked+=1
assert blocked==2
print('Exact FFmpeg discovery allowed; writes and execution blocked')
"""
assert subprocess.run([sys.executable,'-c',code],cwd=root/'checkout',env=env).returncode==0
print(json.dumps({'original_guard_controls':8,'ffmpeg_discovery':True,'ffmpeg_write_and_execution_blocked':True}),flush=True)
