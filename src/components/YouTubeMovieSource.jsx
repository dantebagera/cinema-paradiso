import { ActionLink } from './ui/Button.jsx';
import Button from './ui/Button.jsx';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { fetchJson } from '../api/client.js';
import { toYouTubeEmbedUrl } from '../utils/appUtils.js';
import { useAIProvider } from '../features/ai/AIProviderContext.jsx';
import useAIJob from '../features/ai/useAIJob.js';
import { jobIsRunning } from '../features/ai/aiClient.js';
import StreamSourceList from './StreamSourceList.jsx';

const duration = seconds => `${Math.floor(seconds / 60)}:${String(Math.round(seconds % 60)).padStart(2, '0')}`;

export default function YouTubeMovieSource({ movie, Player }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [video, setVideo] = useState(null);
  const request = useRef(null);
  const applied = useRef('');
  const ai = useAIProvider();
  const gpt = useAIJob('F6', result?.search_id || '', { enabled: Boolean(result?.search_id) });
  const running = jobIsRunning(gpt.job);
  const busy = loading || gpt.busy || running;
  const ready = ai.provider === 'chatgpt' && ai.feature('F6')?.ready;
  const setupMessage = {
    youtube_and_tmdb_required: 'Add YouTube and TMDB keys in Settings to use GPT search.',
    model_required: 'Choose a ChatGPT model in Settings to use GPT search.',
    consent_required: 'Enable permission for your connected ChatGPT account in Settings to use GPT search.',
  }[ai.feature('F6')?.reason] || 'To use GPT, select and connect ChatGPT in Settings.';

  const search = useCallback(async searchId => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true); setError(''); setVideo(null);
    try {
      const next = await fetchJson('/api/youtube/movie-search', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify(searchId ? { search_id: searchId } : { tmdb_id: String(movie.tmdb_id || '') }),
      });
      if (!controller.signal.aborted) setResult(next);
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure.message);
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [movie.tmdb_id]);

  useEffect(() => {
    search();
    return () => request.current?.abort();
  }, [search]);

  useEffect(() => {
    const job = gpt.job;
    if (['completed', 'failed'].includes(job?.state) && job.output?.search_id === result?.search_id && applied.current !== job.id) {
      applied.current = job.id;
      setResult(job.output);
    }
    if (job?.state !== 'cancelled' || job.request?.search_id !== result?.search_id || applied.current === job.id) return undefined;
    const controller = new AbortController();
    fetchJson('/api/youtube/movie-search/status', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
      body: JSON.stringify({ search_id: result.search_id }),
    }).then(next => {
      if (!controller.signal.aborted) { applied.current = job.id; setResult(next); }
    }).catch(failure => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [gpt.job?.id, gpt.job?.state, gpt.job?.revision, result?.search_id]);

  function assist() {
    setError(''); setVideo(null);
    gpt.start('/api/ai/youtube/movie-search', { search_id: result.search_id }, { followUp: false }).catch(() => {});
  }

  const failure = error || gpt.error || (gpt.job?.state === 'failed' ? gpt.job.message?.replaceAll('_', ' ') : '');
  return <div className="youtube-movie-source">
    <div className="youtube-search-controls">
      <div><strong>YouTube</strong>
        {result && <small dir="auto">{result.movie.title} · Movie {duration(result.runtime_seconds)} · ±5%: {result.duration_range.map(duration).join('–')}</small>}
      </div>
      <Button type="button"  disabled={busy} onClick={() => { gpt.newSession(); search(result?.search_id); }}>Search more</Button>
      <Button type="button"  disabled={busy || !ready || !result} onClick={assist}>Use GPT</Button>
      {running && <Button type="button"  disabled={gpt.busy} onClick={gpt.cancel}>Cancel GPT</Button>}
    </div>
    {!ready && <p className="stream-source-status">{setupMessage}</p>}
    {!result && !loading && <p className="stream-source-status">GPT needs a movie search with known runtime first.</p>}
    {failure && <p className="stream-source-error" role="alert">{failure}</p>}
    {gpt.job?.state === 'cancelled' && <p className="stream-source-status">GPT cancelled. Results already found are kept.</p>}
    {busy && <p className="stream-source-status" role="status"><Loader2 size={18} className="spin" />{loading ? 'Searching YouTube…' : 'GPT is helping search…'}</p>}
    {video ? <>
      <div className="youtube-search-controls">
        <Button type="button"  onClick={() => setVideo(null)}>Back to results</Button>
        <ActionLink  href={video.url} target="_blank" rel="noopener noreferrer">Open on YouTube</ActionLink>
      </div>
      {video.embeddable !== false ? <Player embedUrl={toYouTubeEmbedUrl(video.url)} title={video.title} />
        : <p className="stream-source-status">This video does not allow embedded playback. Open it on YouTube.</p>}
      <p className="stream-source-status">If playback is unavailable here, try Open on YouTube or choose another result.</p>
    </> : <div className="stream-source-stage">
      {result?.candidates.length > 0 && <>
        <p className="stream-source-status">{result.candidates.length} possible matches within ±5% of runtime. Choose a video to check the movie.</p>
        <StreamSourceList disabled={busy} onChoose={setVideo} items={result.candidates.map(candidate => ({
          id: candidate.video_id, value: candidate, title: candidate.title, actionLabel: `Play ${candidate.title}`,
          detail: `${candidate.channel_title || 'YouTube'} · ${duration(candidate.duration_seconds)}${candidate.embeddable === false ? ' · Opens on YouTube' : ''}`,
        }))} />
      </>}
      {result && !busy && !result.candidates.length && !failure && <p className="stream-source-status">No videos matched the ±5% runtime range in these results.</p>}
      {result && !result.has_more && <p className="stream-source-status">No more results for the current queries. You can use GPT to try different queries.</p>}
      {result?.explanation && <p className="stream-source-status">{result.explanation}</p>}
    </div>}
  </div>;
}
