export function ratingsIdentity(movie) {
  if (!movie || (movie.type && movie.type !== 'movie') || movie.media_type === 'tv') return null;
  const out = {};
  for (const [field, pattern] of [['tmdb_id', /^[0-9]{1,12}$/], ['imdb_id', /^tt[0-9]{5,12}$/], ['plex_guid', /^plex:\/\/movie\/[a-f0-9]{24}$/]]) {
    const raw = movie[field];
    if (raw == null || raw === '') continue;
    const value = String(raw).trim().toLowerCase();
    if (typeof raw === 'boolean' || !pattern.test(value)) return null;
    out[field] = field === 'tmdb_id' ? String(Number(value)) : value;
    if (field === 'tmdb_id' && Number(value) <= 0) return null;
  }
  const key = out.tmdb_id ? `movie:tmdb:${out.tmdb_id}` : out.imdb_id ? `movie:imdb:${out.imdb_id}` : out.plex_guid ? `movie:plex:${out.plex_guid.split('/').at(-1)}` : '';
  return key ? { ...out, key } : null;
}

async function fetchBatch(route, items) {
  const response = await fetch(`/api/movie-ratings/${route}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({items})});
  if (!response.ok) throw new Error('optional_ratings_unavailable');
  return response.json();
}

export function createMovieRatingsClient({eligible, fetchBatch: request = fetchBatch, idle = callback => setTimeout(callback, 0)} = {}) {
  const entries = new Map();
  let timer, timerDue = 0, leaseTimer, busy = false, destroyed = false, epoch = 0, owner = null, leaseUntil = 0;
  const visible = entry => [...entry.subscribers].some(s => s.visible());
  const notify = entry => { for (const s of entry.subscribers) s.listener(); };
  function schedule(delay = 50) {
    if (destroyed || busy || ![...entries.values()].some(e=>e.subscribers.size)) return;
    const due=Date.now()+delay;
    if(timer&&timerDue<=due)return;
    clearTimeout(timer);timerDue=due;
    timer = setTimeout(() => { timer = null;timerDue=0; idle(run); }, Math.min(delay,2147483647));
  }
  function hideUnowned() {
    for (const entry of entries.values()) if (entry.value && !entry.value.owned) {
      entry.value = null; entry.phase = 'read'; notify(entry);
    }
  }
  function trim() {
    let excess = entries.size - 1000;
    for (const [key, entry] of entries) {
      if (excess <= 0) break;
      if (!entry.subscribers.size) { entries.delete(key); excess--; }
    }
  }
  function invalidate() {
    epoch++; owner = null; leaseUntil = 0; clearTimeout(leaseTimer);
    for (const entry of entries.values()) {
      entry.value = null; entry.phase = 'read'; entry.polls = 0; entry.due = 0; notify(entry);
    }
    schedule();
  }
  async function run() {
    if (busy || destroyed || !eligible()) return;
    const candidates = [...entries.values()].filter(e => visible(e) && e.phase !== 'done' && e.due <= Date.now());
    if (!candidates.length) {
      const due=[...entries.values()].filter(e=>visible(e)&&e.phase!=='done').map(e=>e.due);
      if(due.length) schedule(Math.max(50,Math.min(...due)-Date.now()));
      return;
    }
    candidates.sort((a,b) => Number(b.expanded)-Number(a.expanded));
    const phase = candidates[0].phase;
    const batch = candidates.filter(e => e.phase === phase).slice(0,40);
    const revisions = new Map(batch.map(e=>[e,e.revision]));
    const version = epoch;
    busy = true;
    let response;
    try { response = await request(['resolve','poll'].includes(phase) ? 'resolve' : 'read', batch.map(e => ({...e.identity, priority:e.expanded?'expanded':'visible'}))); }
    catch { response = null; }
    // Permission revocation is immediate. Adding scores waits for idle/input gates.
    if (version === epoch && (!response || response.plex?.state !== 'available')) hideUnowned();
    const publish = () => {
      if (destroyed || version !== epoch) { busy = false; schedule(); return; }
      if (!eligible()) { timer = setTimeout(() => {timer=null; idle(publish);}, 250); return; }
      if (response?.owner && owner && response.owner !== owner) {
        invalidate();
      }
      owner = response?.owner || owner;
      const currentEpoch = epoch;
      leaseUntil=response?.plex?.state === 'available' ? response.plex.valid_until*1000 : 0;
      for (const entry of batch) {
        if(entry.revision!==revisions.get(entry))continue;
        const incoming = response?.items?.[entry.identity.key];
        const retainSaved = entry.value?.owned && ((!response) || (response.cache_state==='unavailable' && incoming?.owned));
        const value = retainSaved ? entry.value : incoming || null;
        const changed = JSON.stringify(entry.value) !== JSON.stringify(value);
        entry.value = value;
        if (changed) notify(entry);
        if (!response) { entry.phase='retry'; entry.due=Date.now()+60000; }
        else if (value?.state === 'pending' && entry.polls++ < 15) { entry.phase='poll'; entry.due=Date.now()+1000; }
        else if (value?.state==='unavailable' && value.retry_at*1000>Date.now()) {entry.phase='retry';entry.due=value.retry_at*1000;}
        else if (['read','retry'].includes(phase) && (!value?.display_allowed || value.stale) && (!['not_found','identity_mismatch'].includes(value?.state) || (value.retry_at && value.retry_at*1000<=Date.now())) && response.plex?.state !== 'not_configured' && response.plex?.state !== 'disconnected' && (!value?.retry_at || value.retry_at*1000 <= Date.now())) { entry.phase='resolve'; entry.due=0; }
        else { entry.phase='done'; entry.due=(value?.retry_at || 0)*1000; }
      }
      clearTimeout(leaseTimer);
      if (response?.plex?.state === 'available') leaseTimer=setTimeout(() => {
        if (currentEpoch !== epoch) return;
        hideUnowned(); schedule();
      }, Math.max(0,response.plex.valid_until*1000-Date.now()));
      busy=false; trim(); schedule(50);
      // One shared timer only while pending visible work exists.
      if (!timer && [...entries.values()].some(e=>visible(e)&&e.phase==='poll')) schedule(1000);
    };
    idle(publish);
  }
  return {
    get: (key,identity) => {
      const entry=entries.get(key),value=entry?.value;
      if(identity&&['tmdb_id','imdb_id','plex_guid'].some(f=>identity[f]&&identity[f]!==entry?.identity[f]))return null;
      return value && (value.owned || leaseUntil>Date.now()) ? value : null;
    },
    subscribe(identity, isVisible, listener, expanded=false) {
      let entry=entries.get(identity.key);
      if (!entry) { entry={identity,revision:0,subscribers:new Set(),phase:'read',due:0,polls:0,value:null,expanded}; entries.set(identity.key,entry); }
      else {
        const conflict=['tmdb_id','imdb_id','plex_guid'].some(f=>identity[f]&&entry.identity[f]&&identity[f]!==entry.identity[f]);
        const next=conflict?identity:ratingsIdentity({...entry.identity,...identity});
        if(JSON.stringify(next)!==JSON.stringify(entry.identity)) {entry.revision++;entry.identity=next;entry.value=null;entry.phase='read';entry.due=0;notify(entry);}
      }
      entry.expanded=expanded;
      const sub={visible:isVisible,listener}; entry.subscribers.add(sub); schedule();
      return () => {entry.subscribers.delete(sub);trim();};
    },
    wake() { schedule(); }, invalidate,
    refresh(identities) {
      for(const identity of identities) {
        const entry=entries.get(identity?.key);
        if(!entry)continue;
        entry.revision++;entry.value=null;entry.phase='read';entry.due=0;entry.polls=0;notify(entry);
      }
      schedule();
    },
    revisit() {for(const entry of entries.values()) if(visible(entry)&&entry.phase==='done'&&entry.due<=Date.now()&&(!entry.value?.display_allowed||entry.value.stale||(!entry.value.owned&&leaseUntil<=Date.now()))) {entry.phase='read';entry.polls=0;} schedule();},
    destroy() {destroyed=true;epoch++;clearTimeout(timer);clearTimeout(leaseTimer);entries.clear();}
  };
}
