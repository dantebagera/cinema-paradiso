import { ActionLink } from '../../components/ui/Button.jsx';
import Button from '../../components/ui/Button.jsx';
import { AlertTriangle, Loader2, Play, Square } from 'lucide-react';
import { formatExactCount, jobCanContinue, jobIsRunning, openAIReview } from './aiClient.js';
import { pickStatus } from './pickStatus.js';

const labels = { queued: 'Waiting to start', running: 'Working', awaiting_clarification: 'A decision is needed',
  awaiting_confirmation: 'Ready for your review', paused_budget: 'Paused at the request budget', completed: 'Finished',
  partial: 'Partial result', failed: 'Request failed', cancelled: 'Cancelled', interrupted: 'Interrupted' };

export default function AIJobStatus({ operation, title = 'ChatGPT request', inline = false }) {
  const { job, error, busy } = operation;
  if (inline) {
    const text = pickStatus(operation);
    if (!text) return null;
    const failed = Boolean(error) || job?.state === 'failed';
    return <section className="ai-job-status-inline" aria-label={title}>
      <p className={`discover-inline-status${failed ? ' discover-inline-error' : ''}`} role={failed ? 'alert' : 'status'}>
        {failed ? <AlertTriangle size={15} aria-hidden="true" /> : (busy || jobIsRunning(job)) && <Loader2 size={15} className="spin" aria-hidden="true" />}
        {text}
      </p>
    </section>;
  }
  if (!job && !error && !busy) return null;
  const iptvTotal = job?.request?.selection_snapshot?.source_keys?.length;
  const reviewReady = Boolean(job?.output?.prepared_review) && job?.state === 'completed';
  return <section className="ai-control-result ai-job-status" aria-label={title}>
    <div className="ai-control-result-header"><div>
      <p className="screen-kicker">{title}</p>
      <h3>{reviewReady ? 'Ready for review' : job ? labels[job.state] || job.state : busy ? 'Starting' : 'Could not start'}</h3>
      {job && <p>{job.selection.provider === 'chatgpt' ? 'ChatGPT' : 'Ollama'} · {job.selection.model}</p>}
      {job?.feature === 'F1' && <p><strong>{formatExactCount(job.accepted_count)}</strong> verified of <strong>{formatExactCount(job.requested_count)}</strong> requested</p>}
      {iptvTotal > 0 && <p>{formatExactCount(job.accepted_count || job.cursor?.iptv_processed || 0)} of {formatExactCount(iptvTotal)} selected sources reviewed</p>}
      {job && <p>{job.run_calls} of {job.inference_budget} AI requests in this run{job.feature === 'F2' ? ` · catalogue coverage ${job.coverage}` : ''}</p>}
      {job?.message && <p>{job.message.replaceAll('_', ' ')}</p>}
      {jobIsRunning(job) && <p role="status"><Loader2 size={15} className="spin" /> Progress is saved while CP is open.</p>}
    </div></div>
    {error && <p role="alert" className="library-status library-status-error"><AlertTriangle size={16} /> {error}</p>}
    <div className="settings-action-grid">
      {jobCanContinue(job) && <Button variant="primary" type="button"  disabled={busy} onClick={operation.continueJob}><Play size={15} /> Continue</Button>}
      {job && !['completed', 'cancelled'].includes(job.state) && <Button type="button"  disabled={busy} onClick={operation.cancel}><Square size={14} /> Cancel future work</Button>}
      {job && ['F1', 'F2'].includes(job.feature) && <Button type="button"  disabled={busy || jobIsRunning(job)} onClick={operation.newSession}>New conversation</Button>}
      {job?.output?.handoff === 'ai-control' && <Button variant="primary" type="button"  onClick={() => openAIReview('ai-control', null, job.output.prompt)}>Open in AI Control</Button>}
      <ActionLink  href="/settings">AI Settings</ActionLink>
    </div>
    {job?.state === 'paused_budget' && <p className="settings-empty-note">Continue starts the next run and keeps the same target and verified results.</p>}
  </section>;
}
