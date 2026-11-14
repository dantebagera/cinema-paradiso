import WorkspaceEmptyState from '../../components/WorkspaceEmptyState.jsx';
import { Input } from '../../components/ui/FormField.jsx';
import Button from '../../components/ui/Button.jsx';
import Badge from '../../components/ui/Badge.jsx';
import WorkspaceControls from '../../components/WorkspaceControls.jsx';
import WorkspaceChrome from '../../components/WorkspaceChrome.jsx';
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
          <Badge size="compact" >{facts.quality_class || 'Quality unknown'}</Badge>
          <Badge size="compact" tone="neutral" muted >{facts.source || 'Source unknown'}</Badge>
          <Badge size="compact" tone="neutral" muted >{Math.round(file.size / 1048576)} MB</Badge>
          <Badge size="compact" kind="status" tone={file.available ? 'owned' : 'missing'}>{file.available ? 'Available' : 'Missing locally'}</Badge>
          {file.episodes.length > 1 && <Badge size="compact" tone="neutral" muted >{file.episodes.length} episodes</Badge>}
        </div>
      </div>
    </div>
    <div className="file-row-actions">
      <Button variant="play" type="button"  disabled={!file.available || !firstEpisode} title={file.episodes.length > 1 ? 'Play the first mapped episode' : 'Play this episode'} onClick={() => onPlay(firstEpisode.episode_id, file.file_id)}><Play size={15}/> Play</Button>
      <Button type="button"  disabled={!firstEpisode} onClick={() => onOpenSeries({ id: firstEpisode.series_id })}><Clapperboard size={15}/> Media View</Button>
      <Button type="button" className="file-row-expand" aria-label={`${expanded ? 'Collapse' : 'Expand'} file details for ${file.filename}`} aria-expanded={expanded} onClick={() => setExpanded(value => !value)}><ChevronDown size={17}/></Button>
    </div>
    {expanded && <div className="file-expanded-panel">
      <div><span>Full path</span><strong>{file.path}</strong></div>
      <div><span>Size</span><strong>{file.size.toLocaleString()} bytes</strong></div>
      <div><span>Video</span><strong>{[facts.video_codec, facts.video_width && facts.video_height ? `${facts.video_width} × ${facts.video_height}` : ''].filter(Boolean).join(' · ') || 'Unavailable'}</strong></div>
      <div><span>Audio</span><strong>{[facts.audio_codec, facts.audio_language].filter(Boolean).join(' · ') || 'Unavailable'}</strong></div>
      <div className="file-expanded-section-title"><span>Episode bindings</span><strong>{file.episodes.length} mapped episode{file.episodes.length === 1 ? '' : 's'}</strong></div>
      {file.episodes.map(episode => <div key={episode.episode_id}><span>Episode</span><strong>{episodeLabel(episode)}</strong><Button type="button"  disabled={!file.available} onClick={() => onPlay(episode.episode_id, file.file_id)}>Play episode</Button></div>)}
    </div>}
  </article>;
}

export default function TVFileView({ onOpenSeries, onPlay, mediaNavigation, viewActions }) {
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
    <WorkspaceChrome navigation={mediaNavigation}>
    <WorkspaceControls actions={viewActions} loadedCount={data?.items?.length || 0} countLabel="files loaded" summary={query ? `Search: ${query}` : undefined} search={<form className="workspace-search-form" data-people-search="true" onSubmit={event => { event.preventDefault(); setPage(1); setQuery(draft.trim()); }}>
      <SearchField className="library-main-search" clearLabel="Clear TV file search" onClear={draft || query ? () => { setDraft(''); setQuery(''); setPage(1); } : undefined}><Search size={17}/><Input aria-label="Search TV files" placeholder="Search TV files or series…" value={draft} onChange={event => setDraft(event.target.value)}/></SearchField>
      <Button type="button" className="tv-file-refresh" aria-label="Refresh TV files" onClick={() => setRevision(value => value + 1)}><RefreshCw size={17}/></Button>
      <Button variant="primary" type="submit" className="library-search-submit"><Search size={15}/> Search</Button>
    </form>}/>
    </WorkspaceChrome>
    {error ? <WorkspaceEmptyState size="compact"  role="alert"><strong>{error}</strong><Button onClick={() => setRevision(value => value + 1)}>Retry</Button></WorkspaceEmptyState>
      : !data ? <div className="loading-state" role="status">Loading TV files…</div>
      : <>{pagination('TV files page controls above results')}
        {data.items.length ? <div className="library-results library-file-results">{data.items.map(file => <TVFileRow key={file.file_id} file={file} onOpenSeries={onOpenSeries} onPlay={onPlay}/>)}</div>
          : <WorkspaceEmptyState size="regular" className="library-empty"><strong>No TV files match this search.</strong><span>TV File View shows files in the native TV catalog.</span></WorkspaceEmptyState>}
        {pagination('TV files pagination')}</>}
  </div>;
}
