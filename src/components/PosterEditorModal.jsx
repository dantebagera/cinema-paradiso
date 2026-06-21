import { AlertTriangle, CheckCircle2, Film, Loader2, RotateCcw, Upload, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

async function readJson(response) {
  const data = await response.json();
  if (!response.ok || data.error) throw new Error(data.error || `Request failed: ${response.status}`);
  return data;
}

export default function PosterEditorModal({ item, onClose, onSaved, notify }) {
  const [data, setData] = useState({ options: [], providers: {}, override: {}, default_poster_url: '' });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const fileInput = useRef(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError('');
      try {
        const response = await fetch(`/api/library/posters?path=${encodeURIComponent(item.path)}`);
        const result = await readJson(response);
        if (!cancelled) setData(result);
      } catch (loadError) {
        if (!cancelled) setError(loadError.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [item.path]);

  async function selectPoster(option) {
    setBusy(option.url);
    setError('');
    try {
      const response = await fetch('/api/library/posters/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: item.path, source: option.source, url: option.url })
      });
      const result = await readJson(response);
      onSaved(result.override.poster_url, result.override);
      notify('Library poster override saved');
      onClose();
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setBusy('');
    }
  }

  async function uploadPoster(file) {
    if (!file) return;
    setBusy('upload');
    setError('');
    try {
      const body = new FormData();
      body.append('path', item.path);
      body.append('poster', file);
      const response = await fetch('/api/library/posters/upload', { method: 'POST', body });
      const result = await readJson(response);
      onSaved(result.override.poster_url, result.override);
      notify('Local Library poster saved');
      onClose();
    } catch (uploadError) {
      setError(uploadError.message);
    } finally {
      setBusy('');
      if (fileInput.current) fileInput.current.value = '';
    }
  }

  async function resetPoster() {
    setBusy('reset');
    setError('');
    try {
      const response = await fetch('/api/library/posters/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: item.path })
      });
      const result = await readJson(response);
      onSaved(result.poster_url || data.default_poster_url || '', {});
      notify('Library poster reset to metadata provider');
      onClose();
    } catch (resetError) {
      setError(resetError.message);
    } finally {
      setBusy('');
    }
  }

  const tmdbOptions = data.options.filter((option) => option.source === 'tmdb');
  const plexOptions = data.options.filter((option) => option.source === 'plex');

  function renderOptions(options) {
    return options.map((option) => (
      <button
        type="button"
        className="poster-option"
        key={`${option.source}-${option.url}`}
        onClick={() => selectPoster(option)}
        disabled={Boolean(busy)}
      >
        <span className="poster-option-image">
          <img src={option.url} alt="" loading="lazy" />
          {busy === option.url && <Loader2 size={20} className="spin" />}
        </span>
        <strong>{option.label}</strong>
        <small>{option.source.toUpperCase()}</small>
      </button>
    ));
  }

  return (
    <div className="modal-backdrop poster-editor-backdrop" role="presentation" onClick={onClose}>
      <section className="poster-editor-modal" role="dialog" aria-modal="true" aria-label={`Edit poster for ${item.title || 'Library movie'}`} onClick={(event) => event.stopPropagation()}>
        <header className="dialog-header">
          <div>
            <p className="screen-kicker">Offline Library presentation</p>
            <h2>Edit poster</h2>
            <p>{item.title || item.filename}</p>
          </div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close poster editor">
            <X size={18} />
          </button>
        </header>

        {loading ? (
          <div className="library-status"><Loader2 size={16} className="spin" /> Loading poster choices...</div>
        ) : (
          <>
            <div className="poster-editor-summary">
              <CheckCircle2 size={17} />
              <span>Selections are copied into Cinema Paradiso storage and shared by duplicate copies of this movie.</span>
            </div>
            <section className="poster-provider-section">
              <div className="poster-provider-heading">
                <div>
                  <span className="mini-label">Primary source</span>
                  <h3>Choose from TMDB</h3>
                </div>
                <span className="chip">TMDB</span>
              </div>
              {tmdbOptions.length ? (
                <div className="poster-option-grid">{renderOptions(tmdbOptions)}</div>
              ) : (
                <div className="poster-option-empty">
                  <Film size={28} />
                  <strong>No TMDB posters available</strong>
                  <span>{data.providers?.tmdb?.message || 'TMDB did not return poster choices for this movie.'}</span>
                </div>
              )}
            </section>
            {(plexOptions.length > 0 || data.providers?.plex?.message) && (
              <section className="poster-provider-section">
                <div className="poster-provider-heading">
                  <div>
                    <span className="mini-label">Library provider</span>
                    <h3>Plex poster</h3>
                  </div>
                  <span className="chip chip-muted">PLEX</span>
                </div>
                {plexOptions.length ? (
                  <div className="poster-option-grid">{renderOptions(plexOptions)}</div>
                ) : (
                  <p className="poster-provider-message">{data.providers?.plex?.message}</p>
                )}
              </section>
            )}
          </>
        )}

        {error && (
          <p className="settings-inline-status settings-inline-error">
            <AlertTriangle size={15} />
            <span>{error}</span>
          </p>
        )}

        <div className="poster-editor-actions">
          <div className="poster-upload-copy">
            <span className="mini-label">Secondary option</span>
            <strong>Or use your own image</strong>
          </div>
          <input
            ref={fileInput}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            onChange={(event) => uploadPoster(event.target.files?.[0])}
          />
          <button type="button" className="btn btn-secondary" onClick={() => fileInput.current?.click()} disabled={Boolean(busy)}>
            {busy === 'upload' ? <Loader2 size={15} className="spin" /> : <Upload size={15} />} Upload local image
          </button>
          {data.override?.id && (
            <button type="button" className="btn btn-secondary" onClick={resetPoster} disabled={Boolean(busy)}>
              {busy === 'reset' ? <Loader2 size={15} className="spin" /> : <RotateCcw size={15} />} Reset poster
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
