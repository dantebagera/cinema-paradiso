import { AlertTriangle, Loader2, RefreshCcw, Save, X } from 'lucide-react';
import { useEffect, useState } from 'react';

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok || data.error) throw new Error(data.error || `Request failed: ${response.status}`);
  return data;
}

export default function MetadataCorrectionModal({
  item,
  onClose,
  onSaved,
  notify,
  resetLabel = 'Reset to provider metadata'
}) {
  const [context, setContext] = useState(null);
  const [title, setTitle] = useState('');
  const [year, setYear] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError('');
      try {
        const data = await fetchJson(`/api/metadata/override?path=${encodeURIComponent(item.path)}`);
        if (cancelled) return;
        setContext(data);
        setTitle(data.effective?.title || data.provider?.title || '');
        setYear(String(data.effective?.year || data.provider?.year || ''));
      } catch (loadError) {
        if (!cancelled) setError(loadError.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [item.path]);

  async function save(event) {
    event.preventDefault();
    setBusy('save');
    setError('');
    try {
      const result = await fetchJson('/api/metadata/override', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: item.path, title: title.trim(), year: year.trim() })
      });
      notify?.('Local metadata correction saved');
      onSaved?.(result);
      onClose();
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setBusy('');
    }
  }

  async function reset() {
    setBusy('reset');
    setError('');
    try {
      const result = await fetchJson('/api/metadata/override', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: item.path })
      });
      notify?.('Reset to provider metadata');
      onSaved?.(result);
      onClose();
    } catch (resetError) {
      setError(resetError.message);
    } finally {
      setBusy('');
    }
  }

  const provider = context?.provider || {};
  const hasOverride = Boolean(context?.override && Object.keys(context.override).length);

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="torrent-dialog metadata-correction-dialog" role="dialog" aria-modal="true" aria-label="Correct movie metadata" onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <p className="screen-kicker">Local correction</p>
            <h2>Correct metadata</h2>
          </div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close metadata correction">
            <X size={18} />
          </button>
        </div>
        <p className="dialog-body-path">{item.filename || item.path}</p>
        {loading ? (
          <div className="library-status"><Loader2 size={16} className="spin" /><span>Loading provider metadata...</span></div>
        ) : (
          <form className="metadata-correction-form" onSubmit={save}>
            <div className="metadata-provider-comparison">
              <span>Provider metadata</span>
              <strong>{provider.title || 'Unknown title'}{provider.year ? ` (${provider.year})` : ''}</strong>
              <small>This value remains stored for comparison. The correction changes only Cinema Paradiso’s display.</small>
            </div>
            <label className="dialog-field">
              <span>Display title</span>
              <input value={title} onChange={(event) => setTitle(event.target.value)} required />
            </label>
            <label className="dialog-field">
              <span>Display year</span>
              <input value={year} onChange={(event) => setYear(event.target.value.replace(/\D/g, '').slice(0, 4))} inputMode="numeric" placeholder="Four-digit year" />
            </label>
            {error && <p className="settings-inline-status settings-inline-error"><AlertTriangle size={15} /><span>{error}</span></p>}
            <div className="dialog-actions metadata-correction-actions">
              {hasOverride && (
                <button type="button" className="btn btn-secondary" onClick={reset} disabled={Boolean(busy)}>
                  {busy === 'reset' ? <Loader2 size={15} className="spin" /> : <RefreshCcw size={15} />} {resetLabel}
                </button>
              )}
              <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={Boolean(busy) || !title.trim()}>
                {busy === 'save' ? <Loader2 size={15} className="spin" /> : <Save size={15} />} Save correction
              </button>
            </div>
          </form>
        )}
        {!loading && error && !context && <p className="settings-inline-status settings-inline-error"><AlertTriangle size={15} /><span>{error}</span></p>}
      </section>
    </div>
  );
}
