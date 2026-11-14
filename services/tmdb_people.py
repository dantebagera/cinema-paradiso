def normalize_tmdb_person_details(data):
    return {
        'id': str(data.get('id', '') or ''),
        'name': data.get('name', '') or '',
        'profile_url': f"https://image.tmdb.org/t/p/w342{data['profile_path']}" if data.get('profile_path') else '',
        'biography': data.get('biography', '') or '',
        'birthday': data.get('birthday', '') or '',
        'deathday': data.get('deathday', '') or '',
        'place_of_birth': data.get('place_of_birth', '') or '',
        'known_for_department': data.get('known_for_department', '') or '',
        'homepage': data.get('homepage', '') or '',
    }

