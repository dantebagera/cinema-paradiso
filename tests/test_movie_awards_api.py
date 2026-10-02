import importlib,tempfile,unittest
from pathlib import Path
from flask import Flask
from services.movie_awards_store import MovieAwardsStore
from unittest.mock import patch
from tests.test_movie_awards_store import seed,manifest,MOVIE,PERSON


class MovieAwardsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=MovieAwardsStore(Path(self.temp.name)/'awards/awards.sqlite')
        self.calls=[];self.project_calls=[]
        def get_store(*,create=False):
            self.calls.append(create);return self.store
        def project(movie):
            self.project_calls.append(movie);return {'tmdb_id':str(movie['id']),'title':movie.get('title','')}
        self.project=project
        self.app=Flask(__name__)
        importlib.import_module('services.movie_awards_routes').register_movie_awards_routes(self.app,get_store,lambda movie:self.project(movie))
        self.client=self.app.test_client()

    def install(self):
        data=seed();self.store.install_seed(data,manifest(data))

    def url(self,query=''):
        return '/api/movie-awards/person-films?person_id=20&role=actor&award=oscar'+query

    def test_missing_snapshot_status_and_person_reads_create_nothing(self):
        self.assertFalse(self.client.get('/api/movie-awards/snapshot').json['ready'])
        self.assertEqual(self.client.get('/api/movie-awards/status').status_code,200)
        self.assertEqual(self.client.get(self.url()).status_code,503)

        self.assertFalse(self.store.path.parent.exists())
        self.assertFalse(any(self.calls));self.assertEqual(self.project_calls,[])

    def test_snapshot_etag_conditional_read_and_role_namespaces(self):
        self.install();response=self.client.get('/api/movie-awards/snapshot')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['movies']['tmdb:10']['oscar'],2)
        self.assertEqual(response.json['people']['tmdb:20']['director']['oscar'],0)
        cached=self.client.get('/api/movie-awards/snapshot',headers={'If-None-Match':response.headers['ETag']})
        self.assertEqual(cached.status_code,304);self.assertEqual(cached.data,b'')
        self.assertFalse(any(self.calls));self.assertEqual(self.project_calls,[])

    def test_exact_ids_role_wins_pagination_and_uncached_films_retained(self):
        data=seed()
        data['identity_mappings'] += [dict(namespace='movie',imdb_id='tt0020202',tmdb_id=11,evidence={'revision':'verified'},facts={'title':'Additional film'}),
                                     dict(namespace='movie',imdb_id='tt0030303',tmdb_id=12,evidence={'revision':'verified'},facts={'title':'Awarded to someone else'})]
        contribution=data['ceremonies'][0]
        contribution['films'].update({MOVIE:3,'movie:imdb:tt0020202':1,'movie:imdb:tt0030303':1})
        contribution['person_wins'][0]['films'].append('movie:imdb:tt0020202')
        contribution['person_wins'].append({'person':PERSON,'role':'actor','award_instance':'SUPPORTING','category':'SUPPORTING','films':[MOVIE],'evidence':[{'revision':'winner'}]})
        self.store.install_seed(data,manifest(data))
        one=self.client.get(self.url('&page_size=1')).json;two=self.client.get(self.url('&page_size=1&page=2')).json
        self.assertEqual({one['results'][0]['id'],two['results'][0]['id']},{10,11})
        self.assertEqual(one['award_wins'],2);self.assertEqual(one['total_results'],2)
        self.assertTrue(one['has_next']);self.assertFalse(two['has_next'])
        self.assertEqual(one['results'][0]['tmdb_id'],'11')
        self.assertFalse(any(self.calls))

    def test_switching_userdata_does_not_reuse_another_stores_etag(self):
        self.install()
        first = self.client.get('/api/movie-awards/snapshot')
        self.store = MovieAwardsStore(Path(self.temp.name) / 'other-user/awards/awards.sqlite')
        self.install()
        second = self.client.get('/api/movie-awards/snapshot', headers={'If-None-Match': first.headers['ETag']})
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(second.json['snapshot_owner'], first.json['snapshot_owner'])
        self.assertNotIn(self.temp.name, second.text)

    def test_invalid_input_unavailable_coverage_unknown_identity_and_generation(self):
        self.install()
        for query in ['person_id=0&role=actor&award=oscar','person_id=true&role=actor&award=oscar',
                      'person_id=20&role=writer&award=oscar','person_id=20&role=actor&award=emmy',
                      'person_id=20&role=actor&award=oscar&page=0','person_id=20&role=actor&award=oscar&page_size=101',
                      'person_id=20&role=actor&award=oscar&generation=-1']:
            self.assertEqual(self.client.get('/api/movie-awards/person-films?'+query).status_code,400,query)
        self.assertEqual(self.client.get(self.url('&generation=99')).status_code,409)
        self.assertEqual(self.client.get(self.url('&generation=99')).json['awards_generation'],1)
        for query in ['person_id=20&role=actor&award=golden_globe','person_id=99&role=actor&award=oscar']:
            self.assertEqual(self.client.get('/api/movie-awards/person-films?'+query).status_code,503)
        self.assertEqual(self.client.get('/api/movie-awards/person-films?person_id=20&role=director&award=oscar').json['results'],[])

    def test_projection_failure_or_changed_identity_cannot_return_partial_success(self):
        self.install()
        def broken(movie):raise RuntimeError('private-provider-secret')
        self.project=broken
        response=self.client.get(self.url())
        self.assertEqual(response.status_code,503);self.assertNotIn('private-provider',response.text)
        self.project=lambda movie:{'tmdb_id':'99','title':'Wrong cached film'}
        self.assertEqual(self.client.get(self.url()).status_code,503)

class AppMovieAwardsIntegrationTests(unittest.TestCase):
    def test_missing_and_uncached_awards_gets_do_not_initialize_or_enrich_catalog(self):
        import app
        with tempfile.TemporaryDirectory() as directory, patch.object(app,'_user_data_dir',directory), \
             patch.object(app,'_catalog_repository_for',side_effect=AssertionError('awards GET must not initialize catalog')), \
             patch.object(app,'_fetch_tmdb_metadata_by_id',side_effect=AssertionError('provider fetch forbidden')), \
             patch.object(app,'_fetch_tmdb_metadata_by_imdb',side_effect=AssertionError('provider fetch forbidden')):
            client=app.app.test_client()
            response=client.get('/api/movie-awards/snapshot')
            self.assertEqual(response.status_code,200);self.assertFalse(response.json['ready'])
            self.assertFalse((Path(directory)/'awards').exists())
            data=seed();store=MovieAwardsStore(Path(directory)/'awards/awards.sqlite')
            store.install_seed(data,manifest(data))
            response=client.get('/api/movie-awards/person-films?person_id=20&role=actor&award=oscar')
            self.assertEqual(response.status_code,200)
            self.assertEqual([r['id'] for r in response.json['results']],[10])
            self.assertEqual(response.json['results'][0]['title'],'Winning film')

