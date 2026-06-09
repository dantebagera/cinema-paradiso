export function discoverMovieKey(movie) {
  return `${String(movie?.title || '').toLowerCase()}|${String(movie?.year || '')}`;
}

function normalizeMovieTitle(title) {
  return String(title || '')
    .toLowerCase()
    .replace(/[³ł]/g, ' ')
    .replace(/[²]/g, ' ')
    .replace(/[^\w\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function discoverIdentityKey(movie) {
  if (movie?.tmdb_id) return `tmdb:${String(movie.tmdb_id)}`;
  if (movie?.path) return `path:${String(movie.path).toLowerCase()}`;
  return `title:${normalizeMovieTitle(movie?.title)}|${String(movie?.year || '')}`;
}

export function discoverMoviePayload(movie, owned) {
  return {
    tmdb_id: String(movie?.tmdb_id || ''),
    title: movie?.title || '',
    year: String(movie?.year || ''),
    poster_url: movie?.poster_url || '',
    path: owned?.path || movie?.path || ''
  };
}

export function listsForDiscoverMovie(movie, lists = [], owned) {
  const key = discoverIdentityKey(discoverMoviePayload(movie, owned));
  return lists.filter((list) => (
    (list.movies || []).some((listMovie) => discoverIdentityKey(listMovie) === key)
  ));
}

export function buildOwnershipMap(results = []) {
  const map = {};
  for (const item of results) {
    if (item?.found && item.path) {
      map[discoverMovieKey(item)] = item;
    }
  }
  return map;
}

export function resolutionRank(resolution) {
  const value = String(resolution || '').toLowerCase();
  if (value.includes('2160') || value.includes('4k')) return 4;
  if (value.includes('1080')) return 3;
  if (value.includes('720')) return 2;
  if (value.includes('480')) return 1;
  return 0;
}

export function sortTorrentVariants(variants = []) {
  return [...variants].sort((a, b) => (
    resolutionRank(b.resolution) - resolutionRank(a.resolution)
    || Number(b.seeders || 0) - Number(a.seeders || 0)
    || String(a.indexer || '').localeCompare(String(b.indexer || ''))
  ));
}

export function hasTmdbMetadata(metadata = {}) {
  return Boolean(
    metadata.tmdb_id
    || metadata.poster_url
    || metadata.plot
    || metadata.tmdb_rating
    || (Array.isArray(metadata.genres) && metadata.genres.length)
  );
}

export function filterEnrichedIndexerResults(results = []) {
  return results
    .filter((row) => hasTmdbMetadata(row.metadata))
    .map((row) => {
      const metadata = row.metadata || {};
      const variants = sortTorrentVariants(row.variants || []);
      const best = variants[0] || {};
      return {
        ...row,
        ...metadata,
        title: metadata.title || row.parsed_title || row.title || '',
        year: metadata.year || row.parsed_year || row.year || '',
        parsed_title: row.parsed_title || metadata.title || '',
        parsed_year: row.parsed_year || metadata.year || '',
        variants,
        best_resolution: best.resolution || row.best_resolution || 'Unknown',
        best_seeders: Number(best.seeders || row.best_seeders || 0),
        indexer: best.indexer || row.indexer || ''
      };
    });
}
