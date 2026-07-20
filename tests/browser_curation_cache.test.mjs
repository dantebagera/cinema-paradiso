import assert from 'node:assert/strict';
import test from 'node:test';

import {
  CURATION_GENERATION_CHANGED_EVENT,
  clearUserListsCache,
  fetchUserListsCached,
  observeCurationGeneration
} from '../src/api/curation.js';

test('curation generation changes invalidate cached lists and broadcast browser invalidation', async () => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  const originalCustomEvent = globalThis.CustomEvent;
  const events = [];
  let calls = 0;
  globalThis.window = { dispatchEvent: (event) => events.push(event) };
  globalThis.CustomEvent = class CustomEvent {
    constructor(type, options = {}) {
      this.type = type;
      this.detail = options.detail;
    }
  };
  globalThis.fetch = async () => {
    calls += 1;
    return new Response(JSON.stringify({
      curation_generation: calls === 1 ? 40 : 41,
      lists: [{ id: `list-${calls}`, name: `List ${calls}`, movies: [] }]
    }), { status: 200 });
  };

  try {
    clearUserListsCache();
    observeCurationGeneration(40);
    const first = await fetchUserListsCached();
    const cached = await fetchUserListsCached();
    observeCurationGeneration(41);
    const refreshed = await fetchUserListsCached();

    assert.equal(calls, 2);
    assert.equal(first.lists[0].id, 'list-1');
    assert.equal(cached.lists[0].id, 'list-1');
    assert.equal(refreshed.lists[0].id, 'list-2');
    assert.equal(events.find((event) => event.type === CURATION_GENERATION_CHANGED_EVENT)?.type, CURATION_GENERATION_CHANGED_EVENT);
    assert.deepEqual(events.find((event) => event.type === CURATION_GENERATION_CHANGED_EVENT)?.detail, {
      previousGeneration: 40,
      generation: 41
    });
    const eventCount = events.length;
    assert.equal(observeCurationGeneration(40), false);
    assert.equal(events.length, eventCount);
  } finally {
    globalThis.fetch = originalFetch;
    if (originalWindow === undefined) delete globalThis.window;
    else globalThis.window = originalWindow;
    if (originalCustomEvent === undefined) delete globalThis.CustomEvent;
    else globalThis.CustomEvent = originalCustomEvent;
    clearUserListsCache();
  }
});

test('the request observing a new generation settles while listeners share one refresh', async () => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  const originalCustomEvent = globalThis.CustomEvent;
  const originalEvent = globalThis.Event;
  const listeners = new Map();
  let calls = 0;
  let followupPromise;
  globalThis.window = {
    addEventListener: (type, listener) => listeners.set(type, listener),
    dispatchEvent: (event) => {
      listeners.get(event.type)?.(event);
      return true;
    }
  };
  globalThis.CustomEvent = class CustomEvent {
    constructor(type, options = {}) {
      this.type = type;
      this.detail = options.detail;
    }
  };
  globalThis.Event = class Event {
    constructor(type) {
      this.type = type;
    }
  };
  globalThis.fetch = async () => {
    calls += 1;
    return new Response(JSON.stringify({
      curation_generation: 101,
      lists: [{ id: `request-${calls}`, name: `Request ${calls}`, movies: [] }]
    }), { status: 200 });
  };

  try {
    clearUserListsCache();
    observeCurationGeneration(100);
    window.addEventListener('cp-curation-changed', () => {
      followupPromise = fetchUserListsCached();
    });

    const initiating = await fetchUserListsCached();
    const followup = await followupPromise;

    assert.equal(calls, 2);
    assert.equal(initiating.lists[0].id, 'request-1');
    assert.equal(followup.lists[0].id, 'request-2');
  } finally {
    globalThis.fetch = originalFetch;
    if (originalWindow === undefined) delete globalThis.window;
    else globalThis.window = originalWindow;
    if (originalCustomEvent === undefined) delete globalThis.CustomEvent;
    else globalThis.CustomEvent = originalCustomEvent;
    if (originalEvent === undefined) delete globalThis.Event;
    else globalThis.Event = originalEvent;
    clearUserListsCache();
  }
});
