"""Read-only protection and backend/configuration comparison; never import CP."""
import hashlib,json,sqlite3,subprocess,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
MAIN=Path(r'C:\Users\dante\Desktop\cinema paradiso')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot(root):
    files=set()
    for folder in ('src','services','tools'):
        files.update(p for p in (root/folder).rglob('*') if p.is_file() and p.suffix in ('.py','.js','.jsx','.css','.mjs','.ps1','.bat') and '__pycache__' not in p.parts)
    files.update(root/f for f in ('app.py','config.json','run.bat','package.json','package-lock.json','requirements.txt','dist/index.html','data/qbittorrent/jobs.json') if (root/f).exists())
    return {str(p.relative_to(root)):digest(p) for p in sorted(files)}
def dbinfo(p):
    con=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
    try:return {'path':str(p),'integrity':con.execute('pragma integrity_check').fetchone()[0],'counts':{name:con.execute('select count(*) from "'+name.replace('"','""')+'"').fetchone()[0] for (name,) in con.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")}}
    finally:con.close()
result={'main':snapshot(MAIN),'worktree':snapshot(ROOT),'databases':{},'configs':{},'http':{}}
for label,root in [('main',MAIN),('worktree',ROOT)]:
    cfg=json.loads((root/'config.json').read_text(encoding='utf-8-sig'))
    result['configs'][label]={k:v for k,v in cfg.items() if k in ('user_data_dir','tmdb_cache_dir','movies_dirs','tv_dirs','tv_root','qbt_webui_port','qbt_mode','qbt_download_dir','qbt_incomplete_dir')}
    paths=list((root/'data').glob('*.sqlite'))
    paths.extend((root/'data'/'awards').glob('*.sqlite'))
    if label=='main':paths.append(Path(r'C:\Users\dante\AppData\Local\Cinema Paradiso\Catalog\catalog-read-cb30c1d963c88463.sqlite'))
    result['databases'][label]=[dbinfo(p) for p in paths if p.exists()]
for port in (5000,15000):
    for route in ('/api/user/lists','/library'):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}{route}',timeout=10) as response:
                body=response.read()
                result['http'][f'{port}{route}']={'status':response.status,'sha256':hashlib.sha256(body).hexdigest()}
                if route=='/api/user/lists':
                    data=json.loads(body);result['http'][f'{port}{route}']['lists']=[{'id':x['id'],'name':x['name'],'count':len(x.get('movies',[]))} for x in data.get('lists',[])]
        except Exception as e:result['http'][f'{port}{route}']={'error':str(e)}
out=ROOT/'docs/verification/mostafa-performance'/('protection-'+(__import__('sys').argv[1] if len(__import__('sys').argv)>1 else 'before')+'.json')
out.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'databases':{k:[{'path':x['path'],'integrity':x['integrity']} for x in v] for k,v in result['databases'].items()},'http':result['http'],'backend_differences':[k for k in result['main'] if k.startswith('services') and (ROOT/k).exists() and (MAIN/k).read_text(encoding='utf-8')!=(ROOT/k).read_text(encoding='utf-8')]},indent=2))
