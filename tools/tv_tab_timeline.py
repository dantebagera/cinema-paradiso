"""Temporary localhost diagnostic proxy; never edits the installed frontend.

Run only during an approved first-tab investigation. Close this owned server after
capture; the existing backend and source remain unchanged. Browser logging is
injected into HTML responses here, not into production assets.
"""
import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit


PROBE = r"""
(() => {
  const captureEnabled = document.currentScript?.dataset.capture === 'true';
  const evidence = [];
  const emit = (phase, value = {}) => {
    const record = {phase, t: performance.now(), ...value};
    if (evidence.length < 2000) evidence.push(record);
    console.info('CP_TAB ' + JSON.stringify(record));
  };
  const tracked = url => /\/api\/(tv\/|library\/search\/advanced|tmdb\/discover\/advanced)/.test(url);
  const responses = new WeakMap();
  const completedImages = new Set();
  const originalFetch = window.fetch;
  window.fetch = async function(...args) {
    const url = String(args[0]?.url || args[0]);
    const start = performance.now();
    if (tracked(url)) emit('fetch_start', {url});
    try {
      const response = await originalFetch.apply(this, args);
      if (tracked(url)) {
        responses.set(response, {url, start});
        emit('headers', {url, elapsed: performance.now()-start, status: response.status,
          server: response.headers.get('X-CP-Route-MS'), encoding: response.headers.get('Content-Encoding')});
      }
      return response;
    } catch(error) { if (tracked(url)) emit('fetch_error', {url, elapsed:performance.now()-start, name:error.name}); throw error; }
  };
  const originalText = Response.prototype.text;
  Response.prototype.text = async function(...args) {
    const value = await originalText.apply(this, args);
    const info = responses.get(this);
    if (info) emit('body', {...info, elapsed:performance.now()-info.start, characters:value.length});
    return value;
  };
  const originalParse = JSON.parse;
  JSON.parse = function(...args) {
    const start = performance.now();
    const result = originalParse.apply(this, args);
    if (typeof args[0] === 'string' && args[0].length > 100000) emit('json_parse', {characters:args[0].length, elapsed:performance.now()-start, count:result?.items?.length});
    if (Array.isArray(result?.items) && result.items.some(row=>row.media_type==='tv'||row.tmdb_id&&row.season_count!=null)) emit('tv_items', {count:result.items.length,pending:result.items.filter(row=>row.season_count==null||!row.status).length});
    return result;
  };
  new PerformanceObserver(list => {
    for (const r of list.getEntries()) {
      if (tracked(r.name) || /\/assets\/.*\.(js|css)/.test(r.name)) emit('resource', {
        url:r.name, start:r.startTime, duration:r.duration, request:r.requestStart,
        response:r.responseStart, transfer:r.transferSize, encoded:r.encodedBodySize,
        decoded:r.decodedBodySize, server:r.serverTiming?.map(s=>({name:s.name,duration:s.duration}))});
      if (r.initiatorType==='img'||r.initiatorType==='css'||/image\.tmdb\.org/.test(r.name)) {
        completedImages.add(r.name);
        emit('image_resource', {url:r.name,start:r.startTime,duration:r.duration,transfer:r.transferSize,decoded:r.decodedBodySize});
        if(!pending){pending=true;queueMicrotask(sample);}
      }
    }
  }).observe({type:'resource', buffered:true});
  try { new PerformanceObserver(list => { for (const r of list.getEntries()) emit('long_task', {start:r.startTime,duration:r.duration}); }).observe({type:'longtask',buffered:true}); } catch {}
  document.addEventListener('click', event => {
    const button = event.target.closest('button');
    const tabs = button?.closest('[role="tablist"]');
    if (tabs && /^(Movies|TV Shows)$/.test(button.textContent.trim())) emit('tab_click', {context:tabs.getAttribute('aria-label'), media:button.textContent.trim()});
  }, true);
  const previous = new Map();
  let pending = false;
  function sample() {
    pending = false;
    for (const section of document.querySelectorAll('[aria-label="Library Movies"],[aria-label="Library TV Shows"],[aria-label="Discover Movies"],[aria-label="Discover TV Shows"]')) {
      const rect = section.getBoundingClientRect();
      if (!rect.width || !rect.height) continue;
      const name = section.getAttribute('aria-label');
      const cards = [...section.querySelectorAll('.unified-movie-card')];
      const count = cards.length;
      const visible = cards.filter(c=>{const r=c.getBoundingClientRect();return r.bottom>0&&r.top<innerHeight&&r.width>0;});
      const images = visible.flatMap(c=>[...c.querySelectorAll('img')]);
      const complete = images.filter(img=>img.complete&&img.naturalWidth>0).length;
      const backdrops=visible.flatMap(card=>[...getComputedStyle(card).backgroundImage.matchAll(/url\(["']?([^"')]+)["']?\)/g)].map(match=>match[1]));
      const backdropsLoaded=backdrops.filter(url=>/^(data:|blob:)/.test(url)||completedImages.has(new URL(url,location.href).href)).length;
      const state = [count,visible.length,images.length,complete,backdrops.length,backdropsLoaded,visible.map(c=>c.textContent).join('|')].join(':');
      if (previous.get(name+':state')!==state) {
        previous.set(name+':state',state);
        emit('visible_state',{name,count,visible:visible.length,posters:images.length,postersLoaded:complete,backdrops:backdrops.length,backdropsLoaded,missingCounts:visible.filter(c=>!/\d+ seas\./.test(c.textContent)).length});
      }
      const key = name+':'+count;
      if (previous.get(name) === key) continue;
      previous.set(name,key);
      emit(count ? 'cards_visible' : 'panel_loading', {name,count, inViewport:cards.filter(c=>{const r=c.getBoundingClientRect();return r.bottom>0&&r.top<innerHeight&&r.width>0;}).length});
    }
  }
  // Hidden diagnostic tabs can throttle animation frames to roughly one second.
  // Measure committed DOM/layout directly; do not mistake a delayed RAF for work.
  new MutationObserver(() => { if (!pending) { pending=true; queueMicrotask(sample); } }).observe(document,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['hidden','class','style']});
  document.addEventListener('load',event=>{if(event.target instanceof HTMLImageElement&&!pending){pending=true;queueMicrotask(sample);}},true);
  if (captureEnabled) document.addEventListener('DOMContentLoaded',()=>{
    const button=document.createElement('button');
    button.textContent='Save timing evidence';
    button.style.cssText='position:fixed;bottom:4px;right:4px;z-index:10000;font-size:11px';
    button.addEventListener('click',async()=>{
      const response=await originalFetch('/__cp_probe_evidence',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(evidence)});
      button.textContent=response.ok?'Timing evidence saved':'Timing evidence save failed';
    });
    document.body.append(button);
  });
  emit('probe_ready',{visibility:document.visibilityState});
})();
"""

READ_POSTS = {'/api/library/search/advanced', '/api/tmdb/discover/advanced',
              '/api/tv/catalog/search', '/api/tv/catalog/enrich', '/api/library/check',
              '/api/movie-awards/snapshot'}


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        self.forward()

    def do_POST(self):
        if urlsplit(self.path).path not in READ_POSTS:
            self.send_error(405, 'Diagnostic proxy permits only normal read requests')
            return
        self.forward()

    def forward(self):
        if self.path == '/__cp_tab_probe.js':
            body = PROBE.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        # Optional isolated compiled candidate; API traffic still uses the same
        # running backend. Resolve every static path inside the explicit dist.
        path = urlsplit(self.path).path
        if self.server.dist is not None and not path.startswith('/api/'):
            target = (self.server.dist/path.lstrip('/')).resolve()
            if not target.is_relative_to(self.server.dist):
                self.send_error(403)
                return
            if not target.is_file():
                target = self.server.dist/'index.html'
            payload = target.read_bytes()
            if target.suffix == '.html':
                payload = payload.replace(b'<head>', b'<head><script src="/__cp_tab_probe.js"></script>', 1)
            self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(target)[0] or 'application/octet-stream')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        connection = http.client.HTTPConnection('127.0.0.1', 5000, timeout=30)
        try:
            body = self.rfile.read(int(self.headers.get('Content-Length', 0))) or None
            headers = {k:v for k,v in self.headers.items() if k.lower() not in {'host','connection'}}
            connection.request(self.command, self.path, body, headers)
            response = connection.getresponse()
            payload = response.read()
            html = response.getheader('Content-Type','').startswith('text/html')
            if html:
                payload = payload.replace(b'<head>', b'<head><script src="/__cp_tab_probe.js"></script>', 1)
            self.send_response(response.status)
            for key,value in response.getheaders():
                if key.lower() not in {'content-length','transfer-encoding','connection'}:
                    self.send_header(key,value)
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5128)
    parser.add_argument('--dist', type=Path)
    args = parser.parse_args()
    if args.port == 5000:
        raise SystemExit('The diagnostic proxy cannot own the production port')
    server = ThreadingHTTPServer(('127.0.0.1',args.port), Handler)
    server.dist = args.dist.resolve() if args.dist else None
    if server.dist and not (server.dist/'index.html').is_file():
        raise SystemExit('Missing isolated compiled index')
    server.serve_forever()
