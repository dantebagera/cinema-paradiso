import assert from 'node:assert/strict';
import test from 'node:test';
import { exactCount, formatExactCount } from '../src/features/ai/aiClient.js';
import { fetchJson } from '../src/api/client.js';

test('GPT targets keep every digit beyond JavaScript safe integers', () => {
  const count = '900719925474099312345';
  assert.equal(exactCount(count), count);
  assert.equal(formatExactCount(count), '900,719,925,474,099,312,345');
  assert.equal(exactCount('00015'), '15');
  for (const invalid of ['0', '-1', '2.5', '1e3', '', null]) assert.equal(exactCount(invalid), null);
});

test('structured provider errors stay readable and retain the machine code', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => ({ ok: false, status: 409,
      text: async () => JSON.stringify({ error: { code: 'account_disconnected' } }) });
    await assert.rejects(fetchJson('/fixture'), error => error.message === 'account disconnected' && error.code === 'account_disconnected');
    globalThis.fetch = async () => ({ ok: false, status: 400, text: async () => JSON.stringify({ error: 'Existing Ollama message' }) });
    await assert.rejects(fetchJson('/fixture'), { message: 'Existing Ollama message' });
  } finally { globalThis.fetch = original; }
});
