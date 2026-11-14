"""Disposable fixture allocation and fail-closed owned-server identity validation."""
from pathlib import Path
from uuid import uuid4
def new_fixture_root(parent,kind):
    root=Path(parent)/('pass3-'+kind+'-'+uuid4().hex);root.mkdir(exist_ok=False);return root
def verify_record(record,*,pid,nonce,root):
    assert isinstance(record,dict)
    assert record.get('pid')==pid and type(pid) is int
    assert record.get('nonce')==nonce and isinstance(nonce,str) and nonce
    assert Path(record.get('root','')).resolve()==Path(root).resolve()
    assert type(record.get('port')) is int and 1024<record['port']<65536 and record['port'] not in {5000,8686}
    assert record.get('test_mode') is True
    return record
