import { useEffect, useState } from 'react';
import { Bookmark, Check, CirclePlus, Pencil, Search, Trash2 } from 'lucide-react';
import { fetchJson } from '../../api/client.js';
import Pagination from '../../components/Pagination.jsx';
import { TVSeriesCard } from '../tv/TVWorkspace.jsx';
import TVBulkActionBar from '../tv/TVBulkActionBar.jsx';
import TVPosterEditor from '../tv/TVPosterEditor.jsx';

const request = (url, method, body) => fetchJson(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export default function TVListsWorkspace({ notify }) {
  const [listId, setListId] = useState('watchlist');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(() => new Set());
  const [data, setData] = useState(null);
  const [newName, setNewName] = useState('');
  const [rename, setRename] = useState('');
  const [targetList, setTargetList] = useState('');
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState('');
  const [posterEditor, setPosterEditor] = useState(null);
  useEffect(() => {
    let alive = true;
    const params = new URLSearchParams({ list_id: listId, query, status: filter, page: String(page), page_size: '40' });
    fetchJson(`/api/tv/lists?${params}`).then((result) => { if (alive) { setData(result); setError(''); } })
      .catch((failure) => { if (alive) setError(failure.message); });
    return () => { alive = false; };
  }, [listId, query, filter, page, revision]);
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
  function changeList(id) { setListId(id); setPage(1); setSelected(new Set()); setRename(lists.find((list) => list.id === id)?.name || ''); }
  async function create(event) {
    event.preventDefault();
    if (!newName.trim()) return;
    await mutate(async () => { const created = await request('/api/tv/lists', 'POST', { name: newName.trim() }); setNewName(''); changeList(created.id); });
  }
  async function renameList(event) {
    event.preventDefault();
    if (current?.system || !rename.trim()) return;
    await mutate(() => request(`/api/tv/lists/${listId}`, 'PATCH', { name: rename.trim() }));
  }
  async function deleteList() {
    if (current?.system || !window.confirm(`Delete TV list "${current.name}"? Its shows and files remain intact.`)) return;
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
    <header className="library-header movie-lists-header"><div><p className="screen-kicker">TV SHOWS</p><h2>Lists</h2><p>TV watch history and custom lists stay separate from movies. Shows remain here after local files are removed.</p></div>
      <div className="movie-list-summary-strip"><span><strong>{data?.total || 0}</strong>Shows</span><span><strong>{(data?.items || []).filter((row) => row.available_count > 0).length}</strong>Offline on this page</span></div></header>
    <form className="library-search-panel movie-lists-search" onSubmit={(event) => event.preventDefault()}><label className="search-field library-main-search"><Search size={18}/><input aria-label="Search TV list" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder="Search the selected TV list..." /></label></form>
    <div className="movie-lists-layout"><aside className="movie-lists-rail" aria-label="TV lists">
      <form className="movie-list-create-inline" onSubmit={create}><input aria-label="New TV list name" value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="New TV list name..."/><button type="submit" className="mini-action" disabled={!newName.trim()}><CirclePlus size={13}/>New list</button></form>
      {lists.map((list) => <button type="button" key={list.id} className={`movie-list-rail-item${listId === list.id ? ' movie-list-rail-item-active' : ''}`} onClick={() => changeList(list.id)}><span className="movie-list-rail-title">{list.id === 'watched' ? <Check size={16}/> : list.id === 'watchlist' ? <Bookmark size={16}/> : null}{list.name}</span><small>{list.count} shows</small></button>)}
    </aside><div className="movie-lists-main">
      <form className="movie-list-management-bar" onSubmit={renameList}><input aria-label="Selected TV list name" value={rename || current?.name || ''} onChange={(event) => setRename(event.target.value)} disabled={!current || current.system}/><button type="submit" className="mini-action" disabled={!current || current.system || !rename.trim()}><Pencil size={13}/>Rename list</button><button type="button" className="mini-action mini-action-danger" disabled={!current || current.system} onClick={deleteList}><Trash2 size={13}/>Delete list</button></form>
      <div className="library-toolbar movie-lists-filterbar">{[['all','All'],['offline','Offline'],['missing','Missing offline'],['watched','Completely watched']].map(([id,label]) => <button type="button" key={id} className={`filter-chip-button${filter === id ? ' filter-chip-button-active' : ''}`} onClick={() => { setFilter(id); setPage(1); }}>{label}</button>)}</div>
      <div className="bulk-selection-bar movie-lists-bulk"><span>{selectedIds.length} selected TV shows</span><button type="button" className="mini-action" disabled={!selectedIds.length} onClick={() => setSelected(new Set())}>Clear</button>
        <select aria-label="Add selected TV shows to list" value={targetList} onChange={(event) => setTargetList(event.target.value)}><option value="">Choose TV custom list</option>{lists.filter((list) => !list.system).map((list) => <option key={list.id} value={list.id}>{list.name}</option>)}</select>
        <button type="button" className="mini-action" disabled={!selectedIds.length || !targetList} onClick={() => changeMembership(targetList, true)}>Add to a list</button>
        <button type="button" className="mini-action mini-action-danger" disabled={!selectedIds.length || !current || current.system} onClick={() => changeMembership(listId, false)}>Remove from list</button></div>
      {selectedIds.length > 0 && <TVBulkActionBar seriesIds={selectedIds} onClear={() => setSelected(new Set())} onChanged={() => setRevision(value => value + 1)} notify={notify} showAdd={false} />}
      {error && <p role="alert">{error}</p>}
      {!data && !error && <p role="status">Loading TV lists…</p>}
      {data && !data.items.length && <p className="empty-state">No TV shows in this list match the current search and filter.</p>}
      {data?.items?.length > 0 && <div className="library-results library-movie-results movie-lists-card-grid">{data.items.map((series) => <TVSeriesCard key={series.id} series={series} context="lists" selected={selected.has(series.id)} onSelect={select}
        onOpen={openSeries} onPlay={play}
        onWatchlist={(row) => mutate(() => request(`/api/tv/series/${row.id}/watchlist`, 'POST', { watchlisted: !row.watchlisted }))}
        onWatched={(row) => mutate(() => request(`/api/tv/series/${row.id}/watched`, 'POST', { watched: !row.series_watched }))}
        onPosterEdit={setPosterEditor}/>)}</div>}
      {data && <Pagination page={page} total={data.total} totalPages={data.total_pages} pageStart={(page-1)*data.page_size} pageEnd={(page-1)*data.page_size+data.items.length} ariaLabel="TV Lists pages" onPageChange={setPage}/>}
      {posterEditor && <TVPosterEditor series={posterEditor} onClose={() => setPosterEditor(null)} onSaved={() => setRevision(value => value + 1)} notify={notify} />}
    </div></div>
  </section>;
}
