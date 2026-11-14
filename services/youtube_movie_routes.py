"""Local JSON admission and composition for the Movie YouTube source."""
from flask import jsonify
from services.ai_routes import local_json
from services.ai_provider import AIProviderError
from services.youtube_playlist import YouTubePlaylistError


def register_youtube_movie_routes(app, search_factory, provider, jobs_factory, check_permission):
    @app.post('/api/youtube/movie-search/status')
    @local_json
    def youtube_movie_status(data):
        if set(data) != {'search_id'} or not isinstance(data['search_id'], str):
            raise AIProviderError('invalid_search_request')
        try:
            return jsonify(search_factory().snapshot(data['search_id']))
        except YouTubePlaylistError as error:
            return jsonify(error={'code': 'youtube_search_expired', 'message': str(error)}), 422

    @app.post('/api/youtube/movie-search')
    @local_json
    def youtube_movie_search(data):
        if set(data) - {'tmdb_id', 'search_id'} or any(not isinstance(v, (str, int)) or isinstance(v, bool) for v in data.values()):
            raise AIProviderError('invalid_search_request')
        try:
            return jsonify(search_factory().search(**data))
        except YouTubePlaylistError as error:
            return jsonify(error={'code': 'youtube_search_failed', 'message': str(error)}), 422

    @app.post('/api/ai/youtube/movie-search')
    @local_json
    def youtube_movie_assist(data):
        if (set(data) != {'search_id', 'request_key'} or
                not isinstance(data['search_id'], str) or not 1 <= len(data['search_id']) <= 64):
            raise AIProviderError('invalid_search_request')
        selection = provider.snapshot('F6', domain_id=data['search_id'])
        if selection.provider != 'chatgpt':
            raise AIProviderError('select_chatgpt_in_settings', 409)
        check_permission(selection)
        try:
            search_factory().snapshot(data['search_id'])
        except YouTubePlaylistError as error:
            return jsonify(error={'code': 'youtube_search_expired', 'message': str(error)}), 422
        jobs = jobs_factory()
        operation = jobs.store.create('F6', selection, {'search_id': data['search_id']}, data['request_key'])
        jobs.start(operation['id'])
        return jsonify(operation), 202
