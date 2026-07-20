import { fetchJson } from './client.js';

function queryString(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== '' && value !== undefined && value !== null && value !== false) query.set(key, String(value));
  });
  return query.toString();
}

export const iptvApi = {
  status: () => fetchJson('/api/iptv/status'),
  sync: () => fetchJson('/api/iptv/sync', { method: 'POST' }),
  categories: (kind) => fetchJson(`/api/iptv/categories?${queryString({ kind })}`),
  items: (params) => fetchJson(`/api/iptv/items?${queryString(params)}`),
  favorites: (params) => fetchJson(`/api/iptv/favorites?${queryString(params)}`),
  detail: (kind, itemId) => fetchJson(`/api/iptv/items/${encodeURIComponent(kind)}/${encodeURIComponent(itemId)}`),
  epg: (streamId) => fetchJson(`/api/iptv/epg/${encodeURIComponent(streamId)}?limit=4`),
  recent: () => fetchJson('/api/iptv/recent?limit=12'),
  favorite: (kind, itemId, favorite) => fetchJson(`/api/iptv/favorites/${encodeURIComponent(kind)}/${encodeURIComponent(itemId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ favorite })
  }),
  lists: (params = {}) => fetchJson(`/api/iptv/lists?${queryString(params)}`),
  createList: (name) => fetchJson('/api/iptv/lists', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  }),
  renameList: (listId, name) => fetchJson(`/api/iptv/lists/${encodeURIComponent(listId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  }),
  deleteList: (listId) => fetchJson(`/api/iptv/lists/${encodeURIComponent(listId)}`, { method: 'DELETE' }),
  listItems: (listId, params = {}) => fetchJson(`/api/iptv/lists/${encodeURIComponent(listId)}/items?${queryString(params)}`),
  setListItem: (listId, kind, itemId, included) => fetchJson(`/api/iptv/lists/${encodeURIComponent(listId)}/items/${encodeURIComponent(kind)}/${encodeURIComponent(itemId)}`, {
    method: included ? 'POST' : 'DELETE'
  }),
  moveListItem: (listId, kind, itemId, direction) => fetchJson(`/api/iptv/lists/${encodeURIComponent(listId)}/items/${encodeURIComponent(kind)}/${encodeURIComponent(itemId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ direction })
  }),
  startPlayback: (payload) => fetchJson('/api/iptv/playback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }),
  stopPlayback: (token) => fetchJson(`/api/iptv/playback/${encodeURIComponent(token)}`, { method: 'DELETE' }),
  history: (kind, itemId, payload) => fetchJson(`/api/iptv/history/${encodeURIComponent(kind)}/${encodeURIComponent(itemId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
};

export function iptvImage(kind, itemId, backdrop = false) {
  return `/api/iptv/image/${encodeURIComponent(kind)}/${encodeURIComponent(itemId)}${backdrop ? '?backdrop=1' : ''}`;
}
