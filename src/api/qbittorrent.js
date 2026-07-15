import { fetchJson } from './client.js';

let configPromise = null;

export function loadTorrentHandlingConfig(force = false) {
  if (force || !configPromise) {
    configPromise = fetchJson('/api/qbittorrent/config').catch((error) => {
      configPromise = null;
      throw error;
    });
  }
  return configPromise;
}

export function setTorrentHandlingConfig(config) {
  configPromise = Promise.resolve(config);
}
