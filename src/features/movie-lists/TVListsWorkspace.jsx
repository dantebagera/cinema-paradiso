import Button from '../../components/ui/Button.jsx';
import { Input, Select } from '../../components/ui/FormField.jsx';
import { useEffect, useState } from 'react';
import { RefreshCw, Search, X } from 'lucide-react';
import { fetchJson } from '../../api/client.js';
import Pagination from '../../components/Pagination.jsx';
import WorkspaceEmptyState from '../../components/WorkspaceEmptyState.jsx';
import SearchField from '../search/SearchField.jsx';
import WorkspaceChrome from '../../components/WorkspaceChrome.jsx';
import WorkspaceControls from '../../components/WorkspaceControls.jsx';
import WorkspaceSelectionBar from '../../components/WorkspaceSelectionBar.jsx';
import ListsToolbar from '../../components/ListsToolbar.jsx';
import CatalogMetadataFilters, { catalogSortChoices } from '../../components/CatalogMetadataFilters.jsx';
import useListCatalogFilters from '../../hooks/useListCatalogFilters.js';
import { tvGenres } from '../../utils/catalogFilterOptions.js';
import { hasListFilters, tvListCriteria } from '../../utils/listCatalogFilters.js';
import { TVSeriesCard } from '../tv/TVWorkspace.jsx';
import TVBulkActionBar from '../tv/TVBulkActionBar.jsx';
import TVPosterEditor from '../tv/TVPosterEditor.jsx';

const request = (url, method, body) => fetchJson(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export default function TVListsWorkspace({ notify, mediaNavigation, onBrowseTV }) {
  const [listId, setListId] = useState('watchlist');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const { filters, effective, countries, yearDraft, changeFilter, resetFilters } = useListCatalogFilters();
  const criteria = JSON.stringify(tvListCriteria(effective, tvGenres));
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(() => new Set());
  const [data, setData] = useState(null);
  const [targetList, setTargetList] = useState('');
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState('');
  const [posterEditor, setPosterEditor] = useState(null);
  const [settledRequestKey, setSettledRequestKey] = useState('');
  const requestKey = JSON.stringify([listId, query, filter, criteria, page, revision]);
  const pending = requestKey !== settledRequestKey;
  useEffect(() => {
    let alive = true;
    setError('');
    const params = new URLSearchParams({ list_id: listId, query, status: filter, criteria, page: String(page), page_size: '40' });
    fetchJson(`/api/tv/lists?${params}`).then((result) => { if (alive) { setData(result); setError(''); } })
      .catch((failure) => { if (alive) setError(failure.message); })
      .finally(() => { if (alive) setSettledRequestKey(requestKey); });
    return () => { alive = false; };
  }, [listId, query, filter, criteria, page, revision, requestKey]);
  function changeMetadataFilter(key, value) { changeFilter(key, value); setPage(1); }
  function clearFilters() { resetFilters(); setFilter('all'); setPage(1); }
  async function mutate(action) {
    try { await action(); setRevision((value) => value + 1); }
    catch (failure) { notify(failure.message, 'error'); }
  }
  const lists = data?.lists || [];
  const current = lists.find((list) => list.id === listId);
  const selectedIds = [...selected];
  function select(series, checked) {
    setSelected((currentIds) => { const next = new Set(currentIds); if (checked) next.add(series.id); else next.delete(series.id); return next; });
  }
  function changeList(id) { setListId(id); setPage(1); setSelected(new Set()); }
  async function create(name) {
    const created = await request('/api/tv/lists', 'POST', { name });
    changeList(created.id);
    setRevision(value => value + 1);
    notify?.(`List created: ${created.name}`);
  }
  async function renameList(name) {
    if (!current || current.system) return;
    await request(`/api/tv/lists/${listId}`, 'PATCH', { name });
    setRevision(value => value + 1);
    notify?.('TV list renamed');
  }
  async function deleteList() {
    if (!current || current.system || !window.confirm(`Delete TV list "${current.name}"? Its shows and files remain intact.`)) return;
    await mutate(async () => { await fetchJson(`/api/tv/lists/${listId}`, { method: 'DELETE' }); changeList('watchlist'); });
  }
  async function changeMembership(destination, present) {
    if (!selectedIds.length) return;
    await mutate(async () => {
      await request(`/api/tv/lists/${destination}/series`, present ? 'POST' : 'DELETE', { series_ids: selectedIds });
      setSelected(new Set());
    });
  }
  async function play(episodeId) {
    await mutate(() => request(`/api/tv/episodes/${episodeId}/play`, 'POST', {}));
  }
  function openSeries(series) {
    window.history.pushState({}, '', `/tv/series/${series.id}`);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }
  return <section className="library-workspace movie-lists-workspace tv-lists-workspace" aria-label="TV Lists">
    <WorkspaceChrome navigation={mediaNavigation}>
      <ListsToolbar lists={lists} selectedList={current} noun="shows" onSelect={changeList}
        onCreate={create} onRename={renameList} onDelete={deleteList} onAdd={onBrowseTV} addLabel="Find shows" />
      <WorkspaceControls loadedCount={current?.count || 0} countLabel="shows" selectedCount={selectedIds.length}
        summary={hasListFilters(filters) ? `${data?.total || 0} matches` : filter === 'all' ? 'All' : filter === 'offline' ? 'Offline' : filter === 'missing' ? 'Missing offline' : 'Completely watched'}
        notice={yearDraft.error && <p role="alert" id="tv-list-year-error">{yearDraft.error}</p>}
        search={<form className="library-search-panel workspace-search-form movie-lists-search" onSubmit={event => event.preventDefault()}>
          <SearchField className="library-main-search" onClear={query ? () => { setQuery(''); setPage(1); } : undefined}>
            <Search size={18}/><Input aria-label="Search TV list" value={query} onChange={event => { setQuery(event.target.value); setPage(1); }} placeholder={`Search ${current?.name || 'the selected TV list'}...`} />
          </SearchField>
          <Button variant="primary" type="submit" className="library-search-submit"><Search size={16}/> Search</Button>
        </form>}
        filters={<div className="workspace-filter-grid lists-filter-row">
          <Select aria-label="TV list status" value={filter} onChange={event => { setFilter(event.target.value); setPage(1); }}>
            <option value="all">All shows</option><option value="offline">Offline</option><option value="missing">Missing offline</option><option value="watched">Completely watched</option>
          </Select>
          <CatalogMetadataFilters prefix="TV " countryLabel="Origin country" values={filters} genres={tvGenres} countries={countries} onChange={changeMetadataFilter} yearError={yearDraft.error} yearErrorId="tv-list-year-error" sortChoices={catalogSortChoices.map(([key, label]) => [key, key === 'primary_release_date.desc' ? 'First-air date' : label])}/>
          <Button type="button" className="lists-filter-icon" aria-label="Clear filters" title="Clear filters" disabled={filter === 'all' && !hasListFilters(filters)} onClick={clearFilters}><X size={16}/></Button>
          <Button type="button" className="lists-filter-icon" aria-label="Refresh TV lists" title="Refresh list" disabled={pending} onClick={() => setRevision(value => value + 1)}><RefreshCw size={16}/></Button>
        </div>}
        selection={data?.items?.length > 0 && <WorkspaceSelectionBar noun="TV shows" selectedCount={selectedIds.length}
          allSelected={data.items.every(row => selected.has(row.id))} label="Select all loaded TV shows"
          onToggleAll={checked => setSelected(previous => { const next = new Set(previous); data.items.forEach(row => checked ? next.add(row.id) : next.delete(row.id)); return next; })}
          onClear={() => setSelected(new Set())}/>} />
      {selectedIds.length > 0 && <div className="lists-tv-selection">
        <div className="bulk-selection-bar lists-active-selection" role="region" aria-label="Selected TV list actions">
          <strong>{selectedIds.length} selected TV shows</strong>
          <Select className="library-mini-input" aria-label="Add selected TV shows to list" value={targetList} onChange={event => setTargetList(event.target.value)}><option value="">Choose TV custom list</option>{lists.filter(list => !list.system).map(list => <option key={list.id} value={list.id}>{list.name}</option>)}</Select>
          <Button size="compact" type="button"  disabled={!targetList} onClick={() => changeMembership(targetList, true)}>Add to a list</Button>
          <Button variant="danger" size="compact" type="button"  disabled={!current || current.system} onClick={() => changeMembership(listId, false)}>Remove from list</Button>
        </div>
        <TVBulkActionBar seriesIds={selectedIds} onClear={() => setSelected(new Set())} onChanged={() => setRevision(value => value + 1)} notify={notify} showAdd={false}/>
      </div>}
    </WorkspaceChrome>
    <div className="movie-lists-main">
      {!pending && error && <p role="alert">{error}</p>}
      {pending && <p role="status">{data ? 'Updating TV lists…' : 'Loading TV lists…'}</p>}
      {!pending && !error && data && !current && <p role="alert">The selected TV list is unavailable. Choose another list above.</p>}
      {!pending && !error && current && data && !data.items.length && (
        data.total > 0 ? (page > data.total_pages ? (
          <WorkspaceEmptyState title="No results on this page." description="This page is outside the available results.">
            <Button variant="primary" type="button"  onClick={() => setPage(data.total_pages)}>Go to page {data.total_pages}</Button>
          </WorkspaceEmptyState>
        ) : <p role="alert">This result page is unavailable. Choose another page or refresh the list.</p>) : current.count > 0 ? (
          <WorkspaceEmptyState title="No shows match this list view." description="Clear the search and filters to see the full list.">
            <Button variant="primary" type="button"  onClick={() => { setQuery(''); clearFilters(); }}>Clear filters</Button>
          </WorkspaceEmptyState>
        ) : (
          <WorkspaceEmptyState
            title={listId === 'watchlist' ? 'Your TV Watchlist is empty.' : listId === 'watched' ? 'No completely watched shows yet.' : 'This TV list is empty.'}
            description={listId === 'watchlist' ? 'Save shows to Watchlist from Library or Discover.' : listId === 'watched' ? 'Shows marked completely watched appear here.' : 'Add shows from Library or Discover using Add to a list.'}
          />
        )
      )}
      {data?.items?.length > 0 && <div className="library-results library-movie-results movie-lists-card-grid">{data.items.map((series) => <TVSeriesCard key={series.id} series={series} context="lists" selected={selected.has(series.id)} onSelect={select}
        onOpen={openSeries} onPlay={play}
        onWatchlist={(row) => mutate(() => request(`/api/tv/series/${row.id}/watchlist`, 'POST', { watchlisted: !row.watchlisted }))}
        onWatched={(row) => mutate(() => request(`/api/tv/series/${row.id}/watched`, 'POST', { watched: !row.series_watched }))}
        onPosterEdit={setPosterEditor}/>)}</div>}
      {data && <Pagination page={page} total={data.total} totalPages={data.total_pages} pageStart={(page-1)*data.page_size} pageEnd={(page-1)*data.page_size+data.items.length} ariaLabel="TV Lists pages" onPageChange={setPage}/>}
      {posterEditor && <TVPosterEditor series={posterEditor} onClose={() => setPosterEditor(null)} onSaved={() => setRevision(value => value + 1)} notify={notify} />}
    </div>
  </section>;
}
