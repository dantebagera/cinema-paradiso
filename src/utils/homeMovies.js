function homeMovieKey(movie) {
  const tmdbId = String(movie?.tmdb_id || movie?.id || '').trim();
  if (tmdbId) return `tmdb:${tmdbId}`;
  return [
    String(movie?.title || '').trim().toLocaleLowerCase(),
    String(movie?.year || '').trim()
  ].join('|');
}

export const HOME_UPCOMING_PREVIEW_SIZE = 20;

// The Upcoming API owns release eligibility; Home owns presentation only.
export function buildUpcomingHomeMovies(results, excludedMovies = []) {
  const excluded = new Set((excludedMovies || []).map(homeMovieKey));
  const seen = new Set();

  return (results || [])
    .filter((movie) => {
      const key = homeMovieKey(movie);
      if (!key || seen.has(key) || excluded.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, HOME_UPCOMING_PREVIEW_SIZE)
    .sort((left, right) => (
      String(left.release_date || '').localeCompare(String(right.release_date || ''))
      || Number(right.popularity || 0) - Number(left.popularity || 0)
      || String(left.title || '').localeCompare(String(right.title || ''))
    ));
}

export function uniqueHomeMovies(...groups) {
  const seen = new Set();
  return groups.flat().filter((movie) => {
    const key = homeMovieKey(movie);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
