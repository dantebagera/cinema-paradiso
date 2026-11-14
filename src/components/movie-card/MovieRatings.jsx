import Tooltip from '../Tooltip.jsx';
import {useMovieRatings} from '../../contexts/MovieRatingsContext.jsx';
import {RottenTomatoesIcon} from './RottenTomatoesIcons.jsx';

export function MovieRatings({identity, cardRef, expanded=false}) {
  const value=useMovieRatings(identity,cardRef,expanded);
  const allowed=Boolean(value?.display_allowed);
  const date=value?.retrieved_at ? new Date(value.retrieved_at*1000).toLocaleString() : '';
  return <span className={`movie-rt-pair${expanded?' movie-rt-expanded':''}`} aria-hidden={!allowed||undefined} data-rt-visible={allowed}>
    {allowed ? ['critics','audience'].map(type=>{
      const score=value[type];
      const valid=Number.isInteger(score)&&score>=0&&score<=100;
      const kind=type==='critics'?(score>=60?'fresh':'rotten'):(score>=60?'upright':'spilled');
      const label=valid?`Rotten Tomatoes® ${type}: ${score}%`:`No ${type} score available`;
      return <Tooltip key={type} title={label} description={`${value.owned?'Saved in CP':'Via Plex'}${date?` · Retrieved ${date}`:''}`}>
        <span className="movie-rt-score" data-movie-rating tabIndex={0} aria-label={label} onClick={e=>e.stopPropagation()} onKeyDown={e=>e.stopPropagation()}>
          {expanded?<small>{type==='critics'?'Critics':'Audience'}</small>:null}
          <span>{valid?<RottenTomatoesIcon kind={kind}/>:null}<strong>{valid?`${score}%`:'—'}</strong></span>
        </span>
      </Tooltip>;
    }):null}
  </span>;
}
