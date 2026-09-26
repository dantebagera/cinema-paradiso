import { useEffect, useState } from 'react';
import { fetchJson } from '../../api/client.js';

export default function TVSettings({ notify }) {
  const [enabled, setEnabled] = useState(false);
  const [roots, setRoots] = useState('');
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    fetchJson('/api/tv/config').then((data) => {
      if (alive) { setEnabled(Boolean(data.enabled)); setRoots((data.roots || []).join('\n')); setBusy(false); }
    }).catch((failure) => { if (alive) { setError(failure.message); setBusy(false); } });
    return () => { alive = false; };
  }, []);

  async function save() {
    setBusy(true);
    try {
      const data = await fetchJson('/api/tv/config', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled, roots: roots.split(/\r?\n/).map((value) => value.trim()).filter(Boolean) }),
      });
      setEnabled(Boolean(data.enabled));
      setRoots((data.roots || []).join('\n'));
      setError('');
      window.dispatchEvent(new CustomEvent('cp-tv-capability-changed', { detail: data.enabled }));
      notify?.('TV settings saved');
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }

  return <section id="settings-tv" className="settings-panel integration-card integration-gold">
    <div><strong>Native TV library</strong><p>Keep series, episodes, files, and progress in the separate TV catalog.</p></div>
    <label className="settings-toggle"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /><span><strong>Enable native TV</strong><small>Shows TV in Library, Discover, Home, and Downloads.</small></span></label>
    <label className="dialog-field"><span>TV library roots</span><textarea rows="3" value={roots} onChange={(event) => setRoots(event.target.value)} placeholder="One existing folder per line" /><small>Local and Plex-discovered files must stay inside these folders.</small></label>
    {error ? <p role="alert">{error}</p> : null}
    <button type="button" className="btn btn-primary" disabled={busy} onClick={save}>{busy ? 'Saving…' : 'Save TV settings'}</button>
  </section>;
}
