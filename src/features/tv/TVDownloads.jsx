import { useEffect, useState } from 'react';
import { fetchJson } from '../../api/client.js';
import './tv.css';

export default function TVDownloads() {
  const [rows,setRows]=useState([]),[error,setError]=useState('');
  useEffect(()=>{let alive=true;async function load(){try{const data=await fetchJson('/api/tv/acquisitions');if(alive){setRows(data.items);setError('');}}catch(e){if(alive)setError(e.message);}}load();const timer=setInterval(load,5000);return()=>{alive=false;clearInterval(timer);};},[]);
  async function manage(row, action) { try { await fetchJson(`/api/tv/acquisitions/${row.id}/action`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) }); const data = await fetchJson('/api/tv/acquisitions'); setRows(data.items); setError(''); } catch (e) { setError(e.message); } }
  return <section aria-label="TV Downloads"><h1>TV Downloads</h1>
    {error&&<p role="alert">{error}</p>}{!rows.length&&!error&&<p>No TV acquisitions yet.</p>}
    {rows.map(row=>{
      const job=row.job, normal=job?.tv_lifecycle_version===1;
      const hasPlan=job?.preserving_import_plan?.length>0;
      const rollback=hasPlan&&job.state!=='rolled_back'&&(!normal||job.rollback_available===true);
      return <article className="tv-episode" key={row.id}><div>
        <strong>{job?.title||row.target}</strong><p>{row.target}</p>
        <p>Acquisition: {row.state} · Transfer: {job?.state||'Not submitted'}</p>
        {job?.destination&&<p>Destination: {job.destination}</p>}
        {normal&&<p>Verified episodes move into the season folder. Completed downloads are removed from qBittorrent.</p>}
        {job?.tv_import&&<><p>{job.tv_import.imported_files} imported · {job.tv_import.failed_files} failed</p>{job.tv_import.failures?.map(failure=><p role="status" key={failure.name}>{failure.name}: {failure.reason}</p>)}</>}
        {job?.seeding_status&&<p>Seeding: {job.seeding_status}{job.seed_ratio!=null?` · ratio ${Number(job.seed_ratio).toFixed(2)}`:''}{job.seed_time_seconds!=null?` · ${job.seed_time_seconds}s`:''}</p>}
        {job?.state==='cleanup_failed'&&<p role="status">Cleanup failed. Review the library destination and finish transfer and staging cleanup.</p>}
        {job?.state==='retry_wait'&&<p role="status">Retry {job.retry_attempts} scheduled after a transient import failure.</p>}
        {job?.last_error&&<p role="status">{job.last_error}</p>}
        <div className="tv-actions">
          {['needs_review','validation_failed','cleanup_failed'].includes(job?.state)&&<button onClick={()=>manage(row,'retry')}>{job.state==='cleanup_failed'?'Retry cleanup':'Retry validation / import'}</button>}
          {rollback&&<button onClick={()=>manage(row,'rollback')}>Roll back imported files</button>}
          {!hasPlan&&!['cancelled','ready'].includes(row.state)&&<><button onClick={()=>manage(row,'cancel')}>Cancel and retain files</button><button onClick={()=>manage(row,'block')}>Block release</button></>}
        </div>
        <details><summary>History</summary>{row.history.map((event,index)=><p key={index}>{event.event} · {event.payload}</p>)}</details>
      </div></article>;
    })}
  </section>;
}
