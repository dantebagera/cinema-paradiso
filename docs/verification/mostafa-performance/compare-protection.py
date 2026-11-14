import json
from pathlib import Path
root=Path(__file__).resolve().parent
before=json.loads((root/'protection-before-complete.json').read_text(encoding='utf-8'))
initial=json.loads((root/'protection-before.json').read_text(encoding='utf-8'))
after=json.loads((root/'protection-after.json').read_text(encoding='utf-8'))
result={
    'main_files_checked':len(before['main']),
    'main_changed_files':[key for key,value in before['main'].items() if after['main'].get(key)!=value],
    'main_added_files':[key for key in after['main'] if key not in before['main']],
    'worktree_changed_source_files':[key for key,value in initial['worktree'].items() if after['worktree'].get(key)!=value and key.startswith(('src\\','services\\'))],
    'worktree_config_unchanged':before['worktree']['config.json']==after['worktree']['config.json'],
    'databases':{},
}
for label in ('main','worktree'):
    old={db['path']:db for db in before['databases'][label]}
    result['databases'][label]=[{'path':db['path'],'integrity':db['integrity'],'counts_unchanged':db['counts']==old[db['path']]['counts'],'changes':{table:{'before':old[db['path']]['counts'].get(table),'after':count} for table,count in db['counts'].items() if old[db['path']]['counts'].get(table)!=count}} for db in after['databases'][label]]
(root/'protection-comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
