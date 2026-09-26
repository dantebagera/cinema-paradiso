"""Native-TV HTTP composition; domain decisions stay in TV services."""
import json
from flask import jsonify, request

from services.player_catalog import PlayerMediaError
from services.qbittorrent import QBittorrentError
from services.movie_relationships import MovieRelationships


def register_tv_routes(app, services, enabled, player_manager, acquisition=None, monitoring=None, config=None):
    tv_relationships = MovieRelationships()
    @app.get('/api/tv/capabilities')
    def tv_capabilities():
        return jsonify({'enabled': bool(enabled())})

    @app.before_request
    def tv_capability_gate():
        if request.path.startswith('/api/tv/') and request.path not in {'/api/tv/capabilities', '/api/tv/config'} and not enabled():
            return jsonify({'error': 'Native TV is not enabled'}), 404

    def action(callback):
        try:
            return jsonify(callback())
        except LookupError as error:
            return jsonify({'error': str(error)}), 404
        except (ValueError, TypeError, KeyError, PlayerMediaError) as error:
            return jsonify({'error': str(error)}), 400

        except (QBittorrentError, OSError, TimeoutError, RuntimeError):
            return jsonify({'error': 'The provider could not complete this request. Check its configuration and retry.'}), 503

    @app.get('/api/tv/config')
    @app.post('/api/tv/config')
    def tv_config():
        if not config:
            return jsonify({'error': 'TV configuration is unavailable'}), 404
        return action(lambda: config(request.get_json(silent=True) or {}) if request.method == 'POST' else config())

    @app.get('/api/tv/series')
    def tv_series():
        def read():
            arguments = {key: request.args[key] for key in ('query', 'page', 'page_size', 'status', 'sort', 'availability', 'genre', 'year', 'minimum_rating', 'progress', 'quality', 'language', 'monitoring') if key in request.args}
            arguments['monitored_ids'] = monitoring().monitored_tmdb_ids() if monitoring else set()
            return services()['read'].library(**arguments)
        return action(read)

    @app.get('/api/tv/files')
    def tv_files():
        return action(lambda: services()['read'].files(
            query=request.args.get('query', ''), page=request.args.get('page', 1),
            page_size=request.args.get('page_size', 50)
        ))

    @app.post('/api/tv/catalog/search')
    def tv_catalog_search():
        def search():
            data = request.get_json(silent=True) or {}
            scope = data.get('scope')
            owner = services()['search']
            if acquisition:
                owner.profile = lambda: acquisition().acquisition.profile('safe-hd')
            if scope == 'library':
                extras = dict(data.get('extras') or {})
                extras['monitored_ids'] = monitoring().monitored_tmdb_ids() if monitoring else set()
                return owner.library(data['query'], data.get('page', 1), data.get('page_size', 24), extras)
            if scope != 'discover':
                raise ValueError('Search scope must be library or discover')
            result = owner.discover(data['query'], data.get('page', 1), data.get('page_size', 20))
            monitored = monitoring().monitored_tmdb_ids() if monitoring else set()
            for item in result['items']:
                item['monitored'] = item['tmdb_id'] in monitored
            return result
        return action(search)

    @app.get('/api/tv/catalog/options')
    def tv_catalog_options():
        return action(lambda: services()['search'].options(request.args.get('scope', 'library')))

    @app.get('/api/tv/catalog/identities')
    def tv_catalog_identities():
        return action(lambda: {'items': services()['search'].identities(request.args.get('scope', 'library'), request.args.get('type', ''), request.args.get('query', ''))})

    @app.get('/api/tv/related')
    def tv_related():
        def listing():
            metadata = services()['metadata']
            related = tv_relationships.listing(
                request.args.get('tmdb_id', '').strip(),
                request.args.get('source', 'recommendations'),
                int(request.args.get('page', 1)),
                lambda identity, source, page: metadata.request(
                    f'/tv/{int(identity)}/{source}', page=page, _timeout=8, _attempts=1
                ),
                lambda row: {
                    **metadata.normalize(row),
                    'year': str(row.get('first_air_date') or '')[:4],
                    'tmdb_rating': row.get('vote_average') or 0,
                },
                page_size=int(request.args.get('page_size', 20)),
            )
            local = {str(row['tmdb_id']): row for row in services()['search'].local_rows()}
            related['results'] = [
                {**row, 'id': local.get(str(row['tmdb_id']), {}).get('id'),
                 'available_count': local.get(str(row['tmdb_id']), {}).get('available_count', 0),
                 'media_type': 'tv'}
                for row in related['results']
            ]
            return related
        return action(listing)

    @app.post('/api/tv/catalog/enrich')
    def tv_enrich_cards():
        def read():
            from concurrent.futures import ThreadPoolExecutor
            ids = list(dict.fromkeys(int(v) for v in (request.get_json(silent=True) or {}).get('ids', [])))
            if len(ids) > 20: raise ValueError('At most 20 visible cards can be enriched')
            metadata = services()['metadata']
            def enrich(identity):
                try:
                    return metadata.display(metadata.preview(identity, fast=True))
                except (OSError, ValueError, KeyError):
                    return {'tmdb_id': identity, 'metadata_notice': 'Details unavailable'}
            with ThreadPoolExecutor(max_workers=4) as pool:
                return {'items': list(pool.map(enrich, ids))}
        return action(read)

    @app.get('/api/tv/preview/<int:tmdb_id>')
    def tv_preview(tmdb_id):
        return action(lambda: services()['metadata'].preview(tmdb_id))

    @app.get('/api/tv/translation/<int:tmdb_id>')
    def tv_translation(tmdb_id):
        return action(lambda: services()['metadata'].translation(tmdb_id, request.args.get('language', 'ar-SA')))

    @app.get('/api/tv/preview/<int:tmdb_id>/seasons/<int:season>')
    def tv_preview_season(tmdb_id, season):
        return action(lambda: services()['metadata'].preview_season(tmdb_id, season))

    @app.post('/api/tv/series/<int:series_id>/watchlist')
    def tv_watchlist(series_id):
        def update():
            repository = services()['repository']
            repository.series(series_id)
            watched = (request.get_json(silent=True) or {}).get('watchlisted')
            if not isinstance(watched, bool):
                raise ValueError('Watchlisted must be true or false')
            with repository.store.transaction() as db:
                db.execute('INSERT INTO series_curation VALUES(?,?) ON CONFLICT(series_id) DO UPDATE SET watchlisted=excluded.watchlisted', (series_id, int(watched)))
            return {'watchlisted': watched}
        return action(update)

    @app.get('/api/tv/series/<int:series_id>')
    def tv_series_detail(series_id):
        def read():
            owners = services()
            row = owners['read'].detail(series_id)
            # Older catalogs retain local identities, files and progress. Fetch newly
            # supported display fields without rewriting the catalog on a read.
            metadata = owners.get('metadata')
            if ('trailer_url' not in row or not row.get('credits_loaded')) and metadata and metadata.key_provider():
                try:
                    online = metadata.preview(row['tmdb_id'], fast=True)
                    for key in ('trailer_url', 'original_language', 'original_language_name', 'origin_country', 'runtime', 'cast'):
                        row[key] = online.get(key)
                except (URLError, TimeoutError, ValueError, KeyError):
                    row['metadata_notice'] = 'Some online details are unavailable. Refresh metadata to retry.'
            return row
        return action(read)

    @app.get('/api/tv/series/<int:series_id>/selection')
    def tv_selection(series_id):
        return action(lambda: {'items': season_rows(series_id, int(request.args['season']))})

    def season_rows(series_id, season):
        owners = services()
        row = owners['repository'].series(series_id)
        episodes = owners['repository'].episodes(series_id, season)
        if not episodes and any(s['season_number'] == season for s in row.get('seasons', [])):
            # A download saves only its season. Other seasons remain provider
            # previews until a download or explicit metadata refresh tracks them.
            episodes = [{**e, 'preview': True} for e in owners['metadata'].preview_season(row['tmdb_id'], season)['items']]
        return episodes

    @app.get('/api/tv/series/<int:series_id>/seasons/<int:season>')
    def tv_season(series_id, season):
        def read():
            page = max(1, int(request.args.get('page', 1)))
            episodes = season_rows(series_id, season)
            total = len(episodes)
            rows = episodes[(page-1)*100:page*100]
            return {'items': rows, 'total': total, 'page': page, 'total_pages': max(1, (total+99)//100)}
        return action(read)

    @app.get('/api/tv/discover')
    def tv_discover():
        def discover():
            result = services()['metadata'].discover(request.args.get('query', ''), request.args.get('page', 1))
            monitored = monitoring().monitored_tmdb_ids() if monitoring else set()
            for item in result['items']:
                item['monitored'] = item['tmdb_id'] in monitored
            return result
        return action(discover)

    @app.post('/api/tv/series')
    def tv_add_series():
        return action(lambda: {'id': services()['metadata'].refresh((request.get_json() or {})['tmdb_id'])})

    @app.post('/api/tv/series/<int:series_id>/refresh')
    def tv_refresh(series_id):
        return action(lambda: {'id': services()['metadata'].refresh(services()['repository'].series(series_id)['tmdb_id'])})

    @app.post('/api/tv/series/<int:series_id>/scan')
    def tv_scan(series_id):
        data = request.get_json(silent=True) or {}
        return action(lambda: {'items': services()['ingestion'].scan(series_id, data['folder'])})

    @app.post('/api/tv/series/<int:series_id>/plex-scan')
    def tv_plex_scan(series_id):
        def scan():
            owners = services()
            series = owners['repository'].series(series_id)
            entries = owners['plex'].entries(series['tmdb_id'])
            return {'items': owners['ingestion'].ingest_plex(series_id, entries), 'discovered': len(entries)}
        return action(scan)

    @app.get('/api/tv/continue-watching')
    def tv_continue():
        return action(lambda: {'items': services()['read'].continue_watching()})

    @app.get('/api/tv/audit')
    def tv_audit():
        def read():
            result = {'catalog': services()['repository'].store.audit()}
            if acquisition:
                owner = acquisition()
                result['acquisition'] = owner.acquisition.audit(owner.manager().jobs)
            return result
        return action(read)

    @app.post('/api/tv/episodes/<int:episode_id>/play')
    def tv_play(episode_id):
        data = request.get_json(silent=True) or {}
        return action(lambda: player_manager.play(services()['playback'].target(episode_id, data.get('file_id')), restart=data.get('restart') is True))

    @app.post('/api/tv/episodes/<int:episode_id>/progress')
    def tv_progress(episode_id):
        data = request.get_json(silent=True) or {}
        return action(lambda: services()['repository'].save_progress(episode_id, data.get('file_id'), **{key: data[key] for key in ('position_ms', 'duration_ms', 'completed', 'restart', 'expected_revision') if key in data}))

    @app.get('/api/tv/review')
    def tv_review():
        def read():
            with services()['repository'].store.connection() as db:
                rows = [dict(row) for row in db.execute("SELECT * FROM ingestion_candidates WHERE state='needs_review' ORDER BY id LIMIT 100")]
            for row in rows:
                row['payload'] = json.loads(row['payload'])
            return {'items': rows}
        return action(read)

    @app.post('/api/tv/review/<int:review_id>/apply')
    def tv_apply_review(review_id):
        return action(lambda: services()['ingestion'].apply_review(review_id, request.get_json(silent=True) or {}))

    @app.post('/api/tv/search')
    def tv_search():
        data = request.get_json(silent=True) or {}
        return action(lambda: acquisition().search(**{key: data[key] for key in ('series_id', 'tmdb_id', 'season', 'episode', 'episode_numbers', 'missing_only', 'upgrade', 'profile_id') if key in data}))

    @app.post('/api/tv/releases/prepare')
    def tv_prepare_release():
        data = request.get_json(silent=True) or {}
        return action(lambda: acquisition().prepare(data['decision_token'], confirm_identity=data.get('confirm_identity') is True, allow_extras=data.get('allow_extras') is True))

    @app.post('/api/tv/acquisitions/batch')
    def tv_submit_batch():
        data = request.get_json(silent=True) or {}
        return action(lambda: acquisition().submit_batch(data.get('decision_tokens'), data.get('request_key'), allow_partial=data.get('allow_partial') is True, allow_extras=data.get('allow_extras') is True))

    @app.post('/api/tv/acquisitions')
    def tv_submit():
        data = request.get_json(silent=True) or {}
        return action(lambda: acquisition().submit(data['decision_token'], data.get('request_key')))

    @app.get('/api/tv/acquisitions')
    @app.get('/api/tv/acquisitions/<intent_id>')
    def tv_acquisitions(intent_id=None):
        def read():
            owner = acquisition()
            with owner.acquisition.connection() as db:
                rows = [dict(row) for row in db.execute('SELECT * FROM intents WHERE (? IS NULL OR id=?) ORDER BY created_at DESC LIMIT 100', (intent_id, intent_id))]
                for row in rows:
                    row['history'] = [dict(event) for event in db.execute('SELECT event,payload,created_at FROM events WHERE intent_id=? ORDER BY id DESC LIMIT 30', (row['id'],))]
            jobs = owner.manager().jobs.all()
            return {'items': [{**row, 'job': jobs.get(row['info_hash'])} for row in rows]}
        return action(read)

    @app.get('/api/tv/series/<int:series_id>/monitor')
    @app.post('/api/tv/series/<int:series_id>/monitor')
    def tv_monitor(series_id):
        if request.method == 'GET':
            return action(lambda: monitoring().describe(series_id))
        data = request.get_json(silent=True) or {}
        return action(lambda: monitoring().configure(series_id, **{key: data[key] for key in ('mode', 'profile_id', 'season', 'episode') if key in data}))

    @app.post('/api/tv/monitoring/run')
    def tv_monitor_once():
        data = request.get_json(silent=True) or {}
        return action(lambda: {'items': monitoring().run_once(limit=data.get('limit', 10), submit=data.get('submit') is True)})

    @app.post('/api/tv/episodes/<int:episode_id>/hide-progress')
    def tv_hide_progress(episode_id):
        def hide():
            with services()['repository'].store.transaction() as db:
                db.execute('UPDATE playback_progress SET hidden=1 WHERE episode_id=?', (episode_id,))
            return {'ok': True}
        return action(hide)

    @app.post('/api/tv/series/<int:series_id>/hide-progress')
    def tv_hide_series_progress(series_id):
        def hide():
            services()['repository'].series(series_id)
            with services()['repository'].store.transaction() as db:
                db.execute('UPDATE playback_progress SET hidden=1 WHERE episode_id IN (SELECT id FROM episodes WHERE series_id=?)', (series_id,))
            return {'ok': True}
        return action(hide)

    @app.post('/api/tv/acquisitions/<intent_id>/action')
    def tv_acquisition_action(intent_id):
        return action(lambda: acquisition().manage(intent_id, (request.get_json(silent=True) or {})['action']))
