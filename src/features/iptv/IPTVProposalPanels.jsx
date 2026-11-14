import Button from '../../components/ui/Button.jsx';
import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { formatCount } from '../../utils/appUtils.js';

const matchOutcomeLabels = { 'no-candidates': 'No TMDB candidates', 'candidate-rejected': 'Candidate rejected',
  skipped: 'Skipped', 'no-match': 'No credible match', locked: 'Manual lock', review: 'Review', recommended: 'Recommended' };

const canApplyClassification = item => !item.locked && item.category !== 'unclassified';

export function ClassificationPreviewPanel({ preview, busy, onApply, onCancel,
  eligible = canApplyClassification, onManualMatch }) {
  const [selected, setSelected] = useState(() => new Set());
  useEffect(() => setSelected(new Set((preview.proposals || []).filter(eligible).map(item => item.proposal_id))), [preview, eligible]);
  const toggle = (id) => setSelected(current => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });
  return <section className="iptv-proposal-panel">
    <header>
      <div><p className="screen-kicker">Classification preview</p><h3>{formatCount(preview.proposals?.length || 0)} provider sources</h3></div>
      {onCancel && <Button type="button" onClick={onCancel} aria-label="Close classification preview"><X size={18} /></Button>}
    </header>
    <div className="iptv-classification-proposals">{(preview.proposals || []).map(item => {
      const control = <label key={item.proposal_id} className={item.locked ? 'is-locked' : ''}>
        <input type="checkbox" checked={selected.has(item.proposal_id)} disabled={!eligible(item)} onChange={() => toggle(item.proposal_id)} />
        <span><strong dir="auto">{item.provider_title || item.source_key}</strong>
          <small>{item.previous_category} → {item.category} · {item.method} · {(Number(item.confidence || 0) * 100).toFixed(0)}%</small>
          {item.review_reason && <em>{item.review_reason}</em>}
          {item.apply_state === 'applied' && <em>Applied</em>}
        </span>
      </label>;
      if (!onManualMatch || item.category !== 'plays' || item.match_manual_lock ||
          (item.previous_category !== 'plays' && item.apply_state !== 'applied')) return control;
      return <div className="iptv-bulk-play-review" key={item.proposal_id}>{control}
        <Button type="button"  onClick={() => onManualMatch({
          category: 'plays', movie_key: `source:${item.source_key}`,
          provider_title: item.provider_title, provider_year: item.provider_year,
        })}>Manual TMDB search</Button>
      </div>;
    })}</div>
    <footer><span>Preview changes no current classification.</span>
      <Button variant="primary" type="button"  disabled={busy || !selected.size} onClick={() => onApply([...selected])}>
        Apply {formatCount(selected.size)} selected classifications
      </Button>
    </footer>
  </section>;
}

export function MatchProposalPanel({ job, busy, onApply, onCancel, onClose, onManualMatch, selectAllInitially = false, readOnly = false, title }) {
  const [selected, setSelected] = useState(() => new Set());
  useEffect(() => setSelected(new Set(selectAllInitially ? (job.proposals || []).filter(item => Number(item.candidate_tmdb_id || 0) > 0 && !item.match_manual_lock && item.category === 'film').map(item => item.proposal_id) : [])), [job.job_id, selectAllInitially]);
  const toggle = (id) => setSelected((current) => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const canSelect = item => Number(item.candidate_tmdb_id || 0) > 0 && !item.match_manual_lock && item.apply_state !== 'applied';
  const ready = job.state === 'ready';
  const applicable = (job.proposals || []).filter(item => selected.has(item.proposal_id) && canSelect(item));
  return <section className="iptv-proposal-panel"><header><div><p className="screen-kicker">{job.method === 'chatgpt-bulk' ? 'ChatGPT bulk' : job.method === 'ai' ? 'AI-assisted' : 'TMDB'} provider-local proposal job</p><h3>{title || (job.method === 'chatgpt-bulk' ? `${formatCount(job.proposals?.length || 0)} verified on this page` : `${formatCount(job.processed || job.proposals?.length || 0)} of ${formatCount(job.total || job.proposals?.length || 0)} reviewed · ${job.state}`)}</h3></div>{onClose && <Button type="button" onClick={onClose} aria-label="Close proposal review"><X size={18} /></Button>}</header>{job.error ? <div className="iptv-error"><span>{job.error}</span></div> : null}<div className="iptv-match-proposals">{(job.proposals || []).map((proposal) => {
    const candidate = proposal.evidence?.candidate || {};
    const selectable = ready && canSelect(proposal);
    return <article key={proposal.proposal_id} className={`is-${proposal.recommendation || 'review'}`}>{readOnly ? <strong>{proposal.apply_state === 'applied' ? 'Applied' : proposal.apply_state || proposal.outcome}</strong> :
      <label><input type="checkbox" checked={selected.has(proposal.proposal_id)} disabled={!selectable || busy} onChange={() => toggle(proposal.proposal_id)} /><span>{matchOutcomeLabels[proposal.recommendation] || 'Review'}</span></label>}<div className="iptv-proposal-comparison"><div><small>Provider source</small><strong dir="auto">{proposal.provider_title}</strong><span>{proposal.provider_year || 'Year unknown'} · {proposal.category || 'unclassified'}</span></div><div><small>Proposed TMDB identity</small><strong dir="auto">{candidate.title || (proposal.candidate_tmdb_id ? `TMDB ${proposal.candidate_tmdb_id}` : 'No credible match')}</strong><span>{candidate.year || 'Year unknown'}{proposal.candidate_tmdb_id ? ` · TMDB ${proposal.candidate_tmdb_id}` : ''}</span></div></div><p>Confidence {Number(proposal.confidence || 0).toFixed(1)}{proposal.evidence?.runner_up_gap !== null && proposal.evidence?.runner_up_gap !== undefined ? ` · runner-up gap ${Number(proposal.evidence.runner_up_gap).toFixed(1)}` : ''}</p>{proposal.evidence?.search_hints?.length > 0 && <p dir="auto">ChatGPT search hints: {proposal.evidence.search_hints.join(', ')}</p>}{proposal.evidence?.recovery && <small>{proposal.evidence.recovery.attempts ? 'Candidate recovery' : 'Recovery evidence check'}</small>}{(proposal.warnings || []).filter(warning => warning !== proposal.review_reason).map(warning => <em key={warning}>{warning}</em>)}{onManualMatch && (!readOnly || proposal.apply_state !== 'applied' || proposal.category === 'plays') && !['sports', 'music'].includes(proposal.category) && <Button type="button"  disabled={busy} onClick={() => onManualMatch({ category: proposal.apply_state === 'applied' ? proposal.category : proposal.previous_category || proposal.category, movie_key: `source:${proposal.source_key}`, provider_title: proposal.provider_title, provider_year: proposal.provider_year, name: proposal.provider_title })}>Manual search</Button>}{proposal.review_reason && <em>{proposal.review_reason}</em>}{proposal.apply_reason && <em>{proposal.apply_reason}</em>}{!readOnly && proposal.apply_state && proposal.apply_state !== 'pending' ? <strong className={`is-${proposal.apply_state}`}>{proposal.apply_state}: {proposal.apply_result}</strong> : null}</article>;
  })}</div>{!readOnly && <footer><Button type="button"  disabled={!ready || busy} onClick={() => setSelected(new Set((job.proposals || []).filter((item) => item.recommendation === 'recommended' && canSelect(item)).map((item) => item.proposal_id)))}>Select recommended</Button>{ready && onCancel ? <Button type="button"  disabled={busy} onClick={onCancel}>Cancel job</Button> : null}<Button variant="primary" type="button"  disabled={!ready || busy || !applicable.length} onClick={() => onApply(applicable.map(item => item.proposal_id))}>Apply {formatCount(applicable.length)} selected proposals</Button></footer>}</section>;
}
