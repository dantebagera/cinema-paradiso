import Pagination from '../../components/Pagination.jsx';
import { Input } from '../../components/ui/FormField.jsx';
import Button from '../../components/ui/Button.jsx';
import { useEffect, useMemo, useState } from 'react';
import { ConfirmDialog } from '../../components/LibraryControls.jsx';
import { jobIsRunning, requestKey } from '../ai/aiClient.js';
import { formatCount } from '../../utils/appUtils.js';
import IPTVMetadataProgress from './IPTVMetadataProgress.jsx';
import { ClassificationPreviewPanel, MatchProposalPanel } from './IPTVProposalPanels.jsx';

const resumable = ['paused', 'paused_budget', 'interrupted'];
const applyActive = ['running', 'stopping', 'interrupted'];
const phases = {
  queued: 'Waiting for a job slot',
  preparing: 'Checking listings with CP before ChatGPT',
  interpreting: 'Interpreting titles with ChatGPT',
  waiting_slot: 'Waiting for a ChatGPT request slot',
  connecting: 'Connecting to ChatGPT',
  retrieving: 'Waiting for the ChatGPT batch',
  matching: 'Verifying TMDB candidates',
  recovery_preparing: 'Gathering recovery evidence',
  recovery_comparing: 'Comparing remaining candidates',
  recovery_verifying: 'Verifying recovery selections',
  applying_verified: 'Applying verified matches',
  rechecking_search: 'Checking competing matches in TMDB',
  backoff: 'ChatGPT is temporarily unavailable. Waiting before retrying.',
  interrupted: 'CP stopped. Resume to continue from the saved checkpoint.',
  completed: 'Matching session complete.',
  cancelled: 'Matching session cancelled. Saved results are available for review.',
};
const views = [
  ['pending_matches', 'Pending matches', 'No verified matches awaiting Apply.'],
  ['applied', 'Applied', 'No saved Apply receipts.'],
  ['needs_attention', 'Needs attention', 'No unresolved proposals or Apply issues.'],
  ['classifications', 'Classifications', 'No classification changes awaiting Apply.'],
];
const canApplyClassification = item => !item.locked && !item.match_manual_lock &&
  !item.catalog_stale && item.apply_state !== 'applied' && item.category !== item.previous_category &&
  item.category !== 'unclassified' && item.classification_confidence >= .9 &&
  ['categorized', 'unmatched', 'review'].includes(item.outcome);

function applySummary({ applied, locked, skipped, failed }) {
  return `${formatCount(applied)} applied · ${formatCount(locked)} locked · ${formatCount(skipped)} skipped · ${formatCount(failed)} failed`;
}

export default function IPTVBulkMetadataJob({ operation, endpoint, providerName, canStart, selectedCount, onStart, onResume,
  onManualMatch, onApplied,  projection, preparationCurrent, preparationError, resumeReady,
  selectionLoading, selectionError, onRetryReadiness, onRetrySelection, selectedQueue, savedQueue }) {
  const [size, setSize] = useState('100');
  const [confirmation, setConfirmation] = useState(null);
  const [explicitReport, setExplicitReport] = useState(null);
  const [showResults, setShowResults] = useState(false);
  const { job, error, busy, status, reviewView } = operation;
  const bulk = job?.bulk;
  const searchRecheck = bulk?.search_recheck;
  const running = jobIsRunning(job);
  const canResume = resumable.includes(job?.state) || bulk?.resume_after_sync;
  const refreshOnResume = bulk?.resume_after_sync || (canResume && bulk?.catalog_resume_supported &&
    projection?.source_generation !== bulk.catalog_generation);
  const needsCalls = job?.state === 'paused_budget';
  const current = status.state === 'ready';
  const apply = bulk?.apply;
  const applying = applyActive.includes(apply?.state);
  const automatic = bulk?.automatic;
  const recoveryEnabled = bulk?.recovery_enabled;
  const automaticApply = apply?.automatic;
  const remaining = Math.max(0, (bulk?.total || 0) - (bulk?.processed || 0));
  const jobLabel = running || canResume || applying ? 'Current matching session' : 'Previous matching session';
  const counts = job?.review_counts;
  const pending = counts?.pending_matches || 0;
  const retryable = counts?.retry_failed || 0;
  const phase = ['waiting_slot', 'connecting', 'retrieving'].includes(job?.progress_phase) &&
    bulk?.phase?.startsWith('recovery_') ? bulk.phase : job?.progress_phase || bulk?.phase;
  const windowEnd = Number(bulk?.local_window_end || 0);
  const batchSize = Number(job?.request?.titles_per_request || 100);
  const windowStart = windowEnd ? Math.floor((windowEnd - 1) / batchSize) * batchSize : 0;
  const prepared = Math.max(0, Math.min(windowEnd, Number(bulk?.local_checked || 0)) - windowStart);
  const validSize = Number.isInteger(Number(size)) && Number(size) >= 1 && Number(size) <= 100;
  const ceiling = validSize ? Math.ceil(selectedCount / Number(size)) : 0;
  const repairSize = Math.min(Number(size), 50);
  const maximumRequests = validSize ? Math.min(10000, 3 * (ceiling + 2 * Math.ceil(selectedCount / repairSize))) : 0;
  const actionsDisabled = !current || busy || running || applying;
  const viewPage = Math.min(operation.page, Math.max(1, Math.ceil((counts?.[reviewView] || 0) / (job?.page_size || 20))));
  const reviewReady = job?.review_view === reviewView && job.page === viewPage;
  const review = useMemo(() => ({
    proposals: (job?.results || []).map(row => ({ ...row, confidence: row.classification_confidence })),
  }), [job?.results]);
  const preparationNotice = preparationError ? <div role="alert" className="iptv-bulk-actions">
    <span>Could not check provider readiness: {preparationError}</span>
    <Button type="button"  onClick={onRetryReadiness}>Retry readiness</Button>
  </div> : !preparationCurrent ? <p role="status">Checking provider readiness…</p> :
    projection?.state === 'running' ? <p role="status">Preparing provider movies. See progress in IPTV Metadata.</p> :
    projection?.state !== 'complete' && <div role="alert" className="iptv-bulk-actions">
      <span>Provider movies are not ready. Check provider preparation in IPTV Metadata.</span>
      <Button type="button"  onClick={onRetryReadiness}>Retry readiness</Button>
    </div>;

  function recheckSearchLimits() {
    operation.mutate(`/api/ai/jobs/${job.id}/continue`, {
      revision: job.revision, request_key: requestKey(), recheck_search_limits: true,
    }, { rememberJob: true }).catch(() => {});
  }

  useEffect(() => {
    if (apply?.id && !automatic && !applyActive.includes(apply.state)) onApplied();
  }, [apply?.id, apply?.state, automatic, onApplied]);

  function chooseView(view) {
    operation.setReviewView(view);
    operation.setPage(1);
    setShowResults(true);
  }

  function confirmApply(scope, count) {
    setExplicitReport(null);
    setConfirmation({ scope, count, revision: job.revision, key: requestKey() });
  }

  async function applyConfirmed() {
    if (!confirmation || actionsDisabled) return;
    setConfirmation(null);
    await operation.mutate(`${endpoint}/${job.id}/apply`, {
      kind: 'match', scope: confirmation.scope, expected_revision: confirmation.revision,
      expected_count: confirmation.count, request_key: confirmation.key,
    }).catch(() => {});
  }

  async function controlApply(action) {
    await operation.mutate(`${endpoint}/${job.id}/apply/${apply.id}/${action}`,
      { expected_revision: job.revision, request_key: requestKey() }).catch(() => {});
  }

  async function applySelected(kind, ids) {
    setExplicitReport(null);
    try {
      const result = await operation.mutate(`${endpoint}/${job.id}/apply`, { kind, proposal_ids: ids });
      setExplicitReport(Object.fromEntries(Object.entries(result).map(([key, rows]) => [key, rows.length])));
      onApplied();
    } catch { /* The job hook displays the error and refreshes status. */ }
  }

  return <section aria-label="ChatGPT matching" className="iptv-chatgpt-bulk">
    <div className="iptv-progress-heading"><strong>ChatGPT matching</strong></div>
    {!running && !canResume && !applying && selectedCount > 0 && <form role="region" aria-label="New matching session"
      className="iptv-enrichment-progress iptv-bulk-start" onSubmit={event => {
      event.preventDefault();
      if (validSize && ceiling <= 10000 && canStart && !busy && current) {
        setExplicitReport(null);
        onStart(Number(size));
      }
    }}>
      <div className="iptv-bulk-launch-row">
        <div className="iptv-bulk-launch-details">
          <strong>Match selected sources</strong>
          <span>Provider: {providerName} · Queue: {selectedQueue || 'Selected sources'}</span>
          <span>{formatCount(selectedCount)} selected {selectedCount === 1 ? 'source' : 'sources'}{validSize ? ` · ${formatCount(ceiling)} estimated first-pass ${ceiling === 1 ? 'request' : 'requests'}` : ''}</span>
          <label>Titles per ChatGPT request <Input type="number" min="1" max="100" step="1" required
            value={size} onChange={event => setSize(event.target.value)} /></label>
        </div>
        <Button variant="primary" type="submit"  disabled={!current || !canStart || busy || !validSize || ceiling > 10000}>
          Start matching
        </Button>
      </div>
      <p>Verified film matches apply automatically. Unresolved titles are available for review.
        The request ceiling is {formatCount(maximumRequests)}, including first-pass repairs.</p>
      {ceiling > 10000 && <p role="alert">Choose at least {Math.ceil(selectedCount / 10000)} titles per request or narrow the selection.</p>}
      {preparationNotice}
      {selectionError ? <div role="alert" className="iptv-bulk-actions">
        <span>Could not refresh selected sources: {selectionError}</span>
        <Button type="button"  onClick={onRetrySelection}>Retry selection</Button>
      </div> : selectionLoading && <p role="status">Refreshing selected sources…</p>}
    </form>}
    {!bulk && !selectedCount && current && <p>Select listings in Unmatched to start ChatGPT matching.</p>}
    {bulk && (running || canResume || applying) && selectedCount > 0 && selectedCount !== bulk.total && <p role="status">
      The current session covers {formatCount(bulk.total)} listings. Finish or cancel it to start a session with the {formatCount(selectedCount)} selected listings.
    </p>}
    {error && <p role="alert">{error}</p>}
    {status.state === 'unavailable' && <p role="alert">{status.message}</p>}
    {status.state === 'reconnecting' && <p role="status">Reconnecting to job status… {status.lastAt ?
      `Last successful status ${new Date(status.lastAt).toLocaleTimeString()}.` : 'Waiting for the first successful status.'}</p>}
    {status.state === 'loading' && !bulk && <p role="status">{busy ? 'Starting matching session…' : 'Checking for a saved matching session…'}</p>}
    {bulk && <section aria-label={jobLabel} className="iptv-enrichment-progress">
      <div className="iptv-progress-heading"><strong>{jobLabel}</strong></div>
      <p>Provider: {providerName} · Scanned queue: {savedQueue || 'Selected sources'}</p>
      <IPTVMetadataProgress label="ChatGPT matching progress" processed={bulk.processed} total={bulk.total}
        description="sources processed" segments={[
          ['is-accepted', automatic ? 'verified identities' : 'verified proposals', bulk.counts.verified],
          ['is-unmatched', automatic ? 'no candidate' : 'unmatched', bulk.counts.unmatched],
          ['is-categorized', 'categorized only', bulk.counts.categorized],
          ['is-review', 'needs review', bulk.counts.review],
          ['is-failed', 'failed', bulk.counts.failed],
        ]} />
      {searchRecheck && <IPTVMetadataProgress label="TMDB recheck progress" processed={searchRecheck.processed}
        total={searchRecheck.total} description="search-limit listings rechecked" segments={[
          ['is-accepted', 'verified', searchRecheck.verified],
          ['is-review', 'still unresolved', searchRecheck.processed - searchRecheck.verified],
        ]} />}
      {job.state === 'completed' && bulk.search_recheck_candidates > 0 && <div className="iptv-bulk-actions">
        <Button type="button"  onClick={recheckSearchLimits}
          disabled={actionsDisabled || !resumeReady}>
          Recheck {formatCount(bulk.search_recheck_candidates)} search-limit {bulk.search_recheck_candidates === 1 ? 'listing' : 'listings'} with TMDB
        </Button>
        <span>Uses saved title hints and verifies matches without new ChatGPT requests.</span>
        {preparationNotice}
      </div>}
      <div className="iptv-bulk-actions">
        <span>{formatCount(job.run_calls)} ChatGPT requests used · {formatCount(job.inference_budget - job.run_calls)} of the approved {formatCount(job.inference_budget)} remaining · {job.request.titles_per_request} titles per {automatic ? 'first-pass ' : ''}request</span>
        {running && <Button type="button"  disabled={!current || busy || bulk.pause_requested}
          onClick={operation.pause}>Pause matching</Button>}
        {canResume && <Button variant="primary" type="button"  disabled={!current || busy || (applying && !automaticApply) || (needsCalls && !bulk.extra_calls) ||
          (bulk.catalog_resume_supported && !resumeReady)}
          onClick={() => onResume(needsCalls ? bulk.extra_calls : undefined)}>
          {needsCalls && bulk.extra_calls ? `Approve ${formatCount(bulk.extra_calls)} more requests and resume` :
            searchRecheck ? 'Resume TMDB recheck' :
            refreshOnResume && remaining ? `Resume ${formatCount(remaining)} unfinished ${remaining === 1 ? 'source' : 'sources'}` : 'Resume matching'}
        </Button>}
        {(running || canResume) && <Button type="button"  disabled={!current || busy || (applying && !automaticApply)}
          onClick={operation.cancel}>Cancel matching</Button>}
      </div>
      {canResume && bulk.catalog_resume_supported && preparationNotice}
      {current && <div role="status">{bulk.resume_after_sync ? 'The catalog changed. Resume from the last saved result.' :
        job.message || (running && phases[phase]) || phases[job.state] || job.state}</div>}
      {automatic && (running || canResume) && phase === 'preparing' && windowEnd > 0 && <p role="status">
        {formatCount(prepared)} of {formatCount(windowEnd - windowStart)} listings prepared for ChatGPT in this batch</p>}
      {automatic && <p>Checked by CP {formatCount((bulk.previously_checked || 0) + bulk.local_checked)} · First-pass results {formatCount(bulk.first_pass_resolved)}
        {' · '}Title interpretation requests {formatCount(job.run_calls - bulk.recovery.requests)}
        {recoveryEnabled && <> · Recovery results {formatCount(bulk.recovery.completed)}
          {' · '}Recovery requests {formatCount(bulk.recovery.requests)} ({formatCount(bulk.recovery.admitted)} sent)</>}</p>}
      <small>Last saved checkpoint {bulk.checkpoint_at ? new Date(bulk.checkpoint_at * 1000).toLocaleTimeString() : 'unavailable'}</small>
      {needsCalls && !bulk.extra_calls && <p>The session has reached its request limit. Saved results are available for review.</p>}
      {automatic && bulk.automatic_counts && <p role="status">Automatic Apply · {applySummary(bulk.automatic_counts)}</p>}
      {apply && (!automaticApply || applying || apply.reason) && <div className="iptv-bulk-actions" aria-label="Apply progress">
        <span role="status">{apply.state === 'running' ? 'Applying verified matches' :
          apply.state === 'stopping' ? 'Stopping Apply' : apply.state === 'interrupted' ? 'Apply interrupted' :
          apply.state === 'completed' ? 'Apply complete' : 'Apply stopped'} · {applySummary(apply.counts)} · {formatCount(apply.total)} {automaticApply ? 'verified' : 'confirmed'}
          {apply.reason ? ` · ${apply.reason}` : ''}</span>
        {!automaticApply && apply.state === 'interrupted' && <Button variant="primary" type="button"  disabled={!current || busy}
          onClick={() => controlApply('resume')}>Resume Apply</Button>}
        {!automaticApply && ['running', 'interrupted'].includes(apply.state) && <Button type="button" 
          disabled={!current || busy} onClick={() => controlApply('stop')}>Stop Apply</Button>}
      </div>}
      {explicitReport && <p role="status">{applySummary(explicitReport)}</p>}
      {counts && <div className="iptv-bulk-actions">
        <strong>{formatCount(pending)} {automatic ? 'verified pending' : 'awaiting Apply'} · {formatCount(counts.applied)} applied</strong>
        {!automatic && pending > 0 && <Button variant="primary" type="button"  disabled={actionsDisabled}
          onClick={() => confirmApply('verified_pending', pending)}>Apply all {formatCount(pending)} verified matches</Button>}
        {retryable > 0 && <Button type="button"  disabled={actionsDisabled}
          onClick={() => confirmApply('retry_failed', retryable)}>Retry {formatCount(retryable)} failed {retryable === 1 ? 'write' : 'writes'}</Button>}
        <Button type="button"  aria-expanded={showResults} onClick={() => setShowResults(value => !value)}>
          {showResults ? 'Hide proposal review' : 'Review proposals (optional)'}
        </Button>
      </div>}
      {showResults && counts && <>
        <nav className="iptv-metadata-subtabs" aria-label="Matching proposal views">{views.map(([id, label]) =>
          <button type="button" key={id} className={reviewView === id ? 'is-active' : ''} aria-pressed={reviewView === id}
            onClick={() => chooseView(id)}>{label} ({formatCount(counts[id])})</button>)}</nav>
        {!reviewReady && <p role="status">Loading proposal page…</p>}
        {reviewReady && !job.results.length && <p>{views.find(([id]) => id === reviewView)?.[2]}</p>}
        {reviewReady && job.results.length > 0 && (reviewView === 'classifications' ?
          <ClassificationPreviewPanel preview={review} eligible={canApplyClassification} busy={actionsDisabled}
            onApply={ids => applySelected('classification', ids)} onManualMatch={onManualMatch} /> :
          <MatchProposalPanel key={`${job.id}:${job.page}:${reviewView}`} job={{ job_id: job.id, method: 'chatgpt-bulk',
            state: actionsDisabled ? 'running' : 'ready', proposals: job.results }}
            readOnly={automatic || reviewView !== 'pending_matches'} title={views.find(([id]) => id === reviewView)?.[1]}
            busy={actionsDisabled} onApply={ids => applySelected('match', ids)} onManualMatch={onManualMatch} />)}
        {reviewReady && <Pagination page={job.page} totalPages={Math.max(1, Math.ceil(counts[reviewView] / job.page_size))} onPageChange={operation.setPage}
          ariaLabel="Matching proposal pagination" previousAriaLabel="Previous matching proposal page" nextAriaLabel="Next matching proposal page" />}
      </>}
    </section>}
    {confirmation && <ConfirmDialog title={confirmation.scope === 'retry_failed' ? 'Retry failed writes' : 'Apply verified IPTV matches'}
      body={confirmation.scope === 'retry_failed' ?
        `Retry ${formatCount(confirmation.count)} failed writes for ${providerName}.` :
        `Apply all ${formatCount(confirmation.count)} verified Film matches to ${providerName}. This includes every eligible proposal in the saved job, across all pages.`}
      confirmLabel={confirmation.scope === 'retry_failed' ? 'Retry failed writes' : 'Apply all verified matches'}
      onCancel={() => setConfirmation(null)} onConfirm={applyConfirmed} />}
  </section>;
}
