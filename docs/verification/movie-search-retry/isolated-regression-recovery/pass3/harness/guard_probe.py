import json,os,socket,sqlite3,subprocess,sys
from pathlib import Path
from guard import BoundaryViolation
root=Path(os.environ['CP_ISOLATION_ROOT'])
checks=[]
def blocked(name,call):
    try:call()
    except (BoundaryViolation,sqlite3.DatabaseError):checks.append(name)
    else:raise RuntimeError('Boundary allowed: '+name)
blocked('production-write',lambda:open(r'C:\Users\dante\Desktop\cinema paradiso\data\ISOLATION-MUST-NOT-EXIST','w'))
blocked('production-read',lambda:open(r'C:\Users\dante\Desktop\cinema paradiso\data\acquisition.sqlite','rb'))
blocked('media-stat',lambda:os.stat(r'E:\Movies'))
blocked('live-socket',lambda:socket.socket().connect(('127.0.0.1',5000)))
blocked('external-socket',lambda:socket.socket().connect(('192.0.2.1',80)))
blocked('production-sqlite',lambda:sqlite3.connect(r'C:\Users\dante\Desktop\cinema paradiso\data\acquisition.sqlite'))
c=sqlite3.connect(':memory:')
blocked('sqlite-attach',lambda:c.execute("ATTACH DATABASE 'C:/Users/dante/Desktop/cinema paradiso/data/acquisition.sqlite' AS forbidden"));c.close()
blocked('subprocess',lambda:subprocess.run([sys.executable,'-c','raise SystemExit(0)']))
(root/'guard-probe.json').write_text(json.dumps({'passed':len(checks)==8,'rejected':checks},indent=2))
print(json.dumps({'guard_negative_controls':len(checks),'passed':True}))
