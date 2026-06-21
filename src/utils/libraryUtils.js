export function splitLibraryTitle(title) {
  const raw = String(title || '');
  const match = raw.match(/\s+\((\d{4})\)$/);
  return {
    title: match ? raw.slice(0, match.index) : raw,
    year: match ? match[1] : ''
  };
}

export function resolutionRank(resolution) {
  const value = String(resolution || '').toLowerCase();
  if (value.includes('2160') || value.includes('4k')) return 4;
  if (value.includes('1080')) return 3;
  if (value.includes('720')) return 2;
  if (value.includes('480')) return 1;
  return 0;
}

export function isLowQuality(resolution) {
  return resolutionRank(resolution) < 3;
}

export function matchesLibraryResolutionFilter(resolution, filter) {
  const rank = resolutionRank(resolution);
  if (filter === 'all') return true;
  if (filter === '4k') return rank === 4;
  if (filter === '1080p') return rank === 3;
  if (filter === '720p') return rank === 2;
  if (filter === 'below-720p') return rank < 2;
  return true;
}

export function getMovieIdentity(item) {
  const canonical = item?.canonical_metadata || {};
  if (canonical.accepted && canonical.title) {
    return {
      title: canonical.title,
      year: String(canonical.year || '').trim()
    };
  }
  const parsed = splitLibraryTitle(item?.title);
  const plexTitle = String(item?.plex_title || '').trim();
  const title = plexTitle || parsed.title || String(item?.filename || '').replace(/\.[^.]+$/, '');
  const year = String(item?.plex_year || parsed.year || '').trim();
  return { title, year };
}

export function getTmdbCacheKey(item) {
  const identity = getMovieIdentity(item);
  const canonical = item?.canonical_metadata || {};
  return canonical?.tmdb_id ? `tmdb:${canonical.tmdb_id}` : item?.tmdb_id ? `tmdb:${item.tmdb_id}` : `${identity.title}|${identity.year}`;
}

export function normalizePersonName(name) {
  return String(name || '').trim().toLowerCase();
}

export function peopleMatch(person, filter) {
  if (!person || !filter) return false;
  const personId = String(person.id || '');
  const filterId = String(filter.id || '');
  if (personId && filterId) return personId === filterId;
  return normalizePersonName(person.name) === normalizePersonName(filter.name);
}

export function mergePeople(primary, fallback) {
  if (!primary.length) return fallback;
  if (!fallback.length) return primary;
  const merged = primary.map((person) => {
    const richMatch = fallback.find((candidate) => normalizePersonName(candidate.name) === normalizePersonName(person.name));
    if (!richMatch) return person;
    return {
      ...richMatch,
      ...person,
      id: person.id || richMatch.id,
      profile_url: person.profile_url || richMatch.profile_url,
      character: person.character || richMatch.character
    };
  });
  const existing = new Set(merged.map((person) => normalizePersonName(person.name)));
  fallback.forEach((person) => {
    const key = normalizePersonName(person.name);
    if (key && !existing.has(key)) {
      merged.push(person);
      existing.add(key);
    }
  });
  return merged;
}

export function getRolePeople(item, details, role) {
  const canonical = item?.canonical_metadata || {};
  if (role === 'director') {
    const plexDirectors = canonical.directors?.length ? canonical.directors : item?.plex_directors || [];
    const tmdbDirectors = details?.directors?.length ? details.directors : details?.director?.name ? [details.director] : [];
    return mergePeople(plexDirectors, tmdbDirectors);
  }
  const plexCast = canonical.cast?.length ? canonical.cast : item?.plex_cast || [];
  return mergePeople(plexCast, details?.cast || []);
}

export function itemMatchesRoleFilter(item, details, filter) {
  if (!filter) return true;
  return getRolePeople(item, details, filter.role).some((person) => peopleMatch(person, filter));
}

export function normalizeCollectionTitle(title) {
  return String(title || '')
    .toLowerCase()
    .replace(/[³ł]/g, ' 3 ')
    .replace(/[²]/g, ' 2 ')
    .replace(/\b(directors?|special|extended|theatrical|ultimate|final|anniversary|edition|cut|dc)\b/g, ' ')
    .replace(/[^\w\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function itemMatchesCollectionFilter(item, details, filter) {
  if (!filter) return true;
  if (Array.isArray(filter.owned_paths)) {
    const ownedPaths = new Set(filter.owned_paths.map((path) => String(path || '').toLowerCase()));
    return ownedPaths.has(String(item?.path || '').toLowerCase());
  }
  if (details?.collection?.id && String(details.collection.id) === String(filter.id)) return true;
  const identity = getMovieIdentity(item);
  const itemTitle = normalizeCollectionTitle(identity.title);
  const itemYear = String(identity.year || '');
  return (filter.parts || []).some((part) => {
    if (item?.tmdb_id && part.tmdb_id && String(item.tmdb_id) === String(part.tmdb_id)) return true;
    const partTitle = normalizeCollectionTitle(part.title);
    const partYear = String(part.year || '');
    return itemTitle === partTitle && (!partYear || !itemYear || partYear === itemYear);
  });
}

export function moviePayload(item) {
  const identity = getMovieIdentity(item);
  const canonical = item?.canonical_metadata || {};
  return {
    tmdb_id: String(canonical.tmdb_id || item?.tmdb_id || ''),
    imdb_id: String(canonical.imdb_id || item?.imdb_id || ''),
    plex_guid: String(canonical.plex_guid || item?.plex_guid || ''),
    title: identity.title || item?.title || '',
    year: identity.year || String(item?.year || '').trim(),
    path: item?.path || '',
    poster_url: canonical.poster_url || item?.plex_poster || item?.poster_url || ''
  };
}

export function movieIdentityKey(movie) {
  if (movie?.tmdb_id) return `tmdb:${movie.tmdb_id}`;
  if (movie?.path) return `path:${String(movie.path).toLowerCase()}`;
  return `title:${normalizeCollectionTitle(movie?.title)}|${String(movie?.year || '')}`;
}

export function movieIdentityKeys(movie) {
  const keys = [];
  if (movie?.tmdb_id) keys.push(`tmdb:${movie.tmdb_id}`);
  if (movie?.imdb_id) keys.push(`imdb:${String(movie.imdb_id).toLowerCase()}`);
  if (movie?.plex_guid) keys.push(`plex:${String(movie.plex_guid).toLowerCase()}`);
  if (movie?.path) keys.push(`path:${String(movie.path).toLowerCase()}`);
  const title = normalizeCollectionTitle(movie?.title);
  const year = String(movie?.year || '').trim();
  if (title && year) keys.push(`title:${title}|${year}`);
  return [...new Set(keys)];
}

export function moviesShareIdentity(left, right) {
  const leftTmdb = String(left?.tmdb_id || '');
  const rightTmdb = String(right?.tmdb_id || '');
  if (leftTmdb && rightTmdb && leftTmdb !== rightTmdb) return false;

  const leftImdb = String(left?.imdb_id || '').toLowerCase();
  const rightImdb = String(right?.imdb_id || '').toLowerCase();
  if (leftImdb && rightImdb && leftImdb !== rightImdb) return false;

  const leftPlex = String(left?.plex_guid || '').toLowerCase();
  const rightPlex = String(right?.plex_guid || '').toLowerCase();
  if (leftPlex && rightPlex && leftPlex !== rightPlex) return false;

  const rightKeys = new Set(movieIdentityKeys(right));
  return movieIdentityKeys(left).some((key) => rightKeys.has(key));
}

export function applyPosterOverrideToLibraryItems(items, selectedItem, posterUrl, override) {
  const selectedMovie = moviePayload(selectedItem);
  return (items || []).map((candidate) => {
    if (!moviesShareIdentity(selectedMovie, moviePayload(candidate))) return candidate;
    return {
      ...candidate,
      canonical_metadata: {
        ...(candidate.canonical_metadata || {}),
        poster_url: posterUrl,
        poster_override: Boolean(override?.id),
        poster_override_source: override?.source || '',
        poster_override_locked: Boolean(override?.id)
      }
    };
  });
}

export function listsForItem(item, lists) {
  const keys = new Set(movieIdentityKeys(moviePayload(item)));
  return (lists || []).filter((list) => (
    (list.movies || []).some((movie) => movieIdentityKeys(movie).some((key) => keys.has(key)))
  ));
}

export function movieHasSystemState(item, lists, systemType) {
  return listsForItem(item, lists).some((list) => (
    list.system_type === systemType || list.id === systemType
  ));
}

export function buildLibraryViewModel({
  items = [],
  pageSize = 40,
  currentPage = 1,
  query = '',
  qualityFilter = 'all',
  plexFilter = 'all',
  sortMode = 'added',
  genreFilter = 'all',
  resolutionFilter = 'all',
  sourceFilter = 'all',
  languageFilter = 'all',
  countryFilter = 'all',
  yearFrom = '',
  yearTo = '',
  minRating = 'all',
  sizeFilter = 'all',
  mode = 'movie',
  roleFilter = null,
  collectionFilter = null,
  listFilter = null,
  lists = [],
  viewingStateFilter = 'all',
  tmdbCache = {},
  showAdultMovies = true
} = {}) {
  const normalizedQuery = query.trim().toLowerCase();
  const result = items.filter((item) => {
    const canonical = item.canonical_metadata || {};
    if (mode === 'movie' && !canonical.accepted) return false;
    if (mode === 'movie' && !showAdultMovies && canonical.adult) return false;
    const identity = getMovieIdentity(item);
    const rating = Number(canonical.rating || item.plex_rating || 0);
    const year = Number(identity.year || 0);
    if (normalizedQuery) {
      const haystack = [
        identity.title,
        identity.year,
        item.filename,
        item.path,
        canonical.summary || canonical.plot || item.plex_summary,
        (canonical.genres?.length ? canonical.genres : item.plex_genres || []).join(' ')
      ].filter(Boolean).join(' ').toLowerCase();
      if (!haystack.includes(normalizedQuery)) return false;
    }
    if (qualityFilter === 'upgrade' && !isLowQuality(item.resolution)) return false;
    if (qualityFilter === 'good' && resolutionRank(item.resolution) < 3) return false;
    if (qualityFilter === '4k' && resolutionRank(item.resolution) !== 4) return false;
    if (!matchesLibraryResolutionFilter(item.resolution, resolutionFilter)) return false;
    if (sourceFilter !== 'all' && item.rip_source !== sourceFilter) return false;
    if (genreFilter !== 'all' && !(canonical.genres?.length ? canonical.genres : item.plex_genres || []).includes(genreFilter)) return false;
    if (languageFilter !== 'all' && (canonical.language || item.plex_language) !== languageFilter) return false;
    if (countryFilter !== 'all' && (canonical.country_flag || canonical.country || item.plex_country_flag || item.plex_country) !== countryFilter) return false;
    if (mode === 'file' && plexFilter === 'matched' && !item.plex_matched) return false;
    if (mode === 'file' && plexFilter === 'unmatched' && item.plex_matched) return false;
    if (mode === 'movie' && minRating !== 'all' && rating < Number(minRating)) return false;
    if (mode === 'movie' && yearFrom && (!year || year < Number(yearFrom))) return false;
    if (mode === 'movie' && yearTo && (!year || year > Number(yearTo))) return false;
    if (mode === 'file' && sizeFilter === 'small' && Number(item.size || 0) > 1.5 * 1024 * 1024 * 1024) return false;
    if (mode === 'file' && sizeFilter === 'large' && Number(item.size || 0) < 6 * 1024 * 1024 * 1024) return false;
    const details = tmdbCache[getTmdbCacheKey(item)];
    if (mode === 'movie' && roleFilter && !itemMatchesRoleFilter(item, details, roleFilter)) return false;
    if (mode === 'movie' && collectionFilter && !itemMatchesCollectionFilter(item, details, collectionFilter)) return false;
    if (mode === 'movie' && listFilter && !listsForItem(item, [listFilter]).length) return false;
    if (mode === 'movie' && viewingStateFilter !== 'all') {
      const watched = movieHasSystemState(item, lists, 'watched');
      const watchlisted = movieHasSystemState(item, lists, 'watchlist');
      if (viewingStateFilter === 'watched' && !watched) return false;
      if (viewingStateFilter === 'unwatched' && watched) return false;
      if (viewingStateFilter === 'watchlist' && !watchlisted) return false;
    }
    return true;
  });

  const filteredItems = [...result];
  filteredItems.sort((a, b) => {
    const aIdentity = getMovieIdentity(a);
    const bIdentity = getMovieIdentity(b);
    if (sortMode === 'rating') return Number(b.plex_rating || 0) - Number(a.plex_rating || 0) || aIdentity.title.localeCompare(bIdentity.title);
    if (sortMode === 'added') return Number(b.added_time || b.modified_time || 0) - Number(a.added_time || a.modified_time || 0) || aIdentity.title.localeCompare(bIdentity.title);
    if (sortMode === 'year-desc') return Number(bIdentity.year || 0) - Number(aIdentity.year || 0) || aIdentity.title.localeCompare(bIdentity.title);
    if (sortMode === 'year-asc') return Number(aIdentity.year || 0) - Number(bIdentity.year || 0) || aIdentity.title.localeCompare(bIdentity.title);
    if (sortMode === 'quality') return resolutionRank(b.resolution) - resolutionRank(a.resolution) || aIdentity.title.localeCompare(bIdentity.title);
    if (sortMode === 'size') return Number(b.size || 0) - Number(a.size || 0) || a.filename.localeCompare(b.filename);
    if (sortMode === 'plex') return Number(Boolean(b.plex_matched)) - Number(Boolean(a.plex_matched)) || a.filename.localeCompare(b.filename);
    if (sortMode === 'source') return String(a.rip_source || '').localeCompare(String(b.rip_source || '')) || a.filename.localeCompare(b.filename);
    if (sortMode === 'filename') return a.filename.localeCompare(b.filename);
    return aIdentity.title.localeCompare(bIdentity.title);
  });

  const totalPages = Math.max(1, Math.ceil(filteredItems.length / pageSize));
  const safePage = Math.min(currentPage, totalPages);
  const pageStart = filteredItems.length ? (safePage - 1) * pageSize : 0;
  const pageEnd = Math.min(pageStart + pageSize, filteredItems.length);
  const visibleItems = filteredItems.slice(pageStart, pageEnd);
  const stats = {
    total: items.length,
    low: items.filter((item) => isLowQuality(item.resolution)).length,
    matched: items.filter((item) => item.canonical_metadata?.accepted).length,
    pending: items.filter((item) => item.metadata_status === 'pending').length,
    unmatched: items.filter((item) => !item.canonical_metadata?.accepted && item.metadata_status !== 'pending').length
  };

  return {
    filteredItems,
    totalPages,
    safePage,
    pageStart,
    pageEnd,
    visibleItems,
    stats
  };
}

export function getLocaleTag(item) {
  const canonical = item?.canonical_metadata || {};
  const countryMap = {
    'United States of America': 'US',
    'United States': 'US',
    'United Kingdom': 'UK',
    'Republic of Korea': 'KR',
    'South Korea': 'KR',
    France: 'FR',
    Germany: 'DE',
    Italy: 'IT',
    Spain: 'ES',
    Japan: 'JP',
    China: 'CN',
    Canada: 'CA',
    Australia: 'AU',
    Netherlands: 'NL',
    India: 'IN',
    Egypt: 'EG'
  };
  const languageMap = {
    English: 'EN',
    Korean: 'KO',
    French: 'FR',
    German: 'DE',
    Italian: 'IT',
    Spanish: 'ES',
    Japanese: 'JA',
    Chinese: 'ZH',
    Hindi: 'HI',
    Arabic: 'AR',
    Dutch: 'NL'
  };
  const rawCountry = String(canonical.country_flag || canonical.country || item?.plex_country_flag || item?.plex_country || '').trim();
  const rawLanguage = String(canonical.language || item?.plex_language || '').trim();
  const country = countryMap[rawCountry] || (rawCountry.length <= 3 ? rawCountry.toUpperCase() : rawCountry.slice(0, 2).toUpperCase());
  const language = languageMap[rawLanguage] || (rawLanguage.length <= 3 ? rawLanguage.toUpperCase() : rawLanguage.slice(0, 2).toUpperCase());
  if (country && language) return `${country} / ${language}`;
  return country || language || '';
}

export function getQualityLabel(item) {
  return [item?.resolution, item?.rip_source].filter((part) => part && part !== 'Unknown').join(' ') || 'Unknown quality';
}

export function rootLabel(path) {
  const value = String(path || '').replace(/[\\/]+$/, '');
  const parts = value.split(/[\\/]+/).filter(Boolean);
  return parts.length ? `Root: ${parts[parts.length - 1]}` : 'Library root';
}
