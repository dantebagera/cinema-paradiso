"""Explicit provider reads, with all CP state disposable and no transfer client."""
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.request


def main():
    config = json.loads(Path(os.environ['CP_PROVIDER_CONFIG']).read_text(encoding='utf-8'))
    root = Path(tempfile.mkdtemp(prefix='cp-tv-provider-read-'))
    os.environ.update(CP_TEST_MODE='1', CP_TEST_ROOT=str(root))
    from services.tv_catalog_repository import TVCatalogRepository
    from services.tv_metadata import TVMetadata
    from services.tv_acquisition import TVAcquisition
    from services.acquisition_store import AcquisitionRepository
    from services.source_search import ProwlarrClient
    import app
    app._prowlarr_url, app._prowlarr_key = config['prowlarr_url'], config['prowlarr_key']
    repo = TVCatalogRepository(root/'tv.sqlite')
    # Explicit network opener only for this opt-in read-only qualification.
    # app's test-mode global network guard remains in place for other services.
    metadata = TVMetadata(repo, lambda: config['tmdb_key'], opener=urllib.request.build_opener().open)
    provider = ProwlarrClient(config['prowlarr_url'], config['prowlarr_key'])
    def no_client():
        raise AssertionError('Provider qualification must never request a transfer client')
    owner = TVAcquisition(repo, AcquisitionRepository(root/'acquisition.sqlite'), lambda:provider,
        no_client, lambda:[], metadata=metadata, resolve_candidate=app._resolve_tv_candidate,
        trusted_indexers=lambda:config.get('tv_download_trusted_indexers', []), search_indexers=lambda:None)
    results = []
    for identity in (196322, 202555, 456):
        started = time.monotonic()
        try:
            result = owner.search(tmdb_id=identity, season=1, episode_numbers=[1,2,3])
            counts = {state:sum(d['state']==state for d in result['decisions']) for state in ('eligible','resolve','identity_review','blocked')}
            evidence = {'tmdb_id':identity,'states':counts,'partial':result['search'].get('partial'),
                'sources':result['search'].get('sources'), 'recommended_count':len(result['recommended']),
                'examples':[{'title':d['candidate']['title'],'state':d['state'], 'episodes':d['candidate']['episode_numbers'],
                             'reasons':[r['code'] for r in d['reasons']]} for d in result['decisions'][:6]]}
            candidate = next((d for d in result['decisions'] if d['selectable']), None)
            if candidate:
                try:
                    prepared = owner.prepare(candidate['decision_token'])
                    evidence['selected_transport_check'] = {'accepted':prepared['accepted'],'hash_length':len(prepared['candidate']['info_hash']),
                        'reasons':[r['code'] for r in prepared['reasons']]}
                except Exception as error:
                    evidence['selected_transport_check'] = {'error_type':type(error).__name__}
        except Exception as error:
            evidence = {'tmdb_id':identity,'error_type':type(error).__name__}
        evidence['seconds'] = round(time.monotonic()-started,2)
        results.append(evidence)
        print(json.dumps(evidence), flush=True)
    with repo.store.connection() as db:
        tracked = db.execute('SELECT COUNT(*) FROM series').fetchone()[0]
    assert tracked == 0
    report = {'read_only_provider_calls':True,'real_torrent_submissions':0,'tracked_series_after_search':tracked,'results':results}
    Path('docs/verification/tv-parity/providers-read-only.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
