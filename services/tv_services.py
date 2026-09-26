"""Lazy, capability-gated composition of native TV owners."""
import threading
from pathlib import Path

from services.tv_catalog_repository import TVCatalogRepository
from services.tv_read_model import TVReadModel
from services.tv_ingestion import TVIngestion
from services.tv_metadata import TVMetadata
from services.tv_search import TVSearch
from services.tv_playback import TVPlayback, TVPlaybackHistory
from services.plex_tv import PlexTVDiscovery


class TVServices:
    def __init__(self, data_root, roots, tmdb_key, player_config, plex_url=lambda: '', plex_token=lambda: ''):
        self.data_root, self.roots, self.tmdb_key, self.player_config = data_root, roots, tmdb_key, player_config
        self.plex_url, self.plex_token = plex_url, plex_token
        self._lock = threading.RLock()
        self._instances = {}

    def __call__(self):
        path = Path(self.data_root()).resolve() / 'tv-catalog.sqlite'
        with self._lock:
            if path not in self._instances:
                repository = TVCatalogRepository(path)
                self._instances[path] = {'repository': repository, 'read': TVReadModel(repository),
                    'ingestion': TVIngestion(repository, self.roots), 'metadata': TVMetadata(repository, self.tmdb_key),
                    'playback': TVPlayback(repository, self.roots), 'history': TVPlaybackHistory(repository, self.player_config),
                    'plex': PlexTVDiscovery(self.plex_url, self.plex_token)}
                owners = self._instances[path]
                owners['search'] = TVSearch(owners['read'], owners['metadata'])
            return self._instances[path]
