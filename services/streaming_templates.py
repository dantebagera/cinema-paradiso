from string import Formatter
from urllib.parse import urlsplit


TV_TOKENS = {'tmdb_id', 'season_number', 'episode_number'}


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
    if parsed.hostname in {'streamimdb.ru', 'www.streamimdb.ru'} and parsed.scheme in {'https', 'http'} and not parsed.username and not parsed.password and parsed.path.startswith('/embed/movie/'):
        return f'{parsed.scheme}://{parsed.netloc}/embed/tv/{{tmdb_id}}/{{season_number}}/{{episode_number}}'
    return ''
