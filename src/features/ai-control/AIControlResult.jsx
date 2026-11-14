import Pagination from '../../components/Pagination.jsx';
import Button from '../../components/ui/Button.jsx';
import { Input } from '../../components/ui/FormField.jsx';
import WorkspaceEmptyState from '../../components/WorkspaceEmptyState.jsx';
import AIControlSelectionBar from './AIControlSelectionBar.jsx';
import { AlertTriangle, Bot, Check, CirclePlus, Loader2, Search, Sparkles, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchJson } from '../../api/client.js';
import { CATALOG_GENERATION_CHANGED_EVENT, fetchOwnershipChecks } from '../../api/library.js';
import { fetchCanonicalMovieDetails, markMovieDetailsCacheStale, movieDetailsCacheKey } from '../../api/movieDetails.js';
import { addMoviePayloadsToList, announceCurationChanged, clearUserListsCache, CURATION_GENERATION_CHANGED_EVENT, fetchCurationJson, fetchUserListsCached } from '../../api/curation.js';
import { previewSourceReview } from '../../api/sourceReview.js';
import DiscoverResultGrid from '../../components/DiscoverResultGrid.jsx';
import ExperimentalBadge from '../../components/ExperimentalBadge.jsx';
import ListEditorModal from '../../components/ListEditorModal.jsx';
import SelectionCheckbox from '../../components/SelectionCheckbox.jsx';
import SourceReviewDialog from '../../components/SourceReviewDialog.jsx';
import { DiscoverMovieCard } from '../../components/SharedMovieCards.jsx';
import useCardGridMetrics from '../../hooks/useCardGridMetrics.js';
import useMovieCollectionCache from '../../hooks/useMovieCollectionCache.js';
import { cx, formatCount, movieKey } from '../../utils/appUtils.js';
import {
  buildOwnershipMap, discoverMoviePayload, listsForDiscoverMovie, ownedMovieFor,
  removeOwnershipPaths, replaceOwnershipScope
} from '../../discoverUtils.js';
import { applySystemListState, movieIdentityKey, moviePayload } from '../../utils/libraryUtils.js';


export default function AIControlResult({
  aiControlPlan,
  aiControlReceipt,
  busy,
  onExecute,
  followed = [],
  notify,
  onPlay,
  onStream,
  streamingAvailable,
  streamingLabel,
  onFindTorrent,
  onOpenTrailer,
  onFollow,
  onEditPoster,
  onOpenFileDetails,
  onOpenDiscoverPerson,
  onOpenDiscoverCollection,
  cardsRenderer,
  readOnly = false
}) {
  const plan = aiControlPlan;
  const Cards = cardsRenderer || AIControlCardResults;
  const [currentPage, setCurrentPage] = useState(1);
  const [aiControlDangerPhrase, setAiControlDangerPhrase] = useState('');
  const [selectedAiControlKeys, setSelectedAiControlKeys] = useState(() => new Set());
  const [reviewedDownloads, setReviewedDownloads] = useState([]);
  const [sourceReview, setSourceReview] = useState(null);
  const planKey = `${plan?.plan_id || ''}-${plan?.summary || ''}-${plan?.message || ''}-${aiControlReceipt?.summary || ''}`;
  const targetPageSize = Number(plan?.page_size || 20);
  const {
    gridRef: aiControlGridRef,
    pageSize
  } = useCardGridMetrics({ target: targetPageSize, max: 200, bias: 'lower' });

  useEffect(() => {
    setCurrentPage(1);
    setAiControlDangerPhrase('');
    setSelectedAiControlKeys(new Set((plan?.items || []).map((item) => item.selection_key).filter(Boolean)));
    setReviewedDownloads([]);
    setSourceReview(null);
  }, [planKey]);

  if (aiControlReceipt) {
    const executedCount = Number(aiControlReceipt.submitted_count ?? aiControlReceipt.total_matches ?? aiControlReceipt.created?.count ?? 0);
    return (
      <section className="ai-control-result ai-control-result-ready ai-control-execution-receipt">
        <div className="ai-control-result-header">
          <div>
            <p className="screen-kicker">{aiControlReceipt.state || 'executed'}</p>
            <h3>{aiControlReceipt.summary || 'Action completed'}</h3>
            <p>{aiControlReceipt.message || 'AI Control completed the reviewed action.'}</p>
          </div>
          {!aiControlReceipt.hideCount && <div className="ai-control-execution-count">
            <strong>{formatCount(executedCount)}</strong>
            <span>{aiControlReceipt.action === 'create_list' ? 'movies saved' : 'actions completed'}</span>
          </div>}
        </div>
        {(aiControlReceipt.effects || []).map((report, index) => <OwnerReport key={index} report={report} />)}
      </section>
    );
  }
  if (!plan) {
    return (
      <WorkspaceEmptyState size="regular" className="library-empty ai-control-empty">
        <Bot size={30} />
        <strong>No command preview yet.</strong>
        <span>Use an example or type a command to see the reviewed plan here.</span>
      </WorkspaceEmptyState>
    );
  }
  const ready = plan.state === 'valid_plan';
  const rows = plan.items || [];
  const blocked = plan.blocked || [];
  const totalMatches = Number(plan.total_matches || rows.length);
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const pageStart = (safeCurrentPage - 1) * pageSize;
  const visibleRows = rows.slice(pageStart, pageStart + pageSize);
  const pageLabel = rows.length > pageSize
    ? `Showing ${formatCount(pageStart + 1)}-${formatCount(Math.min(pageStart + pageSize, rows.length))} of ${formatCount(totalMatches)}`
    : `${formatCount(totalMatches)} total`;
  const selectedKeys = rows
    .map((row) => row.selection_key)
    .filter((selectionKey) => selectionKey && selectedAiControlKeys.has(selectionKey));
  const selectedRows = rows.filter((row) => row.selection_key && selectedAiControlKeys.has(row.selection_key));
  const selectedCount = selectedRows.length;
  const allResultsSelected = rows.length > 0 && selectedCount === rows.length;
  const customizedSelection = selectedCount !== rows.length;
  const requiresDeletePhrase = ready && plan.action === 'delete' && selectedCount > 50;
  const expectedDeletePhrase = requiresDeletePhrase ? `DELETE ${selectedCount} FILES` : '';
  const deletePhraseConfirmed = !requiresDeletePhrase || aiControlDangerPhrase.trim() === expectedDeletePhrase;
  const reviewedForSelection = reviewedDownloads.filter((row) => selectedAiControlKeys.has(row.selection_key));

  function toggleSelection(selectionKey, checked) {
    setSelectedAiControlKeys((current) => {
      const next = new Set(current);
      if (checked) next.add(selectionKey);
      else next.delete(selectionKey);
      return next;
    });
  }

  function selectAllResults() {
    setSelectedAiControlKeys(new Set(rows.map((row) => row.selection_key).filter(Boolean)));
  }

  function clearSelection() {
    setSelectedAiControlKeys(new Set());
  }

  async function openSourceReview() {
    if (!selectedRows.length) {
      notify?.('Select movies before finding sources.', 'neutral');
      return;
    }
    setSourceReview({ loading: true, rows: [], error: '', title: 'Find sources' });
    try {
      const data = await previewSourceReview(selectedRows, { policy: 'ai_control' });
      setSourceReview({
        loading: false,
        submitting: false,
        rows: data.rows || [],
        blocked: data.blocked || [],
        defaults: data.defaults || {},
        error: '',
        title: 'Find sources'
      });
    } catch (error) {
      setSourceReview((current) => ({ ...current, loading: false, error: error.message }));
    }
  }

  function confirmAction() {
    onExecute({
      confirmationPhrase: aiControlDangerPhrase,
      selectedKeys,
      reviewedDownloads: reviewedForSelection
    });
  }

  return (
    <section className={cx('ai-control-result', ready ? 'ai-control-result-ready' : 'ai-control-result-blocked')}>
      <div className="ai-control-result-header">
        <div>
          <p className="screen-kicker">{plan.state || 'AI Control'}</p>
          <h3>{plan.summary || plan.message || 'Command result'}</h3>
          {plan.message && <p>{plan.message}</p>}
          {ready && <p>{customizedSelection ? `Customized selection: ${formatCount(selectedCount)} of ${formatCount(rows.length)} results.` : `Exact command selection: all ${formatCount(rows.length)} results.`}</p>}
        </div>
      </div>
      {(plan.warnings || []).map((warning) => (
        <div className="library-status library-status-warning" key={warning}><AlertTriangle size={16} /> {warning}</div>
      ))}
      {ready && (
        <AIControlPagination
          pageLabel={pageLabel}
          currentPage={safeCurrentPage}
          totalPages={totalPages}
          onPrevious={() => setCurrentPage((page) => Math.max(1, page - 1))}
          onNext={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
        />
      )}
      {requiresDeletePhrase && (
        <label className="ai-control-danger-confirm">
          <span>Type the confirmation phrase before deleting this selection.</span>
          <strong>{expectedDeletePhrase}</strong>
          <Input
            value={aiControlDangerPhrase}
            onChange={(event) => setAiControlDangerPhrase(event.target.value)}
            placeholder="Type the confirmation phrase"
          />
        </label>
      )}
      {ready && visibleRows.length > 0 ? (
        <Cards
          plan={plan}
          allRows={rows}
          rows={visibleRows}
          selectedKeys={selectedAiControlKeys}
          allResultsSelected={allResultsSelected}
          onToggleSelection={toggleSelection}
          onSelectAll={selectAllResults}
          onClearSelection={clearSelection}
          onFindSources={openSourceReview}
          onConfirm={readOnly ? undefined : confirmAction}
          confirmDisabled={!aiControlPlan?.plan_id || busy || !deletePhraseConfirmed || !selectedCount}
          busy={busy}
          followed={followed}
          notify={notify}
          onPlay={onPlay}
          onStream={onStream}
          streamingAvailable={streamingAvailable}
          streamingLabel={streamingLabel}
          onFindTorrent={onFindTorrent}
          onOpenTrailer={onOpenTrailer}
          onFollow={onFollow}
          onEditPoster={onEditPoster}
          onOpenFileDetails={onOpenFileDetails}
          onOpenDiscoverPerson={onOpenDiscoverPerson}
          onOpenDiscoverCollection={onOpenDiscoverCollection}
          gridRef={aiControlGridRef}
        />
      ) : null}
      {blocked.length > 0 && <p className="settings-empty-note">{formatCount(blocked.length)} result{blocked.length === 1 ? '' : 's'} could not be included in the selectable plan.</p>}
      {sourceReview && (
        <SourceReviewDialog
          state={sourceReview}
          setState={setSourceReview}
          onClose={() => setSourceReview(null)}
          onReviewComplete={(rowsToApply) => setReviewedDownloads(rowsToApply)}
          notify={notify}
        />
      )}
    </section>
  );
}

function AIControlPagination({ pageLabel, currentPage, totalPages, onPrevious, onNext }) {
  return <Pagination page={currentPage} totalPages={totalPages} summary={pageLabel} showSinglePage
    previousLabel="Previous page" nextLabel="Next page"
    ariaLabel="AI Control pagination" onPageChange={page => page < currentPage ? onPrevious() : onNext()} />;
}

function AIControlCardResults({
  plan,
  allRows,
  rows,
  selectedKeys,
  allResultsSelected,
  onToggleSelection,
  onSelectAll,
  onClearSelection,
  onFindSources,
  onConfirm,
  confirmDisabled,
  busy,
  followed,
  notify,
  onPlay,
  onStream,
  streamingAvailable,
  streamingLabel,
  onFindTorrent,
  onOpenTrailer,
  onFollow,
  onEditPoster,
  onOpenFileDetails,
  onOpenDiscoverPerson,
  onOpenDiscoverCollection,
  gridRef
}) {
  const [ownership, setOwnership] = useState(() => buildAiControlOwnershipMap(rows));
  const [ownershipResolved, setOwnershipResolved] = useState(false);
  const [userLists, setUserLists] = useState([]);
  const [detailsCache, setDetailsCache] = useState({});
  const {
    clear: clearCollectionCache,
    getView: getCollectionView,
    load: loadMovieCollection
  } = useMovieCollectionCache();
  const [expandedMovieKey, setExpandedMovieKey] = useState('');
  const [ownershipRefreshKey, setOwnershipRefreshKey] = useState(0);
  const [listEditorTarget, setListEditorTarget] = useState(null);
  const ownershipRequestSeq = useRef(0);
  const movies = rows || [];
  const ownershipScopeKey = useMemo(() => (
    `${plan?.plan_id || ''}:${movies.map((movie) => movieIdentityKey(movie)).join('|')}`
  ), [plan?.plan_id, movies]);

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

  const loadUserLists = useCallback(async (options = {}) => {
    try {
      const data = await fetchUserListsCached({ force: Boolean(options?.force) });
      setUserLists(data.lists || []);
    } catch (error) {
      notify?.(`Lists unavailable: ${error.message}`, 'error');
    }
  }, [notify]);

  useEffect(() => {
    loadUserLists();
    window.addEventListener('cp-curation-changed', loadUserLists);
    return () => window.removeEventListener('cp-curation-changed', loadUserLists);
  }, [loadUserLists]);

  useEffect(() => {
    const requestSeq = ownershipRequestSeq.current + 1;
    ownershipRequestSeq.current = requestSeq;
    setOwnership(buildAiControlOwnershipMap(movies));
    setOwnershipResolved(false);
    setExpandedMovieKey('');
    return () => {
      if (ownershipRequestSeq.current === requestSeq) ownershipRequestSeq.current += 1;
    };
  }, [ownershipScopeKey]);

  useEffect(() => {
    const requestSeq = ownershipRequestSeq.current + 1;
    ownershipRequestSeq.current = requestSeq;
    checkAiControlOwnership(movies, requestSeq);
    return () => {
      if (ownershipRequestSeq.current === requestSeq) ownershipRequestSeq.current += 1;
    };
  }, [ownershipRefreshKey, ownershipScopeKey]);

  useEffect(() => {
    const refreshOwnership = (event) => {
      setOwnership((state) => removeOwnershipPaths(state, event?.detail?.deleted_paths));
      setOwnershipRefreshKey((value) => value + 1);
    };
    window.addEventListener('cp-library-changed', refreshOwnership);
    window.addEventListener(CATALOG_GENERATION_CHANGED_EVENT, refreshOwnership);
    return () => {
      window.removeEventListener('cp-library-changed', refreshOwnership);
      window.removeEventListener(CATALOG_GENERATION_CHANGED_EVENT, refreshOwnership);
    };
  }, []);

  async function checkAiControlOwnership(items, requestSeq) {
    const payload = (items || []).filter((movie) => movie?.title);
    if (!payload.length) return;
    try {
      const ownershipResults = await fetchOwnershipChecks(payload);
      if (requestSeq !== ownershipRequestSeq.current) return;
      setOwnership((state) => replaceOwnershipScope(state, payload, ownershipResults));
      setOwnershipResolved(true);
    } catch {
      // AI Control card view can still render without best-effort ownership enrichment.
    }
  }

  async function loadAiControlDetails(movie, owned = null) {
    const cacheKey = movieDetailsCacheKey(movie, owned);
    if (!cacheKey) return null;
    let details = detailsCache[cacheKey];
    if (!details || details.stale) {
      setDetailsCache((state) => ({ ...state, [cacheKey]: { loading: true, cast: [], directors: [], collection: {}, trailer_url: '' } }));
      try {
        details = await fetchCanonicalMovieDetails(movie, owned);
        setDetailsCache((state) => ({ ...state, [cacheKey]: details }));
      } catch (error) {
        details = { error: error.message, cast: [], directors: [], collection: {}, trailer_url: '' };
        setDetailsCache((state) => ({ ...state, [cacheKey]: details }));
      }
    }
    loadMovieCollection(details);
    return details;
  }

  function toggleAiControlDetails(movie, owned = null) {
    const key = movieKey(movie);
    const nextKey = expandedMovieKey === key ? '' : key;
    setExpandedMovieKey(nextKey);
    if (nextKey) loadAiControlDetails(movie, owned);
  }

  const expandedOwnershipMovie = movies.find((movie) => movieKey(movie) === expandedMovieKey) || null;
  const expandedOwnership = expandedOwnershipMovie
    ? ownedMovieFor(expandedOwnershipMovie, ownership) || (!ownershipResolved && expandedOwnershipMovie.path ? expandedOwnershipMovie : null)
    : null;
  const expandedDetailsKey = movieDetailsCacheKey(expandedOwnershipMovie, expandedOwnership);

  useEffect(() => {
    if (!expandedMovieKey || !expandedOwnershipMovie || !expandedDetailsKey) return;
    const cached = detailsCache[expandedDetailsKey];
    if (!cached || cached.stale) loadAiControlDetails(expandedOwnershipMovie, expandedOwnership);
  }, [expandedDetailsKey]);

  async function openAiControlTrailer(movie) {
    const owned = ownedMovieFor(movie, ownership) || (!ownershipResolved && movie.path ? movie : null);
    if (!movieDetailsCacheKey(movie, owned)) {
      onOpenTrailer(movie, '');
      return;
    }
    const details = await loadAiControlDetails(movie, owned);
    onOpenTrailer(movie, details?.trailer_url || '');
  }

  async function createAiControlList(name) {
    const created = await fetchCurationJson('/api/user/lists', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    await loadUserLists({ force: true });
    announceCurationChanged();
    notify?.(`List created: ${created.name}`);
    return created;
  }

  async function addAiControlMovieToList(listId, movie) {
    await fetchCurationJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie: moviePayload(movie) })
    });
    await loadUserLists({ force: true });
    announceCurationChanged();
    notify?.('Movie added to list');
  }

  async function addAiControlMoviesToList(listId, moviesToAdd) {
    await addMoviePayloadsToList(listId, (moviesToAdd || []).map((movie) => moviePayload(movie)));
    await loadUserLists({ force: true });
    announceCurationChanged();
    notify?.(`${formatCount((moviesToAdd || []).length)} movie${(moviesToAdd || []).length === 1 ? '' : 's'} added to list`);
  }

  async function removeAiControlMovieFromList(listId, movie) {
    await fetchCurationJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie: moviePayload(movie) })
    });
    await loadUserLists({ force: true });
    announceCurationChanged();
    notify?.('Movie removed from list');
  }

  async function toggleAiControlSystemList(systemType, movie, owned) {
    const payload = discoverMoviePayload(movie, owned);
    const currentLists = listsForDiscoverMovie(movie, userLists, owned);
    const active = currentLists.some((list) => list.system_type === systemType || list.id === systemType);
    const nextActive = !active;
    setUserLists((current) => applySystemListState(current, systemType, payload, nextActive));
    try {
      await fetchCurationJson(`/api/user/system-lists/${encodeURIComponent(systemType)}/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ movie: payload, active: nextActive })
      });
    } catch (error) {
      setUserLists((current) => applySystemListState(current, systemType, payload, active));
      notify?.(error.message, 'error');
      return;
    }
    notify?.(`${movie.title} ${active ? 'removed from' : 'added to'} ${systemType === 'watched' ? 'Watched' : 'Watchlist'}`);
  }

  const selectedAiControlMovies = useMemo(() => (
    (allRows || [])
      .filter((movie) => selectedKeys.has(movie.selection_key))
      .map((movie) => discoverMoviePayload(movie, movie.path ? movie : null))
  ), [allRows, selectedKeys]);

  return (
    <div className="ai-control-card-results">
      <AIControlSelectionBar
        selectedCount={selectedAiControlMovies.length} allResultsSelected={allResultsSelected}
        onSelectAll={onSelectAll} onClearSelection={onClearSelection}
        onAddToList={() => setListEditorTarget({ bulkItems: selectedAiControlMovies })}
        onFindSources={onFindSources} onConfirm={onConfirm} confirmDisabled={confirmDisabled} busy={busy}
      />

      <DiscoverResultGrid gridRef={gridRef} emptyText="No AI Control movies are available for card display.">
        {movies.map((movie, index) => {
          const owned = ownedMovieFor(movie, ownership) || (!ownershipResolved && movie.path ? movie : null);
          const details = detailsCache[movieDetailsCacheKey(movie, owned)] || null;
          const collectionView = getCollectionView(details);
          const movieWithDetails = details ? { ...movie, plot: movie.plot || details.plot || '', release_date: movie.release_date || details.release_date || '' } : movie;
          return (
            <DiscoverMovieCard
              key={`${movie.tmdb_id || movie.path || movie.title}-${movie.year}-${index}`}
              movie={movieWithDetails}
              owned={owned}
              followed={followed.some((item) => movieKey(item) === movieKey(movie))}
              expanded={expandedMovieKey === movieKey(movie)}
              details={details}
              collection={collectionView.data}
              collectionStatus={collectionView.status}
              collectionError={collectionView.error}
              itemLists={listsForDiscoverMovie(movie, userLists, owned)}
              watched={listsForDiscoverMovie(movie, userLists, owned).some((list) => list.system_type === 'watched')}
              watchlisted={listsForDiscoverMovie(movie, userLists, owned).some((list) => list.system_type === 'watchlist')}
              onToggleWatched={owned ? () => toggleAiControlSystemList('watched', movie, owned) : undefined}
              onToggleWatchlist={() => toggleAiControlSystemList('watchlist', movie, owned)}
              selected={selectedKeys.has(movie.selection_key)}
              onSelect={(checked) => onToggleSelection(movie.selection_key, checked)}
              onPlay={onPlay}
              onStream={onStream}
              streamingAvailable={streamingAvailable}
              streamingLabel={streamingLabel}
              onFindTorrent={onFindTorrent}
              onFollow={onFollow}
              onTrailer={openAiControlTrailer}
              onToggleDetails={() => toggleAiControlDetails(movie, owned)}
              onPersonBrowse={(role, person) => onOpenDiscoverPerson(movieWithDetails, role, person)}
              onPersonDiscover={(role, person) => onOpenDiscoverPerson(movieWithDetails, role, person, { fullFilmography: true })}
              onPersonAwardDiscover={(role, person, award) => onOpenDiscoverPerson(movieWithDetails, role, person, { award })}
              onCollectionBrowse={(collection) => onOpenDiscoverCollection(movieWithDetails, collection)}
              onCollectionRetry={() => loadMovieCollection(details, { force: true })}
              onEditLists={() => setListEditorTarget(discoverMoviePayload(movie, owned))}
              onRemoveFromList={(listId) => removeAiControlMovieFromList(listId, discoverMoviePayload(movie, owned))}
              onEditPoster={owned?.path ? () => onEditPoster?.(owned, movie) : undefined}
              onOpenFileDetails={onOpenFileDetails}
            />
          );
        })}
      </DiscoverResultGrid>

      {listEditorTarget && (
        <ListEditorModal
          item={listEditorTarget.bulkItems ? null : listEditorTarget}
          bulkItems={listEditorTarget.bulkItems || []}
          items={[]}
          lists={userLists}
          onClose={() => setListEditorTarget(null)}
          onCreate={createAiControlList}
          onAdd={addAiControlMovieToList}
          onAddBulk={addAiControlMoviesToList}
        />
      )}
    </div>
  );
}

function buildAiControlOwnershipMap(movies) {
  return buildOwnershipMap((movies || [])
    .filter((movie) => movie?.path)
    .map((movie) => ({ ...movie, found: true })));
}

function OwnerReport({ report }) {
  const keys = ['applied', 'submitted_count', 'failed', 'locked', 'missing', 'skipped', 'renamed'];
  const counts = keys.filter(key => report[key] !== undefined).map(key => ({ key,
    count: Array.isArray(report[key]) ? report[key].length : report[key] }));
  return <div className="library-status ai-owner-report">
    {report.name && <strong>{report.name}</strong>}
    {report.state && <span>{String(report.state).replaceAll('_', ' ')}</span>}
    {counts.map(row => <span key={row.key}>{formatCount(row.count)} {row.key.replaceAll('_', ' ')}</span>)}
    {!counts.length && !report.state && !report.name && <span>{report.message || (report.playback_ready ? 'Playback is ready' : 'The requested change was recorded.')}</span>}
  </div>;
}
