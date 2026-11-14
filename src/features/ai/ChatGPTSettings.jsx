import Button from '../../components/ui/Button.jsx';
import { Select, Input } from '../../components/ui/FormField.jsx';
import { Bot, ExternalLink, Loader2, LogOut, RefreshCcw, Save, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { fetchJson } from '../../api/client.js';
import { useAIProvider } from './AIProviderContext.jsx';
import { aiJson, exactCount } from './aiClient.js';

export default function ChatGPTSettings({ Card, notify }) {
  const ai = useAIProvider();
  const [draft, setDraft] = useState({ count: '15', model: '', movieHints: false, iptvTitles: false });
  const [models, setModels] = useState([]);
  const [attempt, setAttempt] = useState(null);
  const [busy, setBusy] = useState('');
  const [status, setStatus] = useState(null);
  const gpt = ai.config?.chatgpt;
  const account = ai.config?.accounts?.find(row => row.account_id === gpt?.active_account_id);

  useEffect(() => {
    if (gpt) setDraft({ count: gpt.recommendation_count, model: gpt.model,
      movieHints: gpt.allow_movie_identity_hints, iptvTitles: gpt.allow_iptv_titles });
  }, [gpt?.recommendation_count, gpt?.model, gpt?.allow_movie_identity_hints, gpt?.allow_iptv_titles]);
  useEffect(() => setModels([]), [gpt?.active_account_id]);

  useEffect(() => {
    if (!attempt?.attempt_id || !['pending', 'exchanging'].includes(attempt.state)) return undefined;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      if (attempt.expires_at && Date.now() / 1000 >= attempt.expires_at) {
        setAttempt(current => ({ ...current, state: 'expired' }));
        setStatus({ tone: 'error', message: 'Sign-in expired. Start a fresh attempt.' });
        return;
      }
      try {
        const next = await fetchJson(`/api/ai/auth/attempts/${attempt.attempt_id}`);
        if (cancelled) return;
        setAttempt({ ...next, attempt_id: attempt.attempt_id });
        if (next.state === 'complete') {
          await ai.refresh();
          setStatus({ tone: next.plan_enabled ? 'success' : 'error', message: next.plan_enabled
            ? 'Signed in. Select the account, load its models, then choose a model.'
            : 'Signed in, but this account has not granted ChatGPT plan use.' });
        } else if (!['pending', 'exchanging'].includes(next.state)) {
          setStatus({ tone: 'error', message: next.error?.code?.replaceAll('_', ' ') || `Sign-in ${next.state}. You can try again.` });
        }
      } catch (failure) {
        if (!cancelled) {
          setStatus({ tone: 'error', message: failure.message });
          setAttempt(current => ({ ...current, ...(failure.data?.state ? failure.data : {}) }));
        }
      }
    }, 800);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [attempt, ai.refresh]);

  async function perform(name, action) {
    setBusy(name); setStatus(null);
    try { await action(); }
    catch (failure) { setStatus({ tone: 'error', message: failure.message }); }
    finally { setBusy(''); }
  }
  function connect(returning = null) {
    return perform('connect', async () => {
      const registration = returning || (attempt?.state === 'error' ? attempt.account_id : null);
      const started = await aiJson('/api/ai/auth/start', registration ? { account_id: registration } : {});
      setAttempt({ ...started, state: 'pending' });
      setStatus({ tone: 'neutral', message: 'Continue in your system browser. If nothing appears here, check the browser window behind CP.' });
    });
  }
  async function loadModels() {
    await perform('models', async () => {
      const result = await fetchJson('/api/ai/models');
      setModels(result.models || []);
      if (!result.models?.length) setStatus({ tone: 'error', message: 'This account currently exposes no available models.' });
    });
  }
  const pending = ['pending', 'exchanging'].includes(attempt?.state);
  const count = exactCount(draft.count);

  return <Card id="settings-chatgpt" icon={Bot} title="AI Provider & ChatGPT" accent="violet" status={status || (ai.error ? { tone: 'error', message: ai.error } : null)}
    fields={<>
      <label className="settings-field"><span>AI provider</span>
        <Select aria-label="AI provider" value={ai.provider || 'ollama'} disabled={!ai.config || Boolean(busy)}
          onChange={event => perform('provider', () => ai.update({ provider: event.target.value }))}>
          <option value="ollama">Ollama</option><option value="chatgpt">ChatGPT</option>
        </Select>
      </label>
      {ai.error && <Button type="button"  disabled={Boolean(busy)}
        onClick={() => perform('reload', ai.refresh)}><RefreshCcw size={15} /> Reload AI settings</Button>}
      <p className="settings-empty-note">Provider failures stay visible. Switch providers here when you choose; running requests keep their original provider and model.</p>
      {ai.provider === 'chatgpt' && <>
        <label className="settings-field"><span>ChatGPT account</span>
          <Select aria-label="ChatGPT account" value={gpt?.active_account_id || ''} disabled={Boolean(busy) || pending}
            onChange={event => perform('account', () => ai.update({ active_account_id: event.target.value || null, chatgpt_model: '' }))}>
            <option value="">Select an account</option>
            {(ai.config.accounts || []).map(row => <option value={row.account_id} key={row.account_id}>
              {row.label || row.email || row.account_id} · {row.connected ? row.plan_enabled ? 'connected' : 'plan permission required' : 'disconnected'}
            </option>)}
          </Select>
        </label>
        <div className="settings-action-grid">
          <Button type="button"  disabled={Boolean(busy) || pending} onClick={() => connect()}><ExternalLink size={15} /> Continue with ChatGPT</Button>
          {account && !account.connected && <Button type="button"  disabled={Boolean(busy) || pending} onClick={() => connect(account.account_id)}>Reconnect account</Button>}
          {pending && <Button type="button"  onClick={() => perform('cancel', async () => {
            const next = await aiJson(`/api/ai/auth/attempts/${attempt.attempt_id}`, {}, 'DELETE');
            setAttempt({ ...next, attempt_id: attempt.attempt_id });
          })}><X size={15} /> Cancel sign-in</Button>}
        </div>
        {pending && <p className="settings-empty-note" role="status"><Loader2 size={15} className="spin" /> Waiting for your browser sign-in and consent…</p>}
        <label className="settings-field"><span>Account model</span>
          <Select aria-label="ChatGPT model" value={draft.model} disabled={Boolean(busy) || !models.length}
            onChange={event => setDraft(current => ({ ...current, model: event.target.value }))}>
            <option value="">Choose from this account's models</option>
            {draft.model && !models.some(row => row.slug === draft.model) && <option value={draft.model}>{draft.model} · saved</option>}
            {models.map(row => <option key={row.slug} value={row.slug}>{row.display_name || row.slug}</option>)}
          </Select>
        </label>
        <Button type="button"  disabled={Boolean(busy) || !account?.connected} onClick={loadModels}>
          {busy === 'models' ? <Loader2 size={15} className="spin" /> : <RefreshCcw size={15} />} Load available models
        </Button>
        <label className="settings-field"><span>Default recommendation count</span>
          <Input aria-label="ChatGPT default recommendation count" type="text" inputMode="numeric" pattern="[0-9]+"
            value={draft.count} onChange={event => setDraft(current => ({ ...current, count: event.target.value }))} />
          <small>Any positive whole number. Large requests continue in batches; this is a starting target.</small>
        </label>
        {!count && <p className="settings-empty-note" role="alert">Enter a positive whole number.</p>}
        <label className="settings-checkbox-field"><input type="checkbox" checked={draft.movieHints}
          onChange={event => setDraft(current => ({ ...current, movieHints: event.target.checked }))} />
          <span>Allow Movie Smart Match to send local basenames and title/year hints to ChatGPT. Full paths stay on this PC.</span>
        </label>
        <label className="settings-checkbox-field"><input type="checkbox" checked={draft.iptvTitles}
          onChange={event => setDraft(current => ({ ...current, iptvTitles: event.target.checked }))} />
          <span>Allow selected IPTV playlist names, title samples and real metadata candidates to be sent to ChatGPT. Stream addresses and credentials stay on this PC.</span>
        </label>
        <div className="ai-feature-status" aria-label="AI feature availability">
          {(ai.config.features || []).map(row => <p key={row.id}><strong>{row.name}</strong><span>{row.ready ? 'Ready' : row.reason === 'provider_required' ? 'Choose an IPTV provider' : row.reason?.replaceAll('_', ' ')}</span></p>)}
        </div>
      </>}
    </>}
    actions={ai.provider === 'chatgpt' ? <>
      <Button variant="primary" type="button"  disabled={Boolean(busy) || !count} onClick={() => perform('save', async () => {
        await ai.update({ chatgpt_model: draft.model, recommendation_count: count,
          allow_movie_identity_hints: draft.movieHints, allow_iptv_titles: draft.iptvTitles });
        setStatus({ tone: 'success', message: 'ChatGPT settings saved.' });
      })}>{busy === 'save' ? <Loader2 size={15} className="spin" /> : <Save size={15} />} Save ChatGPT settings</Button>
      <Button type="button"  disabled={Boolean(busy) || !account?.connected || !gpt?.model || draft.model !== gpt.model}
        onClick={() => perform('test', async () => {
          const result = await aiJson('/api/ai/test', {});
          setStatus({ tone: 'success', message: 'ChatGPT connection test completed.', detail: result.response_id });
          notify?.('ChatGPT connection test completed', 'success');
        })}>{busy === 'test' ? <Loader2 size={15} className="spin" /> : <Bot size={15} />} Test ChatGPT connection</Button>
      <Button type="button"  disabled={Boolean(busy) || !account?.connected} onClick={() => perform('disconnect', async () => {
        const result = await aiJson(`/api/ai/accounts/${account.account_id}/session`, {}, 'DELETE');
        await ai.refresh();
        setStatus({ tone: 'neutral', message: result.remote_revocation_confirmed ? 'Account disconnected; its session was revoked.'
          : 'Account disconnected locally. Remote revocation could not be confirmed.' });
      })}><LogOut size={15} /> Disconnect selected account</Button>
    </> : <p className="settings-empty-note">Ollama keeps its existing controls below.</p>} />;
}
