export async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const raw = await response.text();
  let data = {};
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      if (response.ok) throw new Error('Failed to parse response JSON');
    }
  }
  if (!response.ok || data.error) {
    const detail = data.error;
    const error = new Error(typeof detail === 'string' ? detail
      : detail?.message || detail?.code?.replaceAll('_', ' ') || `Request failed: ${response.status}`);
    if (detail?.code) error.code = detail.code;
    error.data = data;
    error.status = response.status;
    throw error;
  }
  const method = String(options?.method || 'GET').toUpperCase();
  const changesCatalog = method !== 'GET' && (
    String(url).startsWith('/api/app-data/config') ||
    (String(url).startsWith('/api/iptv/providers') && !/\/(playback|history|test|selection)(\/|$|\?)/.test(String(url)))
  );
  if (changesCatalog && typeof window !== 'undefined') {
    window.dispatchEvent(new Event('cp-iptv-catalog-changed'));
  }
  return data;
}
