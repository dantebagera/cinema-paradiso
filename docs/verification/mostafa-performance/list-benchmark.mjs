import { filterListRows as after, emptyListFilters } from '../../../src/utils/listCatalogFilters.js';
import { movieGenres } from '../../../src/utils/catalogFilterOptions.js';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
// The frozen PR inventory omits unchanged dependency files. Resolve its imports
// to the preserved current dependencies without editing the frozen evidence.
const frozen=fs.readFileSync(new URL('../../../.superpowers/sdd/mostafa-ui-ux/pr-head/src/utils/listCatalogFilters.js',import.meta.url),'utf8');
const source=frozen.replace(/from (['"])(\.\.?\/[^'"]+)\1/g,(_,quote,specifier)=>`from '${new URL(specifier,new URL('../../../src/utils/listCatalogFilters.js',import.meta.url)).href}'`);
const {filterListRows:before}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const rows=Array.from({length:10000},(_,id)=>({id,movie:{title:`Movie ${id}`,canonical_metadata:{title:`Movie ${id}`,genre_ids:[16],country:'US',tmdb_rating:8,tmdb_vote_count:5000,release_date:'2021-07-08',popularity:(id*7919)%10000,...Object.fromEntries(Array.from({length:30},(_,n)=>[`field${n}`,`value${n}`]))}}}));
const scenarios=[['default',emptyListFilters()],['filtered-sort',{...emptyListFilters(),genre:'16',country:'US',minVotes:'1000',minRating:'7',yearFrom:'2020',yearTo:'2023',sort:'popularity.desc'}]];
const results=[];
for(const [name,filters] of scenarios) {
  const output={scenario:name,rows:rows.length};
  let expected;
  for(const [label,filter] of [['before',before],['after',after]]) {
    const times=[];let reads;
    for(let n=0;n<6;n++) {
      reads=0;const start=performance.now();
      const result=filter(rows,filters,movieGenres,row=>{reads++;return {...row.movie,...row.movie.canonical_metadata};});
      if(n)times.push(performance.now()-start);
      const identities=result.map(row=>row.id);
      if(label==='before')expected=identities;
      else if(JSON.stringify(identities)!==JSON.stringify(expected))throw new Error('Membership/order changed');
    }
    output[label]={medianMs:times.sort((a,b)=>a-b)[2],metadataReads:reads};
  }
  results.push(output);
}
fs.writeFileSync(fileURLToPath(new URL('./list-benchmark-independent.json',import.meta.url)),JSON.stringify(results,null,2));
console.log(JSON.stringify(results,null,2));
