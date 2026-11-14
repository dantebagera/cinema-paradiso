import Button from '../../components/ui/Button.jsx';
import { Select } from '../../components/ui/FormField.jsx';
import { useCallback, useEffect, useState } from 'react';
import { Layers3, RefreshCcw, ServerCog, X } from 'lucide-react';
import { iptvApi } from '../../api/iptv.js';
import { formatCount } from '../../utils/appUtils.js';
import IPTVWorkspace from './IPTVWorkspace.jsx';
import useIPTVMovieStatus from './useIPTVMovieStatus.js';
import './iptv.css';

export default function IPTVMaintenance({ notify, active, onOpenSettings }) {
  const [providers, setProviders] = useState([]);
  const [providerId, setProviderId] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    if (!active) return undefined;
    let closed = false;
    iptvApi.providers().then(result => {
      if (closed) return;
      const items = result.providers || [];
      setProviders(items);
      setProviderId(current => items.some(item => item.provider_id === current) ? current :
        items.find(item => item.provider_id === result.last_selected_provider_id)?.provider_id || items[0]?.provider_id || '');
    }).catch(failure => { if (!closed) setError(failure.message); });
    return () => { closed = true; };
  }, [active]);
  const provider = providers.find(item => item.provider_id === providerId);
  return <div className="iptv-workspace iptv-aux-workspace">
    <div className="iptv-header-status">
      <label className="iptv-provider-select"><ServerCog size={15} />
        <Select aria-label="Active IPTV provider" value={providerId} disabled={!providers.length}
          onChange={event => setProviderId(event.target.value)}>
          {!providers.length && <option value="">No IPTV providers</option>}
          {providers.map(item => <option key={item.provider_id} value={item.provider_id}>{item.name}</option>)}
        </Select>
      </label>
      {!provider && <Button  type="button" onClick={onOpenSettings}>IPTV Provider Settings</Button>}
    </div>
    {error && <p role="alert">{error}</p>}
    {provider && <ProviderTools key={providerId} provider={provider} active={active} notify={notify} onOpenSettings={onOpenSettings} />}
  </div>;
}

function ProviderTools({ provider, active, notify, onOpenSettings }) {
  const activeProviderId = provider.provider_id;
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState('');
  const [rebuildJob, setRebuildJob] = useState(null);
  const [fusionPreview, setFusionPreview] = useState(null);
  const [proposalBusy, setProposalBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const reload = useCallback(() => setRefresh(value => value + 1), []);
  const movieStatus = useIPTVMovieStatus(activeProviderId, {
    enabled: active, refresh, onSettled: reload, notify,
  });
  const { worker, publish, error: statusError, control, controlError, requestControl } = movieStatus;

  useEffect(() => {
    if (!active) return undefined;
    const controller = new AbortController();
    iptvApi.metadataSettings({ signal: controller.signal }).then(result => {
      if (!controller.signal.aborted) setSettings(result);
    }).catch(failure => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [active]);

  async function reopenRebuild() {
    setProposalBusy(true);
    try {
      setRebuildJob(await iptvApi.movieRebuildJob(activeProviderId, worker.latest_jobs.rebuild.job_id));
    } catch (failure) { setError(failure.message); }
    finally { setProposalBusy(false); }
  }

  async function previewRebuild() {
    setProposalBusy(true);
    try {
      const job = await iptvApi.movieRebuildPreview(activeProviderId, { scope: { automatic: true } });
      setRebuildJob(job);
      reload();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProposalBusy(false);
    }
  }

  async function cancelRebuildPreview() {
    if (!rebuildJob) return;
    try {
      const cancelled = await iptvApi.cancelMovieRebuild(activeProviderId, rebuildJob.job_id);
      setRebuildJob(cancelled);
      reload();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function previewFusionRepairs() {
    setProposalBusy(true);
    setError('');
    try {
      setFusionPreview(await iptvApi.movieFusionPreview(activeProviderId, { limit: 500 }));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProposalBusy(false);
    }
  }

  async function applyFusionRepairs(proposalIds) {
    if (!fusionPreview) return;
    setProposalBusy(true);
    try {
      const result = await iptvApi.applyMovieFusion(activeProviderId, {
        catalog_generation: fusionPreview.catalog_generation,
        proposal_ids: proposalIds
      });
      notify?.(`${formatCount(result.applied?.length || 0)} same-movie source repairs applied`);
      setFusionPreview(null);
      publish(result.status);
      reload();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProposalBusy(false);
    }
  }

  const running = ['starting', 'running', 'pausing', 'cancelling', 'waiting-capacity'].includes(worker?.state);
  return (
    <section className="iptv-metadata-dashboard">
      <header className="iptv-metadata-header">
        <div><p className="screen-kicker">IPTV movie maintenance</p><h2>{provider.name}</h2>
          <p>Review unresolved listings and run matching for this provider.</p></div>
      </header>
      <IPTVWorkspace reviewProvider={provider} reviewStatus={movieStatus} reviewRevision={refresh} onReviewRefresh={reload}
        active={active} notify={notify} onOpenSettings={onOpenSettings} />
      <div className="iptv-worker-controls iptv-dashboard-controls">
        <Button type="button"  disabled={Boolean(control) || !Number(worker?.queue?.failed || 0)}
          onClick={() => requestControl('retry-failures')}><RefreshCcw size={15} /> Retry failures</Button>
        <Button type="button"  disabled={Boolean(control) || !(worker?.rules_update_pending || Number(worker?.stale || 0))}
          onClick={() => requestControl('re-evaluate-stale')}><RefreshCcw size={15} /> Re-evaluate stale automatic results</Button>
        <details className="iptv-diagnostic-controls"><summary>Diagnostics</summary>
          <Button type="button"  disabled={!settings?.tmdb_configured || running || Boolean(control)}
            onClick={() => requestControl('start-diagnostic')}>Run next {formatCount(worker?.batch_limit || 100)}</Button></details>
        {control && <span role="status">Requesting {control.replaceAll('-', ' ')}…</span>}
      </div>
      {(error || statusError || controlError) && <p role="alert">{error || statusError || controlError}</p>}
      {settings && !settings.tmdb_configured && <Button type="button" 
        onClick={onOpenSettings}>Set up IPTV TMDB in Settings</Button>}
      {!worker && <Button type="button"  onClick={reload}>Refresh IPTV status</Button>}
      <details className="iptv-rebuild-controls">
        <summary>Recheck automatic matches</summary>
        <p>Shadow-evaluate automatic decisions only. Preview never synchronizes a provider, deletes its database, applies identity changes, or starts enrichment.</p>
        {!rebuildJob ? <Button type="button"  disabled={proposalBusy} onClick={() => window.confirm('Create a provider-local logical rebuild preview? This does not apply changes, sync the provider, or start enrichment.') && previewRebuild()}><RefreshCcw size={15} /> Preview rechecking automatic matches</Button> : <RebuildPreviewPanel job={rebuildJob} onCancel={cancelRebuildPreview} onClose={() => setRebuildJob(null)} />}
        {!rebuildJob && worker?.latest_jobs?.rebuild?.job_id ? <Button type="button"  disabled={proposalBusy} onClick={reopenRebuild}>Reopen last rebuild preview</Button> : null}
      </details>
      <details className="iptv-rebuild-controls">
        <summary>Group versions of the same movie</summary>
        <p>Preview existing manual-classification repairs and independently validated quality variants. Provider View remains one raw source per card; CP View fuses accepted Film sources by TMDB identity.</p>
        {!fusionPreview ? <Button type="button"  disabled={proposalBusy} onClick={previewFusionRepairs}><Layers3 size={15} /> Preview grouping versions of the same movie</Button> : <FusionPreviewPanel preview={fusionPreview} busy={proposalBusy} onApply={applyFusionRepairs} onClose={() => setFusionPreview(null)} />}
      </details>
    </section>
  );
}

function FusionPreviewPanel({ preview, busy, onApply, onClose }) {
  const [selected, setSelected] = useState(() => new Set());
  const proposals = preview.proposals || [];
  function toggle(proposalId) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(proposalId)) next.delete(proposalId); else next.add(proposalId);
      return next;
    });
  }
  return <section className="iptv-proposal-panel"><header><div><p className="screen-kicker">Fusion repair preview</p><h3>{formatCount(proposals.length)} safe repairs · {formatCount(preview.conflicts?.length || 0)} conflicts unchanged</h3></div><Button type="button" onClick={onClose} aria-label="Close fusion preview"><X size={18} /></Button></header><div className="iptv-classification-proposals">{proposals.map((item) => <label key={item.proposal_id}><input type="checkbox" checked={selected.has(item.proposal_id)} onChange={() => toggle(item.proposal_id)} /><span><strong dir="auto">{item.provider_title}</strong><small>{item.type === 'sibling' ? `Validate into TMDB ${item.tmdb_id}` : `${item.current_category || 'unclassified'} → Film`} · {item.quality_claim || item.playlist_name || 'provider source'}</small><em>{item.reason}</em></span></label>)}</div><footer><span>Preview is read-only. Unselected and conflicting sources remain unchanged.</span><Button variant="primary" type="button"  disabled={busy || !selected.size} onClick={() => onApply([...selected])}>Apply {formatCount(selected.size)} selected repairs</Button></footer></section>;
}

function RebuildPreviewPanel({ job, onCancel, onClose }) {
  const counts = job.report?.transition_counts || {};
  return <section className="iptv-rebuild-preview"><header><strong>Preview {job.job_id?.slice(0, 8)} · {job.state}</strong><Button type="button" onClick={onClose} aria-label="Close rebuild preview"><X size={16} /></Button></header><div>{Object.entries(counts).map(([label, count]) => <span key={label}><strong>{formatCount(count)}</strong>{label.replaceAll('-', ' ')}</span>)}</div><p>{job.report?.note || 'Preview only. No provider decisions were applied.'}</p><footer>{job.state === 'ready' ? <Button type="button"  onClick={onCancel}>Cancel preview</Button> : null}<strong>Live rebuild apply is not available from this Gate 4–6 surface.</strong></footer></section>;
}

