import { AlertTriangle, CheckCircle2, Loader2, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchJson } from '../../api/client.js';

export default function DownloadsWorkspace() {
  const [audit, setAudit] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);

  const loadAudit = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setAudit(await fetchJson('/api/qbittorrent/import-audit'));
    } catch (requestError) {
      setError(requestError.message || 'Could not load the legacy import audit.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAudit();
  }, [loadAudit]);

  const candidates = useMemo(
    () => (audit?.items || []).filter((item) => item.classification === 'verified_candidate'),
    [audit],
  );
  const reviewItems = useMemo(
    () => (audit?.items || []).filter((item) => item.classification === 'review_required'),
    [audit],
  );

  async function verifyCandidates() {
    if (!candidates.length) return;
    setVerifying(true);
    setError('');
    try {
      await fetchJson('/api/qbittorrent/import-audit/verify', {
        method: 'POST',
        body: JSON.stringify({ hashes: candidates.map((item) => item.hash) }),
      });
      await loadAudit();
    } catch (requestError) {
      setError(requestError.message || 'Could not verify the exact SQL matches.');
    } finally {
      setVerifying(false);
    }
  }

  return (
    <section className="downloads-workspace" aria-label="Downloads powered by qBittorrent">
      {audit?.summary?.deferred_jobs > 0 ? (
        <section className="download-legacy-audit" aria-label="Legacy import audit">
          <div className="download-legacy-audit-head">
            <div>
              <p className="screen-kicker">Legacy import audit</p>
              <strong>{audit.summary.deferred_jobs} deferred completed imports</strong>
            </div>
            <button className="icon-button" type="button" onClick={loadAudit} disabled={loading || verifying} title="Refresh legacy import audit" aria-label="Refresh legacy import audit">
              {loading ? <Loader2 size={16} className="spin-icon" /> : <RefreshCw size={16} />}
            </button>
          </div>
          <div className="download-legacy-audit-summary">
            <span><CheckCircle2 size={15} /> {audit.summary.verified_candidates} exact SQL matches</span>
            <span><AlertTriangle size={15} /> {audit.summary.review_required} need review</span>
            {candidates.length > 0 ? (
              <button className="secondary-button" type="button" onClick={verifyCandidates} disabled={verifying}>
                {verifying ? <Loader2 size={15} className="spin-icon" /> : <CheckCircle2 size={15} />}
                Verify exact matches
              </button>
            ) : null}
          </div>
          {reviewItems.length > 0 ? (
            <div className="download-legacy-review-list">
              {reviewItems.slice(0, 5).map((item) => (
                <div className="download-legacy-review-row" key={item.hash}>
                  <AlertTriangle size={15} aria-hidden="true" />
                  <div>
                    <strong>{item.title || item.release_title || item.hash}</strong>
                    <span>{item.reason}</span>
                  </div>
                </div>
              ))}
              {reviewItems.length > 5 ? <span className="download-legacy-more">+{reviewItems.length - 5} more records require review</span> : null}
            </div>
          ) : null}
        </section>
      ) : null}
      {error ? <div className="library-status library-status-error" role="alert">{error}</div> : null}
      <iframe className="downloads-frame" title="qBittorrent Downloads" src="/qbittorrent/" />
    </section>
  );
}
