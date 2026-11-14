import Button from './ui/Button.jsx';
import { DialogHeader } from './ui/DialogShell.jsx';
import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, Loader2, Play, X } from 'lucide-react';
import { fetchJson } from '../api/client.js';
import { buildStreamTemplateUrl, canResolveMovieStreamTemplate, streamTemplateTokens } from '../utils/appUtils.js';
import usePlayerDialog from '../hooks/usePlayerDialog.js';
import useIPTVMovieAvailability from '../hooks/useIPTVMovieAvailability.js';
import { getMovieStreamingSources, invalidateMovieAvailability } from '../api/iptvAvailability.js';
import useIPTVPlaybackSession from '../features/iptv/useIPTVPlaybackSession.js';
import IPTVPlayer from '../features/iptv/IPTVPlayer.jsx';
import IPTVSourceList from '../features/iptv/IPTVSourceList.jsx';
import YouTubeMovieSource from './YouTubeMovieSource.jsx';
import './streamPlayer.css';

function WebStreamPlayer({ embedUrl, title }) {
  const [visible, setVisible] = useState(true);
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    setVisible(true);
    setSlow(false);
    const slowTimer = window.setTimeout(() => setSlow(true), 12000);
    const hideTimer = window.setTimeout(() => setVisible(false), 30000);
    return () => { window.clearTimeout(slowTimer); window.clearTimeout(hideTimer); };
  }, [embedUrl]);
  return <div className="trailer-player-shell stream-player-shell">
    {visible && <div className="stream-loading-overlay" role="status" aria-live="polite">
      <Loader2 size={28} className="spin" /><strong>Loading stream page...</strong>
      <span className="stream-loading-bar" aria-hidden="true"><span /></span>
      <small>{slow ? 'The streaming page is taking longer than usual. You can keep waiting or close the player.'
        : 'The streaming page can take a moment to load.'}</small>
    </div>}
    <iframe key={embedUrl} title={`${title} stream`} src={embedUrl}
      allow="autoplay; fullscreen; picture-in-picture; encrypted-media"
      onLoad={() => setVisible(false)} allowFullScreen />
  </div>;
}

export default function StreamPlayerModal({ state, config = {}, onClose }) {
  const dialogRef = usePlayerDialog(onClose);
  const title = [state.title, state.year].filter(Boolean).join(' ');
  const [embedUrl, setEmbedUrl] = useState(state.embedUrl || '');
  const [youtube, setYoutube] = useState(false);
  const [versions, setVersions] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const request = useRef(null);
  const session = useIPTVPlaybackSession();
  const availability = useIPTVMovieAvailability([state.movie?.tmdb_id],
    Boolean(state.movie) && !embedUrl && !session.playback);
  useEffect(() => () => request.current?.abort(), []);
  const webSources = config.enabled ? config.movie_sources || [] : [];
  const selectableWebSources = webSources.filter(source => canResolveMovieStreamTemplate(source.url_template, state.movie));
  const providers = availability.loading && !availability.providers?.length
    ? (config.iptv_providers || []).map(provider => ({ ...provider, state: 'checking' }))
    : availability.providers || [];
  const matched = providers.filter(provider => provider.state === 'ready' && provider.matches?.[String(state.movie?.tmdb_id)]);
  const other = providers.filter(provider => !matched.includes(provider));

  function beginRequest() {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setError('');
    setBusy(true);
    return controller;
  }

  async function chooseWeb(source) {
    const controller = beginRequest();
    try {
      await session.stopActive();
      const ids = { tmdb_id: state.movie?.tmdb_id, imdb_id: state.movie?.imdb_id };
      if (streamTemplateTokens(source.url_template).includes('imdb_id') && !ids.imdb_id) {
        if (!ids.tmdb_id) throw new Error('Missing TMDB ID for IMDb lookup');
        const data = await fetchJson(`/api/tmdb/imdb_id?tmdb_id=${encodeURIComponent(ids.tmdb_id)}`, { signal: controller.signal });
        ids.imdb_id = data.imdb_id;
      }
      const url = buildStreamTemplateUrl(source.url_template, ids);
      if (!controller.signal.aborted) { setVersions(null); setEmbedUrl(url); }
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure.message);
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  async function playVersion(provider, source) {
    const controller = beginRequest();
    try {
      const fresh = await getMovieStreamingSources(provider.provider_id, state.movie.tmdb_id, { signal: controller.signal });
      const current = fresh.items.find(item => item.source_key === source.source_key && item.available);
      if (!current) throw new Error('This version is no longer in the saved catalog. Choose another source.');
      await session.start(provider.provider_id, {
        kind: 'movie', item_id: current.item_id, extension: current.container_extension,
        title: current.name || state.title,
      });
      if (!controller.signal.aborted) setVersions(null);
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure.message);
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  async function chooseProvider(provider) {
    const controller = beginRequest();
    try {
      const result = await getMovieStreamingSources(provider.provider_id, state.movie.tmdb_id, { signal: controller.signal });
      if (controller.signal.aborted) return;
      const sources = result.items.filter(source => source.available);
      if (!sources.length) throw new Error('This movie is no longer in the saved catalog.');
      if (sources.length === 1) {
        await playVersion(provider, sources[0]);
      } else {
        setVersions({ provider, sources: result.items });
      }
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure.message);
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  async function changeSource() {
    request.current?.abort();
    setEmbedUrl('');
    setYoutube(false);
    setVersions(null);
    setBusy(false);
    setError('');
    try { await session.stop(); } catch (failure) { setError(failure.message); }
  }

  function retryAvailability() {
    invalidateMovieAvailability();
    window.dispatchEvent(new Event('cp-iptv-catalog-changed'));
  }

  function providerRow(provider, available) {
    return <button type="button" key={provider.provider_id} disabled={busy || !available}
      className={provider.provider_id === state.highlightedProviderId ? 'stream-source-highlighted' : ''}
      onClick={() => chooseProvider(provider)}>
      <span><strong dir="auto">{provider.name}</strong><small>{available ? 'In catalog'
        : provider.state === 'checking' ? 'Checking saved catalog'
          : provider.state === 'unknown' ? 'Catalog unavailable' : 'Not in saved catalog'}</small></span>
      {available && <Play size={18} />}
    </button>;
  }

  return <div className="modal-backdrop trailer-backdrop" role="presentation" onClick={onClose}>
    <section ref={dialogRef} className="trailer-dialog stream-dialog" role="dialog" aria-modal="true"
      aria-label={`Stream ${title}`} onClick={event => event.stopPropagation()}>
      <DialogHeader className="trailer-dialog-header">
        <div><p className="screen-kicker">Streaming</p><h2>{title}</h2></div>
        {state.movie && (embedUrl || session.playback || versions || youtube) &&
          <Button type="button"  onClick={changeSource}>Change source</Button>}
        <Button size="icon" type="button" className="inspector-close" onClick={onClose} aria-label="Close stream"><X size={18} /></Button>
      </DialogHeader>
      {youtube ? <YouTubeMovieSource movie={state.movie} Player={WebStreamPlayer} />
        : embedUrl ? <WebStreamPlayer embedUrl={embedUrl} title={title} />
        : session.playback ? <IPTVPlayer playback={session.playback} />
          : <div className="stream-source-stage">
            {(error || availability.error) && <div className="stream-source-error" role="alert">
              <AlertTriangle size={18} /><span>{error || availability.error}</span>
              <Button type="button"  onClick={retryAvailability}>Retry</Button>
            </div>}
            {versions ? <IPTVSourceList sources={versions.sources} disabled={busy}
              onChoose={source => playVersion(versions.provider, source)} />
              : <div className="iptv-source-list">
                {matched.map(provider => providerRow(provider, true))}
                {webSources.map(source => <button type="button" key={source.id} disabled={busy || !selectableWebSources.includes(source)} onClick={() => chooseWeb(source)}>
                  <span><strong>{source.label}</strong><small>{selectableWebSources.includes(source) ? 'Availability unknown' : 'Movie identity unavailable'}</small></span><Play size={18} />
                </button>)}
                {config.enabled && <button type="button" disabled={busy || !state.movie?.tmdb_id} onClick={async () => {
                  const controller = beginRequest();
                  try {
                    await session.stopActive();
                    if (!controller.signal.aborted) setYoutube(true);
                  } catch (failure) { if (!controller.signal.aborted) setError(failure.message); }
                  finally { if (!controller.signal.aborted) setBusy(false); }
                }}><span><strong>YouTube</strong><small>Find full movies · runtime ±5%</small></span><Play size={18} /></button>}
                {other.map(provider => providerRow(provider, false))}
              </div>}
            {(busy || session.loading || availability.loading) && <div className="stream-source-status" role="status">
              <Loader2 size={18} className="spin" />{busy || session.loading ? 'Preparing selected source...' : 'Checking saved catalog...'}
            </div>}
            {!busy && !availability.loading && !matched.length && !selectableWebSources.length && !(config.enabled && state.movie?.tmdb_id) && !versions &&
              <div className="stream-source-status"><span>No streaming source available</span>
                <Button type="button"  onClick={retryAvailability}>Retry</Button></div>}
          </div>}
    </section>
  </div>;
}
