"""Small bounded Plex JSON transport; credentials stay in headers."""
import json
import urllib.parse
import urllib.request


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def plex_json(base, token, path, *, params=None, timeout=5, max_bytes=1048576, open_url=None):
    url = base.rstrip('/') + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'X-Plex-Token': token, 'Accept': 'application/json'})
    opener = open_url or urllib.request.build_opener(_NoRedirect).open
    with opener(req, timeout=timeout) as response:
        raw = response.read(max_bytes + 1 if max_bytes is not None else -1)
        if max_bytes is not None and len(raw) > max_bytes:
            raise ValueError('plex_response_too_large')
        return json.loads(raw)
