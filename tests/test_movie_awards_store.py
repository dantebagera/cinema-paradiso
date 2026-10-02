import hashlib,importlib,json,sqlite3,tempfile,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from services.movie_awards_sources import CeremonyContribution,PersonWin,ValidationReport
from tools.build_movie_awards_snapshot import canonical_bytes

NOW=datetime(2026,3,20,tzinfo=timezone.utc)
MOVIE='movie:imdb:tt0010101';PERSON='person:imdb:nm0010101'

def owner():
    return importlib.import_module('services.movie_awards_store')

def seed():
    return {'schema_version':1,'coverage':{'oscar':{'status':'complete','first_ceremony':1,'last_ceremony':1},
            'golden_globe':{'status':'pending','first_ceremony':1,'last_ceremony':83}},
        'identity_mappings':[{'namespace':'movie','imdb_id':'tt0010101','tmdb_id':10,'evidence':{'revision':'verified'},
                              'facts':{'title':'Winning film','release_date':'1928-01-01'}},
                             {'namespace':'person','imdb_id':'nm0010101','tmdb_id':20,'evidence':{'revision':'verified'}}],
        'ceremonies':[{'organization':'oscar','ceremony':1,'ceremony_year':1929,'films':{MOVIE:2},
            'person_wins':[{'person':PERSON,'role':'actor','award_instance':'ACTOR','category':'ACTOR','films':[MOVIE],'evidence':[{'revision':'winner'}]}],
            'validation':{'ceremony_date':'1929-05-16','expected_instances':['ACTOR','BEST PICTURE'],
                          'evidence':{'revision':'program'},'crosscheck':{'crosscheck_agrees':True,'revision':'independent'}},
            'source_evidence':'primary'}]}

def manifest(data):
    return {'schema_version':1,'ready':True,'seed_sha256':hashlib.sha256(canonical_bytes(data)).hexdigest()}

class MovieAwardsStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'awards/awards.sqlite'
        self.store=owner().MovieAwardsStore(self.path,clock=lambda:NOW)

    def install(self):
        data=seed();return self.store.install_seed(data,manifest(data))

    def claim(self,ceremony=2):
        self.store.ensure_refresh_state('oscar',ceremony,ceremony+1928,NOW,force=ceremony==1)
        return self.store.claim_due('oscar',ceremony,NOW)

    def contribution(self,ceremony=2,wins=1):
        return CeremonyContribution('oscar',ceremony,ceremony+1928,{MOVIE:wins},
            (PersonWin(PERSON,'director','DIRECTING','DIRECTING',(MOVIE,),({'revision':'new'},)),))

    def proof(self):
        return ValidationReport(True,(),{'crosscheck_agrees':True,'revision':'validated'})

    def test_new_annual_identities_publish_with_their_counts_in_one_generation(self):
        self.install(); lease=self.claim()
        film='movie:imdb:tt0099999';person='person:imdb:nm0099999'
        mappings=[{'namespace':'movie','imdb_id':'tt0099999','tmdb_id':99,'evidence':{'revision':'verified'},'facts':{'title':'New winning film'}},
                  {'namespace':'person','imdb_id':'nm0099999','tmdb_id':98,'evidence':{'revision':'verified'}}]
        value=CeremonyContribution('oscar',2,1930,{film:1},(PersonWin(person,'actor','ACTOR','ACTOR',(film,),({'revision':'winner'},)),))
        proof=ValidationReport(True,(),{'crosscheck_agrees':True,'revision':'validated','identity_mappings':mappings})
        self.assertEqual(self.store.publish_ceremony(value,proof,lease.token),2)
        self.assertEqual(self.store.read_snapshot()['movies']['tmdb:99']['oscar'],1)
        self.assertEqual(self.store.person_films(98,'actor','oscar',1,20)['results'][0]['id'],99)
        self.assertEqual(self.store.publish_ceremony(value,proof,lease.token),2)

    def test_new_identity_conflict_leaves_old_generation_and_lease_intact(self):
        self.install();lease=self.claim()
        proof=ValidationReport(True,(),{'crosscheck_agrees':True,'revision':'validated','identity_mappings':[
            {'namespace':'movie','imdb_id':'tt0099999','tmdb_id':10,'evidence':{'revision':'verified'}}]})
        with self.assertRaises(owner().AwardsError):self.store.publish_ceremony(self.contribution(),proof,lease.token)
        self.assertEqual(self.store.read_snapshot()['awards_generation'],1)
        self.assertEqual(self.store.read_status()['refresh'][-1]['status'],'checking')

    def test_missing_store_reads_never_create_files(self):
        snap=self.store.read_snapshot()
        self.assertFalse(snap['ready']);self.assertEqual(snap['movies'],{})
        self.assertFalse(self.path.parent.exists())
        self.assertEqual(self.store.read_status()['awards_generation'],0)
        self.assertFalse(self.path.exists())

    def test_seed_idempotence_domain_aliases_and_unknown_coverage(self):
        self.assertEqual(self.install(),1);self.assertEqual(self.install(),1)
        snap=self.store.read_snapshot()
        self.assertEqual(snap['movies']['tmdb:10'],{'entity_id':MOVIE,'oscar':2,'golden_globe':None})
        self.assertEqual(snap['movies']['imdb:tt0010101'],snap['movies']['tmdb:10'])
        self.assertEqual(snap['people']['tmdb:20']['actor'],{'oscar':1,'golden_globe':None})
        self.assertEqual(snap['people']['tmdb:20']['director']['oscar'],0)

    def test_validated_publication_is_idempotent_and_replacement_does_not_add_old_count(self):
        self.install();lease=self.claim()
        self.assertEqual(self.store.publish_ceremony(self.contribution(),self.proof(),lease.token),2)
        self.assertEqual(self.store.publish_ceremony(self.contribution(),self.proof(),lease.token),2)
        self.assertEqual(self.store.read_snapshot()['movies']['tmdb:10']['oscar'],3)
        correction=self.claim(1)
        self.assertEqual(self.store.publish_ceremony(self.contribution(1,4),self.proof(),correction.token),3)
        self.assertEqual(self.store.read_snapshot()['movies']['tmdb:10']['oscar'],5)
        self.assertEqual(self.store.read_snapshot()['people']['tmdb:20']['actor']['oscar'],0)

    def test_failed_mid_publication_rolls_back_counts_links_generation_and_lease(self):
        self.install();lease=self.claim()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE TRIGGER abort_person BEFORE INSERT ON person_wins BEGIN SELECT RAISE(ABORT,'fixture interruption'); END")
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.publish_ceremony(self.contribution(),self.proof(),lease.token)
        snap=self.store.read_snapshot()
        self.assertEqual(snap['awards_generation'],1);self.assertEqual(snap['movies']['tmdb:10']['oscar'],2)
        self.assertEqual(snap['people']['tmdb:20']['director']['oscar'],0)
        self.assertIsNone(self.store.claim_due('oscar',2,NOW+timedelta(minutes=1)))

    def test_bad_seed_schema_hash_identity_and_partial_coverage_rejected_before_creation(self):
        for mutate in [lambda d:d.update(schema_version=2),lambda d:d['ceremonies'][0]['films'].update({MOVIE:True}),
                       lambda d:d['identity_mappings'][0].update(imdb_id='nm0010101'),
                       lambda d:d['coverage']['oscar'].update(last_ceremony=2)]:
            data=seed();mutate(data)
            with self.assertRaises(owner().AwardsError):self.store.install_seed(data,manifest(data))
            self.assertFalse(self.path.exists())
        with self.assertRaises(owner().AwardsError):self.store.install_seed(seed(),{'schema_version':1,'ready':True,'seed_sha256':'wrong'})
        self.assertFalse(self.path.exists())

    def test_old_seed_never_downgrades_newer_ceremonies_or_corrections(self):
        self.install();lease=self.claim()
        self.store.publish_ceremony(self.contribution(),self.proof(),lease.token)
        before=self.store.read_snapshot();self.install()
        self.assertEqual(self.store.read_snapshot(),before)

    def test_person_role_membership_zero_unknown_and_generation_conflict(self):
        self.install()
        page=self.store.person_films(20,'actor','oscar',1,1,None)
        self.assertEqual([r['id'] for r in page['results']],[10]);self.assertEqual(page['award_wins'],1)
        self.assertEqual(self.store.person_films(20,'director','oscar',1,10,None)['results'],[])
        with self.assertRaises(owner().AwardsUnavailable):self.store.person_films(20,'actor','golden_globe',1,10,None)
        with self.assertRaises(owner().AwardsUnavailable):self.store.person_films(999,'actor','oscar',1,10,None)
        with self.assertRaises(owner().GenerationConflict) as error:self.store.person_films(20,'actor','oscar',1,10,99)
        self.assertEqual(error.exception.generation,1)

    def test_two_workers_claim_once_and_expired_lease_recovers(self):
        self.install();self.store.ensure_refresh_state('oscar',2,1930,NOW)
        with ThreadPoolExecutor(max_workers=2) as pool:
            leases=list(pool.map(lambda _:owner().MovieAwardsStore(self.path).claim_due('oscar',2,NOW),range(2)))
        self.assertEqual(sum(x is not None for x in leases),1)
        recovered=self.store.claim_due('oscar',2,NOW+timedelta(minutes=16))
        self.assertIsNotNone(recovered);self.assertNotEqual(recovered.token,next(x.token for x in leases if x))

    def test_unsupported_existing_schema_is_not_overwritten(self):
        self.path.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.path)) as db:db.execute('PRAGMA user_version=99')
        original=self.path.read_bytes()
        with self.assertRaises(owner().AwardsUnavailable):self.store.read_snapshot()
        with self.assertRaises(owner().AwardsUnavailable):self.install()
        self.assertEqual(self.path.read_bytes(),original)

    def test_two_fresh_store_owners_bootstrap_one_seed_without_partial_schema_or_double_generation(self):
        from threading import Barrier
        barrier = Barrier(2)
        data = seed()
        def install():
            independent = owner().MovieAwardsStore(self.path, clock=lambda: NOW)
            barrier.wait(timeout=5)
            return independent.install_seed(data, manifest(data))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: install(), range(2)))
        self.assertEqual(results, [1, 1])
        self.assertEqual(self.store.read_snapshot()['movies']['tmdb:10']['oscar'], 2)

    def test_unversioned_nonempty_foreign_database_is_preserved(self):
        self.path.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('CREATE TABLE unrelated(value TEXT)')
        original=self.path.read_bytes()
        with self.assertRaises(owner().AwardsUnavailable):self.install()
        self.assertEqual(self.path.read_bytes(),original)
