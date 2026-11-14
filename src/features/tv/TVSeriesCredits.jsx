import { useEffect, useId, useMemo, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { fetchJson } from '../../api/client.js';
import HorizontalCardRail from '../../components/HorizontalCardRail.jsx';
import { PersonCreditCard } from '../../components/PersonCreditCard.jsx';

const portraitCache = new Map();
const creativeKinds = new Set(['director', 'creator']);

function portraitFor(id) {
  const cached = portraitCache.get(id);
  if (cached && cached.expires > Date.now()) return cached.promise;
  if (portraitCache.size >= 200) portraitCache.delete(portraitCache.keys().next().value);
  const entry = { expires: Date.now() + 15 * 60_000 };
  entry.promise = fetchJson(`/api/tmdb/person?person_id=${encodeURIComponent(id)}`)
    .then(person => person.profile_url || '')
    .catch(() => { entry.expires = Date.now() + 30_000; return ''; });
  portraitCache.set(id, entry);
  return entry.promise;
}

function groupCredits(credits) {
  const grouped = new Map();
  for (const credit of credits) {
    const key = credit.tmdb_id || credit.name;
    const previous = grouped.get(key);
    if (previous) {
      previous.roles = [...new Set([...previous.roles, credit.role || credit.kind])];
      previous.portrait_url ||= credit.portrait_url;
      if (credit.kind === 'director') previous.kind = 'director';
    } else grouped.set(key, { ...credit, roles: [credit.role || credit.kind] });
  }
  return [...grouped.values()].map(credit => ({ ...credit, role: credit.roles.join(' · ') }));
}

export default function TVSeriesCredits({ series, onPersonCredits, onBio }) {
  const fullCreditId = useId();
  const credits = series.cast || [];
  const groups = useMemo(() => ({
    creative: groupCredits(credits.filter(credit => creativeKinds.has(credit.kind))),
    crew: groupCredits(credits.filter(credit => credit.kind && credit.kind !== 'actor' && !creativeKinds.has(credit.kind))),
    actors: credits.filter(credit => !credit.kind || credit.kind === 'actor'),
  }), [credits]);
  const [portraits, setPortraits] = useState({});

  useEffect(() => {
    let cancelled = false;
    const pending = [...new Set([...groups.creative, ...groups.crew]
      .filter(credit => credit.tmdb_id && !credit.portrait_url).map(credit => credit.tmdb_id))];
    async function worker() {
      while (!cancelled && pending.length) {
        const id = pending.shift();
        const url = await portraitFor(id);
        if (!cancelled && url) setPortraits(previous => ({ ...previous, [id]: url }));
      }
    }
    const workerCount = Math.min(4, pending.length);
    for (let i = 0; i < workerCount; i++) void worker();
    return () => { cancelled = true; };
  }, [groups]);

  function card(credit, index) {
    const person = { ...credit, id: credit.tmdb_id, profile_url: credit.portrait_url || portraits[credit.tmdb_id], character: credit.role };
    return <PersonCreditCard key={`${credit.tmdb_id || credit.name}-${credit.role}-${index}`} person={person} role={credit.kind || 'actor'}
      canBrowse={Boolean(credit.tmdb_id && onPersonCredits)} onBrowse={onPersonCredits} onDiscover={onPersonCredits} onBio={onBio} />;
  }

  return <section aria-label="Series cast" className="tv-main-cast">
    {(groups.creative.length > 0 || groups.crew.length > 0) &&
      <details className="tv-full-credit" key={series.tmdb_id || series.id}>
        <summary role="button" aria-controls={fullCreditId}>Full Credit <ChevronDown size={16} /></summary>
        <div id={fullCreditId} className="tv-full-credit-body">
          {[[groups.creative, 'Directors and creators'], [groups.crew, 'Writers and crew']].map(([people, label]) => people.length > 0 &&
            <section key={label} className="tv-creative-credits" aria-label={label}>
              <span className="mini-label">{label}</span>
              <div className="tv-creative-credits-grid">{people.map(card)}</div>
            </section>)}
        </div>
      </details>}
    {groups.actors.length ? <HorizontalCardRail label="cast" className="credit-card-rail" trackClassName="movie-expanded-people-grid" arrowPlacement="edges" resetKey={series.tmdb_id}
      header={<span className="mini-label">Actors</span>}>{groups.actors.map(card)}</HorizontalCardRail>
      : <p>{series.metadata_notice ? 'Cast could not be loaded.' : 'No cast information available.'}</p>}
  </section>;
}
