"""Explicit local-only integration qualification; never connects to a user's client."""
import hashlib, json, os, shutil, socket, subprocess, tempfile, time
from pathlib import Path
from types import SimpleNamespace

def encode(value):
    if isinstance(value, int): return b'i'+str(value).encode()+b'e'
    if isinstance(value, str): value=value.encode()
    if isinstance(value, bytes): return str(len(value)).encode()+b':'+value
    if isinstance(value, list): return b'l'+b''.join(encode(v) for v in value)+b'e'
    return b'd'+b''.join(encode(k)+encode(v) for k,v in sorted(value.items()))+b'e'

def main():
    root=Path(tempfile.mkdtemp(prefix='cp-tv-real-client-')).resolve()
    os.environ['CP_TEST_MODE']='1';os.environ['CP_TEST_ROOT']=str(root)
    from services.qbittorrent import QBittorrentManager, QBittorrentClient, process_launch_kwargs
    from services.tv_acquisition import TVAcquisition
    from services.tv_catalog_repository import TVCatalogRepository
    from services.acquisition_store import AcquisitionRepository
    from services.media_file_facts import probe_media_file
    executable=Path(os.environ['CP_QBT_QUALIFY_EXE']).resolve()
    if not executable.is_file(): raise ValueError('Explicit qBittorrent executable required')
    def port():
        with socket.socket() as s: s.bind(('127.0.0.1',0));return s.getsockname()[1]
    clients=[];processes=[]
    try:
        for name in ['seed','download']:
            web,peer=port(),port()
            manager=QBittorrentManager(root/name,{'webui_port':web},[root/(name+'library')])
            manager._write_profile()
            print('Starting isolated',name,web,peer,flush=True)
            config=manager.profile_dir/'qBittorrent/config/qBittorrent.ini'
            with config.open('a') as f:f.write(f'\n[BitTorrent]\nSession\\DHTEnabled=false\nSession\\LSDEnabled=false\nSession\\PeXEnabled=false\nSession\\Port={peer}\nSession\\InterfaceAddress=127.0.0.1\n')
            process=subprocess.Popen([str(executable),f'--profile={manager.profile_dir}',f'--webui-port={web}','--no-splash'],**process_launch_kwargs())
            processes.append(process)
            for _ in range(80):
                try: manager.client.request('/api/v2/app/version',timeout=1);break
                except Exception: time.sleep(.25)
            else: raise RuntimeError('Isolated client did not start')
            manager.ensure_running=lambda:True
            manager.client.request('/api/v2/app/setPreferences',{'json':json.dumps({'dht':False,'pex':False,'lsd':False,'listen_port':peer,'upnp':False,'allow_multiple_connections_per_ip':True})})
            clients.append((manager,peer))
        seed,seedport=clients[0];download,_=clients[1]
        pack='Harbor.Signals.S01.1080p.WEB-DL'
        folder=seed.staging_dir/pack;folder.mkdir()
        for n in [1,2]:
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i',f'testsrc2=size=1920x1080:rate=12:duration=2','-c:v','libx264','-preset','ultrafast','-crf',str(23+n),str(folder/f'Harbor.Signals.S01E{n:02d}.1080p.WEB-DL.mkv')],check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        files=sorted(folder.iterdir());payload=b''.join(p.read_bytes() for p in files);piece=16384
        info={'name':pack,'piece length':piece,'pieces':b''.join(hashlib.sha1(payload[i:i+piece]).digest() for i in range(0,len(payload),piece)), 'files':[{'length':p.stat().st_size,'path':[p.name]} for p in files]}
        content=encode({'info':info});digest=hashlib.sha1(encode(info)).hexdigest()
        seed.client.add_torrent(content,'fixture.torrent',str(seed.staging_dir))
        for _ in range(80):
            torrents=seed.client.torrents()
            if torrents and torrents[0]['progress']==1:break
            time.sleep(.25)
        else: raise RuntimeError('Local seeder did not finish checking synthetic media')
        repo=TVCatalogRepository(root/'tv.sqlite');series=repo.refresh({'tmdb_id':900001,'title':'Harbor Signals','first_air_date':'2020-01-01'},[{'season_number':1,'episode_number':n,'title':f'Episode {n}','air_date':'2020-01-01'} for n in [1,2]])
        library=root/'library';library.mkdir()
        provider=SimpleNamespace(base_url='http://fixture.invalid',search_tv=lambda **_: [{'title':pack,'infoHash':digest,'magnetUrl':f'magnet:?xt=urn:btih:{digest}&x.pe=127.0.0.1:{seedport}','size':len(payload),'seeders':1,'indexerId':1}])
        owner=TVAcquisition(repo,AcquisitionRepository(root/'acquisition.sqlite'),lambda:provider,lambda:download,lambda:[library])
        download.domain_handlers['tv']=owner
        mode=os.environ.get('CP_QBT_QUALIFY_TRANSPORT','magnet')
        if mode=='torrent': owner.submit_candidate=lambda manager,candidate,metadata:manager.submit_torrent(content,'fixture.torrent',metadata)
        decision=owner.search(series,1,episode_numbers=[1])['decisions'][0]
        assert decision['accepted'],decision['reasons']
        result=owner.submit(decision['decision_token'],'local-integration')
        assert result['job']['state']=='validating'
        # Explicit loopback peer; the torrent contains no public tracker.
        observed=[]
        for attempt in range(160):
            try: download.client.request('/api/v2/torrents/addPeers',{'hashes':digest,'peers':f'127.0.0.1:{seedport}'})
            except Exception: pass
            download.process_completed()
            job=download.jobs.get(digest)
            if job['state'] not in observed:observed.append(job['state'])
            if job['state'] in {'imported','validation_failed','needs_review'}:break
            time.sleep(.5)
        actual=download.client.files(digest)
        assert job['state']=='imported',{'job_state':job['state'],'error':job.get('last_error'),'files':actual}
        assert [f['priority'] for f in actual]==[1,0],actual
        episodes=repo.episodes(series,1)
        assert episodes[0]['available'] and not episodes[1]['available']
        report={'root':str(root),'client_version':download.client.version(),'transport':mode+' from loopback-only synthetic seeder','states':observed,'file_priorities':[f['priority'] for f in actual],'published_episode_numbers':[e['episode_number'] for e in episodes if e['available']],'source_retained':all(p.exists() for p in files),'measured_quality':episodes[0]['versions'][0]['facts'].get('quality_class')}
        output=Path('docs/verification/tv-parity/real-client'+('-torrent' if mode=='torrent' else '')+'.json');output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2));print(json.dumps(report))
    finally:
        for manager,_ in clients:
            try:manager.client.shutdown()
            except Exception:pass
        for process in processes:
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=10)
        print('Isolated client processes stopped. Test files retained at',root)

if __name__=='__main__':main()
