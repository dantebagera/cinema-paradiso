import { exactCount, formatExactCount, jobCanContinue, jobIsRunning } from './aiClient.js';

const invalidated = job => /scope_changed|skill_changed/.test(job?.message || '');

function failureMessage(message = '') {
  const code = message.toLowerCase().replaceAll(' ', '_');
  if (/scope_changed|skill_changed/.test(code)) return 'The request requirements changed.';
  if (/rate_limit|usage_limit/.test(code)) return 'ChatGPT is busy or its usage limit was reached. Try again later.';
  if (/account|sign_in|unauthoriz|authentication|token/.test(code)) return 'Sign in to ChatGPT again in Settings.';
  if (/network|fetch|deadline|timeout/.test(code)) return 'Couldn’t reach ChatGPT. Check your connection and try again.';
  if (/permission|evidence_scope/.test(code)) return 'Check your ChatGPT permissions in Settings.';
  if (/metadata|tmdb/.test(code)) return 'Movie information is unavailable. Try again later.';
  return 'The request couldn’t finish. Try again or check AI Settings.';
}

export function pickStatus({ job, error, busy } = {}) {
  const ready = job ? `${formatExactCount(job.accepted_count)} of ${formatExactCount(job.requested_count)} movies ready.` : '';
  if (error) return `${failureMessage(error)}${job?.accepted_count ? ` ${ready}` : ''}`;
  if (!job) return busy ? 'Starting your request…' : '';
  const saved = job.accepted_count ? ` ${ready}` : '';
  if (job.state === 'queued') return `Preparing your request…${saved}`;
  if (job.state === 'running') {
    const phase = { preparing: 'Preparing your request…', connecting: 'Connecting to ChatGPT…',
      retrieving: 'Getting movie suggestions…', matching: 'Checking movie matches…' };
    return `${phase[job.progress_phase] || 'Working on your request…'}${saved}`;
  }
  if (job.state === 'completed') return `${formatExactCount(job.accepted_count)} ${String(job.accepted_count) === '1' ? 'movie' : 'movies'} ready.`;
  if (job.state === 'paused_budget') return `Paused. ${ready} Continue when you’re ready.`;
  if (job.state === 'cancelled') return `Stopped.${saved}`;
  if (job.state === 'interrupted') return `Interrupted. ${ready} Continue to resume.`;
  if (job.output?.handoff === 'ai-control') return 'This request needs AI Control to find and review the full catalogue.';
  if (invalidated(job)) return `${failureMessage(job.message)} ${ready} Start a new request.`;
  if (job.state === 'partial') return `${ready} ${job.message?.includes('No further verified') || !job.message
    ? 'Couldn’t verify more matches.' : failureMessage(job.message)}`;
  if (job.state === 'awaiting_clarification') return `Please clarify your request.${saved}`;
  return `${failureMessage(job.message)}${saved}`;
}

export function pickAction(job, prompt = '', count = '', { promptEdited = false, countEdited = false } = {}) {
  if (jobIsRunning(job)) return { kind: 'stop', label: 'Stop' };
  const edited = (promptEdited || prompt.trim()) && prompt.trim() !== job?.request?.prompt
    || countEdited && !count.trim()
    || count.trim() && exactCount(count) !== exactCount(job?.requested_count);
  if (!edited && job?.output?.handoff === 'ai-control') return { kind: 'review', label: 'Open in AI Control' };
  if (invalidated(job)) return { kind: 'restart', label: 'Ask AI' };
  if (!edited && jobCanContinue(job)) return { kind: 'continue', label: 'Continue' };
  return { kind: 'ask', label: 'Ask AI' };
}
