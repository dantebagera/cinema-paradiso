from flask import jsonify, request


def register_curation_routes(app, store_provider, owned_checker):
    def user_lists():
        store = store_provider()
        if request.method == 'GET':
            movie = {
                'tmdb_id': request.args.get('tmdb_id', ''),
                'title': request.args.get('title', ''),
                'year': request.args.get('year', ''),
                'path': request.args.get('path', ''),
            }
            result = {'lists': store.list_all()}
            if any(movie.values()):
                result['movie_lists'] = store.lists_for_movie(movie)
            return jsonify(result)
        body = request.get_json(force=True, silent=True) or {}
        try:
            return jsonify(store.create_list(body.get('name', '')))
        except ValueError as error:
            return jsonify({'error': str(error)}), 400
        except Exception as error:
            return jsonify({'error': str(error)}), 500

    def user_list_detail(list_id):
        store = store_provider()
        try:
            if request.method == 'DELETE':
                return jsonify({'success': True, 'deleted': store.delete_list(list_id)})
            body = request.get_json(force=True, silent=True) or {}
            return jsonify(store.rename_list(list_id, body.get('name', '')))
        except ValueError as error:
            return jsonify({'error': str(error)}), 400
        except KeyError:
            return jsonify({'error': 'List not found'}), 404
        except Exception as error:
            return jsonify({'error': str(error)}), 500

    def user_list_movies(list_id):
        body = request.get_json(force=True, silent=True) or {}
        movie = body.get('movie') or body
        try:
            if request.method == 'POST':
                if list_id == 'watched' and not owned_checker(movie):
                    return jsonify({'error': 'Watched is available only for owned Library movies'}), 400
                return jsonify(store_provider().add_movie_to_list(list_id, movie))
            return jsonify(store_provider().remove_movie_from_list(list_id, movie))
        except KeyError:
            return jsonify({'error': 'List not found'}), 404
        except Exception as error:
            return jsonify({'error': str(error)}), 500

    def user_list_movies_bulk(list_id):
        body = request.get_json(force=True, silent=True) or {}
        movies = body.get('movies') or []
        if not isinstance(movies, list) or not movies:
            return jsonify({'error': 'At least one movie is required'}), 400
        try:
            if list_id == 'watched':
                unowned = [movie for movie in movies if not owned_checker(movie)]
                if unowned:
                    return jsonify({'error': 'Watched is available only for owned Library movies'}), 400
            return jsonify(store_provider().add_movies_to_list(list_id, movies))
        except KeyError:
            return jsonify({'error': 'List not found'}), 404
        except Exception as error:
            return jsonify({'error': str(error)}), 500

    def user_system_list_state():
        movie = {
            'tmdb_id': request.args.get('tmdb_id', ''),
            'imdb_id': request.args.get('imdb_id', ''),
            'title': request.args.get('title', ''),
            'year': request.args.get('year', ''),
            'path': request.args.get('path', ''),
        }
        return jsonify(store_provider().system_states_for_movie(movie))

    def user_system_list_toggle(system_type):
        if system_type not in {'watched', 'watchlist'}:
            return jsonify({'error': 'System list not found'}), 404
        body = request.get_json(force=True, silent=True) or {}
        movie = body.get('movie') or {}
        if not any(movie.get(key) for key in ('tmdb_id', 'imdb_id', 'title', 'path')):
            return jsonify({'error': 'Movie identity is required'}), 400
        if system_type == 'watched' and bool(body.get('active')) and not owned_checker(movie):
            return jsonify({'error': 'Watched is available only for owned Library movies'}), 400
        try:
            return jsonify(store_provider().set_system_list_state(system_type, movie, bool(body.get('active'))))
        except KeyError:
            return jsonify({'error': 'System list not found'}), 404
        except Exception as error:
            return jsonify({'error': str(error)}), 500

    app.add_url_rule('/api/user/lists', 'user_lists', user_lists, methods=['GET', 'POST'])
    app.add_url_rule('/api/user/lists/<list_id>', 'user_list_detail', user_list_detail, methods=['PATCH', 'DELETE'])
    app.add_url_rule(
        '/api/user/lists/<list_id>/movies',
        'user_list_movies',
        user_list_movies,
        methods=['POST', 'DELETE'],
    )
    app.add_url_rule(
        '/api/user/lists/<list_id>/movies/bulk',
        'user_list_movies_bulk',
        user_list_movies_bulk,
        methods=['POST'],
    )
    app.add_url_rule('/api/user/system-lists/state', 'user_system_list_state', user_system_list_state)
    app.add_url_rule(
        '/api/user/system-lists/<system_type>/toggle',
        'user_system_list_toggle',
        user_system_list_toggle,
        methods=['POST'],
    )
