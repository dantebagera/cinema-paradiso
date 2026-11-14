import Button from '../../components/ui/Button.jsx';
import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, RefreshCcw } from 'lucide-react';
import { fetchJson } from '../../api/client.js';
import { announceCurationChanged, clearUserListsCache } from '../../api/curation.js';
import AIControlResult from '../ai-control/AIControlResult.jsx';
import { ClassificationPreviewPanel, MatchProposalPanel } from '../iptv/IPTVProposalPanels.jsx';
import IPTVPlayer from '../iptv/IPTVPlayer.jsx';
import { iptvApi } from '../../api/iptv.js';
import DomainActionRows from './DomainActionRows.jsx';
import useAIJob from './useAIJob.js';
import AIJobStatus from './AIJobStatus.jsx';
import { aiJson, openAIReview, requestKey } from './aiClient.js';

export default function AIActionReview({ view, onChanged, disabled = false, ...movieProps }) {
  const [action, setAction] = useState(view.action);
  const [plan, setPlan] = useState(view.plan);
  const [receipt, setReceipt] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [playback, setPlayback] = useState(null);
  const confirmation = useRef(null);
  const preparation = useAIJob('F5', 'deferred-' + view.action.action_id);
  const preparationId = action?.payload?.preparation_job_id;
  useEffect(() => {
    if (preparationId && preparation.job?.id !== preparationId) preparation.attach(preparationId).catch(failure => setError(failure.message));
  }, [preparationId]);

  function accept(next) {
    setAction(next.action || next);
    if (Object.hasOwn(next, 'plan')) setPlan(next.plan);
    const current = next.action || next;
    if (current.state !== 'prepared') setReceipt({ ...(current.outcome || {}), state: current.state,
      summary: current.outcome?.summary || (current.state === 'completed' ? 'Action completed' : 'Recorded action outcome'),
      message: current.outcome?.message || current.outcome?.code?.replaceAll('_', ' '),
      hideCount: current.outcome?.total_matches == null });
    if (current.state === 'prepared' && Object.hasOwn(next, 'plan') && !next.plan) {
      setError('This review expired or CP restarted. Ask again to prepare a fresh review.');
    }
  }
  useEffect(() => {
    let cancelled = false;
    setAction(view.action); setPlan(view.plan); setReceipt(null); setError(''); setHidden(false);
    fetchJson(`/api/ai/control/plans/${view.action.action_id}`).then(next => { if (!cancelled) accept(next); })
      .catch(failure => { if (!cancelled) setError(failure.message); });
    return () => { cancelled = true; };
  }, [view.action.action_id]);

  async function refresh() {
    setBusy(true); setError('');
    try { accept(await aiJson(`/api/ai/control/plans/${action.action_id}/review`, {})); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  async function confirm({ selectedKeys, confirmationPhrase = '' }) {
    if (busy || disabled) return;
    const fingerprint = JSON.stringify([action.action_id, action.revision, [...selectedKeys].sort(), confirmationPhrase]);
    if (confirmation.current?.fingerprint !== fingerprint) confirmation.current = { fingerprint, key: requestKey() };
    setBusy(true); setError('');
    try {
      const next = await aiJson(`/api/ai/control/plans/${action.action_id}/confirm`, {
        revision: action.revision, selected_keys: selectedKeys, confirmation_phrase: confirmationPhrase,
        request_key: confirmation.current.key
      });
      accept(next);
      if (next.transient_ui?.kind === 'iptv-playback') setPlayback({ ...next.transient_ui.data, ...next.transient_ui.media });
      clearUserListsCache(); announceCurationChanged();
      await onChanged?.(next);
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  async function cancel() {
    setBusy(true); setError('');
    try { accept(await aiJson(`/api/ai/control/plans/${action.action_id}/cancel`, { revision: action.revision })); await onChanged?.(); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  const operation = plan?.operation;
  const deferred = operation?.kind === 'iptv_deferred';
  const selectProposals = ids => confirm({ selectedKeys: plan.items.filter(row => ids.includes(row.proposal_id)).map(row => row.selection_key) });
  const nonMovie = ['tv', 'iptv', 'shared'].includes(plan?.domain);

  if (hidden) return <Button type="button"  onClick={() => setHidden(false)}>Reopen review</Button>;
  return <div className="ai-action-review">
    {error && <p className="library-status library-status-error" role="alert"><AlertTriangle size={16} /> {error}</p>}
    {!receipt && <div className="settings-action-grid">
      <Button type="button"  disabled={busy || disabled} onClick={refresh}><RefreshCcw size={15} /> {deferred ? preparation.job?.state === 'completed' ? 'Load prepared review' : 'Prepare next step' : 'Refresh review'}</Button>
      <Button type="button"  disabled={busy || disabled} onClick={cancel}>Cancel this action</Button>
    </div>}
    {deferred && !receipt && <>
      <p className="settings-empty-note">Confirm the preceding classification first. Prepare next step starts a new saved AI run using only its confirmed targets. Matching still requires a separate Apply.</p>
      <AIJobStatus operation={preparation} title="Next IPTV preparation" />
    </>}
    {receipt ? <AIControlResult aiControlReceipt={receipt} />
      : operation?.kind === 'iptv_apply' && operation.feature === 'F4'
        ? <ClassificationPreviewPanel preview={{ ...operation.review, proposals: plan.items }} busy={busy || disabled}
            onApply={selectProposals} onCancel={() => setHidden(true)} />
        : operation?.kind === 'iptv_apply' && operation.feature === 'F5'
          ? <MatchProposalPanel job={{ ...operation.review, proposals: plan.items }} busy={busy || disabled}
              selectAllInitially onApply={selectProposals} onCancel={cancel} onClose={() => setHidden(true)}
              onManualMatch={() => openAIReview('iptv')} />
          : <AIControlResult {...movieProps} aiControlPlan={plan} busy={busy || disabled} onExecute={confirm} readOnly={deferred}
              cardsRenderer={nonMovie ? DomainActionRows : undefined} />}
    {playback && <IPTVPlayer playback={playback} onClose={async () => {
      await iptvApi.stopPlayback(playback.provider_id, playback.token); setPlayback(null);
    }} />}
  </div>;
}
