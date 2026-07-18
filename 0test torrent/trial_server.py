from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import argparse
import re


LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8090
QBT_ORIGIN = "http://127.0.0.1:8080"
TEST_ORIGIN = f"http://{LISTEN_HOST}:{LISTEN_PORT}"
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def build_shell_html():
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Portable qBittorrent Test</title>
  <style>
    html, body { height: 100%; margin: 0; }
    body { display: flex; font-family: sans-serif; }
    aside { width: 160px; padding: 12px; border-right: 1px solid #ccc; }
  </style>
</head>
<body>
  <aside><a id="downloads-link" href="/downloads">Downloads</a></aside>
  <main></main>
</body>
</html>
"""


def inject_sidebar(html):
    style = """
<style id="cp-test-layout">
  html, body { width: 100%; }
  body { padding-left: 160px !important; box-sizing: border-box !important; }
  #cp-test-sidebar {
    position: fixed; inset: 0 auto 0 0; z-index: 2147483647;
    width: 160px; padding: 12px; box-sizing: border-box;
    border-right: 1px solid #ccc; background: white; font: 16px sans-serif;
  }
</style>
"""
    sidebar = '<aside id="cp-test-sidebar"><a href="/downloads">Downloads</a></aside>'
    html = html.replace("</head>", f"{style}</head>", 1)
    return re.sub(r"<body([^>]*)>", rf"<body\1>{sidebar}", html, count=1, flags=re.I)


def build_upstream_headers(source_headers):
    headers = {
        key: value
        for key, value in source_headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }
    headers["Host"] = "127.0.0.1:8080"
    headers.pop("Accept-Encoding", None)
    if "Origin" in headers:
        headers["Origin"] = QBT_ORIGIN
    if "Referer" in headers:
        headers["Referer"] = headers["Referer"].replace(TEST_ORIGIN, QBT_ORIGIN)
    return headers


def rewrite_location(location):
    return location.replace(QBT_ORIGIN, TEST_ORIGIN)


class TrialHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path == "/shell":
            payload = build_shell_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/downloads":
            self.proxy_request(upstream_path="/", inject_test_sidebar=True)
            return
        self.proxy_request()

    def do_POST(self):
        self.proxy_request()

    def do_PUT(self):
        self.proxy_request()

    def do_DELETE(self):
        self.proxy_request()

    def proxy_request(self, upstream_path=None, inject_test_sidebar=False):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        request = Request(
            f"{QBT_ORIGIN}{upstream_path or self.path}",
            data=body,
            headers=build_upstream_headers(dict(self.headers.items())),
            method=self.command,
        )

        try:
            response = urlopen(request, timeout=30)
        except HTTPError as error:
            response = error
        except URLError:
            payload = b"qBittorrent WebUI is not available on 127.0.0.1:8080."
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        payload = response.read()
        if inject_test_sidebar:
            payload = inject_sidebar(payload.decode("utf-8")).encode("utf-8")
        self.send_response(response.status)
        for key, value in response.headers.items():
            lowered = key.lower()
            if lowered in HOP_BY_HOP_HEADERS or lowered == "content-length":
                continue
            if lowered == "location":
                value = rewrite_location(value)
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format_string, *args):
        print(f"{self.address_string()} - {format_string % args}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=LISTEN_PORT)
    args = parser.parse_args()
    server = ThreadingHTTPServer((LISTEN_HOST, args.port), TrialHandler)
    print(f"Trial page: http://{LISTEN_HOST}:{args.port}/shell")
    server.serve_forever()


if __name__ == "__main__":
    main()
