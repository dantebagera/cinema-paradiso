"""Optional display data only: these routes never wait for a provider."""
from flask import jsonify, request
from .movie_ratings import movie_identity


def register_movie_ratings_routes(app, get_service):
    def handle(resolve=False):
        if request.content_length and request.content_length > 32768:
            return jsonify({'error': 'invalid_ratings_request'}), 400
        body = request.get_json(silent=True)
        try:
            raw = body.get('items') if isinstance(body, dict) else None
            if not isinstance(raw, list) or not 1 <= len(raw) <= 40:
                raise ValueError()
            items = [movie_identity(item) for item in raw]
        except (TypeError, ValueError):
            return jsonify({'error': 'invalid_ratings_request'}), 400
        service = get_service()
        result = service.request(items) if resolve else service.read(items)
        response = jsonify(result)
        response.headers['Cache-Control'] = 'private, no-store'
        return response, (202 if resolve and any(v['state'] == 'pending' for v in result['items'].values()) else 200)

    app.add_url_rule('/api/movie-ratings/read', 'movie_ratings_read', lambda: handle(), methods=['POST'])
    app.add_url_rule('/api/movie-ratings/resolve', 'movie_ratings_resolve', lambda: handle(True), methods=['POST'])
