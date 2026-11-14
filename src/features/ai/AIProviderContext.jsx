import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { fetchJson } from '../../api/client.js';
import { aiJson } from './aiClient.js';

const Context = createContext(null);

export function AIProviderProvider({ children }) {
  const [config, setConfig] = useState(null);
  const [error, setError] = useState('');
  const refresh = useCallback(async () => {
    try {
      const next = await fetchJson('/api/ai/config');
      setConfig(current => current && current.generation > next.generation ? current : next); setError(''); return next;
    } catch (failure) { setError(failure.message); throw failure; }
  }, []);
  useEffect(() => { refresh().catch(() => {}); }, [refresh]);
  const update = useCallback(async fields => {
    const next = await aiJson('/api/ai/config', { ...fields, expected_generation: config?.generation }, 'PUT');
    setConfig(next); setError(''); return next;
  }, [config?.generation]);
  return <Context.Provider value={{ config, error, refresh, update,
    provider: config?.provider, feature: id => config?.features?.find(row => row.id === id) }}>{children}</Context.Provider>;
}

export function useAIProvider() {
  const context = useContext(Context);
  if (!context) throw new Error('AI provider context is unavailable');
  return context;
}

export function AIProviderStatus({ feature }) {
  const ai = useAIProvider();
  const state = ai.feature(feature);
  return <p className="discover-inline-status ai-provider-status" role="status">
    {!ai.config ? ai.error || 'Loading AI settings…' : <>
      <strong>{ai.provider === 'chatgpt' ? 'ChatGPT' : 'Ollama'}</strong>
      {ai.provider === 'chatgpt' && ai.config.chatgpt.model ? ` · ${ai.config.chatgpt.model}` : ''}
      {state && !state.ready ? ` · ${state.reason?.replaceAll('_', ' ')}` : ''}
      {' · '}<a href="/settings">AI Settings</a>
    </>}
  </p>;
}
