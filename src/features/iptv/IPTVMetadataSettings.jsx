import { Select, Input } from '../../components/ui/FormField.jsx';
import Button from '../../components/ui/Button.jsx';
import { useEffect, useState } from 'react';
import { KeyRound, Loader2, WandSparkles } from 'lucide-react';
import { iptvApi } from '../../api/iptv.js';
import './iptv.css';

export default function IPTVMetadataSettings({ notify, active }) {
  const [metadataSettings, setMetadataSettings] = useState(null);
  const [metadataCredential, setMetadataCredential] = useState('');
  const [metadataCredentialType, setMetadataCredentialType] = useState('bearer');
  const [metadataEditing, setMetadataEditing] = useState(false);
  const [metadataBusy, setMetadataBusy] = useState(false);
  const [ollamaEnabled, setOllamaEnabled] = useState(false);
  const [ollamaUrl, setOllamaUrl] = useState('http://127.0.0.1:11434');
  const [ollamaModel, setOllamaModel] = useState('');
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    if (!active) return undefined;
    const controller = new AbortController();
    iptvApi.metadataSettings({ signal: controller.signal }).then(saved => {
      if (controller.signal.aborted) return;
      setMetadataSettings(saved);
      setMetadataCredentialType(saved.credential_type || 'bearer');
      setOllamaEnabled(Boolean(saved.ollama_enabled));
      setOllamaUrl(saved.ollama_url || 'http://127.0.0.1:11434');
      setOllamaModel(saved.ollama_model || '');
      setError('');
    }).catch(failure => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [active, refresh]);

  async function saveMetadataCredential() {
    if (!metadataCredential.trim()) return;
    setMetadataBusy(true);
    setError('');
    try {
      const saved = await iptvApi.saveMetadataSettings({
        credential: metadataCredential,
        credential_type: metadataCredentialType
      });
      setMetadataCredential('');
      setMetadataSettings(saved);
      setMetadataEditing(false);
      const validation = await iptvApi.testMetadata();
      notify?.(validation.valid ? 'IPTV TMDB credential validated' : 'IPTV TMDB validation failed');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setMetadataBusy(false);
    }
  }

  async function testSavedMetadataCredential() {
    setMetadataBusy(true);
    setError('');
    try {
      const validation = await iptvApi.testMetadata();
      notify?.(validation.valid ? 'Saved IPTV TMDB credential is valid' : 'Saved IPTV TMDB credential is invalid');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setMetadataBusy(false);
    }
  }

  async function saveOllamaConfiguration() {
    setMetadataBusy(true);
    setError('');
    try {
      const saved = await iptvApi.saveMetadataSettings({
        ollama: { enabled: ollamaEnabled, url: ollamaUrl.trim(), model: ollamaModel.trim() }
      });
      setMetadataSettings(saved);
      setOllamaEnabled(Boolean(saved.ollama_enabled));
      setOllamaUrl(saved.ollama_url || 'http://127.0.0.1:11434');
      setOllamaModel(saved.ollama_model || '');
      notify?.(saved.ollama_enabled ? 'IPTV Ollama assistance configured' : 'IPTV Ollama assistance disabled');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setMetadataBusy(false);
    }
  }

  const settings = metadataSettings;
  const credential = metadataCredential;
  const credentialType = metadataCredentialType;
  const editing = metadataEditing;
  const busy = metadataBusy;
  const onReplace = () => {
    setMetadataCredential('');
    setMetadataCredentialType(settings.credential_type || 'bearer');
    setMetadataEditing(true);
  };
  const onCancelReplace = () => { setMetadataCredential(''); setMetadataEditing(false); };
  return <section className="iptv-workspace iptv-aux-workspace iptv-metadata-settings" aria-label="IPTV movie metadata settings">
    <h3>Movie metadata</h3>
    {error && <p role="alert">{error}</p>}
    {!settings && (error ? <Button type="button" 
      onClick={() => setRefresh(value => value + 1)}>Retry IPTV settings</Button> : <p>Loading IPTV movie metadata settings…</p>)}
    {settings && <>
      <div className="iptv-metadata-panel">
        <div className="iptv-metadata-copy"><span className={settings.tmdb_configured ? 'is-ready' : ''}><KeyRound size={18} /> {settings.tmdb_configured ? 'IPTV TMDB stored on this device' : 'IPTV TMDB not configured'}</span><p>These settings are shared across IPTV providers. They use separate saved values from Movie and TV. Automatic enrichment has its own controls in Maintenance.</p></div>
        {editing || !settings.tmdb_configured ? <><label><span>Credential type</span><Select value={credentialType} onChange={(event) => setMetadataCredentialType(event.target.value)}><option value="bearer">Read access token</option><option value="api_key">API key</option></Select></label><label className="iptv-metadata-secret"><span>IPTV TMDB credential</span><Input type="password" autoComplete="new-password" value={credential} onChange={(event) => setMetadataCredential(event.target.value)} placeholder={settings.tmdb_configured ? 'Enter replacement credential' : 'Enter credential'} /></label><div className="iptv-metadata-actions"><Button variant="primary" type="button"  disabled={busy || !credential.trim()} onClick={saveMetadataCredential}>{busy ? <Loader2 className="spin" size={15} /> : <KeyRound size={15} />} Save &amp; validate</Button>{settings.tmdb_configured ? <Button type="button"  disabled={busy} onClick={onCancelReplace}>Cancel</Button> : null}</div></> : <div className="iptv-metadata-actions iptv-metadata-saved-actions"><Button type="button"  disabled={busy} onClick={testSavedMetadataCredential}>{busy ? <Loader2 className="spin" size={15} /> : <KeyRound size={15} />} Test saved credential</Button><Button type="button"  disabled={busy} onClick={onReplace}>Replace credential</Button></div>}
      </div>
      <details className="iptv-rebuild-controls"><summary>Advanced AI</summary><div className="iptv-metadata-panel iptv-ollama-panel">
        <div className="iptv-metadata-copy"><span className={settings.ollama_enabled ? 'is-ready' : ''}><WandSparkles size={18} /> {settings.ollama_enabled ? 'IPTV Ollama assistance configured' : 'IPTV Ollama assistance disabled'}</span><p>Ollama may classify unclear sources or rank real IPTV TMDB candidates. It cannot invent or directly apply an identity.</p></div>
        <label className="iptv-claim-check"><input type="checkbox" checked={ollamaEnabled} onChange={(event) => setOllamaEnabled(event.target.checked)} /> Enable IPTV Ollama</label>
        <label><span>Ollama URL</span><Input value={ollamaUrl} onChange={(event) => setOllamaUrl(event.target.value)} placeholder="http://127.0.0.1:11434" /></label>
        <label><span>Model</span><Input value={ollamaModel} onChange={(event) => setOllamaModel(event.target.value)} placeholder="Configured local model" /></label>
        <Button type="button"  disabled={busy || (ollamaEnabled && !ollamaModel.trim())} onClick={saveOllamaConfiguration}>Save Ollama settings</Button>
      </div></details>
    </>}
  </section>;
}
