"""Fail-closed Python boundary for copied CP execution; never edits application code."""
import atexit,json,os,sqlite3,sys,threading
from pathlib import Path

ROOT=os.path.normcase(os.path.abspath(os.environ['CP_ISOLATION_ROOT']))
ROLE=os.environ.get('CP_ISOLATION_ROLE','suite')
BASE=r'C:\Users\dante\Desktop\cinema paradiso'
READ=[ROOT,os.path.normcase(sys.prefix),os.path.normcase(sys.base_prefix),
      os.path.normcase(os.environ.get('SystemRoot',r'C:\Windows')),
      os.path.normcase(BASE+r'\.venv')]
TOOL_READ={os.path.normcase(r'C:\Users\dante\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe')}
_real_stat=os.stat; _real_scandir=os.scandir; _real_listdir=os.listdir
_real_connect=sqlite3.connect
violations=[];counts={};_tls=threading.local()
_report=open(os.path.join(ROOT,'guard-'+str(os.getpid())+'.json'),'w',encoding='utf-8')

class BoundaryViolation(PermissionError):pass

def norm(p):
    if isinstance(p,int) or p is None:return None
    p=os.fsdecode(p)
    if p in {':memory:','NUL','nul'}:return None
    if p.startswith('file:'):
        from urllib.parse import unquote,urlsplit
        p=unquote(urlsplit(p).path)
        if p.startswith('/') and len(p)>2 and p[2]==':':p=p[1:]
    if p.startswith('\\\\?\\'):p=p[4:]
    return os.path.normcase(os.path.abspath(p))

def inside(p,root):return p==root or p.startswith(root.rstrip('\\/')+os.sep)

def deny(event,value):
    if len(violations)<200:violations.append({'event':event,'value':str(value)[:400]})
    raise BoundaryViolation('ISOLATION BLOCKED '+event+': '+str(value)[:180])

def check(p,write=False):
    p=norm(p)
    if p is None:return
    if write:
        if not inside(p,ROOT):deny('write',p)
    elif p not in TOOL_READ and not any(inside(p,r) for r in READ):deny('read',p)

def audit(event,args):
    if getattr(_tls,'busy',False):return
    _tls.busy=True
    try:
        counts[event]=counts.get(event,0)+1
        if event=='open':
            p,mode,flags=args
            write=bool((flags or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)) or bool(mode and any(k in mode for k in 'wax+'))
            check(p,write)
        elif event=='sqlite3.connect':check(args[0],True)
        elif event=='sqlite3.load_extension':deny(event,'extension loading')
        elif event in {'os.remove','os.rmdir','os.mkdir','os.chmod','os.utime','os.truncate'}:check(args[0],True)
        elif event in {'os.rename','os.replace'}:check(args[0],True);check(args[1],True)
        elif event in {'os.link','os.symlink'}:check(args[0]);check(args[1],True)
        elif event in {'os.listdir','os.scandir','os.chdir'}:check(args[0])
        elif event in {'socket.connect','socket.connect_ex','socket.sendto'}:deny(event,args[-1])
        elif event=='socket.getaddrinfo':
            if args[0] not in {'localhost','127.0.0.1','::1',None}:deny(event,args[0])
        elif event=='socket.bind':
            address=args[1]
            if isinstance(address,tuple) and (address[0] not in {'127.0.0.1','localhost','::1'} or address[1] in {5000,8686}):deny(event,address)
        elif event=='subprocess.Popen':
            exe,command,cwd,env=args
            first=str(command).lstrip()
            executable=str(exe) if exe else (first[1:].split('"',1)[0] if first.startswith('"') else first.split(' ',1)[0])
            # Existing lease crash/ownership tests require a guarded child interpreter.
            permitted=(ROLE=='suite' and 'from services.catalog_writer_lease import' in str(command)
                and os.path.normcase(executable)==os.path.normcase(sys.executable)
                and isinstance(env,dict) and env.get('CP_ISOLATION_ROOT')==os.environ['CP_ISOLATION_ROOT']
                and str(Path(__file__).parent) in env.get('PYTHONPATH',''))
            if not permitted:deny(event,exe)
            check(cwd)
        elif event in {'os.system','os.startfile','os.exec','os.posix_spawn'}:deny(event,args[0])
    finally:_tls.busy=False

def stat(path,*args,**kwargs):check(path);return _real_stat(path,*args,**kwargs)
def scandir(path='.'):check(path);return _real_scandir(path)
def listdir(path='.'):check(path);return _real_listdir(path)
def connect(*args,**kwargs):
    check(args[0] if args else kwargs['database'],True)
    con=_real_connect(*args,**kwargs)
    def authorizer(action,*rest):
        return sqlite3.SQLITE_DENY if action in {sqlite3.SQLITE_ATTACH,sqlite3.SQLITE_DETACH} else sqlite3.SQLITE_OK
    con.set_authorizer(authorizer)
    return con

def save():
    json.dump({'pid':os.getpid(),'role':ROLE,'root':ROOT,'violations':violations,'audit_counts':counts},_report,indent=2)
    _report.close()

def install():
    sys.dont_write_bytecode=True
    sys.addaudithook(audit)
    os.stat=stat;os.scandir=scandir;os.listdir=listdir
    sqlite3.connect=connect
    atexit.register(save)
