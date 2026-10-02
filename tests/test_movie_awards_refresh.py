import importlib, tempfile, unittest, os
from pathlib import Path
from datetime import datetime, timedelta, timezone, date
from unittest.mock import patch
from services.movie_awards_store import MovieAwardsStore
from services.movie_awards_sources import CeremonyContribution, ValidationReport, parse_source, parse_annual_program
from tests.test_movie_awards_store import seed, manifest, MOVIE


class AwardsRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.now=datetime(2026,1,15,tzinfo=timezone.utc)
        self.store=MovieAwardsStore(Path(self.temp.name)/'awards.sqlite',clock=lambda:self.now)
        data=seed();data['coverage']['oscar']['last_ceremony']=97
        data['coverage']['golden_globe']={'status':'complete','first_ceremony':1,'last_ceremony':82}
        original=data['ceremonies'][0];data['ceremonies']=[]
        for org,number,offset in [('oscar',97,1928),('golden_globe',82,1943)]:
            for n in range(1,number+1):
                data['ceremonies'].append({**original,'organization':org,'ceremony':n,'ceremony_year':n+offset})
        self.store.install_seed(data,manifest(data));self.calls=[]
        self.module=importlib.import_module('services.movie_awards_refresh')
        self.proof=ValidationReport(True,(),{'crosscheck_agrees':True,'revision':'verified'})
        self.worker=self.module.MovieAwardsRefresh(self.store,self.fetch,self.resolve,lambda:self.now)

    def fetch(self,lease):
        self.calls.append((lease.organization,lease.ceremony));return lease

    def resolve(self,lease,payload,mappings):
        return CeremonyContribution(lease.organization,lease.ceremony,lease.ceremony_year,{MOVIE:1},()),self.proof

    def test_january_globe_then_march_oscar_completed_jobs_never_recheck(self):
        self.worker.run_due_once(self.now)
        self.assertEqual(self.calls,[('golden_globe',83)])
        self.worker.run_due_once(self.now+timedelta(days=1));self.assertEqual(len(self.calls),1)
        self.now=datetime(2026,3,1,tzinfo=timezone.utc);self.worker.run_due_once(self.now)
        self.assertEqual(self.calls[-1],('oscar',98))
        self.worker.run_due_once(self.now+timedelta(days=8));self.assertEqual(len(self.calls),2)

    def test_incomplete_results_continue_weekly_outside_month_without_generation_change(self):
        generation=self.store.read_snapshot()['awards_generation']
        self.proof=ValidationReport(False,('missing_winners',),{})
        self.worker.run_due_once(self.now)
        self.worker.run_due_once(self.now+timedelta(days=6));self.assertEqual(len(self.calls),1)
        self.now=datetime(2026,2,2,tzinfo=timezone.utc);self.worker.run_due_once(self.now)
        self.assertEqual(len(self.calls),2)
        self.assertEqual(self.store.read_snapshot()['awards_generation'],generation)
        job=next(r for r in self.store.read_status()['refresh'] if r['organization']=='golden_globe' and r['ceremony']==83)
        self.assertIn('missing_winners',job['reason'])

    def test_closed_app_catches_up_multiple_years_chronologically_per_organization(self):
        self.now=datetime(2028,10,1,tzinfo=timezone.utc);self.worker.run_due_once(self.now)
        for org,start in [('golden_globe',83),('oscar',98)]:
            self.assertEqual([n for o,n in self.calls if o==org],list(range(start,start+3)))

    def test_pending_earlier_year_blocks_later_year_for_that_organization(self):
        self.now=datetime(2028,10,1,tzinfo=timezone.utc)
        def resolve(lease,payload,mappings):
            if lease.organization=='golden_globe' and lease.ceremony==83:return None,ValidationReport(False,('missing_winners',),{})
            return self.resolve(lease,payload,mappings)
        self.worker.identity_resolver=resolve;self.worker.run_due_once(self.now)
        self.assertEqual([n for org,n in self.calls if org=='golden_globe'],[83])
        self.assertEqual(self.store.read_snapshot()['coverage']['golden_globe']['last_committed_year'],2025)
        self.assertEqual([n for org,n in self.calls if org=='oscar'],[98,99,100])

    def test_network_failure_and_429_keep_counts_and_honor_later_retry(self):
        before=self.store.read_snapshot()
        def failed(lease):raise self.module.SourceTransportError('source_http_429',retry_after=timedelta(days=12))
        self.worker.source_transport=failed;self.worker.run_due_once(self.now)
        rows=self.store.read_status()['refresh'];job=next(r for r in rows if r['organization']=='golden_globe' and r['ceremony']==83)
        self.assertEqual(datetime.fromisoformat(job['next_due']),self.now+timedelta(days=12))
        self.assertEqual(self.store.read_snapshot(),before)

    def test_timezone_failure_does_not_contact_sources_or_damage_counts(self):
        with patch.object(self.module,'cairo_calendar',side_effect=RuntimeError('unavailable')):
            self.worker.run_due_once(self.now)
        self.assertEqual(self.calls,[]);self.assertEqual(self.worker.diagnostic,'cairo_timezone_unavailable')
        self.assertTrue(self.store.read_snapshot()['ready'])

    def test_invalid_seed_reports_exact_validation_reason_and_keeps_installed_counts(self):
        self.now=datetime(2025,12,20,tzinfo=timezone.utc)
        before=self.store.read_snapshot()
        self.worker.seed_loader=lambda:(seed(),{'schema_version':1,'ready':True,'seed_sha256':'invalid'})
        self.worker.run_due_once(self.now)
        self.assertEqual(self.worker.diagnostic,'awards_seed_invalid_seed_schema_or_hash')
        self.assertEqual(self.store.read_snapshot(),before)
        self.assertEqual(self.calls,[])

    def test_test_mode_does_not_auto_start_and_stop_is_idempotent(self):
        with patch.dict(os.environ,{'CP_TEST_MODE':'1'}),patch.object(self.module.threading,'Thread') as thread:
            self.assertFalse(self.worker.start());thread.assert_not_called()
        self.worker.stop();self.worker.stop()

    def test_runtime_double_start_owns_only_one_worker(self):
        with patch.dict(os.environ,{'CP_TEST_MODE':'0'}),patch.object(self.module.threading,'Thread') as thread:
            thread.return_value.is_alive.return_value=True
            self.assertTrue(self.worker.start());self.assertFalse(self.worker.start())
            self.assertEqual(thread.call_count,1)
            self.worker.stop();self.assertTrue(self.worker.stop_event.is_set())

    def test_cairo_calendar_uses_real_dst_and_year_boundary(self):
        self.assertEqual(self.module.cairo_calendar(datetime(2025,12,31,22,30,tzinfo=timezone.utc)),date(2026,1,1))
        self.assertEqual(self.module.cairo_calendar(datetime(2026,6,30,21,30,tzinfo=timezone.utc)),date(2026,7,1))
        self.assertEqual(self.module.cairo_calendar(datetime(2026,7,1,21,30,tzinfo=timezone.utc)),date(2026,7,2))

    @unittest.skipUnless(os.name=='nt','Windows calendar adapter')
    def test_missing_windows_cairo_zone_or_conversion_failure_is_explicit(self):
        with patch.object(self.module,'_windows_cairo_zone',side_effect=RuntimeError('cairo_timezone_unavailable')):
            with self.assertRaisesRegex(RuntimeError,'cairo_timezone_unavailable'):
                self.module.cairo_calendar(self.now)
        with patch.object(self.module,'_windows_cairo_zone',return_value=self.module._DynamicZone()),patch.object(self.module.ctypes,'WinDLL') as dll:
            dll.return_value.SystemTimeToTzSpecificLocalTimeEx.return_value=0
            with self.assertRaisesRegex(RuntimeError,'cairo_timezone_conversion_failed'):
                self.module.cairo_calendar(self.now)

    def test_identity_failure_is_pending_and_independent_organization_can_publish(self):
        self.now=datetime(2026,4,1,tzinfo=timezone.utc)
        def resolve(lease,payload,mappings):
            if lease.organization=='golden_globe':raise ValueError('unresolved_identity')
            return self.resolve(lease,payload,mappings)
        self.worker.identity_resolver=resolve;self.worker.run_due_once(self.now)
        states={r['organization']:r['status'] for r in self.store.read_status()['refresh'] if r['ceremony_year']==2026}
        self.assertEqual(states,{'golden_globe':'pending','oscar':'complete'})

    def test_missing_credentials_make_the_job_pending_without_network_or_false_zero(self):
        from services.movie_awards_identity import TMDbIdentityBridge
        bridge=TMDbIdentityBridge.__new__(TMDbIdentityBridge)
        bridge._get_key=lambda:'';bridge._cancelled=lambda:False
        before=self.store.read_snapshot()
        self.worker.identity_resolver=lambda *args:bridge.find('tt0010101','movie')
        with patch('services.movie_awards_identity.urllib.request.build_opener',side_effect=AssertionError('Missing credentials must not contact TMDb')):
            self.worker.run_due_once(self.now)
        self.assertEqual(self.store.read_snapshot(),before)
        job=next(row for row in self.store.read_status()['refresh'] if row['organization']=='golden_globe' and row['ceremony']==83)
        self.assertEqual(job['status'],'pending');self.assertEqual(job['reason'],'tmdb_credentials_unavailable')
        self.assertEqual(datetime.fromisoformat(job['next_due']),self.now+timedelta(days=7))

    def test_job_finishing_after_ten_minutes_cannot_publish(self):
        from types import SimpleNamespace
        elapsed=[0.0];before=self.store.read_snapshot()
        def resolve(*args):
            result=self.resolve(*args);elapsed[0]=601.0;return result
        self.worker.identity_resolver=resolve
        with patch.object(self.module,'time',SimpleNamespace(monotonic=lambda:elapsed[0])):
            self.worker.run_due_once(self.now)
        self.assertEqual(self.store.read_snapshot(),before)
        self.assertEqual(self.worker.diagnostic,'awards_job_cancelled_or_deadline')


class RuntimeAwardsSourceTests(unittest.TestCase):
    def test_conditional_304_reuses_exact_source_bytes_and_network_timeout_is_bounded(self):
        import urllib.error
        module=importlib.import_module('services.movie_awards_refresh')
        requests=[]
        class Response:
            headers={'ETag':'pinned-tag','Last-Modified':'Wed, 01 Oct 2025 00:00:00 GMT'}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,limit):return b'complete pinned source'
        class Opener:
            def open(self,request,timeout):
                requests.append((request,timeout))
                if len(requests)>1:raise urllib.error.HTTPError(request.full_url,304,'Not Modified',{},None)
                return Response()
        transport=module.BoundedSourceTransport(opener=Opener())
        url='https://en.wikipedia.org/source'
        self.assertEqual(transport.get(url),transport.get(url))
        self.assertEqual(requests[1][0].get_header('If-none-match'),'pinned-tag')
        self.assertEqual(requests[1][0].get_header('If-modified-since'),Response.headers['Last-Modified'])
        self.assertEqual([timeout for _,timeout in requests],[20,20])

    def test_cancelled_transport_never_contacts_provider_and_timeout_reason_has_no_private_message(self):
        module=importlib.import_module('services.movie_awards_refresh')
        class Opener:
            def open(self,*args,**kwargs):raise TimeoutError('private credential should never leave the worker')
        transport=module.BoundedSourceTransport(opener=Opener(),cancelled=lambda:True)
        with self.assertRaisesRegex(module.SourceTransportError,'awards_refresh_cancelled'):
            transport.get('https://en.wikipedia.org/source')
        transport.cancelled=lambda:False
        with self.assertRaises(module.SourceTransportError) as error:transport.get('https://en.wikipedia.org/source')
        self.assertEqual(str(error.exception),'source_transport_TimeoutError')

    def test_production_adapter_compares_actual_pinned_sources_without_provider_when_mapped(self):
        from tests.test_movie_awards_sources import oscar,payload,OSCAR_FIELDS
        from services.movie_awards_store import Lease
        module=importlib.import_module('services.movie_awards_refresh')
        primary=parse_source('dlu_oscar',payload(OSCAR_FIELDS,[oscar()], '\t'),{'revision':'csv-pinned'})
        raw=b"{{Infobox film awards|number=1}}\n{| class=wikitable\n{{Award category|Academy Award for Best Actor|Best Actor}}\n*'''[[Person]]''' - ''[[First]]''\n|}"
        meta={'organization':'oscar','ceremony':1,'ceremony_year':1929,'ceremony_date':'1929-05-16','revision':'wiki-pinned'}
        independent=parse_source('annual_wikitext',raw,meta)
        class Bridge:
            def find(self,*args):raise AssertionError('Verified mappings must be reused')
            def credits(self,*args):raise AssertionError('Existing mapping must not fetch credits')
        adapter=module.RuntimeAwardsSources(None,bridge=Bridge())
        mappings=seed()['identity_mappings']
        value,proof=adapter.resolve(Lease('oscar',1,1929,'token',datetime.now(timezone.utc)),
            {'primary':primary,'independent':independent,'program':parse_annual_program(raw,meta)},mappings)
        self.assertTrue(proof.complete,proof.diagnostics)
        self.assertEqual(value.films,{MOVIE:1})

    def test_bounded_transport_rejects_nonallowlisted_url_and_oversized_body(self):
        module=importlib.import_module('services.movie_awards_refresh')
        class Response:
            headers={}
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,limit):return b'x'*limit
        class Opener:
            def open(self,*a,**k):return Response()
        transport=module.BoundedSourceTransport(opener=Opener())
        for url in ['http://en.wikipedia.org','https://example.com/source']:
            with self.assertRaises(module.SourceTransportError):transport.get(url)
        with self.assertRaisesRegex(module.SourceTransportError,'source_payload_limit'):transport.get('https://en.wikipedia.org/source')
