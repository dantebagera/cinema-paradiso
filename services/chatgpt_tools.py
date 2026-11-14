"""Typed read/preparation registry. There is deliberately no model execution tool."""
from dataclasses import dataclass, field
import json
import re

from services.advanced_search import query_json_schema
from services.chatgpt_skills import object_schema, array_schema, validate_schema


class ToolError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ToolResult:
    model: dict
    ui: dict | None = None


@dataclass
class ToolContext:
    selection: object
    job_id: str
    session_id: str
    result_sets: dict = field(default_factory=dict)
    prepared: list = field(default_factory=list)
    identities: dict = field(default_factory=lambda: {'person': [], 'company': []})
    private: dict = field(default_factory=dict)


def text(maximum=240):
    return {'type': 'string', 'maxLength': maximum}


def nullable(schema):
    return {'anyOf': [schema, {'type': 'null'}]}


def enum(*values):
    return {'type': 'string', 'enum': list(values)}


ID = {'type': 'integer', 'minimum': 1}
PAGE = {'type': 'integer', 'minimum': 1}
COUNT = nullable({'type': 'string', 'pattern': '^[1-9][0-9]*$'})
BOOL = {'type': 'boolean'}
STR_ID = {'type': 'string', 'minLength': 1, 'maxLength': 160}
DEPENDENCIES = array_schema(STR_ID)
MOVIE_REF = object_schema({'domain': enum('movie'), 'key': STR_ID})
TV_REF = object_schema({'domain': enum('tv'), 'series_id': ID, 'episode_id': nullable(ID)})
IPTV_REF = object_schema({'domain': enum('iptv'), 'provider_id': STR_ID,
                        'kind': enum('live', 'movie', 'series'), 'item_id': STR_ID})
MEDIA_REF = {'anyOf': [MOVIE_REF, TV_REF, IPTV_REF]}
IPTV_FILTERS = object_schema({'view': enum('provider', 'cp'), 'q': nullable(text()), 'playlist_id': nullable(STR_ID),
    'list_id': nullable(STR_ID), 'category': nullable(enum('film', 'sports', 'plays', 'music', 'misc')),
    'metadata_status': nullable(text()), 'year_from': nullable({'type': 'integer', 'minimum': 1870}),
    'year_to': nullable({'type': 'integer', 'minimum': 1870}), 'genre_id': nullable(ID),
    'language': nullable(text()), 'country': nullable(text()), 'min_rating': nullable({'type': 'number', 'minimum': 0, 'maximum': 10}),
    'quality': nullable(text()), 'dubbed': nullable(BOOL), 'subtitled': nullable(BOOL), 'watched': nullable(enum('all', 'watched', 'unwatched')),
    'sort': nullable(enum('recent', 'title', 'rating', 'year-newest', 'year-oldest'))})
IPTV_SELECTION = object_schema({'mode': enum('explicit', 'all_filtered'),
    'keys': array_schema(STR_ID), 'filters': IPTV_FILTERS})


def _definition(namespace, name, parameters, *, kind='read', domain=None, description=None):
    return {'namespace': namespace, 'name': name, 'parameters': object_schema(parameters),
            'kind': kind, 'domain': domain, 'description': description or name.replace('_', ' ')}


DEFINITIONS = [
    _definition('cp_movie', 'search_movies', {'query': query_json_schema('discover'), 'count': COUNT,
        'scope': object_schema({'include_shorts': BOOL, 'include_upcoming': BOOL, 'include_documentaries': BOOL})}, domain='movie'),
    _definition('cp_movie', 'suggest_movies', {'prompt': text(12000), 'count': COUNT}, domain='movie'),
    _definition('cp_movie', 'resolve_people', {'text': text(), 'role': enum('actor', 'director', 'writer'), 'page': PAGE}, domain='movie'),
    _definition('cp_movie', 'resolve_companies', {'text': text(), 'page': PAGE}, domain='movie'),
    _definition('cp_movie', 'movie_details', {'ids': array_schema(ID, maximum=20)}, domain='movie'),
    _definition('cp_movie', 'collection_details', {'id': ID}, domain='movie'),
    _definition('cp_movie', 'movie_relationships', {'id': ID}, domain='movie'),
    _definition('cp_movie', 'list_movie_lists', {'page': PAGE}, domain='movie'),
    _definition('cp_movie', 'prepare_movie_list', {'action': enum('create', 'rename', 'delete', 'add', 'remove'),
        'list_id': nullable(STR_ID), 'name': nullable(text()), 'result_set': nullable(STR_ID),
        'depends_on': DEPENDENCIES}, kind='prepare', domain='movie'),
    _definition('cp_movie', 'prepare_movie_state', {'kind': enum('watched', 'watchlist', 'followed'),
        'active': BOOL, 'result_set': STR_ID, 'depends_on': DEPENDENCIES}, kind='prepare', domain='movie'),
    _definition('cp_movie', 'prepare_collection_override', {'collection_id': ID,
        'parts': array_schema(MOVIE_REF), 'depends_on': DEPENDENCIES}, kind='prepare', domain='movie'),
    _definition('cp_movie', 'prepare_movie_download', {'result_set': STR_ID, 'quality': text(30),
        'profile_id': nullable(STR_ID), 'depends_on': DEPENDENCIES}, kind='prepare', domain='movie'),
    _definition('cp_movie', 'prepare_movie_delete', {'result_set': STR_ID, 'whole_movie_folders': BOOL,
        'depends_on': DEPENDENCIES}, kind='prepare', domain='movie'),
    _definition('cp_movie', 'download_status', {'ids': array_schema(STR_ID, maximum=100)}, domain='movie'),
    _definition('cp_metadata', 'maintenance_status', {'kind': enum('duplicates', 'storage', 'identity', 'upgrade'),
        'query': text(), 'page': PAGE}, domain='movie'),
    _definition('cp_metadata', 'prepare_movie_match', {'file_ids': array_schema(STR_ID),
        'database': enum('tmdb', 'plex'), 'method': enum('classic', 'ai'), 'depends_on': DEPENDENCIES}, kind='prepare', domain='movie'),
    _definition('cp_metadata', 'prepare_rename', {'proposal_ids': array_schema(STR_ID), 'depends_on': DEPENDENCIES}, kind='prepare', domain='movie'),
    _definition('cp_metadata', 'metadata_job_status', {'id': STR_ID}, domain='movie'),
    _definition('cp_metadata', 'prepare_metadata_apply', {'job_id': STR_ID, 'proposal_ids': array_schema(STR_ID),
        'depends_on': DEPENDENCIES}, kind='prepare', domain='movie'),
    _definition('cp_tv', 'search_tv', {'query': {'anyOf': [query_json_schema('discover', media_type='tv'),
        query_json_schema('library', media_type='tv')]}, 'page': PAGE}, domain='tv'),
    _definition('cp_tv', 'tv_coverage', {'series': TV_REF, 'scope': enum('series', 'season', 'episode'),
        'season': nullable({'type': 'integer', 'minimum': 0})}, domain='tv'),
    _definition('cp_tv', 'tv_lists', {'page': PAGE}, domain='tv'),
    _definition('cp_tv', 'prepare_tv_list', {'action': enum('create', 'rename', 'delete', 'add', 'remove'),
        'list_id': nullable(STR_ID), 'series': array_schema(TV_REF), 'name': nullable(text()), 'depends_on': DEPENDENCIES}, kind='prepare', domain='tv'),
    _definition('cp_tv', 'prepare_tv_state', {'series': TV_REF, 'kind': enum('watched', 'watchlist'),
        'active': BOOL, 'depends_on': DEPENDENCIES}, kind='prepare', domain='tv'),
    _definition('cp_tv', 'prepare_tv_task', {'series': TV_REF, 'scope': enum('series', 'season', 'episode', 'missing'),
        'action': enum('download', 'monitor', 'finish_season'), 'season': nullable({'type': 'integer', 'minimum': 0}),
        'episode_ids': array_schema(ID), 'profile_id': nullable(STR_ID), 'depends_on': DEPENDENCIES}, kind='prepare', domain='tv'),
    _definition('cp_tv', 'tv_task_status', {'id': STR_ID}, domain='tv'),
    _definition('cp_tv', 'prepare_tv_task_cancel', {'task_id': STR_ID,
        'mode': enum('task_only', 'task_and_downloads'), 'depends_on': DEPENDENCIES}, kind='prepare', domain='tv'),
    _definition('cp_tv', 'prepare_tv_delete', {'series': array_schema(TV_REF), 'depends_on': DEPENDENCIES}, kind='prepare', domain='tv'),
    _definition('cp_iptv', 'search_iptv', {'provider_id': STR_ID, 'kind': enum('live', 'movie', 'series'),
        'filters': IPTV_FILTERS, 'page': PAGE}, domain='iptv'),
    _definition('cp_iptv', 'list_iptv_providers', {}, domain='iptv'),
    _definition('cp_iptv', 'iptv_details', {'media': IPTV_REF}, domain='iptv'),
    _definition('cp_iptv', 'iptv_lists', {'provider_id': STR_ID, 'page': PAGE}, domain='iptv'),
    _definition('cp_iptv', 'iptv_facets', {'provider_id': STR_ID}, domain='iptv'),
    _definition('cp_iptv', 'prepare_iptv_list', {'provider_id': STR_ID,
        'action': enum('create', 'rename', 'delete', 'add', 'remove'), 'list_id': nullable(STR_ID),
        'items': array_schema(IPTV_REF), 'name': nullable(text()), 'depends_on': DEPENDENCIES}, kind='prepare', domain='iptv'),
    _definition('cp_iptv', 'prepare_iptv_favorite', {'media': IPTV_REF, 'active': BOOL,
        'depends_on': DEPENDENCIES}, kind='prepare', domain='iptv'),
    _definition('cp_iptv', 'prepare_iptv_match', {'provider_id': STR_ID, 'selection': IPTV_SELECTION,
        'depends_on': DEPENDENCIES}, kind='prepare', domain='iptv'),
    _definition('cp_iptv', 'prepare_iptv_classification', {'provider_id': STR_ID, 'selection': IPTV_SELECTION,
        'depends_on': DEPENDENCIES}, kind='prepare', domain='iptv'),
    _definition('cp_runtime', 'continue_watching', {'domain': enum('movie', 'tv', 'iptv')}, domain='shared'),
    _definition('cp_runtime', 'playback_status', {}, domain='shared'),
    _definition('cp_runtime', 'prepare_play', {'media': MEDIA_REF, 'restart': BOOL, 'depends_on': DEPENDENCIES}, kind='prepare', domain='shared'),
    _definition('cp_runtime', 'prepare_clear_progress', {'media': MEDIA_REF, 'depends_on': DEPENDENCIES}, kind='prepare', domain='shared'),
    _definition('cp_runtime', 'notifications', {'page': PAGE}, domain='tv'),
    _definition('cp_runtime', 'prepare_mark_notifications_read', {'ids': array_schema(STR_ID),
        'depends_on': DEPENDENCIES}, kind='prepare', domain='tv'),
    _definition('cp_runtime', 'copy_job_status', {'id': STR_ID}, domain='shared'),
    _definition('cp_runtime', 'action_status', {'id': STR_ID}, domain='shared'),
    _definition('cp_runtime', 'redacted_integration_status', {'kind': enum('tmdb', 'plex', 'prowlarr', 'ollama', 'iptv', 'tv', 'player', 'subtitles')}, domain='shared'),
    _definition('cp_runtime', 'open_review', {'surface': enum('library', 'movie-lists', 'cleanup', 'discover',
        'tv', 'iptv', 'downloads', 'settings', 'help', 'player'), 'target_ref': nullable(MEDIA_REF)}, kind='review', domain='shared'),
]


_PRIVATE_KEY = re.compile(r'path|filename|folder|token|secret|credential|password|stream_url|authorization|cookie|username', re.I)


def model_safe(value):
    if isinstance(value, dict):
        return {str(key): model_safe(item) for key, item in value.items() if not _PRIVATE_KEY.search(str(key))}
    if isinstance(value, (list, tuple)):
        return [model_safe(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r'(?:https?|rtsp|ftp)://\S+', '[URL omitted]', value, flags=re.I)
        return re.sub(r'(?i)\b[a-z]:[\\/][^\r\n"]+', '[local path omitted]', value)
    return value


class ChatGPTTools:
    def __init__(self, owners, *, availability=lambda definition, context: None):
        self.owners, self.availability = dict(owners), availability
        self.definitions = {row['namespace'] + '.' + row['name']: row for row in DEFINITIONS}

    def manifest(self, context):
        rows = []
        for full_name, definition in self.definitions.items():
            reason = self.availability(definition, context)
            implemented = callable(self.owners.get(definition['name']))
            rows.append({'name': full_name, 'kind': definition['kind'], 'domain': definition['domain'],
                'status': 'disabled' if reason else 'callable' if implemented else 'not_implemented',
                'reason': reason or (None if implemented else 'not_implemented')})
        return rows

    def available(self, selection, context):
        if selection.provider != 'chatgpt':
            raise ToolError('gpt_selection_required')
        grouped = {}
        for full_name, definition in self.definitions.items():
            if not callable(self.owners.get(definition['name'])) or self.availability(definition, context):
                continue
            grouped.setdefault(definition['namespace'], []).append({'type': 'function', 'name': definition['name'],
                'description': definition['description'] + ('; preparation only, user confirmation is required.' if definition['kind'] == 'prepare' else ''),
                'parameters': definition['parameters'], 'strict': True})
        return [{'type': 'namespace', 'name': namespace, 'description': 'Validated CP ' + namespace.removeprefix('cp_') + ' operations.',
                 'tools': tools} for namespace, tools in grouped.items()]

    def call(self, name, arguments, context):
        definition = self.definitions.get(name)
        if not definition or not callable(self.owners.get(definition['name'])):
            raise ToolError('unsupported_tool')
        reason = self.availability(definition, context)
        if reason:
            raise ToolError(reason)
        try:
            validate_schema(definition['parameters'], arguments)
        except ValueError:
            raise ToolError('invalid_tool_arguments') from None
        result_set = arguments.get('result_set')
        if result_set:
            resolved = context.result_sets.get(result_set)
            if not resolved or resolved.domain != definition['domain']:
                raise ToolError('result_set_domain_mismatch')
        for reference in arguments.get('items', []):
            if isinstance(reference, dict) and reference.get('domain') == 'iptv' and reference.get('provider_id') != arguments.get('provider_id'):
                raise ToolError('iptv_provider_mismatch')
        dependencies = arguments.get('depends_on', [])
        if set(dependencies) - {row.get('action_id') or row.get('plan_id') for row in context.prepared}:
            raise ToolError('unknown_action_dependency')
        result = self.owners[definition['name']](arguments, context)
        if not isinstance(result, ToolResult):
            result = ToolResult(result)
        safe = model_safe(result.model)
        if len(json.dumps(safe, ensure_ascii=False).encode()) > 256 * 1024:
            raise ToolError('tool_output_requires_paging')
        return ToolResult(safe, result.ui)
