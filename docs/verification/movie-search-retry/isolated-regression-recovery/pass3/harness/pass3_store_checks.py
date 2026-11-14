"""Read-only integrity and retained-count checks on copied, reopened recovery stores."""
import json,sqlite3
from pathlib import Path
R=Path(__file__).parent;DATA=R/'tmp/recovered/data'
files=[DATA/'.catalog-test.sqlite',DATA/'acquisition.sqlite',DATA/'tv-catalog.sqlite',DATA/'awards/awards.sqlite']
files+=sorted((DATA/'iptv/providers').glob('*/*.sqlite'));assert len(files)==8
results=[]
for p in files:
    assert R in p.resolve().parents
    with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True) as con:
        con.execute('PRAGMA query_only=ON')
        check=con.execute('PRAGMA quick_check').fetchall();fk=con.execute('PRAGMA foreign_key_check').fetchall()
        assert check==[('ok',)],(str(p),check)
        assert not fk,(str(p),fk[:2])
        counts={}
        if p.name=='.catalog-test.sqlite':
            for table in ['media_files','tmdb_movies']:counts[table]=con.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
            assert counts==json.loads((R/'prepared.json').read_text())['movie_table_counts']
        results.append({'path':str(p.relative_to(DATA)),'mode':'ro; query_only=ON','quick_check':check,'foreign_key_errors':len(fk),'counts':counts})
    con.close()
proof={'databases':results,'all_ok':True,'movie_rows_preserved':True,'after_completed_second_recovery_boot':True}
(R/'pass3-post-recovery-stores.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'post_recovery_databases_checked':len(results),'all_ok':True,'movie_rows_preserved':True}),flush=True)
