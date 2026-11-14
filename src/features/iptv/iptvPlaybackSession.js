export function createIPTVPlaybackCoordinator(api) {
  let current = { owner: null, playback: null, loading: false, error: '' };
  let generation = 0;
  let retained = null;
  let cleanup = null;
  const pendingStops = new Set();
  const listeners = new Set();
  const publish = value => { current = value; listeners.forEach(listener => listener()); };

  async function dispose(playback) {
    if (!playback?.token) return;
    pendingStops.add(playback);
    try {
      await api.stopPlayback(playback.provider_id, playback.token);
    } catch {
      await api.stopPlayback(playback.provider_id, playback.token);
    }
    pendingStops.delete(playback);
  }

  async function stopRetained() {
    if (cleanup) return cleanup;
    const playback = retained;
    if (playback) pendingStops.add(playback);
    if (!pendingStops.size) return;
    cleanup = Promise.all([...pendingStops].map(dispose)).then(() => {
      if (retained === playback) retained = null;
    }).finally(() => { cleanup = null; });
    return cleanup;
  }

  async function stop(owner) {
    if (current.owner !== owner) return;
    await stopActive(owner);
  }

  async function stopActive(owner) {
    generation++;
    publish({ owner, playback: null, loading: false, error: '' });
    await stopRetained();
  }

  async function start(owner, providerId, payload, history = {}) {
    const request = ++generation;
    publish({ owner, playback: null, loading: true, error: '' });
    try {
      await stopRetained();
      if (request !== generation) return null;
      const result = await api.startPlayback(providerId, payload);
      const playback = { ...result, ...payload, ...history, provider_id: providerId };
      if (request !== generation) {
        await dispose(playback);
        return null;
      }
      retained = playback;
      publish({ owner, playback, loading: false, error: '' });
      return playback;
    } catch (error) {
      if (request === generation) publish({ owner, playback: null, loading: false, error: error.message });
      throw error;
    }
  }

  return {
    start, stop, stopActive, state: () => current,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
  };
}
