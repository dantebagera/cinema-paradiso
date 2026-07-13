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
    const error = new Error(data.error || `Request failed: ${response.status}`);
    error.data = data;
    error.status = response.status;
    throw error;
  }
  return data;
}
