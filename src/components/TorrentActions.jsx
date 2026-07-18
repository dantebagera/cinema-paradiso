import { Download, ExternalLink, Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { fetchJson } from '../api/client.js';
import { loadTorrentHandlingConfig } from '../api/qbittorrent.js';
import { cx, torrentPrimaryAction } from '../utils/appUtils.js';

export default function TorrentActions({ variant, movieTitle, movieYear, tmdbId = '', imdbId = '', upgrade = false, notify, primary = false }) {
  const action = torrentPrimaryAction(variant);
  const magnetUrl = action.kind === 'magnet' ? action.url : '';
  const downloadUrl = action.kind === 'torrent' ? action.url : '';
  const hasStableIdentity = Boolean(tmdbId || imdbId);
  const [mode, setMode] = useState('embedded');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadTorrentHandlingConfig().then((config) => { if (!cancelled) setMode(config.mode || 'embedded'); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  async function handlePrimary() {
    if (action.kind === 'none' || action.kind === 'source') return;
    setBusy(true);
    try {
      const config = await loadTorrentHandlingConfig();
      setMode(config.mode || 'embedded');
      if (config.mode === 'system') {
        if (!magnetUrl) {
          notify('This result has no magnet link. Use Open source page instead.', 'error');
          return;
        }
        window.location.href = magnetUrl;
        return;
      }
      const job = await fetchJson('/api/qbittorrent/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          magnet_url: magnetUrl,
          download_url: downloadUrl,
          title: movieTitle || '',
          year: movieYear || '',
          tmdb_id: tmdbId || '',
          imdb_id: imdbId || '',
          upgrade: Boolean(upgrade),
          release_title: variant.title || '',
          indexer: variant.indexer || ''
        })
      });
      if (job.already_exists) {
        notify(`${variant.title || movieTitle} ${job.state === 'imported' ? 'already imported' : 'already added'}`);
        return;
      }
      notify(`${variant.title || movieTitle} download added`);
    } catch (error) {
      notify(`qBittorrent submission failed: ${error.message}`, 'error');
    } finally {
      setBusy(false);
    }
  }

  const canSubmit = (action.kind === 'magnet' || (action.kind === 'torrent' && mode === 'embedded'))
    && (mode === 'system' || hasStableIdentity);
  return <div className="torrent-action-group">
    {canSubmit ? <button type="button" className={cx('btn', primary ? 'btn-primary' : 'btn-secondary')} onClick={handlePrimary} disabled={busy}>{busy ? <Loader2 size={15} className="spin" /> : <Download size={15} />}{mode === 'system' ? 'Open magnet' : 'Download'}</button> : action.kind === 'torrent' ? <span className="torrent-no-link">No magnet</span> : null}
    {mode === 'embedded' && magnetUrl ? <a className="btn btn-secondary" href={magnetUrl}><ExternalLink size={15} /> Open externally</a> : null}
    {variant.info_url ? <a className="btn btn-secondary" href={variant.info_url} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Open source page</a> : null}
    {action.kind === 'none' ? <span className="torrent-no-link">No link</span> : null}
  </div>;
}
