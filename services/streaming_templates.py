from string import Formatter
from urllib.parse import urlsplit


TV_TOKENS = {'tmdb_id', 'season_number', 'episode_number'}

STREAMING_PROVIDERS = (
    {
        'id': 'streamimdb',
        'label': 'StreamIMDB',
        'url_template': 'https://streamimdb.ru/embed/movie/{tmdb_id}',
        'tv_url_template': 'https://streamimdb.ru/embed/tv/{tmdb_id}/{season_number}/{episode_number}',
    },
    {
        'id': 'vsembed',
        'label': 'VSEmbed',
        'url_template': 'https://vsembed.ru/embed/movie/{tmdb_id}/',
        'tv_url_template': 'https://vsembed.ru/embed/tv/{tmdb_id}/{season_number}-{episode_number}',
    },
)

DEFAULT_STREAMING_MOVIE_TEMPLATE = STREAMING_PROVIDERS[0]['url_template']


def streaming_provider_options():
    return [dict(provider) for provider in STREAMING_PROVIDERS]


def movie_streaming_sources(enabled, template, label="Stream"):
    if not enabled:
        return []
    sources = [{"id": provider["id"], "label": provider["label"], "url_template": provider["url_template"]}
               for provider in STREAMING_PROVIDERS]
    selected = next((source for source in sources if source["url_template"] == template), None)
    if template and selected is None:
        selected = {"id": "custom", "label": label if label and label != "Stream" else "Custom URL",
                    "url_template": template}
        sources.insert(0, selected)
    elif selected:
        sources.remove(selected)
        sources.insert(0, selected)
    return sources


def identify_streaming_provider(movie_template, tv_template=''):
    return next((provider['id'] for provider in STREAMING_PROVIDERS
                 if movie_template == provider['url_template']
                 and effective_tv_template(movie_template, tv_template) == provider['tv_url_template']), 'custom')


def validate_tv_template(template):
    template = str(template or '').strip()
    if not template:
        return ''
    if len(template) > 2048:
        raise ValueError('TV streaming template is too long')
    try:
        parsed = urlsplit(template)
        fields = [(name, spec, conversion) for _, name, spec, conversion in Formatter().parse(template) if name is not None]
    except ValueError as error:
        raise ValueError('Invalid TV streaming template') from error
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('TV streaming template must be an http or https URL without credentials')
    if {field[0] for field in fields} != TV_TOKENS or any(spec or conversion for _, spec, conversion in fields):
        raise ValueError('TV streaming requires tmdb_id, season_number and episode_number placeholders')
    if '{' in parsed.netloc or '}' in parsed.netloc:
        raise ValueError('TV identifiers cannot change the streaming host')
    return template


def effective_tv_template(movie_template, tv_template=''):
    if tv_template:
        return validate_tv_template(tv_template)
    parsed = urlsplit(str(movie_template or '').strip())
    if parsed.scheme in {'https', 'http'} and not parsed.username and not parsed.password:
        for provider in STREAMING_PROVIDERS:
            movie = urlsplit(provider['url_template'])
            if parsed.hostname in {movie.hostname, f'www.{movie.hostname}'} and parsed.path.startswith('/embed/movie/'):
                return f"{parsed.scheme}://{parsed.netloc}{urlsplit(provider['tv_url_template']).path}"
    return ''
