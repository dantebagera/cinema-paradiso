import { fetchJson } from '../../api/client.js';

export function exactCount(value) {
  const text = String(value ?? '').trim();
  if (!/^[0-9]+$/.test(text)) return null;
  return text.replace(/^0+/, '') || null;
}

export function formatExactCount(value) {
  return String(value ?? '0').replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

export function requestKey() {
  return globalThis.crypto?.randomUUID?.() || `request-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export const aiJson = (url, body, method = 'POST') => fetchJson(url, {
  method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
});

export const jobStorageKey = (feature, account, provider = '') => `cp-ai-job:${feature}:${account || 'none'}:${provider}`;
export const jobIsRunning = job => ['queued', 'running'].includes(job?.state);
export const jobCanContinue = job => ['paused_budget', 'partial', 'failed', 'interrupted'].includes(job?.state);

export function openAIReview(surface, target = null, prompt = '') {
  let path = surface === 'tv' && target?.series_id ? `/tv/series/${target.series_id}`
    : `/${surface === 'tv' ? 'library' : surface}`;
  if (surface === 'tv') sessionStorage.setItem('cp-library-media', 'tv');
  const state = surface === 'tv' ? { tvContext: 'library', tvBack: true,
    ...(target?.series_id ? {} : target?.tmdb_id ? { tvPreview: target.tmdb_id } : {}) } : {};
  if (surface === 'iptv') {
    const review = target || {};
    sessionStorage.setItem('cp-iptv-review-target', JSON.stringify(review));
    window.dispatchEvent(new CustomEvent('cp-iptv-review', { detail: review }));
  }
  if (surface === 'ai-control' && prompt) {
    sessionStorage.setItem('cp-ai-control-draft', prompt);
    window.dispatchEvent(new CustomEvent('cp-ai-control-request', { detail: { prompt } }));
  }
  history.pushState(state, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
