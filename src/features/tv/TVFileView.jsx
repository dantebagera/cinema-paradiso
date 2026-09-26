import { useEffect, useState } from 'react';
import { ChevronDown, Clapperboard, Play, RefreshCw, Search } from 'lucide-react';
import { fetchJson } from '../../api/client.js';
import Pagination from '../../components/Pagination.jsx';
import SearchField from '../search/SearchField.jsx';

function episodeLabel(episode) {
  return `${episode.series_title} · S${String(episode.season_number).padStart(2, '0')}E${String(episode.episode_number).padStart(2, '0')} · ${episode.episode_title}`;
}

function TVFileRow({ file, onOpenSeries, onPlay }) {
  const [expanded, setExpanded] = useState(false);
  const firstEpisode = file.episodes[0];
  const facts = file.facts || {};
  return <article className={`library-file-row${expanded ? ' library-file-row-expanded' : ''}`}>
    <div className="file-row-main">
      <div className="file-row-copy">
        <div className="file-row-title"><strong>{file.filename}</strong><span>{firstEpisode?.series_title || 'Episode identity needs review'}</span></div>
        <div className="file-row-path" title={file.path}>{file.path}</div>
        <div className="file-row-meta">
          <span className="chip">{facts.quality_class || 'Quality unknown'}</span>
          <span className="chip chip-muted">{facts.source || 'Source unknown'}</span>
          <span className="chip chip-muted">{Math.round(file.size / 1048576)} MB</span>
          <span className={file.available ? 'chip status-owned' : 'chip status-missing'}>{file.available ? 'Available' : 'Missing locally'}</span>
          {file.episodes.length > 1 && <span className="chip chip-muted">{file.episodes.length} episodes</span>}
        </div>
      </div>
    </div>
    <div className="file-row-actions">
      <button type="button" className="btn btn-primary btn-green" disabled={!file.available || !firstEpisode} title={file.episodes.length > 1 ? 'Play the first mapped episode' : 'Play this episode'} onClick={() => onPlay(firstEpisode.episode_id, file.file_id)}><Play size={15}/> Play</button>
      <button type="button" className="btn btn-secondary" disabled={!firstEpisode} onClick={() => onOpenSeries({ id: firstEpisode.series_id })}><Clapperboard size={15}/> Media View</button>
      <button type="button" className="btn btn-secondary file-row-expand" aria-label={`${expanded ? 'Collapse' : 'Expand'} file details for ${file.filename}`} aria-expanded={expanded} onClick={() => setExpanded(value => !value)}><ChevronDown size={17}/></button>
    </div>
    {expanded && <div className="file-expanded-panel">
      <div><span>Full path</span><strong>{file.path}</strong></div>
      <div><span>Size</span><strong>{file.size.toLocaleString()} bytes</strong></div>
      <div><span>Video</span><strong>{[facts.video_codec, facts.video_width && facts.video_height ? `${facts.video_width} × ${facts.video_height}` : ''].filter(Boolean).join(' · ') || 'Unavailable'}</strong></div>
      <div><span>Audio</span><strong>{[facts.audio_codec, facts.audio_language].filter(Boolean).join(' · ') || 'Unavailable'}</strong></div>
      <div className="file-expanded-section-title"><span>Episode bindings</span><strong>{file.episodes.length} mapped episode{file.episodes.length === 1 ? '' : 's'}</strong></div>
      {file.episodes.map(episode => <div key={episode.episode_id}><span>Episode</span><strong>{episodeLabel(episode)}</strong><button type="button" className="btn btn-secondary" disabled={!file.available} onClick={() => onPlay(episode.episode_id, file.file_id)}>Play episode</button></div>)}
    </div>}
  </article>;
}

export default function TVFileView({ onOpenSeries, onPlay }) {
  const [draft, setDraft] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError('');
    fetchJson(`/api/tv/files?${new URLSearchParams({ query, page: String(page), page_size: '50' })}`, { signal: controller.signal })
      .then(setData).catch(cause => { if (cause.name !== 'AbortError') setError(cause.message); });
    return () => controller.abort();
  }, [query, page, revision]);
  const pagination = label => data && <Pagination total={data.total} page={data.page} totalPages={data.total_pages} pageStart={(data.page - 1) * data.page_size} pageEnd={(data.page - 1) * data.page_size + data.items.length} ariaLabel={label} onPageChange={setPage}/>;
  return <div className="tv-file-view">
    <form className="library-search-panel" data-people-search="true" onSubmit={event => { event.preventDefault(); setPage(1); setQuery(draft.trim()); }}>
      <SearchField className="library-main-search"><Search size={17}/><input aria-label="Search TV files" placeholder="Search TV files or series…" value={draft} onChange={event => setDraft(event.target.value)}/></SearchField>
      <button type="button" className="btn btn-secondary tv-file-refresh" aria-label="Refresh TV files" onClick={() => setRevision(value => value + 1)}><RefreshCw size={17}/></button>
      <button type="submit" className="btn btn-primary library-search-submit"><Search size={15}/> Search</button>
    </form>
    {error ? <div className="empty-state" role="alert"><strong>{error}</strong><button onClick={() => setRevision(value => value + 1)}>Retry</button></div>
      : !data ? <div className="loading-state" role="status">Loading TV files…</div>
      : <>{pagination('TV files page controls above results')}
        {data.items.length ? <div className="library-results library-file-results">{data.items.map(file => <TVFileRow key={file.file_id} file={file} onOpenSeries={onOpenSeries} onPlay={onPlay}/>)}</div>
          : <div className="empty-state library-empty"><strong>No TV files match this search.</strong><span>TV File View shows files in the native TV catalog.</span></div>}
        {pagination('TV files pagination')}</>}
  </div>;
}
