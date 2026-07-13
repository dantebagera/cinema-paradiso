import { AlertTriangle, Bot, CheckCircle2, Clapperboard, Loader2, Search, Sparkles, Wand2, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { fetchJson } from '../api/client.js';

function normalizeProposal(proposal) {
  const evidenceScore = proposal.evidence_score ?? proposal.confidence ?? 0;
  const recommendation = proposal.recommendation || (proposal.preselected ? 'recommended' : evidenceScore >= 55 ? 'review' : 'weak');
  return {
    ...proposal,
    evidence_score: evidenceScore,
    runner_up_gap: proposal.runner_up_gap ?? 0,
    recommendation
  };
}

export function SmartMatchControls({ selectedPaths, ollamaAvailable, providers, onStarted, notify }) {
  const [provider, setProvider] = useState('tmdb');
  const [method, setMethod] = useState('classic');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (providers?.tmdb === false && providers?.plex !== false) setProvider('plex');
  }, [providers?.tmdb, providers?.plex]);

  async function start() {
    if (!selectedPaths.length) return;
    setBusy(true);
    try {
      const job = await fetchJson('/api/metadata/smart-match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths: selectedPaths, provider, method })
      });
      onStarted(job);
    } catch (error) {
      notify(`Smart Match could not start: ${error.message}`, 'error');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="smart-match-controls">
      <div>
        <strong>Smart Match</strong>
        <span>Build provider suggestions for selected unmatched files. Nothing applies during preview.</span>
      </div>
      <fieldset>
        <legend>Database</legend>
        <label><input type="radio" name="smart-provider" value="tmdb" checked={provider === 'tmdb'} onChange={() => setProvider('tmdb')} disabled={providers?.tmdb === false} /> TMDB</label>
        <label><input type="radio" name="smart-provider" value="plex" checked={provider === 'plex'} onChange={() => setProvider('plex')} disabled={providers?.plex === false} /> Plex</label>
      </fieldset>
      <fieldset>
        <legend>Method</legend>
        <label><input type="radio" name="smart-method" value="classic" checked={method === 'classic'} onChange={() => setMethod('classic')} /> Classic match</label>
        <label title={ollamaAvailable ? '' : 'Configure Ollama in Settings to use Match by AI'}>
          <input type="radio" name="smart-method" value="ai" checked={method === 'ai'} onChange={() => setMethod('ai')} disabled={!ollamaAvailable} />
          Match by AI
        </label>
      </fieldset>
      <button type="button" className="btn btn-primary btn-violet" onClick={start} disabled={busy || !selectedPaths.length || !providers?.[provider]}>
        {busy ? <Loader2 size={15} className="spin" /> : method === 'ai' ? <Bot size={15} /> : <Wand2 size={15} />}
        Smart Match Selected ({selectedPaths.length})
      </button>
    </section>
  );
}

export function SmartMatchReviewModal({
  job,
  items,
  onJobChange,
  onClose,
  onApplied,
  onTmdbMatch,
  onPlexMatch,
  plexAvailable,
  notify
}) {
  const [selected, setSelected] = useState(new Set());
  const [confirmApply, setConfirmApply] = useState(false);
  const [applying, setApplying] = useState(false);
  const [approved, setApproved] = useState([]);
  const [renamePreview, setRenamePreview] = useState(null);
  const [renameSelected, setRenameSelected] = useState(new Set());
  const [confirmRename, setConfirmRename] = useState(false);
  const bulkCheckboxRef = useRef(null);
  const proposals = useMemo(() => (job?.proposals || []).map(normalizeProposal), [job?.proposals]);
  const proposalIds = useMemo(() => proposals.map((proposal) => proposal.id), [proposals]);
  const recommendedIds = useMemo(
    () => proposals.filter((proposal) => proposal.recommendation === 'recommended').map((proposal) => proposal.id),
    [proposals]
  );

  useEffect(() => {
    if (!job?.id || job.status !== 'running') return undefined;
    const timer = window.setInterval(async () => {
      try {
        const next = await fetchJson(`/api/metadata/smart-match/${job.id}`);
        onJobChange(next);
      } catch (error) {
        notify(`Smart Match status failed: ${error.message}`, 'error');
      }
    }, 700);
    return () => window.clearInterval(timer);
  }, [job?.id, job?.status, notify, onJobChange]);

  useEffect(() => {
    if (job?.status === 'completed') {
      setSelected(new Set(recommendedIds));
    }
  }, [job?.status, recommendedIds]);

  useEffect(() => {
    if (bulkCheckboxRef.current) {
      bulkCheckboxRef.current.indeterminate = selected.size > 0 && selected.size < proposalIds.length;
    }
  }, [proposalIds.length, selected]);

  const itemByPath = useMemo(() => new Map((items || []).map((item) => [item.path, item])), [items]);

  function toggleProposal(id, checked) {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
    setConfirmApply(false);
  }

  function selectProposalIds(ids) {
    setSelected(new Set(ids));
    setConfirmApply(false);
  }

  async function cancel() {
    try {
      onJobChange(await fetchJson(`/api/metadata/smart-match/${job.id}/cancel`, { method: 'POST' }));
    } catch (error) {
      notify(`Smart Match cancel failed: ${error.message}`, 'error');
    }
  }

  async function applyMatches() {
    setApplying(true);
    try {
      const result = await fetchJson(`/api/metadata/smart-match/${job.id}/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proposal_ids: [...selected] })
      });
      const succeeded = new Set((result.results || []).filter((entry) => entry.success).map((entry) => entry.id));
      const appliedProposals = proposals.filter((proposal) => succeeded.has(proposal.id));
      setApproved(appliedProposals);
      onApplied(appliedProposals.map((proposal) => proposal.path));
      setConfirmApply(false);
      notify(`${result.applied} Smart Match result${result.applied === 1 ? '' : 's'} applied`);
      if (result.failed) notify(`${result.failed} Smart Match result${result.failed === 1 ? '' : 's'} failed`, 'error');
    } catch (error) {
      notify(`Smart Match apply failed: ${error.message}`, 'error');
    } finally {
      setApplying(false);
    }
  }

  async function previewRename() {
    try {
      const preview = await fetchJson('/api/metadata/smart-rename/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items: approved.map((proposal) => ({
            path: proposal.path,
            title: proposal.candidate.title || proposal.candidate.name,
            year: proposal.candidate.year || proposal.parsed.year,
            release: proposal.parsed
          }))
        })
      });
      setRenamePreview(preview);
      setRenameSelected(new Set((preview.items || []).filter((item) => !item.blocked).map((item) => item.path)));
    } catch (error) {
      notify(`Rename preview failed: ${error.message}`, 'error');
    }
  }

  async function applyRename() {
    setApplying(true);
    try {
      const result = await fetchJson('/api/metadata/smart-rename/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: renamePreview.token, paths: [...renameSelected] })
      });
      notify(`${result.renamed} file${result.renamed === 1 ? '' : 's'} renamed`);
      if (result.failed) notify(`${result.failed} file rename${result.failed === 1 ? '' : 's'} failed`, 'error');
      onClose();
    } catch (error) {
      notify(`Batch rename failed: ${error.message}`, 'error');
    } finally {
      setApplying(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="smart-match-dialog" role="dialog" aria-modal="true" aria-label="Smart Match review" onClick={(event) => event.stopPropagation()}>
        <header className="dialog-header">
          <div>
            <p className="screen-kicker">Unmatched metadata</p>
            <h2>Smart Match review</h2>
            <p>{job.provider?.toUpperCase()} · {job.method === 'ai' ? 'Match by AI' : 'Classic match'}</p>
          </div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close Smart Match review"><X size={18} /></button>
        </header>

        {job.status === 'running' && (
          <div className="smart-match-progress">
            <Loader2 size={17} className="spin" />
            <div><strong>{job.processed} of {job.total}</strong><span>{job.current_path || 'Preparing next file...'}</span></div>
            <button type="button" className="btn btn-secondary" onClick={cancel}>Cancel preview</button>
          </div>
        )}

        {job.status !== 'running' && !renamePreview && (
          <>
            {proposals.length > 0 && (
              <div className="smart-match-bulk">
                <label>
                  <input
                    ref={bulkCheckboxRef}
                    type="checkbox"
                    checked={proposalIds.length > 0 && selected.size === proposalIds.length}
                    onChange={(event) => selectProposalIds(event.target.checked ? proposalIds : [])}
                  />
                  <span>{selected.size} of {proposalIds.length} selected</span>
                </label>
                <div>
                  <button type="button" className="mini-action" onClick={() => selectProposalIds(recommendedIds)} disabled={!recommendedIds.length}>Select recommended</button>
                  <button type="button" className="mini-action" onClick={() => selectProposalIds(proposalIds)} disabled={!proposalIds.length}>Select all proposals</button>
                  <button type="button" className="mini-action" onClick={() => selectProposalIds([])} disabled={!selected.size}>Clear</button>
                </div>
              </div>
            )}
            <div className="smart-match-result-list">
              {proposals.map((proposal) => {
                const aiQuery = (proposal.queries || []).find((query) => query.source === 'ai_primary') || proposal.query;
                return (
                <article className={`smart-match-result smart-match-${proposal.recommendation}`} key={proposal.id}>
                  <label className="cleanup-check">
                    <input type="checkbox" checked={selected.has(proposal.id)} onChange={(event) => toggleProposal(proposal.id, event.target.checked)} />
                    <span>Select</span>
                  </label>
                  <span className="match-result-poster">{proposal.candidate.poster_url ? <img src={proposal.candidate.poster_url} alt="" /> : <Clapperboard size={20} />}</span>
                  <div>
                    <strong>{proposal.filename}</strong>
                    <span>Parsed: {proposal.parsed.title}{proposal.parsed.year ? ` (${proposal.parsed.year})` : ''}</span>
                    {job.method === 'ai' && aiQuery?.title && <span>AI query: {aiQuery.title}{aiQuery.year ? ` (${aiQuery.year})` : ''}</span>}
                    <b>{proposal.candidate.title || proposal.candidate.name} {proposal.candidate.year ? `(${proposal.candidate.year})` : ''}</b>
                    <div className="smart-match-evidence">
                      <span className={`chip smart-match-label-${proposal.recommendation}`}>{proposal.recommendation}</span>
                      <small>Evidence score {proposal.evidence_score} · Runner-up gap {proposal.runner_up_gap} · {(proposal.reasons || []).join(' · ')}</small>
                    </div>
                    {proposal.ai_status === 'classic_fallback' && (
                      <small className="smart-match-warning">Classic fallback — {proposal.ai_warning || 'AI response invalid'}</small>
                    )}
                  </div>
                </article>
              )})}
              {(job.unresolved || []).map((entry) => {
                const item = itemByPath.get(entry.path);
                return (
                  <article className="smart-match-result smart-match-unresolved" key={entry.path}>
                    <AlertTriangle size={18} />
                    <div>
                      <strong>{entry.filename || item?.filename}</strong>
                      <span>{entry.reason || 'No strong candidate found'}</span>
                      {entry.ai_status === 'classic_fallback' && <small className="smart-match-warning">Classic fallback — {entry.ai_warning || 'AI response invalid'}</small>}
                    </div>
                    <div className="cleanup-row-actions">
                      <button type="button" className="btn btn-secondary" onClick={() => item && onTmdbMatch(item)}><Search size={14} /> Search TMDB manually</button>
                      <button type="button" className="btn btn-secondary" onClick={() => item && onPlexMatch(item)} disabled={!item || !plexAvailable}><Clapperboard size={14} /> Search Plex manually</button>
                    </div>
                  </article>
                );
              })}
              {(job.errors || []).map((entry) => (
                <article className="smart-match-result smart-match-unresolved" key={`${entry.path}-${entry.error}`}>
                  <AlertTriangle size={18} />
                  <div><strong>{itemByPath.get(entry.path)?.filename || entry.path}</strong><span>{entry.error}</span></div>
                </article>
              ))}
            </div>
            <footer className="smart-match-footer">
              {approved.length ? (
                <button type="button" className="btn btn-secondary" onClick={previewRename}><Sparkles size={15} /> Preview rename approved files</button>
              ) : confirmApply ? (
                <button type="button" className="btn btn-primary btn-violet" onClick={applyMatches} disabled={applying || !selected.size}>
                  {applying ? <Loader2 size={15} className="spin" /> : <CheckCircle2 size={15} />} Confirm apply matches
                </button>
              ) : (
                <button type="button" className="btn btn-primary btn-violet" onClick={() => setConfirmApply(true)} disabled={!selected.size}>
                  Review selected matches ({selected.size})
                </button>
              )}
              <span>Only explicitly selected proposals will be applied.</span>
            </footer>
          </>
        )}

        {renamePreview && (
          <>
            <div className="smart-rename-list">
              {(renamePreview.items || []).map((item) => (
                <label className={item.blocked ? 'smart-rename-row smart-rename-blocked' : 'smart-rename-row'} key={item.path}>
                  <input
                    type="checkbox"
                    disabled={Boolean(item.blocked)}
                    checked={!item.blocked && renameSelected.has(item.path)}
                    onChange={(event) => setRenameSelected((current) => {
                      const next = new Set(current);
                      if (event.target.checked) next.add(item.path); else next.delete(item.path);
                      return next;
                    })}
                  />
                  <span><strong>{item.old_filename}</strong><b>{item.new_filename}</b><small>{item.blocked || 'Ready to rename'}</small></span>
                </label>
              ))}
            </div>
            <footer className="smart-match-footer">
              {confirmRename ? (
                <button type="button" className="btn btn-primary" onClick={applyRename} disabled={applying || !renameSelected.size}>
                  Confirm rename selected files
                </button>
              ) : (
                <button type="button" className="btn btn-secondary" onClick={() => setConfirmRename(true)} disabled={!renameSelected.size}>
                  Review file rename ({renameSelected.size})
                </button>
              )}
              <span>Renaming is optional, file-only, and separate from metadata matching.</span>
            </footer>
          </>
        )}
      </section>
    </div>
  );
}
