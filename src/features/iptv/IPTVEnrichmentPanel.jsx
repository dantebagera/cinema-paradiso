import Button from '../../components/ui/Button.jsx';
import { Pause, Play, Square, WandSparkles } from 'lucide-react';
import { formatCount } from '../../utils/appUtils.js';
import IPTVMetadataProgress from './IPTVMetadataProgress.jsx';

function lastHeartbeat(timestamp) {
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - Number(timestamp)));
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function IPTVEnrichmentOverview({ worker, workerLabel, syncing, onRetryProjection }) {
  if (!worker) return null;
  const sources = Number(worker.sources || 0);
  const matches = worker.matches || {};
  const pending = Math.min(sources, Number(worker.automatic_remaining || 0));
  const handled = sources - pending;
  const projection = worker.projection || {};
  return <>
    <div className="iptv-enrichment-progress">
      <IPTVMetadataProgress label="IPTV first-pass progress" processed={handled} total={sources}
        description="provider sources handled" remainingLabel="pending CP work"
        segments={[[ 'is-accepted', 'handled', handled ]]} />
      <div className="iptv-progress-facts">
        <span>Accepted matches <strong>{formatCount(Number(matches['matched-auto'] || 0) + Number(matches['matched-manual'] || 0))}</strong></span>
        <span>No verified match <strong>{formatCount(matches.unmatched || 0)}</strong></span>
        <span>Uncertain matches <strong>{formatCount(matches.ambiguous || 0)}</strong></span>
        <span>Category unknown <strong>{formatCount(worker.classification_review || 0)}</strong></span>
        <span>Technical failures <strong>{formatCount(matches['error-terminal'] || 0)}</strong></span>
        {Number(matches['error-retryable'] || 0) > 0 && <span>Retryable errors <strong>{formatCount(matches['error-retryable'])}</strong></span>}
        <span>Distinct TMDB movies <strong>{formatCount(worker.distinct_tmdb_movies || 0)}</strong></span>
        <span>Worker checkpoint <strong>{formatCount(worker.checkpoint || 0)}</strong></span>
        <span>Counter revision <strong>{formatCount(worker.summary_revision || 0)}</strong></span>
        <span>{worker.heartbeat_at ? `Last heartbeat ${lastHeartbeat(worker.heartbeat_at)}` : 'Worker has not started yet'}</span>
        {worker.status_stale && <span>Status refresh delayed. Showing the last exact totals.</span>}
      </div>
    </div>
    {projection.state === 'running' && <div className="iptv-enrichment-progress">
      <IPTVMetadataProgress label="Provider movie preparation" processed={projection.processed || 0}
        total={projection.total || 0} description="sources prepared" segments={[[ 'is-live', 'prepared', projection.processed || 0 ]]} />
    </div>}
    <div className="iptv-stage-grid">
      <article><span>Provider sync</span><strong>{syncing ? 'Syncing provider catalog…' : `${formatCount(sources)} available sources`}</strong>
        <small>Provider catalogue and playback.</small></article>
      <article><span>Local projection</span><strong>{projection.state || 'not started'}</strong>
        <small>{formatCount(projection.processed || 0)} of {formatCount(projection.total || 0)} prepared · {formatCount(projection.published || 0)} browseable</small>
        {['failed', 'not-started'].includes(projection.state) && <Button type="button" 
          onClick={onRetryProjection}>Retry projection</Button>}</article>
      <article><span>First-pass worker</span><strong>{workerLabel}</strong>
        <small>{worker.retry_reason || worker.worker_error || 'Progress is saved for this provider.'}</small></article>
    </div>
  </>;
}

export default function IPTVEnrichmentPanel({ worker, current, syncing, settings, control, controlError,
  statusError, onControl, onRetryProjection, onRefresh }) {
  const state = worker?.state || 'idle';
  const running = ['starting', 'running', 'pausing', 'cancelling'].includes(state);
  const waiting = state === 'waiting-capacity';
  const paused = state === 'paused';
  const restart = state === 'awaiting-continuation' || worker?.restart_confirmation_required;
  const startRequested = ['start', 'resume'].includes(control);
  const hasWork = Number(worker?.automatic_remaining || 0) > 0;
  const crashed = state === 'crashed';
  const canStart = current && !syncing && settings?.tmdb_configured && worker?.projection?.state === 'complete';
  const workerLabel = state === 'complete' ? (hasWork ? 'Ready to continue' : 'First pass complete') : state;
  const canPause = ['starting', 'running'].includes(state) || startRequested;
  const canCancel = running || paused || waiting || restart || startRequested || control === 'pause';

  return <section className="iptv-enrichment-panel" aria-label="Enrich Metadata">
    <p>CP classifies sources and looks up eligible films using provider and TMDB evidence.</p>
    {!worker && !statusError && <p role="status">Loading provider enrichment status…</p>}
    <IPTVEnrichmentOverview worker={worker} workerLabel={workerLabel} syncing={syncing} onRetryProjection={onRetryProjection} />
    <div className="iptv-worker-controls iptv-dashboard-controls">
      {startRequested && <Button variant="primary" type="button"  disabled>
        <WandSparkles size={15} /> Starting enrichment…</Button>}
      {!control && !running && !paused && !waiting && !restart && !crashed && state !== 'complete' &&
        <Button variant="primary" type="button"  disabled={!canStart} onClick={() => onControl('start')}>
          <WandSparkles size={15} /> Start enrichment</Button>}
      {!control && (restart || crashed || (state === 'complete' && hasWork)) &&
        <Button variant="primary" type="button"  disabled={!canStart} onClick={() => onControl('resume')}>
          <Play size={15} /> Continue enrichment</Button>}
      {!control && paused && !restart && <Button variant="primary" type="button" 
        disabled={!canStart} onClick={() => onControl('resume')}><Play size={15} /> Resume</Button>}
      {canPause && <Button type="button"  disabled={Boolean(control)}
        onClick={() => onControl('pause')}><Pause size={15} /> Pause</Button>}
      {canCancel && <Button type="button"  disabled={Boolean(control)}
        onClick={() => onControl('cancel')}><Square size={15} /> Cancel future work</Button>}
      {control === 'pause' && <span role="status">Pausing enrichment…</span>}
      {control === 'cancel' && <span role="status">Cancelling future work…</span>}
      {statusError && <Button type="button"  onClick={onRefresh}>Refresh IPTV status</Button>}
    </div>
    {!control && current && !syncing && state === 'complete' && !hasWork && !restart &&
      <p role="status">The first pass is complete. Review unmatched listings in Maintenance → IPTV.</p>}
    {(statusError || controlError) && <p role="alert">{controlError || statusError}</p>}
  </section>;
}
