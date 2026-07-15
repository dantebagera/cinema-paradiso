import {
  AlertTriangle,
  CheckCircle2,
  Clapperboard,
  Loader2,
  Pause,
  Play,
  RefreshCcw,
  Search,
  Sparkles
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { fetchJson } from '../api/client.js';
import MetadataCorrectionModal from './MetadataCorrectionModal.jsx';

function providerId(item, side) {
  const identity = item?.[side] || {};
  return String(
    identity.tmdb_id
    || identity.plex_guid
    || identity.guid
    || (side === 'current' ? item?.previous_provider_id : item?.provider_id)
    || ''
  );
}

function IdentityRows({
  rows,
  selected,
  selectable,
  plexAvailable,
  onToggle,
  onPlay,
  onTmdbMatch,
  onPlexMatch,
  onCorrectMetadata
}) {
  return (
    <div className="identity-review-list">
      {rows.map((proposal) => {
        const currentId = providerId(proposal, 'current');
        const candidateId = providerId(proposal, 'candidate');
        const idChanged = Boolean(currentId && candidateId && currentId !== candidateId);
        const statusLabel = proposal.proposal_type === 'metadata_discrepancy'
          ? 'Metadata discrepancy'
          : proposal.classification === 'actionable'
            ? 'Actionable contradiction'
          : proposal.classification === 'recommended'
          ? 'Recommended correction'
          : proposal.classification === 'weak'
            ? 'Weak match'
            : proposal.classification === 'automatic'
              ? 'Automatically verified'
              : 'Needs review';
        return (
          <article className={`identity-review-row identity-review-${proposal.classification || 'review'}`} key={proposal.id}>
            {selectable ? (
              <label className="cleanup-check">
                <input type="checkbox" checked={selected.has(proposal.id)} onChange={(event) => onToggle(proposal.id, event.target.checked)} />
                <span>Select</span>
              </label>
            ) : (
              <span className="identity-review-applied"><AlertTriangle size={17} /></span>
            )}
            <span className="match-result-poster">
              {proposal.candidate?.poster_url ? <img src={proposal.candidate.poster_url} alt="" loading="lazy" /> : <Clapperboard size={20} />}
            </span>
            <div className="identity-review-copy">
              <strong>{proposal.filename}</strong>
              <span>
                {proposal.current?.title || 'Unknown identity'} {proposal.current?.year ? `(${proposal.current.year})` : ''}
                {' → '}
                {proposal.candidate?.title || proposal.candidate?.name || 'Unknown candidate'} {proposal.candidate?.year ? `(${proposal.candidate.year})` : ''}
              </span>
              <small>Evidence score {proposal.evidence_score || 0} · runner-up gap {proposal.runner_up_gap || 0} · {(proposal.reasons || []).join(', ')}</small>
              {candidateId && (
                <small className={idChanged ? 'identity-review-id-conflict' : ''}>
                  {idChanged
                    ? `Provider ID ${currentId} → ${candidateId} · Existing provider ID changes require approval.`
                    : currentId
                      ? `Provider ID ${candidateId}`
                      : `Provider ID added: ${candidateId}`}
                </small>
              )}
              <b>{statusLabel}</b>
            </div>
            <div className="cleanup-row-actions">
              <button type="button" className="btn btn-primary btn-green" onClick={() => onPlay(proposal.path)}>
                <Play size={15} /> Play file
              </button>
              <button type="button" className="btn btn-primary btn-violet" onClick={() => onTmdbMatch(proposal)}>
                <Search size={15} /> Search TMDB manually
              </button>
              {plexAvailable && (
                <button type="button" className="btn btn-secondary" onClick={() => onPlexMatch(proposal)}>
                  <Clapperboard size={15} /> Search Plex manually
                </button>
              )}
              <button type="button" className="btn btn-secondary" onClick={() => onCorrectMetadata(proposal)}>
                Correct metadata
              </button>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function ReviewSection({ title, description, rows, children }) {
  if (!rows.length) return null;
  return (
    <section className="identity-review-group">
      <header>
        <div>
          <strong>{title}</strong>
          <p>{description}</p>
        </div>
        <span>{rows.length}</span>
      </header>
      {children}
    </section>
  );
}

export default function IdentityReviewPanel({
  audit,
  items,
  loading,
  error,
  plexAvailable,
  onStart,
  onPause,
  onResume,
  onRefresh,
  onAuditChanged,
  onPlay,
  onTmdbMatch,
  onPlexMatch,
  onHealthChanged,
  externalApproved,
  onExternalApprovedConsumed,
  notify
}) {
  const [selected, setSelected] = useState(new Set());
  const [selectedJob, setSelectedJob] = useState('');
  const [busy, setBusy] = useState('');
  const [approved, setApproved] = useState([]);
  const [renamePreview, setRenamePreview] = useState(null);
  const [renameSelected, setRenameSelected] = useState(new Set());
  const [correctionTarget, setCorrectionTarget] = useState(null);
  const bulkRef = useRef(null);
  const visibleIds = useMemo(() => (items || []).map((item) => item.id), [items]);
  const recommendedIds = useMemo(
    () => (audit?.proposals || []).filter((item) => item.classification === 'recommended').map((item) => item.id),
    [audit?.proposals]
  );
  const recommendedRows = useMemo(
    () => (items || []).filter((item) => item.classification === 'recommended' && item.proposal_type !== 'metadata_discrepancy'),
    [items]
  );
  const discrepancyRows = useMemo(
    () => (items || []).filter((proposal) => proposal.proposal_type === 'metadata_discrepancy'),
    [items]
  );
  const reviewRows = useMemo(
    () => (items || []).filter((item) => !['recommended', 'weak'].includes(item.classification) && item.proposal_type !== 'metadata_discrepancy'),
    [items]
  );
  const weakRows = useMemo(
    () => (items || []).filter((item) => item.classification === 'weak'),
    [items]
  );
  const automaticRows = audit?.automatic_fixes || [];
  const shadowMode = audit?.shadow_mode !== false;
  const outcomeCounts = audit?.outcome_counts || {};

  useEffect(() => {
    if (!audit?.id || selectedJob === audit.id) return;
    setSelected(new Set());
    setSelectedJob(audit.id);
  }, [audit?.id, selectedJob]);

  useEffect(() => {
    if (!externalApproved) return;
    setApproved([externalApproved]);
    setRenamePreview(null);
    onExternalApprovedConsumed();
  }, [externalApproved, onExternalApprovedConsumed]);

  useEffect(() => {
    if (bulkRef.current) {
      const visibleSelectedCount = visibleIds.filter((id) => selected.has(id)).length;
      bulkRef.current.indeterminate = visibleSelectedCount > 0 && visibleSelectedCount < visibleIds.length;
    }
  }, [selected, visibleIds]);

  function choose(ids) {
    setSelected(new Set(ids));
  }

  function addSelected(ids) {
    setSelected((current) => new Set([...current, ...ids]));
  }

  function toggle(id, checked) {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  async function applySelected() {
    if (!audit?.id || !selected.size) return;
    const visibleSelectedCount = visibleIds.filter((id) => selected.has(id)).length;
    const hiddenSelectedCount = selected.size - visibleSelectedCount;
    const hiddenNotice = hiddenSelectedCount ? ` ${hiddenSelectedCount} selected item${hiddenSelectedCount === 1 ? ' is' : 's are'} hidden by this filter.` : '';
    if (!window.confirm(`Apply ${selected.size} selected correction${selected.size === 1 ? '' : 's'}?${hiddenNotice}`)) return;
    setBusy('apply');
    try {
      const result = await fetchJson(`/api/metadata/identity-audit/${encodeURIComponent(audit.id)}/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proposal_ids: [...selected] })
      });
      const successfulIds = new Set((result.results || []).filter((entry) => entry.success).map((entry) => entry.id));
      setApproved((audit?.proposals || []).filter((item) => successfulIds.has(item.id) && item.proposal_type !== 'metadata_discrepancy'));
      const state = await fetchJson(`/api/metadata/identity-audit/${encodeURIComponent(audit.id)}`);
      onAuditChanged(state);
      setSelected(new Set());
      onHealthChanged();
      notify(`${result.applied} identity correction${result.applied === 1 ? '' : 's'} applied`);
      if (result.failed) notify(`${result.failed} correction${result.failed === 1 ? '' : 's'} failed`, 'error');
    } catch (applyError) {
      notify(`Identity correction failed: ${applyError.message}`, 'error');
    } finally {
      setBusy('');
    }
  }

  async function metadataCorrectionSaved() {
    setCorrectionTarget(null);
    setSelected((current) => {
      const next = new Set(current);
      if (correctionTarget?.id) next.delete(correctionTarget.id);
      return next;
    });
    await onRefresh();
    onHealthChanged();
  }

  const visibleSelectedCount = visibleIds.filter((id) => selected.has(id)).length;
  const hiddenSelectedCount = selected.size - visibleSelectedCount;

  function ApplyControls({ label }) {
    return (
      <div className="identity-review-apply-controls">
        <button type="button" className="btn btn-primary btn-violet" onClick={applySelected} disabled={!selected.size || Boolean(busy)}>
          {busy === 'apply' ? <Loader2 size={15} className="spin" /> : <CheckCircle2 size={15} />}
          {label} ({selected.size})
        </button>
        {hiddenSelectedCount > 0 && <small>{hiddenSelectedCount} selected item{hiddenSelectedCount === 1 ? '' : 's'} hidden by this filter</small>}
      </div>
    );
  }

  async function previewRename() {
    setBusy('rename-preview');
    try {
      const preview = await fetchJson('/api/metadata/smart-rename/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items: approved.map((proposal) => ({
            path: proposal.path,
            title: proposal.candidate?.title || proposal.candidate?.name,
            year: proposal.candidate?.year || ''
          }))
        })
      });
      setRenamePreview(preview);
      setRenameSelected(new Set((preview.items || []).filter((item) => !item.blocked).map((item) => item.path)));
    } catch (renameError) {
      notify(`Rename preview failed: ${renameError.message}`, 'error');
    } finally {
      setBusy('');
    }
  }

  async function applyRename() {
    if (!renamePreview || !renameSelected.size) return;
    if (!window.confirm(`Rename ${renameSelected.size} corrected file${renameSelected.size === 1 ? '' : 's'}?`)) return;
    setBusy('rename');
    try {
      const result = await fetchJson('/api/metadata/smart-rename/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: renamePreview.token, paths: [...renameSelected] })
      });
      notify(`${result.renamed} corrected file${result.renamed === 1 ? '' : 's'} renamed`);
      if (result.failed) notify(`${result.failed} rename${result.failed === 1 ? '' : 's'} failed`, 'error');
      setRenamePreview(null);
      setApproved([]);
      onRefresh();
      onHealthChanged();
    } catch (renameError) {
      notify(`Rename failed: ${renameError.message}`, 'error');
    } finally {
      setBusy('');
    }
  }

  if (loading) {
    return <div className="library-status"><Loader2 size={16} className="spin" /><span>Loading Identity Review...</span></div>;
  }

  if (error) {
    return <div className="library-status library-status-error"><AlertTriangle size={16} /><span>{error}</span></div>;
  }

  return (
    <div className="cleanup-panel identity-review-panel">
      <section className="identity-review-intro">
        <div>
          <strong>Review possible identity corrections</strong>
          <p>The full library check is read-only. Only identities contradicted by independent provider evidence appear below.</p>
          {audit?.requires_refresh && (
            <p className="identity-review-refresh-note">
              Previous results used older matching rules. Run the audit again to review only results
              produced by the current identity checks.
            </p>
          )}
        </div>
        <div className="identity-review-scan-actions">
          {audit?.status === 'running' && (
            <button type="button" className="btn btn-secondary" onClick={onPause}>
              <Pause size={15} /> Pause scan
            </button>
          )}
          {audit?.status === 'paused' && (
            <button type="button" className="btn btn-primary" onClick={onResume}>
              <Play size={15} /> Resume scan
            </button>
          )}
          {audit?.status !== 'running' && (
            <button type="button" className="btn btn-secondary" onClick={onStart}>
              <RefreshCcw size={15} /> Recheck all identities
            </button>
          )}
        </div>
      </section>

      {['running', 'paused'].includes(audit?.status) && (
        <div className="identity-review-progress">
          {audit?.status === 'running' ? <Loader2 size={17} className="spin" /> : <Pause size={17} />}
          <div>
            <strong>{audit.processed || 0} of {audit.total || 0} checked</strong>
            <span>{audit?.status === 'paused' ? 'Scan paused. Partial results are saved.' : audit.current_path || 'Checking accepted movie identities...'}</span>
          </div>
        </div>
      )}

      <div className="identity-review-summary">
        <span><CheckCircle2 size={14} /> {outcomeCounts.verified || 0} verified</span>
        <span>{outcomeCounts.manual || 0} manual identities protected</span>
        <span>{outcomeCounts.actionable || 0} actionable</span>
        <span>{outcomeCounts.ambiguous || 0} uncertain, no action</span>
        <span>{outcomeCounts.unmatched || 0} unmatched</span>
        <span>{audit?.last_checked_at ? `Last checked ${new Date(audit.last_checked_at * 1000).toLocaleString()}` : 'Not checked yet'}</span>
      </div>

      {!shadowMode && automaticRows.length > 0 && (
        <details className="identity-review-automatic">
          <summary>
            <span><CheckCircle2 size={16} /> Automatic verifications</span>
            <small>{automaticRows.length} verified without changing the accepted identity</small>
          </summary>
          <p>These rows only added a missing provider link to the same exact movie identity. No existing provider identity was replaced.</p>
          <IdentityRows
            rows={automaticRows}
            selected={selected}
            selectable={false}
            plexAvailable={plexAvailable}
            onToggle={toggle}
            onPlay={onPlay}
            onTmdbMatch={onTmdbMatch}
            onPlexMatch={onPlexMatch}
            onCorrectMetadata={setCorrectionTarget}
          />
        </details>
      )}

      {!shadowMode && visibleIds.length > 0 && (
        <div className="smart-match-bulk">
          <label>
            <input
              ref={bulkRef}
              type="checkbox"
              checked={visibleIds.length > 0 && visibleIds.every((id) => selected.has(id))}
              onChange={(event) => {
                if (event.target.checked) addSelected(visibleIds);
                else setSelected((current) => new Set([...current].filter((id) => !visibleIds.includes(id))));
              }}
            />
            <span>{selected.size} selected{hiddenSelectedCount ? ` · ${hiddenSelectedCount} hidden` : ''}</span>
          </label>
          <div>
            <button type="button" className="mini-action" onClick={() => addSelected(recommendedIds)} disabled={!recommendedIds.length}>Select recommended</button>
            <button type="button" className="mini-action" onClick={() => addSelected(visibleIds)} disabled={!visibleIds.length}>Select all visible</button>
            <button type="button" className="mini-action" onClick={() => choose([])} disabled={!selected.size}>Clear</button>
          </div>
        </div>
      )}

      {!shadowMode && selected.size > 0 && <ApplyControls label="Apply selected corrections" />}

      {shadowMode && (
        <ReviewSection
          title="Actionable contradictions"
          description="Independent provider IDs or content evidence contradict the accepted movie identity. Nothing has been changed."
          rows={items || []}
        >
          <IdentityRows rows={items || []} selected={selected} selectable={false} plexAvailable={plexAvailable} onToggle={toggle} onPlay={onPlay} onTmdbMatch={onTmdbMatch} onPlexMatch={onPlexMatch} onCorrectMetadata={setCorrectionTarget} />
        </ReviewSection>
      )}

      {!shadowMode && <ReviewSection
        title="Recommended corrections"
        description="Strong identity-changing proposals. They remain unselected until you explicitly choose them."
        rows={recommendedRows}
      >
        <IdentityRows rows={recommendedRows} selected={selected} selectable plexAvailable={plexAvailable} onToggle={toggle} onPlay={onPlay} onTmdbMatch={onTmdbMatch} onPlexMatch={onPlexMatch} onCorrectMetadata={setCorrectionTarget} />
      </ReviewSection>}

      {!shadowMode && <ReviewSection
        title="Metadata discrepancies"
        description="The accepted movie identity is exact, but the filename and provider years differ by at least three years. Review the display year before saving a local correction."
        rows={discrepancyRows}
      >
        <IdentityRows rows={discrepancyRows} selected={selected} selectable plexAvailable={plexAvailable} onToggle={toggle} onPlay={onPlay} onTmdbMatch={onTmdbMatch} onPlexMatch={onPlexMatch} onCorrectMetadata={setCorrectionTarget} />
      </ReviewSection>}

      {!shadowMode && <ReviewSection
        title="Needs review"
        description="Plausible proposals with ambiguous evidence, a narrow runner-up gap, or a provider-ID conflict."
        rows={reviewRows}
      >
        <IdentityRows rows={reviewRows} selected={selected} selectable plexAvailable={plexAvailable} onToggle={toggle} onPlay={onPlay} onTmdbMatch={onTmdbMatch} onPlexMatch={onPlexMatch} onCorrectMetadata={setCorrectionTarget} />
      </ReviewSection>}

      {!shadowMode && <ReviewSection
        title="Weak matches"
        description="Evidence score below 70. These are never preselected and need close manual inspection."
        rows={weakRows}
      >
        <IdentityRows rows={weakRows} selected={selected} selectable plexAvailable={plexAvailable} onToggle={toggle} onPlay={onPlay} onTmdbMatch={onTmdbMatch} onPlexMatch={onPlexMatch} onCorrectMetadata={setCorrectionTarget} />
      </ReviewSection>}

      {!items?.length && !automaticRows.length && !['running', 'paused'].includes(audit?.status) && (
        <div className="empty-state library-empty cleanup-empty">
          <strong>No matched identities currently need review.</strong>
          <span>Run the full-library check after changing metadata authority or matching rules.</span>
        </div>
      )}

      {!shadowMode && <footer className="identity-review-footer">
        <ApplyControls label="Apply selected corrections" />
        {approved.length > 0 && !renamePreview && (
          <button type="button" className="btn btn-secondary" onClick={previewRename} disabled={Boolean(busy)}>
            <Sparkles size={15} /> Preview rename corrected files
          </button>
        )}
      </footer>}

      {renamePreview && (
        <section className="identity-rename-preview">
          {(renamePreview.items || []).map((item) => (
            <label className={item.blocked ? 'smart-rename-row smart-rename-blocked' : 'smart-rename-row'} key={item.path}>
              <input
                type="checkbox"
                disabled={Boolean(item.blocked)}
                checked={!item.blocked && renameSelected.has(item.path)}
                onChange={(event) => setRenameSelected((current) => {
                  const next = new Set(current);
                  if (event.target.checked) next.add(item.path);
                  else next.delete(item.path);
                  return next;
                })}
              />
              <span><strong>{item.old_filename}</strong><b>{item.new_filename}</b><small>{item.blocked || 'Ready to rename'}</small></span>
            </label>
          ))}
          <button type="button" className="btn btn-primary" onClick={applyRename} disabled={!renameSelected.size || Boolean(busy)}>
            Confirm rename selected files
          </button>
        </section>
      )}
      {correctionTarget && (
        <MetadataCorrectionModal
          item={correctionTarget}
          notify={notify}
          onClose={() => setCorrectionTarget(null)}
          onSaved={metadataCorrectionSaved}
        />
      )}
    </div>
  );
}
