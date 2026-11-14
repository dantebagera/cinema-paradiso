import { AlertTriangle, ChevronDown, Loader2, Play, X, Youtube } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import HorizontalCardRail from '../../components/HorizontalCardRail.jsx';
import { groupHomeTrailers } from './homeTrailerModel.js';

function publishedLabel(value) {
  const timestamp = Date.parse(value || '');
  if (!Number.isFinite(timestamp)) return '';
  const minutes = Math.max(1, Math.floor((Date.now() - timestamp) / 60000));
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)} hr ago`;
  const days = Math.floor(minutes / 1440);
  return `${days} day${days === 1 ? '' : 's'} ago`;
}

export default function HomeTrailersPanel({ feed, loading, refreshing, loadingMore, error, onOpenVideo, onRetry, onLoadMore }) {
  const [source, setSource] = useState('all');
  const [versions, setVersions] = useState(null);
  const dialog = useRef(null);
  const groups = useMemo(() => groupHomeTrailers(feed?.items, source), [feed?.items, source]);
  useEffect(() => {
    if (!versions) return;
    const trigger = document.activeElement;
    const element = dialog.current;
    element.showModal();
    const owner = element.closest('.workspace-panel');
    const observer = new MutationObserver(() => { if (owner?.hidden) setVersions(null); });
    if (owner) observer.observe(owner, { attributes: true, attributeFilter: ['hidden'] });
    return () => { observer.disconnect(); element.close(); if (!owner?.hidden) trigger?.focus({ preventScroll: true }); };
  }, [versions]);
  const heading = <div className="section-heading home-trailers-heading">
    <div><p className="screen-kicker">Trailer channels</p><h3 id="home-trailers-heading">New Trailers</h3></div>
    <div className="home-trailer-actions">
      {feed?.has_more && !error && <button className="home-load-trailers ghost-link" disabled={loadingMore || refreshing} onClick={onLoadMore}>{loadingMore && <Loader2 className="spin" size={15} />}{loadingMore ? 'Loading videos…' : 'More videos'}</button>}
    </div>
    <div className="home-trailer-source-filters" role="group" aria-label="Trailer channel">
      {[{ id: 'all', name: 'All' }, ...(feed?.sources || [])].map(item => <button key={item.id} type="button" aria-pressed={source === item.id} onClick={() => { setSource(item.id); setVersions(null); }}>{item.name}</button>)}
    </div>
  </div>;
  return <section className="home-trailers-panel" aria-labelledby="home-trailers-heading">
    <HorizontalCardRail label="New trailers" arrowPlacement="header" resetKey={source} header={heading} trackClassName="home-trailer-grid">
      {loading ? Array.from({ length: 4 }, (_, index) => <div className="home-video-card skeleton-card" key={index} />) : !error && groups.map(group => {
        const video = group.videos[0];
        return <article className="home-video-card" key={group.key}>
          <button type="button" className="home-video-thumbnail" aria-label={`Play ${video.title}`} onClick={() => onOpenVideo(video)}><img src={video.thumbnail_url} alt="" loading="lazy" /><span className="home-video-play"><Youtube size={24} /></span><span className="home-video-type">{group.type}</span></button>
          <div className="home-video-copy"><button className="home-video-title" onClick={() => onOpenVideo(video)} title={video.title}>{group.title}</button><small className="home-video-source">{video.source_name || 'YouTube'}</small><div className="home-video-footer"><small>{publishedLabel(video.published_at)}</small>{group.videos.length > 1 && <button onClick={() => setVersions(group)} aria-label={`Choose from ${group.videos.length} videos for ${group.title}`}>{group.videos.length} videos<ChevronDown size={13} /></button>}</div></div>
        </article>;
      })}
    </HorizontalCardRail>
    {!loading && (error || !groups.length) && <div className="home-feed-empty">{error ? <AlertTriangle size={22} /> : <Youtube size={22} />}<strong>{error ? 'Trailers are temporarily unavailable.' : 'No videos in this channel.'}</strong>{error && <><span>{error}</span><button className="ghost-link" onClick={onRetry}>Retry</button></>}</div>}
    {feed?.stale && <small className="home-feed-stale">Showing the last successfully refreshed trailers.</small>}
    {versions && <dialog ref={dialog} className="home-trailer-versions" aria-labelledby="home-trailer-versions-title" onCancel={() => setVersions(null)} onClick={event => { if (event.target === event.currentTarget) setVersions(null); }}><header><h3 id="home-trailer-versions-title">{versions.title}</h3><button onClick={() => setVersions(null)} aria-label="Close trailer versions"><X size={18} /></button></header>{versions.videos.map(video => <button key={video.video_id} onClick={() => { setVersions(null); onOpenVideo(video); }}><Youtube size={20} /><span><strong>{video.title}</strong><small>{video.source_name}</small></span><Play size={18} /></button>)}</dialog>}
  </section>;
}
