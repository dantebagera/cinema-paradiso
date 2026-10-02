import { positiveAwards } from '../api/movieAwards.js';

const labels = {oscar:'Oscars',golden_globe:'Golden Globe'};
export function MovieAwards({counts,person=false,onAwardDiscover}) {
  const pairs = positiveAwards(counts);
  if (!pairs.length) return null;
  return <span className={`movie-awards${person ? ' movie-awards-person' : ''}`} dir="ltr">
    {pairs.map(([award,count]) => {
      const content = <><strong>{count}</strong><img src={`/static/movie-awards/${award}.png`} alt="" /></>;
      const props = {className:`movie-award-pair movie-award-${award}`,title:labels[award],'data-award':award};
      return person && onAwardDiscover
        ? <button key={award} type="button" {...props} aria-label={labels[award]} onClick={event => {event.stopPropagation();onAwardDiscover(award);}}>{content}</button>
        : <span key={award} {...props}>{content}</span>;
    })}
  </span>;
}
