import { useEffect, useRef, useState } from 'react';
import { fetchJson } from '../../api/client.js';
const post=(url,data,signal)=>fetchJson(url,{method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
const sizeLabel=n=>n ? `${(n/1024/1024/1024).toFixed(2)} GB` : 'Size unknown';
export default function TVAcquisitionReview({ target, onClose, notify }) {
  const dialog=useRef(null), batchKey=useRef(null), alive=useRef(true);
  const [review,setReview]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[attempt,setAttempt]=useState(0),[selected,setSelected]=useState([]),[blocked,setBlocked]=useState(false),[extras,setExtras]=useState(false),[outcome,setOutcome]=useState(null);
  const [profiles,setProfiles]=useState([]),[profile,setProfile]=useState(target.profile_id||'safe-hd');
  useEffect(()=>{const controller=new AbortController();fetchJson('/api/acquisition/profiles',{signal:controller.signal}).then(r=>setProfiles(r.profiles)).catch(()=>{});return ()=>controller.abort();},[]);
  useEffect(()=>{const previous=document.activeElement;dialog.current?.showModal();alive.current=true;return ()=>{alive.current=false;previous?.focus();};},[]);
  useEffect(()=>{const controller=new AbortController();setReview(null);setError('');setOutcome(null);batchKey.current=null;post('/api/tv/search',{...target,profile_id:profile},controller.signal).then(r=>{if(!controller.signal.aborted){setReview(r);setSelected(r.recommended||[]);}}).catch(e=>{if(e.name!=='AbortError')setError(e.message);});return ()=>controller.abort();},[target,attempt,profile]);
  const chosen=review?.decisions.filter(r=>selected.includes(r.decision_token))||[];
  const covered=new Set(chosen.flatMap(r=>r.covered_episodes));
  const missing=review?.episodes?.filter(e=>!covered.has(e.id))||[];
  const overlap=chosen.reduce((n,r)=>n+r.covered_episodes.length,0)!==covered.size;
  function choose(token,checked){if(outcome)return;batchKey.current=null;setSelected(old=>checked?[...old,token]:old.filter(t=>t!==token));}
  async function confirmIdentity(row){setBusy(true);setError('');try{const next=await post('/api/tv/releases/prepare',{decision_token:row.decision_token,confirm_identity:true});if(alive.current){setReview(old=>({...old,decisions:old.decisions.map(d=>d.decision_token===row.decision_token?next:d)}));if(next.selectable)setSelected(old=>[...old.filter(t=>t!==row.decision_token),next.decision_token]);}}catch(e){if(alive.current)setError(e.message);}finally{if(alive.current)setBusy(false);}}
  async function download(){setBusy(true);setError('');batchKey.current ||= crypto.randomUUID();try{const result=await post('/api/tv/acquisitions/batch',{decision_tokens:selected,request_key:batchKey.current,allow_partial:missing.length>0,allow_extras:extras});if(alive.current){setOutcome(result);if(result.complete){notify('Selected releases queued for episode-file verification','success');}else setError('Some releases could not be queued. Retry submits only unfinished releases.');}}catch(e){if(alive.current)setError(e.message);}finally{if(alive.current)setBusy(false);}}
  return <dialog ref={dialog} className="tv-version-dialog tv-release-dialog" aria-label="TV release review" onCancel={e=>{if(busy)e.preventDefault();else onClose();}}>
    <header className="tv-release-heading"><div><h2>Choose TV downloads</h2><p>Season {target.season}{target.episode?` · Episode ${target.episode}`:''}</p></div><button onClick={onClose} disabled={busy} aria-label="Close TV release review">Close</button></header>
    <label>Quality profile <select aria-label="Download quality profile" value={profile} disabled={busy||Boolean(outcome)} onChange={e=>setProfile(e.target.value)}>{profiles.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
    {error&&<p role="alert">{error}</p>}{!review&&!error&&<p role="status">Searching TV sources…</p>}
    {review?.search?.partial&&<p role="status">Some sources did not finish. Available releases are shown.</p>}
    {(error||review?.search?.partial)&&!outcome&&<button disabled={busy} onClick={()=>setAttempt(n=>n+1)}>Retry search</button>}
    {review&&<>
      <div className="tv-release-summary"><strong>{selected.length} releases · {covered.size} of {review.episodes?.length||0} episodes · {sizeLabel(chosen.reduce((n,r)=>n+r.estimated_bytes,0))}</strong>
        {missing.length>0&&<p>Not covered: {missing.map(e=>e.code).join(', ')}</p>}{overlap&&<p role="alert">Selected releases overlap. Choose one release per episode.</p>}
        <label><input type="checkbox" checked={extras} disabled={busy||Boolean(outcome)} onChange={e=>setExtras(e.target.checked)}/>Allow extra episodes only when inseparable from selected episodes in one file</label>
        <button className="primary-button" disabled={busy||!selected.length||overlap||outcome?.complete} onClick={download}>{busy?'Preparing and queuing…':outcome?.complete?'Queued':outcome?'Retry unfinished releases':missing.length?'Download available':'Download selected releases'}</button>
        <p>Season-pack coverage is checked against its actual files before downloading. Unselected separate files are skipped.</p>
      </div>
      {outcome&&<div role="status">{outcome.items.map(item=><p key={item.token}>{review.decisions.find(r=>r.decision_token===item.token)?.candidate.title}: {item.state==='submitted'?'Queued':item.message}</p>)}</div>}
      <label><input type="checkbox" checked={blocked} onChange={e=>setBlocked(e.target.checked)}/>Show blocked releases ({review.decisions.filter(r=>r.state==='blocked').length})</label>
      <div className="tv-release-list">{review.decisions.filter(r=>blocked||r.state!=='blocked').map(row=><article className="tv-release-row" key={row.decision_token}>
        <label><input type="checkbox" aria-label={`Select release ${row.candidate.title}`} checked={selected.includes(row.decision_token)} disabled={!row.selectable||busy||Boolean(outcome)} onChange={e=>choose(row.decision_token,e.target.checked)}/><strong>{row.candidate.title}</strong></label>
        <p>{row.candidate.coverage_claim==='season_pack'?'Season pack':`Episodes ${(row.candidate.episode_numbers||[]).join(', ')}`} · {row.claim.resolution} · {row.claim.source.replaceAll('_',' ')} · {sizeLabel(row.estimated_bytes)} · {row.candidate.seeders} seeders · {row.candidate.indexer||'Indexer'}</p>
        {row.state==='resolve'&&!outcome?.items.some(item=>item.token===row.decision_token&&item.state==='submitted')&&<p>Torrent link will be resolved before queuing.</p>}
        {row.state==='identity_review'&&<p>{row.candidate.identity_evidence.reason} <button disabled={busy} onClick={()=>confirmIdentity(row)}>Confirm this is the selected series</button></p>}
        <details><summary>Details{row.reasons.length?' and reasons':''}</summary><p>{row.candidate.identity_evidence?.reason}</p>{row.reasons.map(r=><p key={r.code}>{r.message}</p>)}{row.warnings.map(r=><p key={r.code}>{r.message}</p>)}</details>
      </article>)}</div>
      {!review.decisions.length&&<p>No releases found for this selection.</p>}
      {review.search?.sources?.length>0&&<details><summary>Source results</summary><ul>{review.search.sources.map(source=><li key={source.id}>{source.name}: {source.state==='complete'?`${source.count} results`:source.state==='timeout'?'Timed out':'Failed'}</li>)}</ul></details>}
    </>}
  </dialog>;
}

export function TVMonitoringControls({ seriesId, season, onSearch, notify }) {
  const [scope, setScope] = useState('series'), [episode, setEpisode] = useState(1);
  const [mode, setMode] = useState('none'), [profile, setProfile] = useState('safe-hd'), [profiles, setProfiles] = useState([]);
  useEffect(() => { let alive = true; Promise.all([fetchJson('/api/acquisition/profiles'), fetchJson(`/api/tv/series/${seriesId}/monitor`)]).then(([catalog, state]) => { if (!alive) return; setProfiles(catalog.profiles); const rule = state.rules.find((row) => row.target.startsWith('series:')); setMode(rule?.mode || 'none'); setProfile(rule?.profile_id || 'safe-hd'); }).catch((e) => notify(e.message,'error')); return () => { alive = false; }; }, [seriesId]);
  async function save() { try { await fetchJson(`/api/tv/series/${seriesId}/monitor`, { method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode,profile_id:profile,...(scope !== 'series' ? {season}: {}),...(scope === 'episode' ? {episode}: {})}) }); notify('Monitoring rule saved','success'); } catch(e) { notify(e.message,'error'); } }
  return <section className="tv-monitoring" aria-label="TV monitoring"><h2>Monitoring and acquisition</h2><p>Adding a series never enables monitoring automatically. Existing copies are retained.</p><div className="tv-actions">
    <select aria-label="Monitoring scope" value={scope} onChange={(e)=>setScope(e.target.value)}><option value="series">Whole series</option><option value="season">Selected season</option><option value="episode">Episode in selected season</option></select>
    {scope === 'episode' && <input type="number" min="1" aria-label="Monitored episode number" value={episode} onChange={(e)=>setEpisode(Number(e.target.value))}/>}
    <select aria-label="Series monitoring" value={mode} onChange={(e)=>setMode(e.target.value)}>{['none','future','missing','all','cutoff',...(scope !== 'series' ? ['inherit'] : [])].map((value)=><option key={value} value={value}>{value === 'none' ? 'Not monitored' : value}</option>)}</select>
    <select aria-label="Series quality profile" value={profile} onChange={(e)=>setProfile(e.target.value)}>{profiles.map((row)=><option key={row.id} value={row.id}>{row.name}</option>)}</select>
    <button className="secondary-button" onClick={save}>Save monitoring</button>
  </div></section>;
}
