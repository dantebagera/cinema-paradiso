import DialogShell, { DialogHeader, DialogActions } from '../../components/ui/DialogShell.jsx';
import Button from '../../components/ui/Button.jsx';
import { Select } from '../../components/ui/FormField.jsx';
import { useEffect, useRef, useState } from 'react';
import { fetchJson } from '../../api/client.js';
const post=(url,data,signal)=>fetchJson(url,{method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
const cairoTime = value => value ? new Intl.DateTimeFormat('en-GB', {timeZone:'Africa/Cairo', dateStyle:'medium', timeStyle:'short'}).format(new Date(value*1000)) : '—';
const sizeLabel=n=>n ? `${(n/1024/1024/1024).toFixed(2)} GB` : 'Size unknown';
export default function TVAcquisitionReview({ target, onClose, notify }) {
  const dialog=useRef(null), batchKey=useRef(null), alive=useRef(true);
  const [review,setReview]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[attempt,setAttempt]=useState(0),[selected,setSelected]=useState([]),[blocked,setBlocked]=useState(false),[extras,setExtras]=useState(false),[outcome,setOutcome]=useState(null);
  const [profiles,setProfiles]=useState([]),[profile,setProfile]=useState(target.profile_id||'safe-hd');
  useEffect(()=>{const controller=new AbortController();fetchJson('/api/acquisition/profiles',{signal:controller.signal}).then(r=>setProfiles(r.profiles)).catch(()=>{});return ()=>controller.abort();},[]);
  useEffect(()=>{const previous=document.activeElement;dialog.current?.showModal();alive.current=true;return ()=>{alive.current=false;previous?.focus();};},[]);
  useEffect(()=>{const controller=new AbortController();setReview(null);setError('');setOutcome(null);batchKey.current=null;post(target.seasons ? '/api/tv/search/seasons' : '/api/tv/search',{...target,profile_id:profile},controller.signal).then(r=>{if(!controller.signal.aborted){setReview(r);setSelected((r.recommended||[]).filter(token => r.decisions.find(d => d.decision_token === token)?.import_destination?.state === 'ready'));}}).catch(e=>{if(e.name!=='AbortError')setError(e.message);});return ()=>controller.abort();},[target,attempt,profile]);
  const chosen=review?.decisions.filter(r=>selected.includes(r.decision_token))||[];
  const covered=new Set(chosen.flatMap(r=>r.covered_episode_keys || r.covered_episodes));
  const missing=review?.episodes?.filter(e=>!covered.has(e.key ?? e.id))||[];
  const overlap=chosen.reduce((n,r)=>n+(r.covered_episode_keys || r.covered_episodes).length,0)!==covered.size;
  function choose(token,checked){if(outcome)return;batchKey.current=null;setSelected(old=>checked?[...old,token]:old.filter(t=>t!==token));}
  async function confirmIdentity(row){setBusy(true);setError('');try{const next=await post('/api/tv/releases/prepare',{decision_token:row.decision_token,confirm_identity:true});if(alive.current){setReview(old=>({...old,decisions:old.decisions.map(d=>d.decision_token===row.decision_token?next:d), season_reviews:old.season_reviews?.map(group => ({...group, decisions:group.decisions.map(d=>d.decision_token===row.decision_token?next:d)}))}));if(next.selectable)setSelected(old=>[...old.filter(t=>t!==row.decision_token),next.decision_token]);}}catch(e){if(alive.current)setError(e.message);}finally{if(alive.current)setBusy(false);}}
  async function download(){setBusy(true);setError('');batchKey.current ||= crypto.randomUUID();try{const result=await post('/api/tv/acquisitions/batch',{decision_tokens:selected,request_key:batchKey.current,allow_partial:missing.length>0,allow_extras:extras});if(alive.current){setOutcome(result);if(result.complete){notify('Selected releases queued for episode-file verification','success');}else setError('Some releases could not be queued. Retry submits only unfinished releases.');}}catch(e){if(alive.current)setError(e.message);}finally{if(alive.current)setBusy(false);}}
  async function chooseHome(path){if(!path)return;setBusy(true);setError('');try{await post(`/api/tv/series/${review.target.series_id}/import-home`,{path});if(alive.current){setSelected([]);batchKey.current=null;setAttempt(n=>n+1);}}catch(e){if(alive.current)setError(e.message);}finally{if(alive.current)setBusy(false);}}
  function homeChoice(destination, season) {
    if (destination?.state !== 'needs_choice' || !(destination.candidates?.length > 1)) return null;
    return <label>Approved show folder <Select aria-label={season ? `Approved TV show folder for season ${season}` : 'Approved TV show folder'} value="" disabled={busy||Boolean(outcome)} onChange={e=>chooseHome(e.target.value)}><option value="">Choose a folder</option>{destination.candidates.map(path=><option key={path} value={path}>{path}</option>)}</Select></label>;
  }
  return <DialogShell as="dialog" size="wide" ref={dialog} className="tv-version-dialog tv-release-dialog" aria-label="TV release review" onCancel={e=>{if(busy)e.preventDefault();else onClose();}}>
    <DialogHeader as="header" className="tv-release-heading"><div><h2>Choose TV downloads</h2><p>{target.seasons ? `Seasons ${target.seasons.join(', ')}` : `Season ${target.season}`}{target.episode?` · Episode ${target.episode}`:''}</p></div><Button onClick={onClose} disabled={busy} aria-label="Close TV release review">Close</Button></DialogHeader>
    <label>Quality profile <Select aria-label="Download quality profile" value={profile} disabled={busy||Boolean(outcome)} onChange={e=>setProfile(e.target.value)}>{profiles.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</Select></label>
    {error&&<p role="alert">{error}</p>}{!review&&!error&&<p role="status">Searching TV sources…</p>}
    {review?.search?.partial&&<p role="status">Some sources did not finish. Available releases are shown.</p>}
    {(error||review?.search?.partial)&&!outcome&&<Button disabled={busy} onClick={()=>setAttempt(n=>n+1)}>Retry search</Button>}
    {review&&<>
      <div className="tv-release-summary"><strong>{selected.length} selected releases · {covered.size} of {review.episodes?.length||0} episodes · {sizeLabel(chosen.reduce((n,r)=>n+r.estimated_bytes,0))}</strong>
        {missing.length>0&&<p>Not covered: {missing.map(e=>e.code).join(', ')}</p>}{overlap&&<p role="alert">Selected releases overlap. Choose one release per episode.</p>}
        <p>{review.season_reviews ? 'Review each season destination below.' : review.import_destination?.state==='ready'?`Destination: ${review.import_destination.path}`:review.import_destination?.reason||'Choose an approved TV show folder before downloading'}</p>
        {homeChoice(review.import_destination)}
        <p>Verified episodes move into the season folder. Completed downloads are removed from qBittorrent.</p>
        <label><input type="checkbox" checked={extras} disabled={busy||Boolean(outcome)} onChange={e=>setExtras(e.target.checked)}/>Allow extra episodes only when inseparable from selected episodes in one file</label>
        <Button variant="primary"  disabled={busy||(review.season_reviews ? chosen.some(row => row.import_destination?.state !== 'ready') : review.import_destination?.state !== 'ready')||!selected.length||overlap||outcome?.complete} onClick={download}>{busy?'Preparing and queuing…':outcome?.complete?'Queued':outcome?'Retry unfinished releases':missing.length?'Download available':'Download selected releases'}</Button>
        <p>Season-pack coverage is checked against its actual files before downloading. Unselected separate files are skipped.</p>
      </div>
      {outcome&&<div role="status">{outcome.items.map(item=><p key={item.token}>{review.decisions.find(r=>r.decision_token===item.token)?.candidate.title}: {item.state==='submitted'?'Queued':item.message}</p>)}</div>}
      <label><input type="checkbox" checked={blocked} onChange={e=>setBlocked(e.target.checked)}/>Show blocked releases ({review.decisions.filter(r=>r.state==='blocked').length})</label>
      {(review.season_reviews || [review]).map(group => <section key={group.target?.season ?? 'single'} aria-label={`Season ${group.target?.season ?? target.season} releases`}>
        {review.season_reviews && <><h3>Season {group.target.season}</h3><p>{group.import_destination?.state === 'ready' ? `Destination: ${group.import_destination.path}` : group.import_destination?.reason}</p>{homeChoice(group.import_destination, group.target.season)}<p>{group.episodes.length} released missing episodes · {group.decisions.length} releases</p>{group.search?.error && <p role="alert">{group.search.error}</p>}{!group.decisions.length && <p>No releases available for this season.</p>}</>}
      <div className="tv-release-list">{group.decisions.filter(r=>blocked||r.state!=='blocked').map(row=><article className="tv-release-row" key={row.decision_token}>
        <label><input type="checkbox" aria-label={`Select release ${row.candidate.title}`} checked={selected.includes(row.decision_token)} disabled={!row.selectable||row.import_destination?.state!=='ready'||busy||Boolean(outcome)} onChange={e=>choose(row.decision_token,e.target.checked)}/><strong>{row.candidate.title}</strong></label>
        <p>{row.candidate.coverage_claim==='season_pack'?'Season pack':`Episodes ${(row.candidate.episode_numbers||[]).join(', ')}`} · {row.claim.resolution} · {row.claim.source.replaceAll('_',' ')} · {sizeLabel(row.estimated_bytes)} · {row.candidate.seeders} seeders · {row.candidate.indexer||'Indexer'}</p>
        {row.state==='resolve'&&!outcome?.items.some(item=>item.token===row.decision_token&&item.state==='submitted')&&<p>Torrent link will be resolved before queuing.</p>}
        {row.state==='identity_review'&&<p>{row.candidate.identity_evidence.reason} <Button disabled={busy} onClick={()=>confirmIdentity(row)}>Confirm this is the selected series</Button></p>}
        <details><summary>Details{row.reasons.length?' and reasons':''}</summary><p>{row.candidate.identity_evidence?.reason}</p>{row.reasons.map(r=><p key={r.code}>{r.message}</p>)}{row.warnings.map(r=><p key={r.code}>{r.message}</p>)}</details>
      </article>)}</div></section>)}
      {!review.decisions.length&&<p>No releases found for this selection.</p>}
      {review.search?.sources?.length>0&&<details><summary>Source results</summary><ul>{review.search.sources.map(source=><li key={source.id}>{source.name}: {source.state==='complete'?`${source.count} results`:source.state==='timeout'?'Timed out':'Failed'}</li>)}</ul></details>}
    </>}
  </DialogShell>;
}

export function TVSeasonSelection({ series, seriesId, tmdbId, onReview, onClose }) {
  const dialog = useRef(null), [selected, setSelected] = useState([]), [counts, setCounts] = useState(null), [error, setError] = useState('');
  const seasons = series.seasons.filter(item => item.number > 0);
  useEffect(() => { const previous = document.activeElement; dialog.current?.showModal(); return () => previous?.focus(); }, []);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      let rows;
      if (seriesId) rows = (await fetchJson(`/api/tv/series/${seriesId}/selection`, {signal:controller.signal})).items;
      else {
        rows = [];
        for (const item of seasons) {
          if (controller.signal.aborted) return;
          rows.push(...(await fetchJson(`/api/tv/preview/${tmdbId}/seasons/${item.number}`, {signal:controller.signal})).items);
        }
      }
      if (!controller.signal.aborted) setCounts(Object.fromEntries(seasons.map(item => {
        const scoped = rows.filter(row => row.season_number === item.number);
        return [item.number, {released:scoped.filter(row => row.released).length, owned:scoped.filter(row => row.available).length,
          missing:scoped.filter(row => row.released && !row.available && !row.reconciliation_required).length}];
      })));
    }
    load().catch(cause => { if (cause.name !== 'AbortError') setError(cause.message); });
    return () => controller.abort();
  }, [seriesId, tmdbId]);
  return <DialogShell as="dialog" ref={dialog} className="small-dialog trusted-indexer-dialog" aria-label="Choose TV seasons" onCancel={onClose}>
    <DialogHeader as="header" ><h2>Choose seasons</h2><Button size="icon"  aria-label="Close season selection" onClick={onClose}>Close</Button></DialogHeader>
    <p>Review released missing regular episodes. Downloads start only after you select and submit releases.</p>
    {error && <p role="alert">{error}</p>}{!counts && !error && <p role="status">Loading season coverage…</p>}
    <div className="settings-checkbox-group trusted-indexer-list">{seasons.map(item => <label className="settings-checkbox-field" key={item.number}>
      <input type="checkbox" checked={selected.includes(item.number)} onChange={event => setSelected(values => event.target.checked ? [...values, item.number] : values.filter(n => n !== item.number))}/>
      <span>Season {item.number}{counts?.[item.number] && <small>{counts[item.number].missing} missing · {counts[item.number].released} released · {counts[item.number].owned} owned</small>}</span>
    </label>)}</div><DialogActions ><Button  onClick={onClose}>Cancel</Button><Button variant="primary"  disabled={!selected.length || !counts || Boolean(error)} onClick={() => onReview(selected.sort((a,b) => a-b))}>Review downloads</Button></DialogActions>
  </DialogShell>;
}

export function TVMonitoringControls({ seriesId, series, season, notify }) {
  const [sourceReview, setSourceReview] = useState(null);
  useEffect(() => setSourceReview(null), [seriesId]);
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
  const previewRequest = useRef(null);
  useEffect(() => {
    let controller, sequence = 0;
    async function refresh() {
      controller?.abort(); controller = new AbortController(); const current = ++sequence;
      try {
        const [catalog, active, past] = await Promise.all([
          fetchJson('/api/acquisition/profiles', {signal:controller.signal}),
          fetchJson(`/api/tv/tasks?series_id=${seriesId}`, {signal:controller.signal}),
          fetchJson(`/api/tv/tasks?series_id=${seriesId}&history=true`, {signal:controller.signal}),
        ]);
        if (current === sequence && !controller.signal.aborted) { setProfiles(catalog.profiles); setTasks(active.items); setHistory(past.items); }
      } catch (cause) { if (cause.name !== 'AbortError' && current === sequence) setError(cause.message); }
    }
    refresh(); const timer = setInterval(refresh, 15000);
    return () => { ++sequence; clearInterval(timer); controller?.abort(); };
  }, [seriesId, revision]);
  useEffect(() => { if (scope !== 'episodes') return undefined; const controller = new AbortController(); fetchJson(`/api/tv/series/${seriesId}/selection`, {signal:controller.signal}).then((data) => setEpisodeChoices(data.items)).catch((cause) => { if (cause.name !== 'AbortError') setError(cause.message); }); return () => controller.abort(); }, [scope, seriesId]);
  useEffect(() => { previewRequest.current?.abort(); setPreview(null); return () => previewRequest.current?.abort(); }, [scope, action, profile, season, selected]);
  const effectiveAction = scope === 'episodes' ? 'selected' : action;
  const payload = {scope, action:effectiveAction, profile_id:profile, ...(scope === 'season' ? {season} : {}), ...(scope === 'episodes' ? {selected_episodes:selected} : {})};
  async function getPreview() { previewRequest.current?.abort(); const controller = new AbortController(); previewRequest.current = controller; setBusy(true); setError(''); try { const next = await post(`/api/tv/series/${seriesId}/tasks/preview`, payload, controller.signal); if (!controller.signal.aborted) setPreview(next); } catch (cause) { if (cause.name !== 'AbortError') setError(cause.message); } finally { if (previewRequest.current === controller) setBusy(false); } }
  async function save() { setBusy(true); setError(''); try { await post(`/api/tv/series/${seriesId}/tasks`, payload); setRevision(value => value + 1); setPreview(null); notify('TV task saved as a draft. Start it when ready.', 'success'); } catch (cause) { setError(cause.message); } finally { setBusy(false); } }
  async function start(task) { setBusy(true); setError(''); try { await post(`/api/tv/tasks/${encodeURIComponent(task.id)}/start`, {}); setRevision(value => value + 1); notify('TV task started', 'success'); } catch (cause) { setError(cause.message); } finally { setBusy(false); } }
  async function finishSeason(task) { setBusy(true); setError(''); try { await post(`/api/tv/tasks/${encodeURIComponent(task.id)}/finish-season`, {}); setRevision(value => value + 1); notify('Season follow task finished', 'success'); } catch (cause) { setError(cause.message); } finally { setBusy(false); } }
  async function openCancel(task) { setCancelTask(task); setCancelPreview(null); setCancelMode('keep'); setBusy(true); setError(''); try { setCancelPreview(await fetchJson(`/api/tv/tasks/${encodeURIComponent(task.id)}/cancel/preview`)); } catch (cause) { setError(cause.message); } finally { setBusy(false); } }
  async function confirmCancel() { setBusy(true); setError(''); try { const result = await post(`/api/tv/tasks/${encodeURIComponent(cancelTask.id)}/cancel`, {mode:cancelMode, token:cancelPreview.token}); setCancelTask(null); setCancelPreview(null); setRevision(value => value + 1); notify(result.task.state === 'cancelled' ? 'TV task cancelled' : 'TV task cancellation needs review', result.task.state === 'cancelled' ? 'success' : 'error'); } catch (cause) { setError(cause.message); } finally { setBusy(false); } }
  const chosenProfile = profiles.find(item => item.id === profile);
  return <section className="tv-monitoring" aria-label="Follow and download"><h2>Follow and download</h2><p>This is separate from identifying files already on disk. Saving creates a draft; only Start begins searching or downloading.</p>
    <div className="tv-actions">
      <label>Scope <Select aria-label="Follow scope" value={scope} onChange={event => setScope(event.target.value)}><option value="series">Whole series</option><option value="season">Selected season</option><option value="episodes">Selected episodes</option></Select></label>
      {scope === 'season' && <span>Season {season}</span>}
      <label>Action <Select aria-label="Follow action" value={effectiveAction} disabled={scope === 'episodes'} onChange={event => setAction(event.target.value)}>{scope === 'episodes' ? <option value="selected">Download selected</option> : <><option value="missing">Missing — download existing missing episodes</option>{series.status !== 'Ended' && <option value="future">Future — follow new episodes</option>}<option value="upgrade">Upgrade</option></>}</Select></label>
      <label>Quality profile <Select aria-label="Follow quality profile" value={profile} onChange={event => setProfile(event.target.value)}>{profiles.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></label>
    </div>
    {chosenProfile && <p>Preferred resolution: {chosenProfile.cutoff}. Eligible sources follow this profile’s allowed, manual-only, and blocked rules. Strict Upgrade requires a trusted, provably better source. Verified episodes move into the season folder. Completed downloads are removed from qBittorrent. An owned copy stays until its replacement is verified.</p>}
    {scope === 'episodes' && <div className="tv-follow-episode-choices" aria-label="Select episodes across seasons">{episodeChoices.map(item => <label key={item.id}><input type="checkbox" checked={selected.includes(item.id)} onChange={event => setSelected(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))}/>{item.code} {item.title}</label>)}</div>}
    <div className="tv-actions"><Button type="button" disabled={busy || (scope === 'episodes' && !selected.length)} onClick={getPreview}>Preview targets</Button><Button type="button"  disabled={busy || !preview || (scope === 'episodes' && !selected.length)} onClick={save}>Save draft</Button></div>
    {preview && <p role="status">{preview.counts.released_missing} released missing · {preview.counts.future} future · {preview.counts.owned} owned · {preview.counts.queued} queued · {preview.counts.review} needs file review · {preview.counts.unknown_date} unknown date. {preview.target_episode_ids.length} target episodes. {preview.metadata_complete ? 'Metadata complete.' : 'Metadata incomplete; Start will require a refresh.'}</p>}
    {preview?.import_destinations?.map(destination=><p key={destination.season}>Season {destination.season}: {destination.state==='ready'?destination.path:destination.reason}</p>)}
    {preview?.readiness?.blockers?.map(blocker => <p role="alert" key={blocker}>{blocker}</p>)}
    <p>Missing and Future retry unsuccessful source searches every five hours. Future first searches at midnight Africa/Cairo on the listed air date, on the next worker pass. Metadata refresh is separate.</p>
    {error && <p role="alert">{error}</p>}
    <h3>Tasks</h3>{tasks.length ? tasks.map(task => <article className="tv-follow-task" key={task.id}>
      <strong>{task.scope === 'series' ? 'Whole series' : task.scope === 'season' ? `Season ${task.season}` : `${task.selected_episodes.length} selected episodes`} · {task.action} · {task.state}</strong>
      <p>{task.profile_id} · {task.episodes.filter(row => row.state === 'acquired').length} / {task.episodes.length} acquired{task.error ? ` · ${task.error}` : ''}</p>
      <p>{task.counts?.queued || 0} queued · {task.counts?.waiting || 0} waiting · {task.counts?.review || 0} needs review</p>
      <p>Last search: {cairoTime(task.last_search)} · Next eligible search: {cairoTime(task.next_eligible_search)} (Africa/Cairo)</p>
      {task.episodes.filter(row => row.error || row.state === 'submitting').map(row => <p role="status" key={row.episode_id}>
        {row.code || `Episode ${row.episode_id}`}: {row.state === 'submitting' ? 'Submission pending' : row.error}
        {row.state === 'needs_review' && !row.intent_id && row.source_diagnostics?.review_required ? ` · Review required; next automatic search: ${cairoTime(row.next_retry)}` : row.next_retry ? ` · Next: ${cairoTime(row.next_retry)}` : ''}
      </p>)}
      {[...new Map(task.episodes.filter(row => row.source_diagnostics?.version).map(row => [JSON.stringify([row.source_diagnostics.search_scope,row.source_diagnostics.query_episode,row.source_diagnostics.episode_ids,row.last_search]),row])).values()].map(row => <details className="tv-source-diagnostics" key={row.episode_id}>
        <summary>Source search details</summary><p>{row.source_diagnostics.summary}</p>
        <p>{row.source_diagnostics.result_count} results returned · {row.source_diagnostics.automatic_eligible_count} automatically eligible</p>
        {row.source_diagnostics.candidates.map((candidate,index) => <div key={index}><strong>{candidate.title}</strong><p>{candidate.indexer} · {candidate.quality.resolution} · {candidate.quality.source?.replaceAll('_',' ')}</p>{candidate.reasons.map(reason => <p key={reason.code}>{reason.message}</p>)}</div>)}
        {row.source_diagnostics.sources.length > 0 && <ul>{row.source_diagnostics.sources.map(source => <li key={source.id}>{source.name}: {source.state === 'complete' ? `${source.count} results` : source.state === 'timeout' ? 'Timed out' : 'Failed'}</li>)}</ul>}
      </details>)}
      {[...new Set(task.episodes.filter(row => !row.intent_id && row.source_diagnostics?.review_required).map(row => row.season))].filter(Boolean).map(number => <Button key={number} type="button" disabled={busy} onClick={() => setSourceReview({series_id:seriesId,season:number,missing_only:true,profile_id:task.profile_id})}>Review season releases</Button>)}
      {task.state === 'draft' && <Button type="button" disabled={busy} onClick={() => start(task)}>Start</Button>}
      {task.state === 'waiting_season_end' && <Button type="button" disabled={busy} onClick={() => finishSeason(task)}>Finish this season</Button>}
      <Button type="button" aria-label={`Cancel ${task.action} task`} disabled={busy} onClick={() => openCancel(task)}>X</Button>
    </article>) : <p>No active tasks.</p>}
    <details><summary>Task history ({history.length})</summary>{history.map(task => <p key={task.id}>{task.scope} · {task.action} · {task.state} · {task.episodes.length} targets</p>)}</details>
    {sourceReview && <TVAcquisitionReview target={sourceReview} notify={notify} onClose={() => {setSourceReview(null);setRevision(value => value+1);}}/>}
    {cancelTask && <div className="modal-backdrop"><DialogShell size="wide" className="tv-bulk-dialog" role="dialog" aria-modal="true" aria-label="Cancel TV task"><h2>Cancel {cancelTask.action} task?</h2>
      {busy && !cancelPreview && <p>Checking task transfers and files…</p>}{error && <p role="alert">{error}</p>}
      {cancelPreview && <><p>{cancelPreview.transfers.length} transfers · {cancelPreview.completed_files.length} files acquired by this task · {cancelPreview.protected.length} protected paths</p>
        {cancelPreview.transfers.map(item => <p key={item.hash}>Transfer {item.hash} ({item.state}){item.paths.length ? `: ${item.paths.join(', ')}` : ''}</p>)}
        {cancelPreview.completed_files.map(item => <p key={item.path}>Completed: {item.path}</p>)}
        {cancelPreview.protected.map((item, index) => <p key={`${item.path}-${index}`}>Protected: {item.path || 'transfer'} — {item.reason}</p>)}
        <fieldset><legend>Cancellation outcome</legend><label><input type="radio" name="tv-cancel-mode" checked={cancelMode === 'keep'} onChange={() => setCancelMode('keep')}/>Stop searching and queued work; keep files</label><label><input type="radio" name="tv-cancel-mode" checked={cancelMode === 'incomplete'} onChange={() => setCancelMode('incomplete')}/>Also cancel in-progress transfers and delete verified incomplete files</label><label><input type="radio" name="tv-cancel-mode" checked={cancelMode === 'all'} onChange={() => setCancelMode('all')}/>Also move exclusively owned completed files to Recycle Bin</label></fieldset></>}
      <div className="tv-actions"><Button type="button" onClick={() => { setCancelTask(null); setCancelPreview(null); setError(''); }}>Keep task</Button><Button variant="primary" type="button"  disabled={busy || !cancelPreview} onClick={confirmCancel}>Confirm cancellation</Button></div>
    </DialogShell></div>}
  </section>;
}
