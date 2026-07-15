import { fetchJson } from './client.js';

export function previewSourceReview(movies) {
  return fetchJson('/api/sources/review/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ movies })
  });
}

export function submitSourceReview(rows) {
  return fetchJson('/api/sources/review/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows })
  });
}
