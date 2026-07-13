import {
  AlertTriangle, CirclePlus, Copy, Download, Film, Loader2, Pencil, Search, Trash2, Wand2, X
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchJson } from '../../api/client.js';
import { addMoviePayloadsToList, announceCurationChanged, fetchUserListsCached } from '../../api/curation.js';
import ExportCopyDialog from '../../components/ExportCopyDialog.jsx';
import ListEditorModal from '../../components/ListEditorModal.jsx';
import MetadataCorrectionModal from '../../components/MetadataCorrectionModal.jsx';
import SelectionCheckbox from '../../components/SelectionCheckbox.jsx';
import { DiscoverMovieCard, LibraryMovieCard } from '../../components/SharedMovieCards.jsx';
import { cx, formatCount, movieKey } from '../../utils/appUtils.js';
import { discoverMoviePayload, listsForDiscoverMovie } from '../../discoverUtils.js';
import { buildMovieListViewModel, listsForItem, movieIdentityKey, moviePayload } from '../../utils/libraryUtils.js';

export default function MovieListsWorkspace({
  notify,
  onPlay,
  onFindTorrent,
  onOpenTrailer,
  onStream,
  streamingAvailable,
  streamingLabel,
  followed = [],
  onFollow,
  onEditPoster
}) {
  const [libraryItems, setLibraryItems] = useState([]);
  const [lists, setLists] = useState([]);
  const [selectedListId, setSelectedListId] = useState('');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedKeys, setSelectedKeys] = useState(() => new Set());
  const [newListName, setNewListName] = useState('');
  const [renameValue, setRenameValue] = useState('');
  const [expandedKey, setExpandedKey] = useState('');
  const [detailsCache, setDetailsCache] = useState({});
  const [collectionCache, setCollectionCache] = useState({});
  const [listEditorTarget, setListEditorTarget] = useState(null);
  const [copyMovies, setCopyMovies] = useState(null);
  const [tmdbAddOpen, setTmdbAddOpen] = useState(false);
  const [metadataCorrection, setMetadataCorrection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [ownershipLoading, setOwnershipLoading] = useState(false);
  const [ownershipRefreshKey, setOwnershipRefreshKey] = useState(0);
  const [error, setError] = useState('');
  const [fulfillment, setFulfillment] = useState(null);
  const ownershipRequestSeq = useRef(0);

  const selectedList = lists.find((list) => list.id === selectedListId) || lists[0] || null;
  const model = useMemo(() => buildMovieListViewModel({
    libraryItems,
    list: selectedList,
    query,
    statusFilter
  }), [libraryItems, selectedList, query, statusFilter]);
  const selectedRows = model.rows.filter((row) => selectedKeys.has(row.identityKey));
  const allRowsSelected = model.rows.length > 0 && model.rows.every((row) => selectedKeys.has(row.identityKey));
  const selectedListIsSystem = Boolean(selectedList?.system_type);
  const selectedCopyMovies = selectedRows.map((row) => (row.ownedItem ? moviePayload(row.ownedItem) : movieListRowMovie(row)));

  const loadMovieLists = useCallback(async (options = {}) => {
    const forceLists = Boolean(options?.forceLists);
    setLoading(true);
    setError('');
    try {
      const listsData = await fetchUserListsCached({ force: forceLists });
      const nextLists = listsData.lists || [];
      setLists(nextLists);
      setSelectedListId((current) => (nextLists.some((list) => list.id === current) ? current : nextLists[0]?.id || ''));
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
    const refreshOwnership = () => setOwnershipRefreshKey((value) => value + 1);
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
    if (!selectedList) {
      setLibraryItems([]);
      setOwnershipLoading(false);
      return;
    }
    const movies = selectedList.movies || [];
    if (!movies.length) {
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
  }, [selectedListId, query, statusFilter]);

  useEffect(() => {
    setRenameValue(selectedList?.name || '');
  }, [selectedList?.id, selectedList?.name]);

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
    const id = String(movie.tmdb_id || row.ownedPayload?.tmdb_id || '');
    if (!id) return null;
    let details = detailsCache[id];
    if (!details) {
      setDetailsCache((state) => ({ ...state, [id]: { loading: true, cast: [], directors: [], collection: {}, trailer_url: '' } }));
      try {
        details = await fetchJson(`/api/tmdb/details?tmdb_id=${encodeURIComponent(id)}`);
        setDetailsCache((state) => ({ ...state, [id]: details }));
      } catch (detailsError) {
        details = { error: detailsError.message, cast: [], directors: [], collection: {}, trailer_url: '' };
        setDetailsCache((state) => ({ ...state, [id]: details }));
      }
    }
    if (details?.collection?.id && !collectionCache[details.collection.id]) {
      fetchJson(`/api/tmdb/collection?collection_id=${encodeURIComponent(details.collection.id)}`)
        .then((collectionData) => setCollectionCache((state) => ({ ...state, [details.collection.id]: collectionData })))
        .catch(() => {});
    }
    return details;
  }

  function toggleMovieListDetails(row) {
    const nextKey = expandedKey === row.identityKey ? '' : row.identityKey;
    setExpandedKey(nextKey);
    if (nextKey) loadMovieListDetails(row);
  }

  async function openMovieListTrailer(row) {
    const movie = movieListRowMovie(row);
    try {
      const details = await loadMovieListDetails(row);
      onOpenTrailer(movie, details?.trailer_url || '');
    } catch {
      onOpenTrailer(movie, '');
    }
  }

  async function createList(name) {
    const created = await fetchJson('/api/user/lists', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    setNewListName('');
    setSelectedListId(created.id);
    await loadMovieLists({ forceLists: true });
    announceCurationChanged();
    notify?.(`List created: ${created.name}`);
    return created;
  }

  async function createListFromRail(event) {
    event.preventDefault();
    const name = newListName.trim();
    if (!name) return;
    await createList(name);
  }

  async function renameSelectedList(event) {
    event.preventDefault();
    if (!selectedList || selectedListIsSystem || !renameValue.trim()) return;
    const renamed = await fetchJson(`/api/user/lists/${encodeURIComponent(selectedList.id)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: renameValue.trim() })
    });
    await loadMovieLists({ forceLists: true });
    announceCurationChanged();
    notify?.(`List renamed: ${renamed.name}`);
  }

  async function deleteSelectedList() {
    if (!selectedList || selectedListIsSystem) return;
    if (!window.confirm(`Delete list "${selectedList.name}"? Movies will not be deleted from Library.`)) return;
    await fetchJson(`/api/user/lists/${encodeURIComponent(selectedList.id)}`, { method: 'DELETE' });
    setSelectedListId('');
    await loadMovieLists({ forceLists: true });
    announceCurationChanged();
    notify?.('List deleted');
  }

  async function addMovieToList(listId, item) {
    const movie = item?.ownedItem ? moviePayload(item.ownedItem) : moviePayload(item);
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
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
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
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
    for (const row of selectedRows) {
      await removeMovieFromList(selectedList.id, row.ownedItem ? moviePayload(row.ownedItem) : movieListRowMovie(row));
    }
    setSelectedKeys(new Set());
    notify?.(`${formatCount(selectedRows.length)} movie${selectedRows.length === 1 ? '' : 's'} removed from ${selectedList.name}`);
  }

  async function addTmdbMovieToSelectedList(movie) {
    if (!selectedList) return;
    await addMovieToList(selectedList.id, movie);
    setTmdbAddOpen(false);
  }

  async function toggleMovieListSystemList(systemType, row) {
    const owned = row.ownedItem ? moviePayload(row.ownedItem) : null;
    const movie = movieListRowMovie(row);
    const currentLists = row.ownedItem ? listsForItem(row.ownedItem, lists) : listsForDiscoverMovie(movie, lists, owned);
    const active = currentLists.some((list) => list.system_type === systemType || list.id === systemType);
    await fetchJson(`/api/user/system-lists/${encodeURIComponent(systemType)}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie: discoverMoviePayload(movie, owned), active: !active })
    });
    await loadMovieLists({ forceLists: true });
    announceCurationChanged();
    notify?.(`${row.title} ${active ? 'removed from' : 'added to'} ${systemType === 'watched' ? 'Watched' : 'Watchlist'}`);
  }

  function selectListFromCard(list) {
    if (list?.id) setSelectedListId(list.id);
  }

  async function openFulfillment(action, forcedRows = null) {
    if (!selectedList) return;
    const candidates = forcedRows || (selectedRows.length ? selectedRows : model.allRows.filter((row) => (
      action === 'missing' ? row.status === 'missing' : row.status === 'upgrade'
    )));
    if (!candidates.length) {
      notify?.(action === 'missing' ? 'No missing movies to find.' : 'No upgrade candidates to find.', 'neutral');
      return;
    }
    setFulfillment({ action, loading: true, rows: [], error: '', title: action === 'missing' ? 'Find missing sources' : 'Find upgrade sources' });
    try {
      const data = await fetchJson('/api/user/lists/fulfillment/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          movies: candidates.map((row) => ({
            tmdb_id: row.tmdb_id || row.ownedPayload?.tmdb_id || '',
            imdb_id: row.imdb_id || row.ownedPayload?.imdb_id || '',
            title: row.title,
            year: row.year,
            poster_url: row.poster_url,
            path: row.ownedItem?.path || ''
          }))
        })
      });
      setFulfillment({
        action,
        loading: false,
        rows: data.rows || [],
        blocked: data.blocked || [],
        defaults: data.defaults || {},
        error: '',
        title: action === 'missing' ? 'Find missing sources' : 'Find upgrade sources'
      });
    } catch (previewError) {
      setFulfillment((current) => ({ ...current, loading: false, error: previewError.message }));
    }
  }

  return (
    <section className="library-workspace movie-lists-workspace">
      <header className="library-header movie-lists-header">
        <div>
          <p className="screen-kicker">Mixed owned and wanted lists</p>
          <h2>Movie Lists</h2>
          <p>Review full lists here. Library stays offline-only; this page shows owned, missing, and upgrade candidates together.</p>
        </div>
        <div className="movie-list-summary-strip" aria-label="Selected list summary">
          <span><strong>{formatCount(model.stats.total)}</strong>Total</span>
          <span><strong>{formatCount(model.stats.owned)}</strong>Owned</span>
          <span><strong>{formatCount(model.stats.missing)}</strong>Missing</span>
          <span><strong>{formatCount(model.stats.upgrades)}</strong>Upgrades</span>
        </div>
      </header>

      <form className="library-search-panel movie-lists-search" onSubmit={(event) => event.preventDefault()}>
        <label className="search-field library-main-search">
          <Search size={18} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search the selected list..." />
        </label>
        <button type="submit" className="btn btn-primary library-search-submit"><Search size={16} /> Search</button>
      </form>

      <div className="movie-lists-layout">
        <aside className="movie-lists-rail" aria-label="Movie lists">
          <form className="movie-list-create-inline" onSubmit={createListFromRail}>
            <input value={newListName} onChange={(event) => setNewListName(event.target.value)} placeholder="New list name..." />
            <button type="submit" className="mini-action" disabled={!newListName.trim()}>
              <CirclePlus size={13} /> New list
            </button>
          </form>
          {lists.length ? lists.map((list) => (
            <button
              type="button"
              key={list.id}
              className={cx('movie-list-rail-item', selectedList?.id === list.id && 'movie-list-rail-item-active')}
              onClick={() => setSelectedListId(list.id)}
            >
              <span>{list.name}</span>
              <small>{formatCount((list.movies || []).length)} movies</small>
            </button>
          )) : (
            <div className="empty-state"><strong>No lists yet.</strong><span>Create lists from Library or Discover.</span></div>
          )}
        </aside>

        <div className="movie-lists-main">
          <form className="movie-list-management-bar" onSubmit={renameSelectedList}>
            <input
              value={renameValue}
              onChange={(event) => setRenameValue(event.target.value)}
              disabled={!selectedList || selectedListIsSystem}
              placeholder="No list selected"
              aria-label="Selected list name"
            />
            <button type="submit" className="mini-action" disabled={!selectedList || selectedListIsSystem || !renameValue.trim()}>
              <Pencil size={13} /> Rename list
            </button>
            <button type="button" className="mini-action" onClick={() => setTmdbAddOpen(true)} disabled={!selectedList}>
              <Search size={13} /> Add movie
            </button>
            <button type="button" className="mini-action mini-action-danger" onClick={deleteSelectedList} disabled={!selectedList || selectedListIsSystem}>
              <Trash2 size={13} /> Delete list
            </button>
          </form>

          <div className="library-toolbar movie-lists-filterbar">
            {[
              ['all', 'All'],
              ['owned', 'Owned'],
              ['missing', 'Missing'],
              ['upgrade', 'Upgrade candidates']
            ].map(([value, label]) => (
              <button type="button" key={value} className={cx('filter-chip-button', statusFilter === value && 'filter-chip-button-active')} onClick={() => setStatusFilter(value)}>
                {label}
              </button>
            ))}
          </div>

          {model.rows.length > 0 && (
            <div className="bulk-selection-bar movie-lists-bulk">
              <SelectionCheckbox
                className="movie-lists-select-all"
                checked={allRowsSelected}
                onChange={(checked) => { if (checked) selectAllVisible(); else clearSelection(); }}
                label="Select all visible list movies"
              />
              <span>{selectedRows.length ? `${formatCount(selectedRows.length)} selected` : 'Select movies'}</span>
              <button type="button" className="mini-action" onClick={clearSelection} disabled={!selectedRows.length}>Clear</button>
              <button type="button" className="mini-action" onClick={() => setCopyMovies(selectedCopyMovies)} disabled={!selectedRows.length}>
                <Copy size={13} /> Copy selected to...
              </button>
              <button type="button" className="mini-action mini-action-danger" onClick={removeSelectedFromActiveList} disabled={!selectedRows.length || !selectedList}>
                <Trash2 size={13} /> Remove selected
              </button>
              <button type="button" className="mini-action" onClick={() => openFulfillment('missing')} disabled={!selectedList || !model.allRows.some((row) => row.status === 'missing')}>
                <Download size={13} /> Find missing
              </button>
              <button type="button" className="mini-action" onClick={() => openFulfillment('upgrade')} disabled={!selectedList || !model.allRows.some((row) => row.status === 'upgrade')}>
                <Wand2 size={13} /> Find upgrades
              </button>
            </div>
          )}

          {error ? <div className="library-status library-status-error"><AlertTriangle size={16} /> {error}</div> : null}
          {loading || ownershipLoading ? (
            <div className="empty-state"><strong>{loading ? 'Loading movie lists...' : 'Checking selected list...'}</strong><span>{loading ? 'Reading saved lists.' : 'Matching this list against Library ownership.'}</span></div>
          ) : selectedList ? (
            model.rows.length ? (
              <div className="library-results library-movie-results movie-lists-card-grid">
                {model.rows.map((row) => {
                  const movie = movieListRowMovie(row);
                  const tmdbId = String(movie.tmdb_id || row.ownedPayload?.tmdb_id || '');
                  const details = tmdbId ? detailsCache[tmdbId] : null;
                  const collection = tmdbId && details?.collection?.id ? collectionCache[details.collection.id] || details.collection : {};
                  const rowLists = row.ownedItem ? listsForItem(row.ownedItem, lists) : listsForDiscoverMovie(movie, lists, null);
                  const watched = rowLists.some((list) => list.system_type === 'watched');
                  const watchlisted = rowLists.some((list) => list.system_type === 'watchlist');
                  if (row.ownedItem) {
                    return (
                      <LibraryMovieCard
                        key={row.identityKey}
                        item={row.ownedItem}
                        expanded={expandedKey === row.identityKey}
                        details={details}
                        collection={collection}
                        itemLists={rowLists}
                        onToggle={() => toggleMovieListDetails(row)}
                        onPlay={onPlay}
                        onFindTorrent={onFindTorrent}
                        onTrailer={() => openMovieListTrailer(row)}
                        onListFilter={selectListFromCard}
                        onEditLists={() => setListEditorTarget({ item: row.ownedItem })}
                        onRemoveFromList={(listId) => removeMovieFromList(listId, moviePayload(row.ownedItem))}
                        onEditPoster={onEditPoster ? () => onEditPoster(row.ownedItem, movie) : undefined}
                        onCorrectMetadata={() => setMetadataCorrection(row.ownedItem)}
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
                      movie={movie}
                      owned={null}
                      followed={followed.some((item) => movieKey(item) === movieKey(movie))}
                      expanded={expandedKey === row.identityKey}
                      details={details}
                      collection={collection}
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
                      onListBrowse={selectListFromCard}
                      onEditLists={() => setListEditorTarget(movie)}
                      onRemoveFromList={(listId) => removeMovieFromList(listId, movie)}
                    />
                  );
                })}
              </div>
            ) : (
              <div className="empty-state"><strong>No movies match this view.</strong><span>Change the search or filter chip.</span></div>
            )
          ) : (
            <div className="empty-state"><strong>No list selected.</strong><span>Create or select a list first.</span></div>
          )}
        </div>
      </div>

      {fulfillment && (
        <MovieListFulfillmentDialog
          state={fulfillment}
          setState={setFulfillment}
          onClose={() => setFulfillment(null)}
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

function MovieListFulfillmentDialog({ state, setState, onClose, notify }) {
  const readyRows = (state.rows || []).filter((row) => row.status === 'ready');
  const selectedCount = readyRows.filter((row) => row.selected !== false).length;

  function updateRows(updater) {
    setState((current) => ({ ...current, rows: updater(current.rows || []) }));
  }

  function setAllRows(selected) {
    updateRows((rows) => rows.map((row) => (row.status === 'ready' ? { ...row, selected } : row)));
  }

  function setSelectedQuality(quality) {
    updateRows((rows) => rows.map((row) => (
      row.status === 'ready' && row.selected !== false ? { ...row, quality } : row
    )));
  }

  async function submitSelected() {
    setState((current) => ({ ...current, submitting: true, error: '' }));
    try {
      const data = await fetchJson('/api/user/lists/fulfillment/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows: state.rows || [] })
      });
      notify?.(`Submitted ${formatCount(data.submitted_count || 0)} movie${Number(data.submitted_count || 0) === 1 ? '' : 's'} to qBittorrent`);
      onClose();
    } catch (submitError) {
      setState((current) => ({ ...current, submitting: false, error: submitError.message }));
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="torrent-dialog movie-list-fulfillment-dialog" role="dialog" aria-modal="true" aria-label={state.title || 'Movie list fulfillment'} onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <p className="screen-kicker">Trusted source review</p>
            <h2>{state.title || 'Review sources'}</h2>
          </div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close source review">
            <X size={18} />
          </button>
        </div>

        {state.loading ? (
          <div className="source-loading-panel"><Loader2 size={20} className="spin" /><strong>Finding trusted sources...</strong><span>This may take some time depending on selected indexers.</span></div>
        ) : (
          <>
            <div className="bulk-selection-bar movie-list-review-actions">
              <span>{formatCount(selectedCount)} selected for download</span>
              <button type="button" className="mini-action" onClick={() => setAllRows(true)}>Select all</button>
              <button type="button" className="mini-action" onClick={() => setAllRows(false)}>Select none</button>
              <button type="button" className="mini-action" onClick={() => setSelectedQuality('1080p')}>Set selected to 1080p</button>
              <button type="button" className="mini-action" onClick={() => setSelectedQuality('4K')}>Set selected to 4K</button>
            </div>
            {state.error ? <div className="library-status library-status-error"><AlertTriangle size={16} /> {state.error}</div> : null}
            <div className="movie-list-review-table">
              <div className="movie-list-review-head">
                <span>Pick</span>
                <span>Movie</span>
                <span>Release</span>
                <span>Indexer</span>
                <span>Quality</span>
                <span>Status</span>
              </div>
              {(state.rows || []).map((row, index) => (
                <div className="movie-list-review-row" key={`${row.tmdb_id || row.title}-${index}`}>
                  <SelectionCheckbox
                    checked={row.status === 'ready' && row.selected !== false}
                    onChange={(checked) => updateRows((rows) => rows.map((item, itemIndex) => itemIndex === index ? { ...item, selected: checked } : item))}
                    label={`Select ${row.title}`}
                  />
                  <span><strong>{row.title}</strong><small>{row.year || 'Unknown year'}</small></span>
                  <span title={row.variant?.title || row.reason || ''}>{row.variant?.title || row.reason || 'No release'}</span>
                  <span>{row.variant?.indexer || '-'}</span>
                  <select
                    value={row.quality || state.defaults?.quality || '1080p'}
                    disabled={row.status !== 'ready'}
                    onChange={(event) => updateRows((rows) => rows.map((item, itemIndex) => itemIndex === index ? { ...item, quality: event.target.value } : item))}
                  >
                    <option value="1080p">1080p</option>
                    <option value="4K">4K</option>
                  </select>
                  <span>{row.status === 'ready' ? [row.variant?.size_human, row.variant?.seeders ? `${row.variant.seeders} seeders` : ''].filter(Boolean).join(' - ') || 'Ready' : row.reason || row.status}</span>
                </div>
              ))}
            </div>
            {state.blocked?.length ? (
              <p className="settings-empty-note">{formatCount(state.blocked.length)} movie{state.blocked.length === 1 ? '' : 's'} had no trusted source.</p>
            ) : null}
          </>
        )}

        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-primary" onClick={submitSelected} disabled={state.loading || state.submitting || !selectedCount}>
            {state.submitting ? <Loader2 size={15} className="spin" /> : <Download size={15} />} Submit selected to qBittorrent
          </button>
        </div>
      </section>
    </div>
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
      <section className="torrent-dialog tmdb-list-add-dialog" role="dialog" aria-modal="true" aria-label={`Add movie to ${list.name}`} onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <p className="screen-kicker">Add movie</p>
            <h2>{list.name}</h2>
          </div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close add movie dialog">
            <X size={18} />
          </button>
        </div>
        <form className="library-search-panel tmdb-list-add-search" onSubmit={searchTmdb}>
          <label className="library-search library-main-search">
            <Search size={17} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search TMDB movies..." />
          </label>
          <button type="submit" className="btn btn-primary" disabled={!query.trim() || loading}>
            {loading ? <Loader2 size={15} className="spin" /> : <Search size={15} />} Search
          </button>
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
                  <strong>{movie.title || 'Untitled'}</strong>
                  <span>{movie.year || 'Unknown year'}</span>
                  <small>{movie.plot || 'No plot summary available.'}</small>
                </div>
                <button type="button" className="btn btn-secondary" onClick={() => addResult(movie)} disabled={Boolean(addingKey)}>
                  {addingKey === key ? <Loader2 size={15} className="spin" /> : <CirclePlus size={15} />} Add to list
                </button>
              </article>
            );
          }) : (
            <div className="empty-state">
              <strong>Search TMDB to add a movie.</strong>
              <span>Owned movies will render as Library cards after they match your archive; missing movies stay Discover-style.</span>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
