import Button from '../../components/ui/Button.jsx';
import { Textarea } from '../../components/ui/FormField.jsx';
import AIControlResult from './AIControlResult.jsx';
import { AIProviderStatus, useAIProvider } from '../ai/AIProviderContext.jsx';
import useAIJob from '../ai/useAIJob.js';
import AIJobStatus from '../ai/AIJobStatus.jsx';
import AIActionReview from '../ai/AIActionReview.jsx';
import AIReadViews from '../ai/AIReadViews.jsx';
import { jobIsRunning, openAIReview } from '../ai/aiClient.js';
import { AlertTriangle, Bot, Check, CirclePlus, Loader2, Search, Sparkles, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchJson } from '../../api/client.js';
import { CATALOG_GENERATION_CHANGED_EVENT, fetchOwnershipChecks } from '../../api/library.js';
import { fetchCanonicalMovieDetails, markMovieDetailsCacheStale, movieDetailsCacheKey } from '../../api/movieDetails.js';
import { addMoviePayloadsToList, announceCurationChanged, clearUserListsCache, CURATION_GENERATION_CHANGED_EVENT, fetchCurationJson, fetchUserListsCached } from '../../api/curation.js';
import { previewSourceReview } from '../../api/sourceReview.js';
import DiscoverResultGrid from '../../components/DiscoverResultGrid.jsx';
import ExperimentalBadge from '../../components/ExperimentalBadge.jsx';
import ListEditorModal from '../../components/ListEditorModal.jsx';
import SelectionCheckbox from '../../components/SelectionCheckbox.jsx';
import SourceReviewDialog from '../../components/SourceReviewDialog.jsx';
import { DiscoverMovieCard } from '../../components/SharedMovieCards.jsx';
import useCardGridMetrics from '../../hooks/useCardGridMetrics.js';
import useMovieCollectionCache from '../../hooks/useMovieCollectionCache.js';
import { cx, formatCount, movieKey } from '../../utils/appUtils.js';
import {
  buildOwnershipMap, discoverMoviePayload, listsForDiscoverMovie, ownedMovieFor,
  removeOwnershipPaths, replaceOwnershipScope
} from '../../discoverUtils.js';
import { applySystemListState, movieIdentityKey, moviePayload } from '../../utils/libraryUtils.js';

const aiControlExamples = [
  'Find Tom Cruise movies I own',
  'Create a list of top rated sci-fi from 2010',
  'Download unowned Nolan movies in 1080p',
  'Delete files larger than 10 GB'
];

const aiControlPreviewStages = [
  'Understanding request with Ollama...',
  'Contacting TMDB...',
  'Checking your library...',
  'Searching trusted indexers...',
  'Preparing review...'
];

export default function AIControlWorkspace({
  followed = [],
  notify,
  onPlay,
  onStream,
  streamingAvailable,
  streamingLabel,
  onFindTorrent,
  onOpenTrailer,
  onFollow,
  onEditPoster,
  onOpenFileDetails,
  onOpenDiscoverPerson = () => {},
  onOpenDiscoverCollection = () => {}
}) {
  const ai = useAIProvider();
  const gpt = useAIJob('F2');
  const [prompt, setPrompt] = useState('');
  const [aiControlPlan, setAiControlPlan] = useState(null);
  const [aiControlReceipt, setAiControlReceipt] = useState(null);
  const [aiControlBusy, setAiControlBusy] = useState(false);
  const [aiControlError, setAiControlError] = useState('');
  const [aiControlLoadingStep, setAiControlLoadingStep] = useState(null);
  const aiControlStageTimersRef = useRef([]);
  const submitting = aiControlBusy || ai.provider === 'chatgpt' && (gpt.busy || jobIsRunning(gpt.job));

  function clearAiControlStageTimers() {
    aiControlStageTimersRef.current.forEach((timer) => window.clearTimeout(timer));
    aiControlStageTimersRef.current = [];
  }

  function startAiControlPreviewProgress() {
    clearAiControlStageTimers();
    setAiControlLoadingStep(0);
    aiControlStageTimersRef.current = aiControlPreviewStages.slice(1).map((_, index) => (
      window.setTimeout(() => setAiControlLoadingStep(index + 1), 1800 + index * 2600)
    ));
  }

  useEffect(() => () => clearAiControlStageTimers(), []);
  useEffect(() => {
    function receive(event) {
      const draft = event?.detail?.prompt || sessionStorage.getItem('cp-ai-control-draft');
      if (draft) { setPrompt(draft); sessionStorage.removeItem('cp-ai-control-draft'); }
    }
    receive(); window.addEventListener('cp-ai-control-request', receive);
    return () => window.removeEventListener('cp-ai-control-request', receive);
  }, []);

  async function previewAiControlCommand(event) {
    event.preventDefault();
    const command = prompt.trim();
    if (!command) {
      setAiControlError('Enter a command first.');
      return;
    }
    if (ai.provider === 'chatgpt') {
      if (gpt.busy || jobIsRunning(gpt.job)) { setAiControlError('Wait for this request or cancel its future work before sending another.'); return; }
      setAiControlError(''); setAiControlPlan(null); setAiControlReceipt(null);
      clearAiControlStageTimers(); setAiControlLoadingStep(null);
      try { await gpt.start('/api/ai/control/turns', { prompt: command }); }
      catch { /* The job status displays the provider failure. */ }
      return;
    }
    setAiControlBusy(true);
    setAiControlError('');
    setAiControlReceipt(null);
    startAiControlPreviewProgress();
    try {
      const data = await fetchJson('/api/ai-control/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: command })
      });
      setAiControlPlan(data);
      if (data.state === 'valid_plan') {
        notify(data.message || 'AI Control preview ready', 'success');
      } else {
        notify(data.message || 'AI Control needs clarification', 'neutral');
      }
    } catch (error) {
      setAiControlError(error.message);
      notify(`AI Control preview failed: ${error.message}`, 'error');
    } finally {
      clearAiControlStageTimers();
      setAiControlLoadingStep(null);
      setAiControlBusy(false);
    }
  }

  async function executeAiControlPlan({ confirmationPhrase = '', selectedKeys = [], reviewedDownloads = [] } = {}) {
    if (!aiControlPlan?.plan_id) return;
    setAiControlBusy(true);
    setAiControlError('');
    setAiControlLoadingStep(null);
    try {
      const data = await fetchJson('/api/ai-control/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plan_id: aiControlPlan.plan_id,
          confirmation_phrase: confirmationPhrase,
          selected_keys: selectedKeys,
          reviewed_downloads: reviewedDownloads
        })
      });
      setAiControlPlan(null);
      setAiControlReceipt(data);
      if (data.action === 'create_list') {
        clearUserListsCache();
        announceCurationChanged();
      }
      notify(data.message || 'AI Control action executed', 'success');
    } catch (error) {
      setAiControlError(error.message);
      notify(`AI Control execute failed: ${error.message}`, 'error');
    } finally {
      setAiControlBusy(false);
    }
  }

  function useExample(example) {
    setPrompt(example);
    setAiControlError('');
  }

  return (
    <section className="ai-control-workspace">
      <header className="library-header ai-control-header">
        <div>
          <p className="screen-kicker">AI command console</p>
          <h2>AI Control <ExperimentalBadge /></h2>
          <p>Turn plain-language movie commands into reviewable CP actions for finding, lists, downloads, and cleanup.</p>
        </div>
      </header>

      <form className="ai-control-command" onSubmit={previewAiControlCommand}>
        <label className="ai-control-prompt">
          <span>Command</span>
          <Textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Tell CP what to find, list, download, or delete..."
            rows={4}
          />
        </label>
        <div className="ai-control-command-actions">
          <Button variant="ai" type="submit"  disabled={!ai.config || submitting || ai.provider === 'chatgpt' && !ai.feature('F2')?.ready}>
            {submitting ? <Loader2 size={15} className="spin" /> : <Sparkles size={15} />} Preview command
          </Button>
          <Button type="button"  onClick={() => { setPrompt(''); setAiControlPlan(null); setAiControlReceipt(null); setAiControlError(''); }} disabled={aiControlBusy}>
            <X size={15} /> Clear
          </Button>
        </div>
      </form>

      <div className="ai-control-guide">
        <div className="ai-control-example-row">
          {aiControlExamples.map((example) => (
            <Button size="compact" type="button"  key={example} onClick={() => useExample(example)}>
              {example}
            </Button>
          ))}
        </div>
        <strong>No action runs automatically. Every result is reviewed before you confirm it.</strong>
      </div>

      {aiControlBusy && aiControlLoadingStep !== null && (
        <div className="ai-control-progress" role="status" aria-live="polite">
          <Loader2 size={16} className="spin" />
          <div>
            <strong>{aiControlPreviewStages[aiControlLoadingStep]}</strong>
            <small>Large actor/director requests can take a while because CP reviews TMDB, your library, and trusted indexers before showing a plan.</small>
          </div>
        </div>
      )}

      {aiControlError && (
        <div className="library-status library-status-error">
          <AlertTriangle size={16} />
          <span>{aiControlError}</span>
        </div>
      )}

      <AIProviderStatus feature="F2" />
      <AIJobStatus operation={gpt} title="AI Control conversation" />
      {gpt.job?.output?.message && <p className="library-status">{gpt.job.output.message}</p>}
      <AIReadViews views={gpt.job?.output?.views} followed={followed} notify={notify} onPlay={onPlay} onStream={onStream}
        streamingAvailable={streamingAvailable} streamingLabel={streamingLabel} onFindTorrent={onFindTorrent}
        onOpenTrailer={onOpenTrailer} onFollow={onFollow} onEditPoster={onEditPoster} onOpenFileDetails={onOpenFileDetails}
        onOpenDiscoverPerson={onOpenDiscoverPerson} onOpenDiscoverCollection={onOpenDiscoverCollection} />
      {(gpt.job?.output?.views || []).filter(view => view.kind === 'action-plan').map(view => (
        <AIActionReview key={view.action.action_id} view={view} onChanged={gpt.reload}
          disabled={gpt.job.state === 'cancelled'} followed={followed} notify={notify} onPlay={onPlay} onStream={onStream}
          streamingAvailable={streamingAvailable} streamingLabel={streamingLabel} onFindTorrent={onFindTorrent}
          onOpenTrailer={onOpenTrailer} onFollow={onFollow} onEditPoster={onEditPoster} onOpenFileDetails={onOpenFileDetails}
          onOpenDiscoverPerson={onOpenDiscoverPerson} onOpenDiscoverCollection={onOpenDiscoverCollection} />
      ))}
      {(gpt.job?.output?.views || []).filter(view => view.kind === 'open-review').map((view, index) => (
        <Button type="button"  key={index} onClick={() => openAIReview(view.data.surface, view.data.target_ref)}>Open {view.data.surface.replaceAll('-', ' ')} review</Button>
      ))}
      {(aiControlPlan || aiControlReceipt || !gpt.job) && <AIControlResult
        aiControlPlan={aiControlPlan}
        aiControlReceipt={aiControlReceipt}
        busy={aiControlBusy}
        onExecute={executeAiControlPlan}
        followed={followed}
        notify={notify}
        onPlay={onPlay}
        onStream={onStream}
        streamingAvailable={streamingAvailable}
        streamingLabel={streamingLabel}
        onFindTorrent={onFindTorrent}
        onOpenTrailer={onOpenTrailer}
        onFollow={onFollow}
        onEditPoster={onEditPoster}
        onOpenFileDetails={onOpenFileDetails}
        onOpenDiscoverPerson={onOpenDiscoverPerson}
        onOpenDiscoverCollection={onOpenDiscoverCollection}
      />}
    </section>
  );
}
