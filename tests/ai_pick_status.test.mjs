import assert from 'node:assert/strict';
import test from 'node:test';
import { pickStatus, pickAction } from '../src/features/ai/pickStatus.js';

const job = (state, extra = {}) => ({ state, accepted_count: 18, requested_count: '50',
  request: { prompt: 'twisted endings', count: '50' }, ...extra });

test('one-line status describes actual stages without internal details', () => {
  assert.equal(pickStatus({ busy: true }), 'Starting your request…');
  const phases = { preparing: 'Preparing your request…', connecting: 'Connecting to ChatGPT…',
    retrieving: 'Getting movie suggestions…', matching: 'Checking movie matches…' };
  for (const [phase, text] of Object.entries(phases)) {
    assert.ok(pickStatus({ job: job('running', { progress_phase: phase }) }).startsWith(text));
  }
  assert.equal(pickStatus({ job: job('running', { progress_phase: null, accepted_count: 0 }) }), 'Working on your request…');
  assert.equal(pickStatus({ job: job('completed', { accepted_count: 50 }) }), '50 movies ready.');
  assert.match(pickStatus({ job: job('paused_budget') }), /Paused.*18 of 50/);
  assert.match(pickStatus({ job: job('failed', { message: 'scope_changed_during_operation' }) }), /requirements changed.*18 of 50.*new request/i);
  assert.doesNotMatch(pickStatus({ job: job('failed', { message: 'secret_internal_error' }) }), /secret|internal|24/);
  assert.match(pickStatus({ error: 'rate limit exceeded' }), /ChatGPT is busy/i);
  assert.match(pickStatus({ job: job('partial') }), /18 of 50.*couldn.t verify/i);
  assert.match(pickStatus({ job: job('interrupted') }), /Interrupted.*18 of 50/);
});

test('main action preserves Stop, explicit resume, fresh requests and factual handoff', () => {
  assert.equal(pickAction(job('running'), '', '').kind, 'stop');
  assert.equal(pickAction(job('paused_budget'), '', '').kind, 'continue');
  assert.equal(pickAction(job('partial'), 'twisted endings', '050').kind, 'continue');
  assert.equal(pickAction(job('partial'), 'comedies', '50').kind, 'ask');
  assert.equal(pickAction(job('partial'), 'twisted endings', '51').kind, 'ask');
  assert.equal(pickAction(job('paused_budget'), 'twisted endings', '', { countEdited: true }).kind, 'ask');
  assert.equal(pickAction(job('paused_budget'), '', '50', { promptEdited: true }).kind, 'ask');
  assert.equal(pickAction(job('failed', { message: 'scope_changed_during_operation' }), '', '').kind, 'restart');
  assert.equal(pickAction(job('failed', { message: 'scope_changed_during_operation' }), 'new prompt', '50').kind, 'restart');
  assert.equal(pickAction(job('failed', { message: 'skill_changed; start a new request' }), '', '').kind, 'restart');
  assert.equal(pickAction(job('awaiting_clarification', { output: { handoff: 'ai-control' } }), '', '').kind, 'review');
  assert.equal(pickAction(job('completed'), '', '').kind, 'ask');
});
