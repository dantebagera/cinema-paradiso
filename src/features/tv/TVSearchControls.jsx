import { useCallback, useEffect, useState } from 'react';
import { ChevronUp, Filter, RefreshCcw, Search, X } from 'lucide-react';
import { fetchJson } from '../../api/client.js';
import AdvancedSearchBuilder, { IdentityPicker } from '../search/AdvancedSearchBuilder.jsx';
import SearchField from '../search/SearchField.jsx';
import { createEmptyQuery, withCriterion, yearRangeDraft } from '../search/advancedSearchModel.js';

export const emptyTVQuery = (scope) => ({ ...createEmptyQuery(scope), mode: 'simple', media_type: 'tv' });
const sortChoices = { library: [['added','Newly added'],['title','Title'],['rating','Rating'],['year-desc','Year newest'],['year-asc','Year oldest'],['quality','Quality']], discover: [['auto','Default order'],['popularity.desc','Popularity'],['vote_average.desc','Rating'],['vote_count.desc','Most voted'],['primary_release_date.desc','First-air date'],['title.asc','Title A–Z']] };
const resolution = [['4k','4K'],['1080p','1080p'],['720p','720p'],['below-720p','Below 720p'],['upgrade','Upgrade candidates']].map(([id,label])=>({id,label}));
export default function TVSearchControls({ scope, query, status, onStatusChange, onRun, onRefresh, onClear, loading }) {
  const [draft,setDraft] = useState(query), [text,setText] = useState(() => query.groups.find(g=>g.type==='title')?.values[0]?.text || '');
  const [mode,setMode] = useState(query.mode === 'advanced' ? 'advanced' : 'title');
  const [options,setOptions] = useState({}), [error,setError] = useState(''), [retry,setRetry] = useState(0), [years,setYears] = useState(['','']);
  const [filtersOpen, setFiltersOpen] = useState(false);
  useEffect(()=>{setDraft(query);setText(query.groups.find(g=>g.type==='title')?.values[0]?.text || ''); const year=query.groups.find(g=>g.type==='year')?.values[0];setYears(year ? [year.from ?? (year.operator==='at_most' ? '' : year.value),year.to ?? (year.operator==='at_least' ? '' : year.value)] : ['','']);},[query]);
  useEffect(()=>{const controller=new AbortController();fetchJson(`/api/tv/catalog/options?scope=${scope}`,{signal:controller.signal}).then(setOptions).catch(e=>{if(e.name!=='AbortError')setError(e.message);});return ()=>controller.abort();},[scope,retry]);
  const identities=useCallback(async(type,value,context,signal)=>(await fetchJson(`/api/tv/catalog/identities?${new URLSearchParams({scope,type,query:value})}`,{signal})).items,[scope]);
  function catalogForStatus(next){return scope==='discover' && next.groups.some(group=>group.type==='tv_status') ? {...next,feed:'catalog'} : next;}
  function run(next){const ready=catalogForStatus(next);setError('');setDraft(ready);onRun(ready);}
  function criterion(type,value){try {const base={...draft,mode:mode==='advanced'?'advanced':'simple',groups:draft.groups.filter(g=>g.type!==type)};run(value ? withCriterion(base,type,value) : base);}catch(e){setError(e.message);}}
  function reset(){const next=emptyTVQuery(scope);setMode('title');setText('');setYears(['','']);onClear?.();run(next);}
  function search(){if(mode==='title')criterion('title',text.trim()?{text:text.trim()}:null);else run(draft);}
  function changeMode(next){
    if(next==='advanced' && mode==='title'){
      try {
        const base={...draft,mode:'advanced',groups:draft.groups.filter(group=>group.type!=='title')};
        setDraft(text.trim()?withCriterion(base,'title',{text:text.trim()}):base);
      } catch(e){setError(e.message);return;}
    } else setDraft({...draft,mode:next==='advanced'?'advanced':'simple'});
    setMode(next);
  }
  function select(type,label,choices){return <select aria-label={`TV ${label}`} value={draft.groups.find(g=>g.type===type)?.values[0]?.id || ''} onChange={e=>criterion(type,choices.find(v=>v.id===e.target.value)||null)}><option value="">All {label.toLowerCase()}</option>{choices.map(v=><option key={v.id} value={v.id}>{v.label}</option>)}</select>;}
  function changeYear(index,value){const next=[...years];next[index]=value;setYears(next);const range=yearRangeDraft(...next);setError(range.error);if(range.ready)criterion('year',next[0]&&next[1]?{operator:'between',from:Number(next[0]),to:Number(next[1])}:next[0]?{operator:'at_least',value:Number(next[0])}:next[1]?{operator:'at_most',value:Number(next[1])}:null);}
  const viewingFilter = () => select('viewing_status','Viewing states',[{id:'watched',label:'Watched'},{id:'unwatched',label:'Unwatched'},{id:'in_progress',label:'In progress'},{id:'watchlist',label:'Watchlist'}]);
  const hasDiscoverFilters = draft.groups.length > 0 || draft.feed !== 'trending_week' || draft.sort.key !== 'auto';
  return <div className="tv-search-controls">
    <form className={`${scope==='library'?'library-search-panel':'discover-search-panel'} tv-search-panel`} data-people-search={scope==='library'||undefined} onSubmit={e=>{e.preventDefault();search();}}>
      {mode==='advanced' ? <AdvancedSearchBuilder mediaType="tv" scope={scope} query={draft} onChange={next=>setDraft(catalogForStatus(next))} onRun={()=>run(draft)} onReset={reset} options={options} searchIdentities={identities} loading={loading}/> : mode==='title' ? <SearchField className={scope==='library'?'library-main-search':'discover-main-search'}><Search size={17}/><input aria-label="Search TV shows" placeholder={scope==='library'?'Search your TV library…':'Search TV shows…'} value={text} onChange={e=>setText(e.target.value)}/></SearchField> : <IdentityPicker scope={scope} type={mode} searchIdentities={identities} onPick={value=>{const next=withCriterion(draft,mode,mode==='person'?{...value,role:'actor'}:value);setMode('advanced');run({...next,mode:'advanced'});}}/>}
      <select aria-label="TV search type" value={mode} onChange={e=>changeMode(e.target.value)}><option value="title">TV shows</option><option value="person">People</option><option value="keyword">Keywords</option><option value="advanced">Advanced</option></select>
      <button type="submit" className={`btn btn-primary ${scope==='library'?'library-search-submit':'discover-search-submit'}${mode==='advanced'?' advanced-search-submit':''}`} aria-label="Search TV"><Search size={16}/>Search</button>
    </form>
    {scope === 'library' && !filtersOpen ? <div className="library-toolbar library-filter-toolbar library-filter-toolbar-collapsed">
      <span>Filters collapsed: resolution, source, genre, viewing state, status, country, year, rating, sort</span>
      <button type="button" className="btn btn-secondary library-filter-icon-button" onClick={() => setFiltersOpen(true)} aria-label="Open filters" title="Open filters"><Filter size={17}/></button>
    </div> : <div className={scope === 'discover' ? 'discover-toolbar tv-discover-toolbar' : 'library-toolbar library-filter-toolbar library-filter-toolbar-tv'}>
      {scope === 'discover' && <>
        <select aria-label="TV Discover feed" value={draft.feed} onChange={e=>run({...draft,feed:e.target.value,groups:e.target.value==='catalog'?draft.groups:draft.groups.filter(group=>group.type!=='tv_status')})}>{[['trending_week','Trending week'],['trending_today','Trending today'],['popular','Popular'],['top_rated','Top rated'],['now_playing','On the air'],['upcoming','Airing today'],['catalog','Catalog']].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select>
        {select('availability','Ownership',[{id:'owned',label:'Available locally'},{id:'unowned',label:'Not owned'}])}
      </>}
      {scope === 'library' && <>{select('resolution','Resolutions',resolution)}{select('library_source','Sources',options.library_source||[])}</>}
      {select('genre','Genres',options.genre||[])}
      {scope === 'library' && viewingFilter()}
      {scope === 'discover' && <>{select('tv_status','Series status',options.tv_status||[])}{select('country','Countries',options.country||[])}{viewingFilter()}</>}
      {scope === 'library' && <>
        <select aria-label="TV Status" value={status} onChange={e=>onStatusChange(e.target.value)}><option value="">All statuses</option>{['Continuing','Ended','Limited Series','Status Unknown'].map(value=><option key={value} value={value}>{value}</option>)}</select>
        {select('country','Countries',options.country||[])}
      </>}
      {scope === 'discover' && <select aria-label="TV minimum votes" value={draft.groups.find(g=>g.type==='minimum_votes')?.values[0]?.value||''} onChange={e=>criterion('minimum_votes',e.target.value?{value:Number(e.target.value)}:null)}><option value="">Any votes</option>{[500,1000,5000,10000].map(n=><option key={n} value={n}>{n}+ votes</option>)}</select>}
      <input className="library-mini-input" aria-label="TV year from" placeholder="Year from" title="Series first-air year" value={years[0]} onChange={e=>changeYear(0,e.target.value)} maxLength={4}/>
      <input className="library-mini-input" aria-label="TV year to" placeholder="Year to" value={years[1]} onChange={e=>changeYear(1,e.target.value)} maxLength={4}/>
      <select aria-label="TV minimum rating" value={draft.groups.find(g=>g.type==='rating')?.values[0]?.value||''} onChange={e=>criterion('rating',e.target.value?{operator:'at_least',value:Number(e.target.value)}:null)}><option value="">Any rating</option>{[6,7,8,8.5].map(n=><option key={n} value={n}>{n}+</option>)}</select>
      <select aria-label="Sort TV shows" value={draft.sort.key} onChange={e=>run({...draft,sort:{key:e.target.value,direction:['title','title.asc','year-asc'].includes(e.target.value)?'asc':'desc'}})}>{sortChoices[scope].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select>
      {scope === 'library' ? <>
        <button type="button" className="btn btn-secondary library-filter-icon-button library-hide-filters" onClick={() => setFiltersOpen(false)} aria-label="Hide filters" title="Hide filters"><ChevronUp size={18}/></button>
        <button type="button" className="btn btn-secondary library-filter-icon-button library-reset-filters" onClick={reset} aria-label="Reset filters" title="Reset filters"><RefreshCcw size={17}/></button>
      </> : <>
        <button type="button" className="btn btn-secondary discover-toolbar-icon-button" onClick={onRefresh} aria-label="Refresh TV results" title="Refresh"><RefreshCcw size={17}/></button>
        {hasDiscoverFilters && <button type="button" className="btn btn-secondary discover-toolbar-icon-button" onClick={reset} aria-label="Reset Discover filters" title="Reset filters"><X size={17}/></button>}
      </>}
    </div>}
    {error && <p role="alert">{error} <button onClick={()=>setRetry(n=>n+1)}>Retry choices</button></p>}
  </div>;
}
