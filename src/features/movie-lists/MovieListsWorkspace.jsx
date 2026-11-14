import DialogShell, { DialogHeader } from '../../components/ui/DialogShell.jsx';
import Button from '../../components/ui/Button.jsx';
import { Input, Select } from '../../components/ui/FormField.jsx';
import { movieDisplayTitle } from '../../utils/movieLanguage.js';
import {
  AlertTriangle, CirclePlus, Copy, Film, Loader2, RefreshCw, Search, Trash2, X
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchJson } from '../../api/client.js';
import { CATALOG_GENERATION_CHANGED_EVENT, observeCatalogGeneration } from '../../api/library.js';
import { fetchCanonicalMovieDetails, markMovieDetailsCacheStale, movieDetailsCacheKey } from '../../api/movieDetails.js';
import { addMoviePayloadsToList, announceCurationChanged, CURATION_GENERATION_CHANGED_EVENT, fetchCurationJson, fetchUserListsCached } from '../../api/curation.js';
import { previewSourceReview } from '../../api/sourceReview.js';
import ExportCopyDialog from '../../components/ExportCopyDialog.jsx';
import ListEditorModal from '../../components/ListEditorModal.jsx';
import MetadataCorrectionModal from '../../components/MetadataCorrectionModal.jsx';
import Pagination from '../../components/Pagination.jsx';
import WorkspaceEmptyState from '../../components/WorkspaceEmptyState.jsx';
import WorkspaceChrome from '../../components/WorkspaceChrome.jsx';
import WorkspaceControls from '../../components/WorkspaceControls.jsx';
import WorkspaceSelectionBar from '../../components/WorkspaceSelectionBar.jsx';
import ListsToolbar from '../../components/ListsToolbar.jsx';
import CatalogMetadataFilters from '../../components/CatalogMetadataFilters.jsx';
import { movieGenres } from '../../utils/catalogFilterOptions.js';
import { filterListRows, hasListFilterMetadata, hasListFilters, needsListMetadata } from '../../utils/listCatalogFilters.js';
import useListCatalogFilters from '../../hooks/useListCatalogFilters.js';
import SearchField from '../search/SearchField.jsx';
import SourceReviewDialog from '../../components/SourceReviewDialog.jsx';
import { DiscoverMovieCard, LibraryMovieCard } from '../../components/SharedMovieCards.jsx';
import useCardGridMetrics from '../../hooks/useCardGridMetrics.js';
import useMovieCollectionCache from '../../hooks/useMovieCollectionCache.js';
import { formatCount, movieKey } from '../../utils/appUtils.js';
import { discoverMoviePayload, listsForDiscoverMovie } from '../../discoverUtils.js';
import { applySystemListState, buildMovieListViewModel, listsForItem, movieIdentityKey, moviePayload } from '../../utils/libraryUtils.js';

export default function MovieListsWorkspace({
  mediaNavigation,
  notify,
  onPlay,
  onFindTorrent,
  onOpenTrailer,
  onStream,
  streamingAvailable,
  streamingLabel,
  followed = [],
  onFollow,
  onEditPoster,
  onOpenFileDetails,
  onOpenDiscoverPerson = () => {},
  onOpenDiscoverCollection = () => {}
}) {
  const [libraryItems, setLibraryItems] = useState([]);
  const [lists, setLists] = useState([]);
  const [selectedListId, setSelectedListId] = useState('');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const { filters, effective: effectiveFilters, countries, yearDraft, changeFilter, resetFilters } = useListCatalogFilters();
  const [projectionRevision, setProjectionRevision] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedKeys, setSelectedKeys] = useState(() => new Set());
  const [expandedKey, setExpandedKey] = useState('');
  const [detailsCache, setDetailsCache] = useState({});
  const [cardProjections, setCardProjections] = useState({});
  const [projectionFailures, setProjectionFailures] = useState(() => new Set());
  const {
    clear: clearCollectionCache,
    getView: getCollectionView,
    load: loadMovieCollection
  } = useMovieCollectionCache();
  const [listEditorTarget, setListEditorTarget] = useState(null);
  const [copyMovies, setCopyMovies] = useState(null);
  const [tmdbAddOpen, setTmdbAddOpen] = useState(false);
  const [metadataCorrection, setMetadataCorrection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [ownershipLoading, setOwnershipLoading] = useState(false);
  const [ownershipRefreshKey, setOwnershipRefreshKey] = useState(0);
  const [error, setError] = useState('');
  const [sourceReview, setSourceReview] = useState(null);
  const ownershipRequestSeq = useRef(0);
  const ownershipResolvedList = useRef(null);
  const cardProjectionInFlightKeys = useRef(new Set());
  const cardProjectionAttemptedKeys = useRef(new Set());
  const cardProjectionMounted = useRef(false);
  const projectionEpoch = useRef(0);

  useEffect(() => {
    const clearDetailCaches = () => {
      setDetailsCache(markMovieDetailsCacheStale);
      clearCollectionCache();
    };
    window.addEventListener(CATALOG_GENERATION_CHANGED_EVENT, clearDetailCaches);
    return () => window.removeEventListener(CATALOG_GENERATION_CHANGED_EVENT, clearDetailCaches);
  }, [clearCollectionCache]);

  useEffect(() => {
    const clearCurationCaches = () => {
      clearCollectionCache();
    };
    window.addEventListener(CURATION_GENERATION_CHANGED_EVENT, clearCurationCaches);
    return () => window.removeEventListener(CURATION_GENERATION_CHANGED_EVENT, clearCurationCaches);
  }, [clearCollectionCache]);

  const displayLists = useMemo(() => {
    const following = {
      id: 'following',
      name: 'Following',
      system_type: 'following',
      movies: followed
    };
    const next = [...lists];
    const watchlistIndex = next.findIndex((list) => list.id === 'watchlist' || list.system_type === 'watchlist');
    next.splice(watchlistIndex >= 0 ? watchlistIndex + 1 : 0, 0, following);
    return next;
  }, [followed, lists]);
  const selectedList = displayLists.find((list) => list.id === selectedListId) || displayLists[0] || null;
  const baseModel = useMemo(() => buildMovieListViewModel({
    libraryItems,
    list: selectedList,
    query,
    statusFilter
  }), [libraryItems, selectedList, query, statusFilter]);
  const model = useMemo(() => ({ ...baseModel, rows: filterListRows(baseModel.rows, effectiveFilters, movieGenres, row => {
    if (row.ownedItem) {
      const item = row.ownedItem;
      return { popularity: cardProjections[row.identityKey]?.popularity, ...item, genres: item.plex_genres || [], country: item.plex_country, country_flag: item.plex_country_flag, rating: item.plex_rating, ...item.canonical_metadata, ...row.ownedPayload };
    }
    return { ...row.movie, ...cardProjections[row.identityKey] };
  }) }), [baseModel, effectiveFilters, cardProjections]);
  const {
    gridRef: movieListsGridRef,
    pageSize: movieListsPageSize
  } = useCardGridMetrics({ target: 40, max: 200, bias: 'lower' });
  const movieListsTotalPages = Math.max(1, Math.ceil(model.rows.length / movieListsPageSize));
  const movieListsPage = Math.min(currentPage, movieListsTotalPages);
  const movieListsPageStart = (movieListsPage - 1) * movieListsPageSize;
  const visibleMovieListRows = model.rows.slice(movieListsPageStart, movieListsPageStart + movieListsPageSize);
  const movieListPaginationProps = {
    total: model.rows.length,
    page: movieListsPage,
    totalPages: movieListsTotalPages,
    pageStart: movieListsPageStart,
    pageEnd: Math.min(movieListsPageStart + movieListsPageSize, model.rows.length),
    ariaLabel: 'Movie list pagination',
    onPageChange: setCurrentPage
  };
  const selectedRows = model.rows.filter((row) => selectedKeys.has(row.identityKey));
  const allRowsSelected = model.rows.length > 0 && model.rows.every((row) => selectedKeys.has(row.identityKey));
  const selectedListIsSystem = Boolean(selectedList?.system_type);
  const selectedListIsFollowing = selectedList?.system_type === 'following';
  const selectedCopyMovies = selectedRows.map((row) => (row.ownedItem ? moviePayload(row.ownedItem) : movieListRowMovie(row)));
  const missingCardProjectionMovies = useMemo(() => {
    const seen = new Set();
    const candidates = needsListMetadata(effectiveFilters) ? baseModel.rows : visibleMovieListRows;
    return candidates.filter((row) => !row.ownedItem || effectiveFilters.sort === 'popularity.desc').flatMap((row) => {
      const movie = movieListRowMovie(row);
      const key = movieIdentityKey(movie);
      if (seen.has(key)) return [];
      seen.add(key);
      return [{
        key,
        tmdb_id: String(movie.tmdb_id || row.tmdb_id || '').trim(),
        poster_url: movie.poster_url || '',
        metadata: movie,
        owned: Boolean(row.ownedItem),
      }];
    });
  }, [baseModel.rows, model.rows, effectiveFilters, movieListsPageStart, movieListsPageSize]);
  function projectionComplete(movie, projection = cardProjections[movie.key]) {
    if (movie.owned) return hasListFilterMetadata(projection, { sort: 'popularity.desc' });
    return Boolean(projection) && (!needsListMetadata(effectiveFilters) || hasListFilterMetadata({ ...movie.metadata, ...projection }, effectiveFilters));
  }
  const metadataPending = needsListMetadata(effectiveFilters) && missingCardProjectionMovies.some(movie => movie.tmdb_id && !projectionComplete(movie) && !cardProjectionAttemptedKeys.current.has(movie.key));
  const failedFilterMovies = needsListMetadata(effectiveFilters) ? missingCardProjectionMovies.filter(movie =>
    !projectionComplete(movie) && (!movie.tmdb_id || projectionFailures.has(movie.key))) : [];
  const metadataIncomplete = metadataPending || failedFilterMovies.length > 0;

  function retryFilterMetadata() {
    const retryKeys = new Set(failedFilterMovies.map(movie => movie.key));
    retryKeys.forEach(key => cardProjectionAttemptedKeys.current.delete(key));
    setProjectionFailures(current => new Set([...current].filter(key => !retryKeys.has(key))));
    setProjectionRevision(value => value + 1);
  }

  function clearFilters() { resetFilters(); setStatusFilter('all'); }

  const loadMovieLists = useCallback(async (options = {}) => {
    const forceLists = Boolean(options?.forceLists);
    setLoading(true);
    setError('');
    try {
      const listsData = await fetchUserListsCached({ force: forceLists });
      const nextLists = listsData.lists || [];
      setLists(nextLists);
      setSelectedListId((current) => (
        current === 'following' || nextLists.some((list) => list.id === current)
          ? current
          : nextLists[0]?.id || 'following'
      ));
    } catch (loadError) {
      setError(loadError.message);
      notify?.(`Movie lists unavailable: ${loadError.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    loadMovieLists();
    window.addEventListener('cp-curation-changed', loadMovieLists);
    const refreshOwnership = () => {
      setDetailsCache({});
      setCardProjections({});
      cardProjectionInFlightKeys.current.clear();
      cardProjectionAttemptedKeys.current.clear();
      setOwnershipRefreshKey((value) => value + 1);
    };
    window.addEventListener('cp-library-changed', refreshOwnership);
    window.addEventListener('cp-library-reconciled', refreshOwnership);
    return () => {
      window.removeEventListener('cp-curation-changed', loadMovieLists);
      window.removeEventListener('cp-library-changed', refreshOwnership);
      window.removeEventListener('cp-library-reconciled', refreshOwnership);
    };
  }, [loadMovieLists]);

  useEffect(() => {
    const requestSeq = ownershipRequestSeq.current + 1;
    ownershipRequestSeq.current = requestSeq;
    ownershipResolvedList.current = null;
    if (!selectedList) {
      setLibraryItems([]);
      setOwnershipLoading(false);
      return;
    }
    const movies = selectedList.movies || [];
    if (!movies.length) {
      ownershipResolvedList.current = selectedList;
      setLibraryItems([]);
      setOwnershipLoading(false);
      return;
    }
    let cancelled = false;
    setOwnershipLoading(true);
    fetchJson('/api/library/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movies, include_items: true })
    }).then((data) => {
      if (cancelled || requestSeq !== ownershipRequestSeq.current) return;
      ownershipResolvedList.current = selectedList;
      if (observeCatalogGeneration(data.catalog_generation)) {
        setDetailsCache({});
        setCardProjections({});
        cardProjectionInFlightKeys.current.clear();
        cardProjectionAttemptedKeys.current.clear();
      }
      setLibraryItems((data.results || []).map((result) => result.library_item).filter(Boolean));
      setError('');
    }).catch((ownershipError) => {
      if (cancelled || requestSeq !== ownershipRequestSeq.current) return;
      setLibraryItems([]);
      setError(ownershipError.message);
      notify?.(`Movie list ownership unavailable: ${ownershipError.message}`, 'error');
    }).finally(() => {
      if (!cancelled && requestSeq === ownershipRequestSeq.current) setOwnershipLoading(false);
    });
    return () => { cancelled = true; };
  }, [selectedList, ownershipRefreshKey, notify]);

  useEffect(() => {
    setSelectedKeys(new Set());
    setExpandedKey('');
    setCurrentPage(1);
  }, [selectedListId, query, statusFilter, filters]);

  useEffect(() => {
    cardProjectionMounted.current = true;
    return () => {
      cardProjectionMounted.current = false;
    };
  }, []);

  useEffect(() => {
    projectionEpoch.current += 1;
    cardProjectionInFlightKeys.current.clear();
    cardProjectionAttemptedKeys.current.clear();
    setProjectionFailures(new Set());
    return () => { projectionEpoch.current += 1; };
  }, [selectedList, ownershipRefreshKey, effectiveFilters]);

  useEffect(() => {
    // Wait for the authoritative ownership projection before enriching unowned
    // cards. Owned cards already have SQL metadata and must not call TMDB.
    if (ownershipLoading || ownershipResolvedList.current !== selectedList) return;
    const movies = missingCardProjectionMovies
      .filter((movie) => movie.tmdb_id && !projectionComplete(movie) && !cardProjectionInFlightKeys.current.has(movie.key) && !cardProjectionAttemptedKeys.current.has(movie.key))
      .slice(0, 50);
    if (!movies.length) return undefined;
    const epoch = projectionEpoch.current;
    const active = () => cardProjectionMounted.current && projectionEpoch.current === epoch;

    movies.forEach((movie) => cardProjectionInFlightKeys.current.add(movie.key));
    fetchJson('/api/tmdb/card-projections', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movies })
    }).catch(() => ({ items: {} })).then(async (data) => {
      if (!active()) return;
      if (observeCatalogGeneration(data.catalog_generation)) {
        setDetailsCache({});
      }
      const items = data.items || {};
      if (Object.keys(items).length) {
        setCardProjections((current) => ({ ...current, ...items }));
        setProjectionFailures(current => new Set([...current].filter(key => !movies.some(movie => movie.key === key && projectionComplete(movie, items[key])))));
      }
      // Saved list entries contain identity and poster only. Cached projections are
      // best-effort; hydrate uncached visible cards through the existing detail API.
      const incomplete = movies.filter(movie => !projectionComplete(movie, items[movie.key]));
      // Owned display remains SQL-authoritative. Popularity is supplemental:
      // use its existing local cache, without calling a provider for owned rows.
      const ownedMissing = incomplete.filter(movie => movie.owned);
      ownedMissing.forEach(movie => cardProjectionAttemptedKeys.current.add(movie.key));
      if (ownedMissing.length) setProjectionFailures(current => new Set([...current, ...ownedMissing.map(movie => movie.key)]));
      const missing = incomplete.filter(movie => !movie.owned && movie.tmdb_id);
      let next = 0;
      await Promise.all(Array.from({ length: Math.min(3, missing.length) }, async () => {
        while (active() && next < missing.length) {
          const movie = missing[next++];
          try {
            const details = await fetchCanonicalMovieDetails(movie);
            if (!active()) return;
            if (!details) throw new Error('Movie metadata was unavailable');
            setCardProjections(current => ({ ...current, [movie.key]: details }));
            setDetailsCache(current => ({ ...current, [movieDetailsCacheKey(movie)]: details }));
            if (!projectionComplete(movie, details)) throw new Error('Required filter metadata was unavailable');
          } catch {
            if (active()) setProjectionFailures(current => new Set([...current, movie.key]));
          } finally {
            if (active()) cardProjectionAttemptedKeys.current.add(movie.key);
          }
        }
      }));
    }).catch(() => {
      // Preserve the saved list if best-effort card enrichment fails.
    }).finally(() => {
      if (!active()) return;
      movies.forEach((movie) => cardProjectionInFlightKeys.current.delete(movie.key));
      if (cardProjectionMounted.current) setProjectionRevision(value => value + 1);
    });
  }, [missingCardProjectionMovies, cardProjections, projectionRevision, ownershipLoading, selectedList, effectiveFilters]);

  function toggleRow(row, checked) {
    setSelectedKeys((current) => {
      const next = new Set(current);
      if (checked) next.add(row.identityKey);
      else next.delete(row.identityKey);
      return next;
    });
  }

  function selectAllVisible() {
    setSelectedKeys(new Set(model.rows.map((row) => row.identityKey)));
  }

  function clearSelection() {
    setSelectedKeys(new Set());
  }

  function movieListRowMovie(row) {
    return row.movie || {
      tmdb_id: row.tmdb_id || '',
      imdb_id: row.imdb_id || '',
      title: row.title,
      year: row.year,
      poster_url: row.poster_url
    };
  }

  async function loadMovieListDetails(row) {
    const movie = movieListRowMovie(row);
    const owned = row.ownedItem || null;
    const cacheKey = movieDetailsCacheKey(movie, owned);
    if (!cacheKey) return null;
    let details = detailsCache[cacheKey];
    if (!details || details.stale) {
      setDetailsCache((state) => ({ ...state, [cacheKey]: { loading: true, cast: [], directors: [], collection: {}, trailer_url: '' } }));
      try {
        details = await fetchCanonicalMovieDetails(movie, owned);
        setDetailsCache((state) => ({ ...state, [cacheKey]: details }));
      } catch (detailsError) {
        details = { error: detailsError.message, cast: [], directors: [], collection: {}, trailer_url: '' };
        setDetailsCache((state) => ({ ...state, [cacheKey]: details }));
      }
    }
    loadMovieCollection(details);
    return details;
  }

  function toggleMovieListDetails(row) {
    const nextKey = expandedKey === row.identityKey ? '' : row.identityKey;
    setExpandedKey(nextKey);
    if (nextKey) loadMovieListDetails(row);
  }

  async function openMovieListTrailer(row) {
    const movie = movieListRowMovie(row);
    const projection = cardProjections[movieIdentityKey(movie)];
    try {
      const details = await loadMovieListDetails(row);
      onOpenTrailer(movie, details?.trailer_url || projection?.trailer_url || '');
    } catch {
      onOpenTrailer(movie, projection?.trailer_url || '');
    }
  }

  async function createList(name) {
    const created = await fetchCurationJson('/api/user/lists', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    setSelectedListId(created.id);
    await loadMovieLists({ forceLists: true });
    announceCurationChanged();
    notify?.(`List created: ${created.name}`);
    return created;
  }

  async function renameSelectedList(name) {
    if (!selectedList || selectedListIsSystem || !name.trim()) return;
    const renamed = await fetchCurationJson(`/api/user/lists/${encodeURIComponent(selectedList.id)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim() })
    });
    await loadMovieLists({ forceLists: true });
    announceCurationChanged();
    notify?.(`List renamed: ${renamed.name}`);
  }

  async function deleteSelectedList() {
    if (!selectedList || selectedListIsSystem) return;
    if (!window.confirm(`Delete list "${selectedList.name}"? Movies will not be deleted from Library.`)) return;
    await fetchCurationJson(`/api/user/lists/${encodeURIComponent(selectedList.id)}`, { method: 'DELETE' });
    setSelectedListId('');
    await loadMovieLists({ forceLists: true });
    announceCurationChanged();
    notify?.('List deleted');
  }

  async function addMovieToList(listId, item) {
    const movie = item?.ownedItem ? moviePayload(item.ownedItem) : moviePayload(item);
    await fetchCurationJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie })
    });
    await loadMovieLists({ forceLists: true });
    announceCurationChanged();
    notify?.('Movie added to list');
  }

  async function addMoviesToList(listId, movies) {
    await addMoviePayloadsToList(listId, movies.map((movie) => moviePayload(movie)));
    await loadMovieLists({ forceLists: true });
    announceCurationChanged();
    notify?.(`${formatCount(movies.length)} movie${movies.length === 1 ? '' : 's'} added to list`);
  }

  async function removeMovieFromList(listId, movie) {
    await fetchCurationJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie })
    });
    await loadMovieLists({ forceLists: true });
    announceCurationChanged();
    notify?.('Movie removed from list');
  }

  async function removeSelectedFromActiveList() {
    if (!selectedList || !selectedRows.length) return;
    if (selectedListIsFollowing) {
      for (const row of selectedRows) {
        await onFollow(movieListRowMovie(row));
      }
      setSelectedKeys(new Set());
      notify?.(`${formatCount(selectedRows.length)} movie${selectedRows.length === 1 ? '' : 's'} unfollowed`);
      return;
    }
    for (const row of selectedRows) {
      await removeMovieFromList(selectedList.id, row.ownedItem ? moviePayload(row.ownedItem) : movieListRowMovie(row));
    }
    setSelectedKeys(new Set());
    notify?.(`${formatCount(selectedRows.length)} movie${selectedRows.length === 1 ? '' : 's'} removed from ${selectedList.name}`);
  }

  async function addTmdbMovieToSelectedList(movie) {
    if (!selectedList) return;
    if (selectedListIsFollowing) {
      if (!followed.some((item) => movieKey(item) === movieKey(movie))) await onFollow(movie);
      setTmdbAddOpen(false);
      return;
    }
    await addMovieToList(selectedList.id, movie);
    setTmdbAddOpen(false);
  }

  async function toggleMovieListSystemList(systemType, row) {
    const owned = row.ownedItem ? moviePayload(row.ownedItem) : null;
    const movie = movieListRowMovie(row);
    const payload = discoverMoviePayload(movie, owned);
    const currentLists = row.ownedItem ? listsForItem(row.ownedItem, lists) : listsForDiscoverMovie(movie, lists, owned);
    const active = currentLists.some((list) => list.system_type === systemType || list.id === systemType);
    const nextActive = !active;
    setLists((current) => applySystemListState(current, systemType, payload, nextActive));
    try {
      await fetchCurationJson(`/api/user/system-lists/${encodeURIComponent(systemType)}/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ movie: payload, active: nextActive })
      });
    } catch (error) {
      setLists((current) => applySystemListState(current, systemType, payload, active));
      notify?.(error.message, 'error');
      return;
    }
    notify?.(`${row.title} ${active ? 'removed from' : 'added to'} ${systemType === 'watched' ? 'Watched' : 'Watchlist'}`);
  }

  function selectListFromCard(list) {
    if (list?.id) setSelectedListId(list.id);
  }

  async function openSelectedSourceReview() {
    if (!selectedRows.length) {
      notify?.('Select movies before finding sources.', 'neutral');
      return;
    }
    setSourceReview({ loading: true, rows: [], error: '', title: 'Find sources' });
    try {
      const data = await previewSourceReview(selectedRows.map((row) => ({
        tmdb_id: row.tmdb_id || row.ownedPayload?.tmdb_id || '',
        imdb_id: row.imdb_id || row.ownedPayload?.imdb_id || '',
        title: row.title,
        year: row.year,
        poster_url: row.poster_url,
        path: row.ownedItem?.path || ''
      })));
      setSourceReview({
        loading: false,
        rows: data.rows || [],
        blocked: data.blocked || [],
        defaults: data.defaults || {},
        error: '',
        title: 'Find sources'
      });
    } catch (previewError) {
      setSourceReview((current) => ({ ...current, loading: false, error: previewError.message }));
    }
  }

  return (
    <section className="library-workspace movie-lists-workspace">
      <WorkspaceChrome navigation={mediaNavigation}>
        <ListsToolbar
          lists={displayLists} selectedList={selectedList} onSelect={setSelectedListId}
          onCreate={createList} onRename={renameSelectedList} onDelete={deleteSelectedList}
          onAdd={() => setTmdbAddOpen(true)}
        />
        <WorkspaceControls loadedCount={model.stats.total} countLabel="movies" selectedCount={selectedRows.length}
          autoCollapseKey={expandedKey}
          summary={hasListFilters(filters) ? `${formatCount(model.rows.length)} ${metadataIncomplete ? 'matches so far' : 'matches'}` : statusFilter === 'all' ? 'All' : statusFilter === 'upgrade' ? 'Upgrade candidates' : statusFilter === 'owned' ? 'Owned' : 'Missing'}
          notice={yearDraft.error && <p role="alert" id="movie-list-year-error">{yearDraft.error}</p>}
          search={<form className="library-search-panel workspace-search-form movie-lists-search" onSubmit={event => event.preventDefault()}>
            <SearchField className="library-main-search" onClear={query ? () => setQuery('') : undefined}>
              <Search size={18}/><Input aria-label="Search movie list" value={query} onChange={event => setQuery(event.target.value)} placeholder={`Search ${selectedList?.name || 'the selected list'}...`} />
            </SearchField>
            <Button variant="primary" type="submit" className="library-search-submit"><Search size={16}/> Search</Button>
          </form>}
          filters={<div className="workspace-filter-grid lists-filter-row">
            <Select aria-label="Movie list status" value={statusFilter} onChange={event => setStatusFilter(event.target.value)}>
              <option value="all">All movies</option><option value="owned">Owned</option><option value="missing">Missing</option><option value="upgrade">Upgrade candidates</option>
            </Select>
            <CatalogMetadataFilters values={filters} countries={countries} onChange={changeFilter} yearError={yearDraft.error} yearErrorId="movie-list-year-error" />
            <span className="lists-ownership-summary">{formatCount(model.stats.owned)} owned · {formatCount(model.stats.missing)} missing · {formatCount(model.stats.upgrades)} upgrades</span>
            <Button type="button" className="lists-filter-icon" aria-label="Clear filters" title="Clear filters" disabled={statusFilter === 'all' && !hasListFilters(filters)} onClick={clearFilters}><X size={16}/></Button>
            <Button type="button" className="lists-filter-icon" aria-label="Refresh movie lists" title="Refresh list" disabled={loading || ownershipLoading} onClick={() => { cardProjectionAttemptedKeys.current.clear(); setProjectionFailures(new Set()); setCardProjections({}); loadMovieLists({ forceLists: true }); setOwnershipRefreshKey(value => value + 1); }}><RefreshCw size={16}/></Button>
          </div>}
          selection={model.rows.length > 0 && <WorkspaceSelectionBar noun="movies" selectedCount={selectedRows.length}
            allSelected={allRowsSelected} onToggleAll={checked => checked ? selectAllVisible() : clearSelection()}
            label="Select all visible list movies" onClear={clearSelection}/>} />
        {selectedRows.length > 0 && <div className="bulk-selection-bar lists-active-selection" role="region" aria-label="Selected movie actions">
          <strong>{formatCount(selectedRows.length)} selected</strong>
          <Button size="compact" type="button"  onClick={clearSelection}>Clear</Button>
          <Button size="compact" type="button"  onClick={() => setCopyMovies(selectedCopyMovies)}><Copy size={13}/> Copy selected to...</Button>
          <Button variant="danger" size="compact" type="button"  onClick={removeSelectedFromActiveList} disabled={!selectedList}><Trash2 size={13}/> Remove selected</Button>
          <Button variant="source" size="compact" type="button"  onClick={openSelectedSourceReview}><Search size={13}/> Find sources</Button>
        </div>}
      </WorkspaceChrome>
      <div className="movie-lists-main">
        {metadataPending && <p role="status">Loading list metadata to find all matches…</p>}
        {failedFilterMovies.length > 0 && <p role="alert">Some titles could not be checked ({failedFilterMovies.length}). Filter results are incomplete. <Button size="compact" type="button"  onClick={retryFilterMetadata} disabled={!failedFilterMovies.some(movie => movie.tmdb_id)}>Retry filter metadata</Button></p>}
          {error ? <div className="library-status library-status-error"><AlertTriangle size={16} /> {error}</div> : null}
          {loading || ownershipLoading ? (
            <WorkspaceEmptyState size="compact" ><strong>{loading ? 'Loading movie lists...' : 'Checking selected list...'}</strong><span>{loading ? 'Reading saved lists.' : 'Matching this list against Library ownership.'}</span></WorkspaceEmptyState>
          ) : selectedList ? (
            model.rows.length ? (
              <>
                <Pagination {...movieListPaginationProps} />
                <div ref={movieListsGridRef} className="library-results library-movie-results movie-lists-card-grid">
                {visibleMovieListRows.map((row) => {
                  const movie = movieListRowMovie(row);
                  const projection = !row.ownedItem ? cardProjections[movieIdentityKey(movie)] : null;
                  const cardMovie = projection ? {
                    ...movie,
                    ...projection,
                    poster_url: projection.poster_url || movie.poster_url || '',
                  } : movie;
                  const details = detailsCache[movieDetailsCacheKey(movie, row.ownedItem)] || null;
                  const cardDetails = projection
                    ? { ...projection, ...(!details?.loading && !details?.error ? details : {}) }
                    : details;
                  const collectionView = getCollectionView(cardDetails);
                  const rowLists = row.ownedItem ? listsForItem(row.ownedItem, lists) : listsForDiscoverMovie(movie, lists, null);
                  const watched = rowLists.some((list) => list.system_type === 'watched');
                  const watchlisted = rowLists.some((list) => list.system_type === 'watchlist');
                  if (row.ownedItem) {
                    return (
                      <LibraryMovieCard
                        key={row.identityKey}
                        item={row.ownedItem}
                        followed={followed.some((item) => movieKey(item) === movieKey(cardMovie))}
                        expanded={expandedKey === row.identityKey}
                        details={details}
                        collection={collectionView.data}
                        collectionStatus={collectionView.status}
                        collectionError={collectionView.error}
                        itemLists={rowLists}
                        onToggle={() => toggleMovieListDetails(row)}
                        onPlay={onPlay}
                        onFindTorrent={onFindTorrent}
                        onTrailer={() => openMovieListTrailer(row)}
                        onPersonFilter={(role, person) => onOpenDiscoverPerson(moviePayload(row.ownedItem), role, person)}
                        onPersonDiscover={(movie, role, person) => onOpenDiscoverPerson(movie, role, person, { fullFilmography: true })}
                        onPersonAwardDiscover={(movie, role, person, award) => onOpenDiscoverPerson(movie, role, person, { award })}
                        onCollectionBrowse={(collection) => onOpenDiscoverCollection(moviePayload(row.ownedItem), collection)}
                        onCollectionRetry={() => loadMovieCollection(cardDetails, { force: true })}
                        onListFilter={selectListFromCard}
                        onEditLists={() => setListEditorTarget({ item: row.ownedItem })}
                        onRemoveFromList={(listId) => removeMovieFromList(listId, moviePayload(row.ownedItem))}
                        onEditPoster={onEditPoster ? () => onEditPoster(row.ownedItem, movie) : undefined}
                        onCorrectMetadata={() => setMetadataCorrection(row.ownedItem)}
                        onOpenFileDetails={onOpenFileDetails}
                        watched={watched}
                        watchlisted={watchlisted}
                        onToggleWatched={() => toggleMovieListSystemList('watched', row)}
                        onToggleWatchlist={() => toggleMovieListSystemList('watchlist', row)}
                        selected={selectedKeys.has(row.identityKey)}
                        onSelect={(checked) => toggleRow(row, checked)}
                      />
                    );
                  }
                  return (
                    <DiscoverMovieCard
                      key={row.identityKey}
                      movie={cardMovie}
                      owned={null}
                      followed={followed.some((item) => movieKey(item) === movieKey(cardMovie))}
                      expanded={expandedKey === row.identityKey}
                      details={cardDetails}
                      collection={collectionView.data}
                      collectionStatus={collectionView.status}
                      collectionError={collectionView.error}
                      itemLists={rowLists}
                      watched={watched}
                      watchlisted={watchlisted}
                      onToggleWatchlist={() => toggleMovieListSystemList('watchlist', row)}
                      selected={selectedKeys.has(row.identityKey)}
                      onSelect={(checked) => toggleRow(row, checked)}
                      onPlay={onPlay}
                      onStream={onStream}
                      streamingAvailable={streamingAvailable}
                      streamingLabel={streamingLabel}
                      onFindTorrent={onFindTorrent}
                      onFollow={onFollow}
                      onTrailer={() => openMovieListTrailer(row)}
                      onToggleDetails={() => toggleMovieListDetails(row)}
                      onPersonBrowse={(role, person) => onOpenDiscoverPerson(cardMovie, role, person)}
                      onPersonDiscover={(role, person) => onOpenDiscoverPerson(cardMovie, role, person, { fullFilmography: true })}
                      onPersonAwardDiscover={(role, person, award) => onOpenDiscoverPerson(cardMovie, role, person, { award })}
                      onCollectionBrowse={(collection) => onOpenDiscoverCollection(cardMovie, collection)}
                      onCollectionRetry={() => loadMovieCollection(cardDetails, { force: true })}
                      onListBrowse={selectListFromCard}
                      onEditLists={() => setListEditorTarget(movie)}
                      onRemoveFromList={(listId) => removeMovieFromList(listId, movie)}
                    />
                  );
                })}
                </div>
                <Pagination {...movieListPaginationProps} ariaLabel="Movie list page controls below results" />
              </>
            ) : (
              !error && (model.stats.total > 0 ? (
                <WorkspaceEmptyState title={metadataIncomplete ? metadataPending ? 'Finding matching movies…' : 'Filter results are incomplete.' : 'No movies match this list view.'} description={metadataIncomplete ? 'Some titles still need metadata before all matches can be determined.' : 'Clear the search and filters to see the full list.'}>
                  <Button variant="primary" type="button"  onClick={() => { setQuery(''); clearFilters(); setCurrentPage(1); }}>Clear filters</Button>
                </WorkspaceEmptyState>
              ) : selectedListIsFollowing ? (
                <WorkspaceEmptyState title="You're not following any movies yet." description="Follow a movie from Discover to track it here." />
              ) : selectedList.system_type === 'watched' ? (
                <WorkspaceEmptyState title="No watched movies yet." description="Movies you mark as watched appear here." />
              ) : (
                <WorkspaceEmptyState
                  title={selectedList.system_type === 'watchlist' ? 'Your Watchlist is empty.' : 'This list is empty.'}
                  description={selectedList.system_type === 'watchlist' ? 'Save movies you want to watch here.' : 'Add a movie to start building this list.'}
                >
                  <Button variant="primary" type="button"  onClick={() => setTmdbAddOpen(true)}>Add movie</Button>
                </WorkspaceEmptyState>
              ))
            )
          ) : (
            !error && <WorkspaceEmptyState title="Select a list to get started." description="Choose a list above, or create a new one." />
          )}
      </div>

      {sourceReview && (
        <SourceReviewDialog
          state={sourceReview}
          setState={setSourceReview}
          onClose={() => setSourceReview(null)}
          notify={notify}
        />
      )}
      {listEditorTarget && (
        <ListEditorModal
          item={listEditorTarget.item || listEditorTarget}
          bulkItems={listEditorTarget.bulkItems || []}
          items={libraryItems}
          lists={lists}
          onClose={() => setListEditorTarget(null)}
          onCreate={createList}
          onAdd={addMovieToList}
          onAddBulk={addMoviesToList}
        />
      )}
      {copyMovies && (
        <ExportCopyDialog
          movies={copyMovies}
          onClose={() => setCopyMovies(null)}
          notify={notify}
        />
      )}
      {tmdbAddOpen && selectedList && (
        <TmdbListAddDialog
          list={selectedList}
          onAdd={addTmdbMovieToSelectedList}
          onClose={() => setTmdbAddOpen(false)}
        />
      )}
      {metadataCorrection && (
        <MetadataCorrectionModal
          item={metadataCorrection}
          notify={notify}
          resetLabel="Reset to provider metadata"
          onClose={() => setMetadataCorrection(null)}
          onSaved={() => loadMovieLists()}
        />
      )}
    </section>
  );
}

function TmdbListAddDialog({ list, onAdd, onClose }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [addingKey, setAddingKey] = useState('');

  async function searchTmdb(event) {
    event.preventDefault();
    const search = query.trim();
    if (!search) return;
    setLoading(true);
    setError('');
    setResults([]);
    try {
      const data = await fetchJson(`/api/tmdb/search?q=${encodeURIComponent(search)}&page=1&include_adult=false`);
      setResults((data.results || []).slice(0, 12));
    } catch (searchError) {
      setError(searchError.message);
    } finally {
      setLoading(false);
    }
  }

  async function addResult(movie) {
    const key = String(movie.tmdb_id || movieIdentityKey(movie));
    setAddingKey(key);
    setError('');
    try {
      await onAdd(movie);
    } catch (addError) {
      setError(addError.message);
      setAddingKey('');
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <DialogShell size="wide" className="torrent-dialog tmdb-list-add-dialog" role="dialog" aria-modal="true" aria-label={`Add movie to ${list.name}`} onClick={(event) => event.stopPropagation()}>
        <DialogHeader >
          <div>
            <p className="screen-kicker">Add movie</p>
            <h2>{list.name}</h2>
          </div>
          <Button size="icon" type="button" className="inspector-close" onClick={onClose} aria-label="Close add movie dialog">
            <X size={18} />
          </Button>
        </DialogHeader>
        <form className="library-search-panel tmdb-list-add-search" onSubmit={searchTmdb}>
          <SearchField className="library-main-search">
            <Search size={17} />
            <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search TMDB movies..." />
          </SearchField>
          <Button variant="primary" type="submit"  disabled={!query.trim() || loading}>
            {loading ? <Loader2 size={15} className="spin" /> : <Search size={15} />} Search
          </Button>
        </form>
        {error ? <p className="settings-inline-status settings-inline-error"><AlertTriangle size={15} /><span>{error}</span></p> : null}
        <div className="tmdb-list-add-results">
          {results.length ? results.map((movie) => {
            const key = String(movie.tmdb_id || movieIdentityKey(movie));
            return (
              <article className="tmdb-list-add-row" key={key}>
                <span className="match-result-poster">
                  {movie.poster_url ? <img src={movie.poster_url} alt="" loading="lazy" /> : <Film size={18} />}
                </span>
                <div>
                  <strong dir="auto">{movieDisplayTitle(movie) || 'Untitled'}</strong>
                  <span>{movie.year || 'Unknown year'}</span>
                  <small>{movie.plot || 'No plot summary available.'}</small>
                </div>
                <Button type="button"  onClick={() => addResult(movie)} disabled={Boolean(addingKey)}>
                  {addingKey === key ? <Loader2 size={15} className="spin" /> : <CirclePlus size={15} />} Add to list
                </Button>
              </article>
            );
          }) : (
            <WorkspaceEmptyState size="compact" >
              <strong>Search TMDB to add a movie.</strong>
              <span>Owned movies will render as Library cards after they match your archive; missing movies stay Discover-style.</span>
            </WorkspaceEmptyState>
          )}
        </div>
      </DialogShell>
    </div>
  );
}
