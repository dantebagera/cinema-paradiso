import json
import ssl
import urllib.error
import urllib.parse
import urllib.request


class XtreamError(RuntimeError):
    pass


MAX_JSON_BYTES = 128 * 1024 * 1024


def normalize_server_url(value):
    text = str(value or "").strip().rstrip("/")
    parsed = urllib.parse.urlsplit(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Xtream server URL must start with http:// or https://")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


class XtreamClient:
    def __init__(self, server_url, username, password, timeout=30, verify_tls=True):
        self.server_url = normalize_server_url(server_url)
        self.username = str(username or "").strip()
        self.password = str(password or "")
        self.timeout = max(3, int(timeout or 30))
        self.verify_tls = bool(verify_tls)
        if not self.username or not self.password:
            raise ValueError("Xtream username and password are required")

    def _request_json(self, action=None, **params):
        query = {"username": self.username, "password": self.password}
        if action:
            query["action"] = action
        query.update({key: value for key, value in params.items() if value is not None})
        url = f"{self.server_url}/player_api.php?{urllib.parse.urlencode(query)}"
        request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Cinema-Paradiso/2.8"})
        try:
            context = None if self.verify_tls else ssl._create_unverified_context()
            with urllib.request.urlopen(request, timeout=self.timeout, context=context) as response:
                raw = response.read(MAX_JSON_BYTES + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as error:
            raise XtreamError(f"Xtream request failed: {getattr(error, 'reason', error)}") from None
        if len(raw) > MAX_JSON_BYTES:
            raise XtreamError("Xtream response exceeded the 128 MB safety limit")
        try:
            return json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise XtreamError("Xtream server returned invalid JSON") from None

    def authenticate(self):
        payload = self._request_json()
        user_info = payload.get("user_info") if isinstance(payload, dict) else None
        if not isinstance(user_info, dict) or str(user_info.get("auth", "0")) != "1":
            raise XtreamError("Xtream credentials were rejected")
        return payload

    def _array(self, action, **params):
        payload = self._request_json(action, **params)
        if not isinstance(payload, list):
            raise XtreamError(f"Xtream {action} response was not a list")
        return payload

    def live_categories(self):
        return self._array("get_live_categories")

    def live_streams(self):
        return self._array("get_live_streams")

    def movie_categories(self):
        return self._array("get_vod_categories")

    def movies(self):
        return self._array("get_vod_streams")

    def series_categories(self):
        return self._array("get_series_categories")

    def series(self):
        return self._array("get_series")

    def movie_info(self, item_id):
        payload = self._request_json("get_vod_info", vod_id=str(item_id))
        if not isinstance(payload, dict):
            raise XtreamError("Xtream movie detail response was invalid")
        return payload

    def series_info(self, item_id):
        payload = self._request_json("get_series_info", series_id=str(item_id))
        if not isinstance(payload, dict):
            raise XtreamError("Xtream series detail response was invalid")
        return payload

    def short_epg(self, stream_id, limit=4):
        payload = self._request_json("get_short_epg", stream_id=str(stream_id), limit=max(1, int(limit)))
        listings = payload.get("epg_listings") if isinstance(payload, dict) else None
        return listings if isinstance(listings, list) else []

    def stream_url(self, kind, item_id, extension=None):
        path_kind = {"live": "live", "movie": "movie", "episode": "series"}.get(kind)
        if not path_kind:
            raise ValueError("Unsupported Xtream stream kind")
        default_extension = "ts" if kind == "live" else "mp4"
        safe_extension = "".join(char for char in str(extension or default_extension).lower() if char.isalnum()) or default_extension
        username = urllib.parse.quote(self.username, safe="")
        password = urllib.parse.quote(self.password, safe="")
        item = urllib.parse.quote(str(item_id), safe="")
        return f"{self.server_url}/{path_kind}/{username}/{password}/{item}.{safe_extension}"
