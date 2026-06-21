import {
  AlertTriangle,
  CheckCircle2,
  Clapperboard,
  Database,
  FileText,
  Loader2,
  Pause,
  Play,
  RefreshCcw,
  RotateCcw,
  Server,
  Square
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

const providerIcons = {
  tmdb: Clapperboard,
  plex: Server,
  filename: FileText
};

function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

export default function MetadataAuthorityPanel({
  fetchJson,
  notify,
  onReviewUnmatched,
  onReviewIdentities
}) {
  const [authority, setAuthority] = useState(null);
  const [target, setTarget] = useState('');
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  async function loadAuthority() {
    const data = await fetchJson('/api/metadata/authority');
    setAuthority(data);
    setTarget((current) => current || data.active_provider || 'filename');
    return data;
  }

  useEffect(() => {
    let cancelled = false;
    loadAuthority().catch((loadError) => {
      if (!cancelled) setError(loadError.message);
    });
    return () => { cancelled = true; };
  }, []);

  const migration = authority?.migration || {};
  const migrationActive = ['running', 'paused'].includes(migration.status);

  useEffect(() => {
    if (!migrationActive) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const state = await fetchJson('/api/metadata/migration');
        setAuthority((current) => current ? { ...current, migration: state } : current);
      } catch (pollError) {
        setError(pollError.message);
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [migrationActive, fetchJson]);

  const providers = useMemo(() => Object.entries(authority?.providers || {}), [authority]);

  async function previewMigration() {
    setBusy('preview');
    setError('');
    try {
      setPreview(await fetchJson('/api/metadata/authority/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target })
      }));
    } catch (previewError) {
      setError(previewError.message);
    } finally {
      setBusy('');
    }
  }

  async function startMigration() {
    setBusy('start');
    setError('');
    try {
      const state = await fetchJson('/api/metadata/authority/migrate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target })
      });
      setAuthority((current) => ({ ...current, migration: state }));
      setPreview(null);
      notify(`Metadata migration to ${authority.providers[target].label} started`);
    } catch (startError) {
      setError(startError.message);
    } finally {
      setBusy('');
    }
  }

  async function controlMigration(action) {
    setBusy(action);
    setError('');
    try {
      const state = await fetchJson(`/api/metadata/migration/${action}`, { method: 'POST' });
      setAuthority((current) => ({ ...current, migration: state }));
      if (action === 'cancel') setPreview(null);
    } catch (controlError) {
      setError(controlError.message);
    } finally {
      setBusy('');
    }
  }

  if (!authority) {
    return (
      <section className="settings-panel metadata-authority-panel">
        <div className="library-status">
          <Loader2 size={16} className="spin" />
          <span>Loading metadata authority...</span>
        </div>
      </section>
    );
  }

  const progress = Math.max(0, Math.min(100, Number(migration.progress_percent || 0)));
  const activeLabel = authority.providers?.[authority.active_provider]?.label || authority.active_provider;

  return (
    <section className="settings-panel metadata-authority-panel">
      <header className="metadata-authority-header">
        <span className="settings-panel-icon"><Database size={18} /></span>
        <div>
          <span className="metadata-authority-kicker">Library identity</span>
          <h3>Metadata authority</h3>
          <p>Choose which saved provider snapshot Cinema Paradiso uses for offline titles, posters, descriptions, cast, ratings, and movie identity.</p>
        </div>
        <div className="metadata-authority-current">
          <small>Current authority</small>
          <strong>{activeLabel}</strong>
        </div>
      </header>

      <div className="metadata-provider-options" role="radiogroup" aria-label="Metadata authority target">
        {providers.map(([key, provider]) => {
          const Icon = providerIcons[key] || Database;
          const selected = target === key;
          return (
            <button
              key={key}
              type="button"
              role="radio"
              aria-checked={selected}
              className={selected ? 'metadata-provider-option metadata-provider-selected' : 'metadata-provider-option'}
              disabled={!provider.available || migrationActive}
              onClick={() => {
                setTarget(key);
                setPreview(null);
              }}
            >
              <Icon size={18} />
              <span>
                <strong>{provider.label}</strong>
                <small>{provider.available ? 'Available' : 'Not configured'}</small>
              </span>
              {selected && <CheckCircle2 size={16} />}
            </button>
          );
        })}
      </div>

      {!migrationActive && migration.status !== 'completed' && (
        <div className="metadata-authority-actions">
          <p>
            Changing authority rebuilds saved display metadata and movie identity links. Existing metadata remains visible until each movie is processed.
            <strong> Local movie files are never changed.</strong>
          </p>
          <button type="button" className="btn btn-secondary" onClick={previewMigration} disabled={Boolean(busy)}>
            {busy === 'preview' ? <Loader2 size={15} className="spin" /> : <RefreshCcw size={15} />} Preview change
          </button>
        </div>
      )}

      {preview && (
        <div className="metadata-migration-preview">
          <AlertTriangle size={18} />
          <div>
            <strong>{formatNumber(preview.total)} local files will be checked</strong>
            <span>High-confidence matches are saved automatically. Uncertain files move to Unmatched Metadata for manual review.</span>
          </div>
          <button type="button" className="btn btn-primary" onClick={startMigration} disabled={Boolean(busy)}>
            {busy === 'start' ? <Loader2 size={15} className="spin" /> : <Play size={15} />} Start migration
          </button>
        </div>
      )}

      {migration.status && migration.status !== 'idle' && (
        <div className={`metadata-migration-state metadata-migration-${migration.status}`}>
          <div className="metadata-migration-heading">
            <div>
              <strong>{migration.status === 'completed' ? 'Migration completed' : `Migration ${migration.status}`}</strong>
              <span>{formatNumber(migration.processed)} of {formatNumber(migration.total)} files processed</span>
            </div>
            <strong>{progress.toFixed(1)}%</strong>
          </div>
          <div className="metadata-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={progress}>
            <span style={{ width: `${progress}%` }} />
          </div>
          <div className="metadata-migration-counts">
            <span><CheckCircle2 size={14} /> {formatNumber(migration.matched)} matched</span>
            <span><AlertTriangle size={14} /> {formatNumber(migration.review)} uncertain</span>
            <span><RotateCcw size={14} /> {formatNumber(migration.failed)} failed</span>
            <span><Database size={14} /> {formatNumber(migration.remaining)} remaining</span>
          </div>
          {migration.current_path && <p className="metadata-current-path" title={migration.current_path}>{migration.current_path}</p>}
          <div className="metadata-migration-controls">
            {migration.status === 'running' && (
              <button type="button" className="btn btn-secondary" onClick={() => controlMigration('pause')} disabled={Boolean(busy)}>
                <Pause size={15} /> Pause
              </button>
            )}
            {migration.status === 'paused' && (
              <button type="button" className="btn btn-primary" onClick={() => controlMigration('resume')} disabled={Boolean(busy)}>
                <Play size={15} /> Resume
              </button>
            )}
            {migrationActive && (
              <button type="button" className="btn btn-secondary" onClick={() => controlMigration('cancel')} disabled={Boolean(busy)}>
                <Square size={15} /> Cancel
              </button>
            )}
            {migration.failed > 0 && migration.status !== 'running' && (
              <button type="button" className="btn btn-secondary" onClick={() => controlMigration('retry')} disabled={Boolean(busy)}>
                <RotateCcw size={15} /> Retry failures
              </button>
            )}
            {migration.review > 0 && (
              <button type="button" className="btn btn-violet" onClick={onReviewUnmatched}>Review uncertain matches</button>
            )}
          </div>
        </div>
      )}

      <div className="metadata-review-routing">
        <div>
          <strong>Matched identities are checked after migration</strong>
          <span>Possible wrong-movie corrections belong in Cleanup, separate from files that have no accepted match.</span>
        </div>
        <button type="button" className="btn btn-secondary" onClick={onReviewIdentities}>
          Review identity corrections
        </button>
      </div>

      {error && (
        <p className="settings-inline-status settings-inline-error">
          <AlertTriangle size={15} />
          <span>{error}</span>
        </p>
      )}
    </section>
  );
}
