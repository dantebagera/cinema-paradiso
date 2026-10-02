"""Read-only local awards endpoints. Projection is injected, never enrichment."""
import hashlib
import re
import sqlite3
from flask import jsonify, request
from services.movie_awards_store import (AwardsError, AwardsUnavailable, GenerationConflict,
                                         ORGANIZATIONS, empty_snapshot)


def register_movie_awards_routes(app, get_store, project_movie, get_diagnostic=lambda: ''):
    def unavailable(reason='awards_unavailable'):
        return jsonify(error=reason, retryable=True), 503

    def integer(name, default=None, minimum=1, maximum=None):
        raw = request.args.get(name)
        if raw is None:
            if default is not None:
                return default
            raise AwardsError('missing_' + name)
        if len(request.args.getlist(name)) != 1 or not re.fullmatch(r'\d{1,12}', raw):
            raise AwardsError('invalid_' + name)
        value = int(raw)
        if value < minimum or (maximum is not None and value > maximum):
            raise AwardsError('invalid_' + name)
        return value

    @app.get('/api/movie-awards/snapshot')
    def movie_awards_snapshot():
        try:
            store = get_store(create=False)
            body = store.read_snapshot() if store else empty_snapshot()
            owner = hashlib.sha256(str(store.path.resolve()).casefold().encode('utf-8')).hexdigest()[:24] if store else 'unavailable'
            body['snapshot_owner'] = owner
            tag = f"movie-awards-v{body['schema_version']}-{owner}-{body['awards_generation']}"
            response = app.response_class(status=304) if request.if_none_match.contains(tag) else jsonify(body)
            response.set_etag(tag)
            response.headers['Cache-Control'] = 'private, no-cache'
            return response
        except (AwardsUnavailable, sqlite3.Error):
            return unavailable()

    @app.get('/api/movie-awards/status')
    def movie_awards_status():
        try:
            store = get_store(create=False)
            body = store.read_status() if store else {**empty_snapshot(), 'refresh': [], 'diagnostic': 'awards_store_missing'}
            diagnostic = get_diagnostic()
            if diagnostic: body['diagnostic'] = str(diagnostic)[:256]
            return jsonify(body)
        except (AwardsUnavailable, sqlite3.Error):
            return unavailable()

    @app.get('/api/movie-awards/person-films')
    def movie_awards_person_films():
        try:
            person = integer('person_id')
            role, award = request.args.get('role'), request.args.get('award')
            if role not in ('actor', 'director') or award not in ORGANIZATIONS:
                raise AwardsError('invalid_award_or_role')
            page, page_size = integer('page', 1), integer('page_size', 20, maximum=100)
            generation = integer('generation', minimum=0) if 'generation' in request.args else None
            store = get_store(create=False)
            if store is None:
                return unavailable('historical_awards_coverage_pending')
            body = store.person_films(person, role, award, page, page_size, generation)
            results = []
            for movie in body['results']:
                projection = project_movie(dict(movie))
                if not isinstance(projection, dict) or any(str(projection[key]) != str(movie['id']) for key in ('id', 'tmdb_id') if projection.get(key)):
                    return unavailable('winning_film_projection_failed')
                results.append({**projection, 'id': movie['id'], 'tmdb_id': str(movie['id']), 'imdb_id': movie['imdb_id']})
            return jsonify({**body, 'results': results})
        except GenerationConflict as error:
            return jsonify(error='awards_generation_changed', awards_generation=error.generation), 409
        except AwardsError as error:
            return jsonify(error=str(error)), 400
        except AwardsUnavailable as error:
            return unavailable(str(error))
        except Exception:
            return unavailable('winning_film_projection_failed')
