import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import app


class RatingsIntegrationTest(unittest.TestCase):
    def tearDown(self):
        app._stop_movie_ratings()

    def test_read_does_not_initialize_catalog_or_start_network(self):
        with tempfile.TemporaryDirectory() as root, patch.object(app,'_user_data_dir',root), \
             patch.object(app,'_catalog_repository_cache',{}), patch.object(app,'_plex_token',''), \
             patch.object(app,'_catalog_repository',side_effect=AssertionError('catalog initialized')), \
             patch('services.movie_ratings.plex_json',side_effect=AssertionError('provider called')):
            response=app.app.test_client().post('/api/movie-ratings/read',json={'items':[{'tmdb_id':44012}]})
            self.assertEqual(response.status_code,200)
            self.assertFalse(response.json['items']['movie:tmdb:44012']['display_allowed'])
            self.assertFalse((Path(root)/'ratings').exists())

    def test_ownership_uses_accepted_catalog_and_rejects_conflicting_ids(self):
        owner=Mock()
        owner.store.owned_identity_candidates.return_value=[{'path_key':'owned-path','tmdb_id':'44012','imdb_id':'tt0073198','plex_guid':''}]
        owner.get_record.return_value={'rating_key':'42'}
        with patch.object(app,'_catalog_repository_cache',{str(Path(app._user_data_dir).resolve()):owner}), patch.object(app,'_plex_cache',{}):
            identity=app.movie_identity({'tmdb_id':44012})
            result=app._ratings_owned_movies([identity])
            self.assertEqual(result[identity['key']]['rating_key'],'42')
            self.assertIn('tmdb:44012',owner.store.owned_identity_candidates.call_args.args[0])
            conflict=app.movie_identity({'tmdb_id':44012,'imdb_id':'tt99999'})
            self.assertEqual(app._ratings_owned_movies([conflict]),{})

    def test_config_change_invalidates_existing_worker_without_instantiating_another(self):
        owner=Mock()
        with patch.object(app,'_movie_ratings_instance',owner),patch.object(app,'_save_config'), \
             patch.object(app,'_plex_url',''),patch.object(app,'_plex_token',''):
            result=app.app.test_client().post('/api/plex/config',json={'url':'','token':''})
            self.assertEqual(result.status_code,200)
            owner.invalidate_config.assert_called_once()

    def test_old_normal_sync_cannot_handoff_facts_after_credentials_change(self):
        owner=Mock();owner.store.epoch=0
        def fetch(base,token,path,**kwargs):
            if path=='/library/sections':
                app._plex_token='replacement'
                return {'MediaContainer':{'Directory':[{'key':'1','type':'movie'}]}}
            return {'MediaContainer':{'Metadata':[]}}
        with patch.object(app,'_get_movie_ratings_service',return_value=owner),patch.object(app,'plex_json',side_effect=fetch), \
             patch.object(app,'_plex_url','http://plex.test'),patch.object(app,'_plex_token','original'):
            app._fetch_plex_library()
            owner.offer_local_snapshot.assert_not_called()


if __name__=='__main__':unittest.main()
