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

export function TVMonitoringControls({ seriesId, series, season, notify }) {
  const [scope, setScope] = useState('series');
  const [action, setAction] = useState('missing');
  const [profile, setProfile] = useState('safe-hd');
  const [profiles, setProfiles] = useState([]);
  const [selected, setSelected] = useState([]);
  const [episodeChoices, setEpisodeChoices] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [history, setHistory] = useState([]);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [cancelTask, setCancelTask] = useState(null);
  const [cancelPreview, setCancelPreview] = useState(null);
  const [cancelMode, setCancelMode] = useState('keep');
  useEffect(() => { let alive = true; Promise.all([
    fetchJson('/api/acquisition/profiles'),
    fetchJson(`/api/tv/tasks?series_id=${seriesId}`),
    fetchJson(`/api/tv/tasks?series_id=${seriesId}&history=true`),
  ]).then(([catalog, active, past]) => { if (alive) { setProfiles(catalog.profiles); setTasks(active.items); setHistory(past.items); } }).catch((cause) => alive && setError(cause.message)); return () => { alive = false; }; }, [seriesId, revision]);
  useEffect(() => { if (scope !== 'episodes') return undefined; const controller = new AbortController(); fetchJson(`/api/tv/series/${seriesId}/selection`, {signal:controller.signal}).then((data) => setEpisodeChoices(data.items)).catch((cause) => { if (cause.name !== 'AbortError') setError(cause.message); }); return () => controller.abort(); }, [scope, seriesId]);
  useEffect(() => { setPreview(null); }, [scope, action, profile, season, selected]);
  const effectiveAction = scope === 'episodes' ? 'selected' : action;
  const payload = {scope, action:effectiveAction, profile_id:profile, ...(scope === 'season' ? {season} : {}), ...(scope === 'episodes' ? {selected_episodes:selected} : {})};
  async function getPreview() { setBusy(true); setError(''); try { setPreview(await post(`/api/tv/series/${seriesId}/tasks/preview`, payload)); } catch (cause) { setError(cause.message); } finally { setBusy(false); } }
  async function save() { setBusy(true); setError(''); try { await post(`/api/tv/series/${seriesId}/tasks`, payload); setRevision(value => value + 1); setPreview(null); notify('TV task saved as a draft. Start it when ready.', 'success'); } catch (cause) { setError(cause.message); } finally { setBusy(false); } }
  async function start(task) { setBusy(true); setError(''); try { await post(`/api/tv/tasks/${encodeURIComponent(task.id)}/start`, {}); setRevision(value => value + 1); notify('TV task started', 'success'); } catch (cause) { setError(cause.message); } finally { setBusy(false); } }
  async function finishSeason(task) { setBusy(true); setError(''); try { await post(`/api/tv/tasks/${encodeURIComponent(task.id)}/finish-season`, {}); setRevision(value => value + 1); notify('Season follow task finished', 'success'); } catch (cause) { setError(cause.message); } finally { setBusy(false); } }
  async function openCancel(task) { setCancelTask(task); setCancelPreview(null); setCancelMode('keep'); setBusy(true); setError(''); try { setCancelPreview(await fetchJson(`/api/tv/tasks/${encodeURIComponent(task.id)}/cancel/preview`)); } catch (cause) { setError(cause.message); } finally { setBusy(false); } }
  async function confirmCancel() { setBusy(true); setError(''); try { const result = await post(`/api/tv/tasks/${encodeURIComponent(cancelTask.id)}/cancel`, {mode:cancelMode, token:cancelPreview.token}); setCancelTask(null); setCancelPreview(null); setRevision(value => value + 1); notify(result.task.state === 'cancelled' ? 'TV task cancelled' : 'TV task cancellation needs review', result.task.state === 'cancelled' ? 'success' : 'error'); } catch (cause) { setError(cause.message); } finally { setBusy(false); } }
  const chosenProfile = profiles.find(item => item.id === profile);
  return <section className="tv-monitoring" aria-label="Follow and download"><h2>Follow and download</h2><p>This is separate from identifying files already on disk. Saving creates a draft; only Start begins searching or downloading.</p>
    <div className="tv-actions">
      <label>Scope <select aria-label="Follow scope" value={scope} onChange={event => setScope(event.target.value)}><option value="series">Whole series</option><option value="season">Selected season</option><option value="episodes">Selected episodes</option></select></label>
      {scope === 'season' && <span>Season {season}</span>}
      <label>Action <select aria-label="Follow action" value={effectiveAction} disabled={scope === 'episodes'} onChange={event => setAction(event.target.value)}>{scope === 'episodes' ? <option value="selected">Download selected</option> : <><option value="missing">Missing</option>{series.status !== 'Ended' && <option value="future">Future</option>}<option value="upgrade">Upgrade</option></>}</select></label>
      <label>Quality profile <select aria-label="Follow quality profile" value={profile} onChange={event => setProfile(event.target.value)}>{profiles.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    </div>
    {chosenProfile && <p>Preferred resolution: {chosenProfile.cutoff}. Eligible sources follow this profile’s allowed, manual-only, and blocked rules. Strict Upgrade requires a trusted, provably better source. TV imports keep the transfer source and use {chosenProfile.import_mode === 'copy' ? 'a verified copy' : 'a verified hardlink or copy'}; seeding: {chosenProfile.seeding_mode === 'none' ? 'stops after import' : chosenProfile.seeding_mode}. An owned copy stays until its replacement is verified.</p>}
    {scope === 'episodes' && <div className="tv-follow-episode-choices" aria-label="Select episodes across seasons">{episodeChoices.map(item => <label key={item.id}><input type="checkbox" checked={selected.includes(item.id)} onChange={event => setSelected(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))}/>{item.code} {item.title}</label>)}</div>}
    <div className="tv-actions"><button type="button" disabled={busy || (scope === 'episodes' && !selected.length)} onClick={getPreview}>Preview targets</button><button type="button" className="secondary-button" disabled={busy || !preview || (scope === 'episodes' && !selected.length)} onClick={save}>Save draft</button></div>
    {preview && <p role="status">{preview.counts.released_missing} released missing · {preview.counts.future} future · {preview.counts.owned} owned · {preview.counts.queued} queued · {preview.counts.review} needs file review · {preview.counts.unknown_date} unknown date. {preview.target_episode_ids.length} target episodes. {preview.metadata_complete ? 'Metadata complete.' : 'Metadata incomplete; Start will require a refresh.'}</p>}
    {error && <p role="alert">{error}</p>}
    <h3>Tasks</h3>{tasks.length ? tasks.map(task => <article className="tv-follow-task" key={task.id}><strong>{task.scope === 'series' ? 'Whole series' : task.scope === 'season' ? `Season ${task.season}` : `${task.selected_episodes.length} selected episodes`} · {task.action} · {task.state}</strong><p>{task.profile_id} · {task.episodes.filter(row => row.state === 'acquired').length} / {task.episodes.length} acquired{task.error ? ` · ${task.error}` : ''}</p>{task.state === 'draft' && <button type="button" disabled={busy} onClick={() => start(task)}>Start</button>}{task.state === 'waiting_season_end' && <button type="button" disabled={busy} onClick={() => finishSeason(task)}>Finish this season</button>}<button type="button" aria-label={`Cancel ${task.action} task`} disabled={busy} onClick={() => openCancel(task)}>X</button></article>) : <p>No active tasks.</p>}
    <details><summary>Task history ({history.length})</summary>{history.map(task => <p key={task.id}>{task.scope} · {task.action} · {task.state} · {task.episodes.length} targets</p>)}</details>
    {cancelTask && <div className="modal-backdrop"><section className="tv-bulk-dialog" role="dialog" aria-modal="true" aria-label="Cancel TV task"><h2>Cancel {cancelTask.action} task?</h2>
      {busy && !cancelPreview && <p>Checking task transfers and files…</p>}{error && <p role="alert">{error}</p>}
      {cancelPreview && <><p>{cancelPreview.transfers.length} transfers · {cancelPreview.completed_files.length} files acquired by this task · {cancelPreview.protected.length} protected paths</p>
        {cancelPreview.transfers.map(item => <p key={item.hash}>Transfer {item.hash} ({item.state}){item.paths.length ? `: ${item.paths.join(', ')}` : ''}</p>)}
        {cancelPreview.completed_files.map(item => <p key={item.path}>Completed: {item.path}</p>)}
        {cancelPreview.protected.map((item, index) => <p key={`${item.path}-${index}`}>Protected: {item.path || 'transfer'} — {item.reason}</p>)}
        <fieldset><legend>Cancellation outcome</legend><label><input type="radio" name="tv-cancel-mode" checked={cancelMode === 'keep'} onChange={() => setCancelMode('keep')}/>Stop searching and queued work; keep files</label><label><input type="radio" name="tv-cancel-mode" checked={cancelMode === 'incomplete'} onChange={() => setCancelMode('incomplete')}/>Also cancel in-progress transfers and delete verified incomplete files</label><label><input type="radio" name="tv-cancel-mode" checked={cancelMode === 'all'} onChange={() => setCancelMode('all')}/>Also move exclusively owned completed files to Recycle Bin</label></fieldset></>}
      <div className="tv-actions"><button type="button" onClick={() => { setCancelTask(null); setCancelPreview(null); setError(''); }}>Keep task</button><button type="button" className="primary-button" disabled={busy || !cancelPreview} onClick={confirmCancel}>Confirm cancellation</button></div>
    </section></div>}
  </section>;
}
