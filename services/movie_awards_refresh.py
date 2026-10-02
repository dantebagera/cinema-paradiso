"""Independent, persisted annual award scheduling and bounded source acquisition."""
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
import ctypes
from ctypes import wintypes
import email.utils
import json
import os
from pathlib import Path
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from services.movie_awards_sources import SourceError, ValidationReport
from services.movie_awards_store import AwardsError, AwardsUnavailable
from services.movie_awards_sources import parse_source, parse_annual_program, validate_ceremony, aggregate_ceremony
from services.movie_awards_identity import (TMDbIdentityBridge, resolve_identities, crosscheck_ceremony,
                                          _reference_labels, verify_linked_candidate)
import hashlib


class SourceTransportError(SourceError):
    def __init__(self, reason, *, retry_after=None):
        super().__init__(reason)
        self.retry_after = retry_after


class _SystemTime(ctypes.Structure):
    _fields_ = [(name, wintypes.WORD) for name in ('year','month','weekday','day','hour','minute','second','millisecond')]


class _DynamicZone(ctypes.Structure):
    _fields_ = [('bias', wintypes.LONG), ('standard_name', wintypes.WCHAR * 32),
                ('standard_date', _SystemTime), ('standard_bias', wintypes.LONG),
                ('daylight_name', wintypes.WCHAR * 32), ('daylight_date', _SystemTime),
                ('daylight_bias', wintypes.LONG), ('key', wintypes.WCHAR * 128),
                ('disabled', wintypes.BOOLEAN)]


@lru_cache(maxsize=1)
def _windows_cairo_zone():
    enum = ctypes.WinDLL('advapi32', use_last_error=True).EnumDynamicTimeZoneInformation
    enum.argtypes = [wintypes.DWORD, ctypes.POINTER(_DynamicZone)]
    enum.restype = wintypes.DWORD
    for index in range(1000):
        zone = _DynamicZone(); result = enum(index, ctypes.byref(zone))
        if result == 259:
            break
        if result:
            raise RuntimeError('cairo_timezone_enumeration_failed')
        if zone.key == 'Egypt Standard Time':
            return zone
    raise RuntimeError('cairo_timezone_unavailable')


def cairo_calendar(now_utc):
    if now_utc.tzinfo is None:
        raise ValueError('aware_utc_timestamp_required')
    utc = now_utc.astimezone(timezone.utc)
    if os.name != 'nt':
        return utc.astimezone(ZoneInfo('Africa/Cairo')).date()
    source = _SystemTime(utc.year, utc.month, 0, utc.day, utc.hour, utc.minute, utc.second, 0)
    target = _SystemTime()
    convert = ctypes.WinDLL('kernel32', use_last_error=True).SystemTimeToTzSpecificLocalTimeEx
    convert.argtypes = [ctypes.POINTER(_DynamicZone), ctypes.POINTER(_SystemTime), ctypes.POINTER(_SystemTime)]
    convert.restype = wintypes.BOOL
    if not convert(ctypes.byref(_windows_cairo_zone()), ctypes.byref(source), ctypes.byref(target)):
        raise RuntimeError('cairo_timezone_conversion_failed')
    return date(target.year, target.month, target.day)


class MovieAwardsRefresh:
    def __init__(self, store, source_transport, identity_resolver, clock=None, *, seed_loader=None):
        self.store = store
        self.source_transport = source_transport
        self.identity_resolver = identity_resolver
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.seed_loader = seed_loader
        self.stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._bootstrap_done = False
        self.diagnostic = ''

    def start(self):
        if os.environ.get('CP_TEST_MODE') == '1':
            return False
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self.stop_event.clear()
            self._thread = threading.Thread(target=self._run, name='cp-movie-awards', daemon=True)
            self._thread.start()
            return True

    def stop(self):
        self.stop_event.set()
        with self._lock:
            thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2)

    def _run(self):
        while not self.stop_event.is_set():
            try:
                self.run_due_once(self.clock())
            except Exception as exc:
                self.diagnostic = 'awards_worker_' + type(exc).__name__
            self.stop_event.wait(60)

    def run_due_once(self, now):
        if not self._bootstrap_done and self.seed_loader:
            try:
                seed, manifest = self.seed_loader()
                self.store.install_seed(seed, manifest)
                self._bootstrap_done = True
            except Exception as exc:
                self.diagnostic = 'awards_seed_' + (str(exc) if isinstance(exc, (SourceError, AwardsError, AwardsUnavailable)) else type(exc).__name__)
                # Existing complete counts can still refresh after a bad seed.
                if not self.store.read_snapshot()['ready']:
                    return
                self._bootstrap_done = True
        try:
            today = cairo_calendar(now)
        except Exception:
            self.diagnostic = 'cairo_timezone_unavailable'
            return
        state = self.store.read_status()
        jobs = {(row['organization'],row['ceremony']):row for row in state['refresh']}
        for org, month in [('golden_globe',1),('oscar',3)]:
            bounds = state['coverage'].get(org, {})
            if bounds.get('status') != 'complete':
                continue
            last_year = bounds.get('last_committed_year')
            last_number = bounds.get('last_ceremony')
            if not last_year or not last_number:
                continue
            for year in range(last_year + 1, today.year + 2):
                if self.stop_event.is_set():
                    return
                ceremony = last_number + year - last_year
                eligible = (today.year,today.month) >= (year,month)
                old = jobs.get((org,ceremony))
                self.store.ensure_refresh_state(org,ceremony,year,now,
                    status='pending' if eligible else 'awaiting_month',
                    force=bool(eligible and old and old['status']=='awaiting_month'))
                if not eligible:
                    break
                lease = self.store.claim_due(org,ceremony,now)
                if not lease:
                    break
                started = time.monotonic()
                try:
                    payload = self.source_transport(lease)
                    if self.stop_event.is_set():
                        raise SourceError('awards_refresh_cancelled')
                    contribution, proof = self.identity_resolver(lease,payload,self.store.read_identity_mappings())
                    if not proof.complete:
                        raise SourceError(','.join(proof.diagnostics) or 'incomplete_results')
                    if self.stop_event.is_set() or time.monotonic()-started > 600:
                        raise SourceError('awards_job_cancelled_or_deadline')
                    self.store.publish_ceremony(contribution,proof,lease.token)
                    self.diagnostic = ''
                except Exception as exc:
                    retry = max(timedelta(days=7), getattr(exc,'retry_after',None) or timedelta())
                    reason = str(exc) if isinstance(exc,SourceError) else type(exc).__name__
                    self.store.record_pending(lease.token,reason,now+retry)
                    self.diagnostic = reason
                    break


class BoundedSourceTransport:
    HOSTS = frozenset({'raw.githubusercontent.com','en.wikipedia.org','www.wikidata.org'})
    USER_AGENT = 'CinemaParadiso/3.0 (+https://github.com/dantebagera/cinema-paradiso) movie-awards'

    def __init__(self, *, clock=None, opener=None, cancelled=None):
        self.clock = clock or (lambda:datetime.now(timezone.utc))
        self.cancelled = cancelled or (lambda:False)
        self.cache = {}
        owner = self
        class Redirects(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                owner._check_url(newurl)
                count = getattr(req,'awards_redirects',0)+1
                if count>5:
                    raise SourceTransportError('source_redirect_limit')
                target = super().redirect_request(req,fp,code,msg,headers,newurl)
                target.awards_redirects=count
                return target
        self.opener = opener or urllib.request.build_opener(Redirects())

    def _check_url(self,url):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme!='https' or parsed.hostname not in self.HOSTS or parsed.username or parsed.password:
            raise SourceTransportError('source_url_not_allowed')

    def get(self,url,*,dataset=False):
        if os.environ.get('CP_TEST_MODE')=='1' and isinstance(self.opener,urllib.request.OpenerDirector):
            raise SourceTransportError('external_source_disabled_in_test_mode')
        if self.cancelled():
            raise SourceTransportError('awards_refresh_cancelled')
        self._check_url(url)
        previous=self.cache.get(url,{})
        headers={'User-Agent':self.USER_AGENT}
        for field,conditional in [('etag','If-None-Match'),('modified','If-Modified-Since')]:
            if previous.get(field):headers[conditional]=previous[field]
        limit=(40 if dataset else 2)*1024*1024
        try:
            with self.opener.open(urllib.request.Request(url,headers=headers),timeout=20) as response:
                raw=response.read(limit+1)
                if len(raw)>limit:raise SourceTransportError('source_payload_limit')
                self.cache[url]={'raw':raw,'etag':response.headers.get('ETag'),'modified':response.headers.get('Last-Modified')}
                return raw
        except urllib.error.HTTPError as exc:
            if exc.code==304 and 'raw' in previous:return previous['raw']
            retry=None
            if exc.code==429:
                value=exc.headers.get('Retry-After','')
                try:retry=timedelta(seconds=max(0,int(value)))
                except ValueError:
                    try:retry=max(timedelta(),email.utils.parsedate_to_datetime(value)-self.clock())
                    except (TypeError,ValueError):pass
            raise SourceTransportError(f'source_http_{exc.code}',retry_after=retry) from None
        except SourceError:
            raise
        except Exception as exc:
            raise SourceTransportError('source_transport_'+type(exc).__name__) from None


class RuntimeAwardsSources:
    """Fetch a complete feed ceremony and its independently revised program.

    Unknown future feed/schema/page formats remain pending. No render path calls
    this adapter. Source bytes and identity candidates are private worker memory.
    """
    DATASETS = {
        'oscar':('dlu_oscar','https://raw.githubusercontent.com/DLu/oscar_data/master/oscars.csv'),
        'golden_globe':('modern_globe','https://raw.githubusercontent.com/MengtingWan/oscar/master/data/processed/df_data_full.csv')}

    def __init__(self, transport, *, bridge=None, get_key=None, cancelled=None):
        self.transport=transport
        self.bridge=bridge or TMDbIdentityBridge(get_key=get_key,cancelled=cancelled)
        self._find_cache={};self._credits_cache={};self._links={}
        self.cancelled=cancelled or (lambda:False)
        self._deadline=None

    def _check(self):
        if self.cancelled() or (self._deadline and time.monotonic()>self._deadline):
            raise SourceError('awards_job_cancelled_or_deadline')

    def _json(self,url):
        self._check();return json.loads(self.transport.get(url))

    def fetch(self,lease):
        self._deadline=time.monotonic()+600
        self._check()
        source,url=self.DATASETS[lease.organization]
        raw=self.transport.get(url,dataset=True)
        primary=parse_source(source,raw,{'revision':hashlib.sha256(raw).hexdigest(),'url':url})
        primary=[w for w in primary if (w.organization,w.ceremony,w.ceremony_year)==(lease.organization,lease.ceremony,lease.ceremony_year)]
        number=lease.ceremony
        suffix='th' if 10<number%100<14 else {1:'st',2:'nd',3:'rd'}.get(number%10,'th')
        title=f'{number}{suffix}_'+('Academy_Awards' if lease.organization=='oscar' else 'Golden_Globe_Awards')
        page=self._json('https://en.wikipedia.org/w/api.php?'+urllib.parse.urlencode(
            {'action':'parse','page':title,'prop':'wikitext','format':'json'})).get('parse',{})
        if not page.get('revid') or not page.get('wikitext',{}).get('*'):
            raise SourceError('annual_source_unavailable')
        meta={'organization':lease.organization,'ceremony':number,'ceremony_year':lease.ceremony_year,
              'revision':str(page['revid']),'url':f"https://en.wikipedia.org/w/index.php?oldid={page['revid']}"}
        annual=page['wikitext']['*'].encode('utf-8')
        return {'primary':primary,'independent':parse_source('annual_wikitext',annual,meta),
                'program':parse_annual_program(annual,meta)}

    def _find(self,imdb,namespace):
        self._check();key=(namespace,imdb)
        if key not in self._find_cache:self._find_cache[key]=self.bridge.find(imdb,namespace)
        return self._find_cache[key]

    def _credits(self,movie_id):
        self._check()
        if movie_id not in self._credits_cache:self._credits_cache[movie_id]=self.bridge.credits(movie_id)
        return self._credits_cache[movie_id]

    def _linked_identity(self,ref):
        target=(ref.evidence[0] if ref.evidence else {}).get('wiki_target')
        if not target:return None
        if target not in self._links:
            page=self._json('https://en.wikipedia.org/w/api.php?'+urllib.parse.urlencode(
                {'action':'query','titles':target,'prop':'pageprops','ppprop':'wikibase_item','redirects':'1','format':'json'}))
            pages=list(page.get('query',{}).get('pages',{}).values())
            qid=pages[0].get('pageprops',{}).get('wikibase_item') if len(pages)==1 else None
            if not qid:self._links[target]={};return None
            entity=self._json('https://www.wikidata.org/w/api.php?'+urllib.parse.urlencode(
                {'action':'wbgetentities','ids':qid,'props':'info|claims','format':'json'})).get('entities',{}).get(qid,{})
            self._links[target]={'qid':qid,'entity':entity}
        value=self._links[target];entity=value.get('entity',{})
        def claims(property_id):
            return [row.get('mainsnak',{}).get('datavalue',{}).get('value') for row in entity.get('claims',{}).get(property_id,[])]
        identifiers=[v for v in claims('P345') if isinstance(v,str) and v.startswith('tt' if ref.namespace=='movie' else 'nm')]
        tmdbs=claims('P4947' if ref.namespace=='movie' else 'P4985')
        if len(identifiers)!=1 or len(tmdbs)>1 or not entity.get('lastrevid'):return None
        try:tmdb=int(tmdbs[0]) if tmdbs else None
        except (ValueError,TypeError):return None
        return {'namespace':ref.namespace,'imdb_id':identifiers[0],'tmdb_id':tmdb,
                'wikidata_qid':value['qid'],'wikidata_revision':entity['lastrevid']}

    @staticmethod
    def _aliases(primary,independent,mappings):
        facts={(m['namespace'],m['imdb_id']):m for m in mappings}
        result=[]
        for win in independent:
            if win.scope!='film':continue
            for ref in win.films+win.people:
                if ref.imdb_id:continue
                matches={r.entity_id:r for other in primary if other.award_instance==win.award_instance
                         for r in other.films+other.people if r.namespace==ref.namespace and r.tmdb_id and r.imdb_id
                         and _reference_labels(r,facts.get((r.namespace,r.imdb_id)))&_reference_labels(ref,None)}
                if len(matches)!=1:continue
                matched=next(iter(matches.values()));mapping=facts[(matched.namespace,matched.imdb_id)]
                context=ref.evidence[0]
                result.append({**mapping,'source_alias':ref.title,'source_context':{k:context[k] for k in ('source','ceremony','category')},
                    'evidence':{'source_url':win.evidence.get('source_url') or f"https://en.wikipedia.org/w/index.php?oldid={context['revision']}",
                        'revision':context['revision'],'reason':'Independent winning subject agrees with a source-ID verified entity in this exact ceremony/category.'}})
        return result

    def resolve(self,lease,payload,mappings):
        self._deadline=self._deadline or time.monotonic()+600
        primary=resolve_identities(payload['primary'],existing_mappings=mappings,find_by_imdb=self._find,
                                   search_candidates=lambda ref:[],overrides=[])
        aliases=self._aliases(primary.wins,payload['independent'],primary.mappings)
        # New annual links generate identifiers only; eligible credits still
        # validate every candidate before they can enter an import transaction.
        candidates={}
        for win in payload['independent']:
            if win.scope!='film':continue
            identities=[]
            for ref in win.films+win.people:
                context=ref.evidence[0]
                known=next((m for m in aliases if m.get('source_alias')==ref.title and m['namespace']==ref.namespace and m.get('source_context',{}).get('category')==context['category']),None)
                identity=known or self._linked_identity(ref)
                if identity and not identity.get('tmdb_id'):
                    rows=self._find(identity['imdb_id'],ref.namespace).get('movie_results' if ref.namespace=='movie' else 'person_results',[])
                    if len(rows)==1:identity={**identity,'tmdb_id':rows[0]['id']}
                identities.append((ref,identity))
            movie_ids=[identity['tmdb_id'] for ref,identity in identities if ref.namespace=='movie' and identity and identity.get('tmdb_id')]
            people_ids=[identity['tmdb_id'] for ref,identity in identities if ref.namespace=='person' and identity and identity.get('tmdb_id')]
            for ref,identity in identities:
                if not identity or identity.get('source_alias'):continue
                context=ref.evidence[0]
                candidate={**identity,'source_alias':ref.title,'source_context':{k:context[k] for k in ('source','ceremony','category')},
                    'winning_movie_ids':movie_ids,'credit_people':people_ids,
                    'evidence':{'source_url':f"https://en.wikipedia.org/w/index.php?oldid={context['revision']}",'revision':context['revision'],
                       'wikidata_revision':identity['wikidata_revision'],'reason':'Pinned winning-subject link and structured external identifiers, verified against TMDb external ID and eligible credits.'}}
                verified=verify_linked_candidate(ref,identity=candidate,find_by_imdb=self._find,load_credits=self._credits)
                if verified:candidates[(ref.namespace,ref.title,context['category'])]=verified
        independent=resolve_identities(payload['independent'],existing_mappings=primary.mappings,find_by_imdb=self._find,
            search_candidates=lambda ref:[candidates[(ref.namespace,ref.title,ref.evidence[0]['category'])]] if (ref.namespace,ref.title,ref.evidence[0]['category']) in candidates else [],overrides=aliases)
        if not primary.complete or not independent.complete:
            return None,ValidationReport(False,('unresolved_or_conflicting_identity',),{})
        crosscheck=crosscheck_ceremony(primary.wins,independent.wins,mappings=independent.mappings)
        proof=validate_ceremony(primary.wins,payload['program'],{**crosscheck.evidence,'as_of':cairo_calendar(datetime.now(timezone.utc)).isoformat()})
        diagnostics=tuple(sorted(set(proof.diagnostics+crosscheck.diagnostics)))
        return aggregate_ceremony(primary.wins),ValidationReport(not diagnostics,diagnostics,
            {**crosscheck.evidence,**proof.evidence,'crosscheck_agrees':crosscheck.complete,'revision':payload['program'].evidence['revision'],
             'identity_mappings':list(independent.mappings)})


def bundled_seed_loader(root):
    root=Path(root)
    def load():
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        if manifest.get('ready') is not True:raise SourceError('historical_seed_unavailable')
        return json.loads((root/'seed.json').read_text(encoding='utf-8')),manifest
    return load
