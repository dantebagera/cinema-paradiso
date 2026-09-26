from copy import deepcopy
from services.quality_catalog import SOURCES, RESOLUTIONS, ELIGIBILITY, FOLLOW_COMPATIBILITY_SOURCES


def default_profile(*, compatibility=False, quality='1080p'):
    quality = '2160p' if quality == '4K' else quality
    states = {}
    for source, facts in SOURCES.items():
        for resolution in RESOLUTIONS:
            state = 'allowed'
            if facts['family'] in {'cinema', 'screener'}:
                state = 'blocked'
            elif source == 'unknown' or resolution == 'unknown':
                state = 'manual_only'
            elif compatibility and (source not in FOLLOW_COMPATIBILITY_SOURCES or resolution not in {'1080p', '2160p'}):
                state = 'manual_only'
            elif resolution == quality:
                state = 'preferred'
            states[f'{source}:{resolution}'] = state
    return {'id': 'cp-compatibility' if compatibility else 'safe-hd', 'name': 'CP Compatibility' if compatibility else 'Safe HD',
            'states': states, 'cutoff': quality, 'automatic_upgrades': False, 'minimum_bytes': 0, 'maximum_bytes': 0,
            'minimum_seeders': 0, 'minimum_score': 0, 'delay_seconds': 0, 'minimum_age_seconds': 0,
            'import_mode': 'move' if compatibility else 'hardlink_copy',
            'seeding_mode': 'none' if compatibility else 'forever', 'seed_ratio': 1.0, 'seed_time_seconds': 0,
            'retry_max_attempts': 3, 'retry_backoff_seconds': 300, 'formats': [], 'version': 1}


def validate_profile(profile):
    value = deepcopy(profile)
    value.setdefault('seeding_mode', 'none' if value.get('import_mode') == 'move' else 'forever')
    value.setdefault('seed_ratio', 1.0)
    value.setdefault('seed_time_seconds', 0)
    value.setdefault('retry_max_attempts', 3)
    value.setdefault('retry_backoff_seconds', 300)
    if not str(value.get('id') or '').strip() or len(value['id']) > 80 or not str(value.get('name') or '').strip():
        raise ValueError('Profile ID and name are required')
    keys = {f'{source}:{resolution}' for source in SOURCES for resolution in RESOLUTIONS}
    if set(value.get('states', {})) != keys or any(state not in ELIGIBILITY for state in value['states'].values()):
        raise ValueError('Every canonical source/resolution needs a valid eligibility state')
    if value.get('cutoff') not in RESOLUTIONS or not isinstance(value.get('automatic_upgrades'), bool):
        raise ValueError('Invalid cutoff or upgrade policy')
    for key in ('minimum_bytes', 'maximum_bytes', 'minimum_seeders', 'minimum_score', 'delay_seconds', 'minimum_age_seconds'):
        if not isinstance(value.get(key), int) or value[key] < 0:
            raise ValueError(f'{key} must be a nonnegative integer')
    if value['maximum_bytes'] and value['minimum_bytes'] > value['maximum_bytes']:
        raise ValueError('Minimum size exceeds maximum size')
    if value.get('import_mode') not in {'move', 'hardlink_copy', 'copy'}:
        raise ValueError('Invalid import mode')
    if value.get('seeding_mode') not in {'none', 'forever', 'ratio', 'time', 'ratio_or_time', 'ratio_and_time'}:
        raise ValueError('Invalid seeding mode')
    if not isinstance(value.get('seed_ratio'), (int, float)) or value['seed_ratio'] < 0 or value['seed_ratio'] > 100:
        raise ValueError('Seed ratio must be between 0 and 100')
    for key, maximum in (('seed_time_seconds', 31536000), ('retry_max_attempts', 20), ('retry_backoff_seconds', 604800)):
        if not isinstance(value.get(key), int) or value[key] < 0 or value[key] > maximum:
            raise ValueError(f'Invalid {key}')
    formats = value.get('formats', [])
    if not isinstance(formats, list) or len(formats) > 30:
        raise ValueError('At most 30 format rules are allowed')
    for rule in formats:
        if rule.get('field') not in {'source', 'resolution', 'codec', 'hdr', 'group', 'edition', 'title', 'language', 'audio'} or rule.get('op') not in {'equals', 'contains'} or not isinstance(rule.get('score'), int) or abs(rule['score']) > 10000 or len(str(rule.get('value', ''))) > 120:
            raise ValueError('Invalid declarative format rule')
    return value
