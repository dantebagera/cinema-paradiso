from flask import jsonify, request
from services.quality_catalog import SOURCE_CATALOG, RESOLUTIONS, ELIGIBILITY


def register_acquisition_routes(app, repository):
    @app.get('/api/acquisition/profiles')
    def acquisition_profiles():
        store = repository()
        return jsonify({'profiles': store.profiles(), 'movie_default': store.profile()['id'],
                        'sources': [{key: value for key, value in row.items() if key in {'id','label','family'}} for row in SOURCE_CATALOG],
                        'resolutions': RESOLUTIONS, 'states': ELIGIBILITY})

    @app.post('/api/acquisition/profiles')
    def acquisition_save_profile():
        try:
            data = request.get_json(silent=True) or {}
            return jsonify(repository().save_profile(data['profile'], make_default=data.get('make_default') is True))
        except (ValueError, KeyError, TypeError) as error:
            return jsonify({'error': str(error)}), 400

    @app.delete('/api/acquisition/profiles/<profile_id>')
    def acquisition_delete_profile(profile_id):
        try:
            repository().delete_profile(profile_id, (request.get_json(silent=True) or {}).get('replacement'))
            return jsonify({'ok': True})
        except ValueError as error:
            return jsonify({'error': str(error)}), 409
