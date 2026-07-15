import {
  Bookmark,
  Clapperboard,
  Download,
  Film,
  Info,
  Play,
  Search,
  Star,
  Wand2,
} from 'lucide-react'
import { cx } from '../../utils/appUtils.js'

export default function CardLab() {
  const compactCards = cardLabMovies.filter((movie) => !movie.expanded);
  const expandedCards = cardLabMovies.filter((movie) => movie.expanded);

  return (
    <main className="card-lab-page">
      <section className="card-lab-hero">
        <div>
          <span className="card-lab-kicker">Internal prototype</span>
          <h1>Unified movie card anatomy</h1>
          <p>
            Static design lab for comparing owned, low-quality, discover, and indexer states before production cards are changed.
          </p>
        </div>
        <div className="card-lab-legend" aria-label="Card anatomy">
          {['Poster', 'Title', 'Metadata chips', 'Plot', 'People', 'Actions'].map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
      </section>

      <CardLabSection title="Compact Cards" description="Same footprint and hierarchy with state-specific actions only.">
        <div className="card-lab-grid card-lab-grid-compact">
          {compactCards.map((movie) => (
            <CardLabMovieCard key={movie.id} movie={movie} />
          ))}
        </div>
      </CardLabSection>

      <CardLabSection title="Expanded Cards" description="Larger poster, readable plot, compact metadata, and stronger people presentation.">
        <div className="card-lab-grid card-lab-grid-expanded">
          {expandedCards.map((movie) => (
            <CardLabMovieCard key={movie.id} movie={movie} expanded />
          ))}
        </div>
      </CardLabSection>
    </main>
  );
}

function CardLabSection({ title, description, children }) {
  return (
    <section className="card-lab-section">
      <div className="card-lab-section-heading">
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {children}
    </section>
  );
}

function CardLabMovieCard({ movie, expanded = false }) {
  const actionIcons = {
    Play,
    Trailer: Clapperboard,
    'Find sources': Search,
    Upgrade: Wand2,
    Follow: Bookmark,
    Torrent: Download,
    Details: Info
  };

  return (
    <article className={cx('card-lab-card', expanded && 'card-lab-expanded', `card-lab-status-${movie.statusTone}`)}>
      <div className="card-lab-poster">
        {movie.poster ? <img src={movie.poster} alt={`${movie.title} poster`} /> : <CardLabPosterFallback title={movie.title} />}
      </div>

      <div className="card-lab-content">
        <header className="card-lab-card-header">
          <div>
            <h3>{movie.title}</h3>
            <div className="card-lab-subline">
              <span>{movie.year}</span>
              <span><Star size={15} /> {movie.rating}</span>
            </div>
          </div>
          <span className="card-lab-status">{movie.status}</span>
        </header>

        <div className="card-lab-chip-row" aria-label="Movie metadata">
          {movie.metadata.map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>

        <p className="card-lab-plot">{movie.plot}</p>

        {expanded && (
          <div className="card-lab-expanded-body">
            <div className="card-lab-director">
              <span className="card-lab-label">Director</span>
              <button type="button" className="card-lab-person-card">
                <CardLabAvatar person={movie.director} />
                <span>
                  <strong>{movie.director.name}</strong>
                  <small>{movie.director.role}</small>
                </span>
              </button>
            </div>

            <div className="card-lab-cast">
              <span className="card-lab-label">Top cast</span>
              <div className="card-lab-cast-grid">
                {movie.cast.slice(0, 6).map((person) => (
                  <button type="button" className="card-lab-cast-person" key={`${movie.id}-${person.name}`}>
                    <CardLabAvatar person={person} />
                    <span>
                      <strong>{person.name}</strong>
                      <small>{person.role}</small>
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="card-lab-collection">
              <Film size={16} />
              <span>{movie.collection}</span>
            </div>
          </div>
        )}

        {!expanded && (
          <div className="card-lab-mini-people">
            <CardLabAvatar person={movie.director} />
            {movie.cast.slice(0, 3).map((person) => <CardLabAvatar key={person.name} person={person} />)}
          </div>
        )}

        <div className="card-lab-actions">
          {movie.actions.map((action) => {
            const Icon = actionIcons[action] || Info;
            return (
              <button type="button" key={action} className={cx('card-lab-action', action === 'Upgrade' && 'card-lab-action-warning', action === 'Play' && 'card-lab-action-primary')}>
                <Icon size={16} />
                <span>{action}</span>
              </button>
            );
          })}
        </div>
      </div>
    </article>
  );
}

function CardLabAvatar({ person }) {
  const initials = String(person?.name || '?')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase();

  return (
    <span className="card-lab-avatar" aria-hidden="true">
      <span>{initials}</span>
      {person?.photo ? (
        <img
          src={person.photo}
          alt=""
          onError={(event) => {
            event.currentTarget.style.display = 'none';
          }}
        />
      ) : null}
    </span>
  );
}

function CardLabPosterFallback({ title }) {
  return (
    <div className="card-lab-poster-fallback">
      <Film size={34} />
      <span>{title}</span>
    </div>
  );
}


const cardLabMovies = [
  {
    id: 'owned-compact',
    section: 'Compact Cards',
    title: 'Interstellar',
    year: '2014',
    rating: '8.7',
    status: 'Owned',
    statusTone: 'owned',
    poster: 'https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg',
    plot: 'A pilot crosses space and time to find a future for humanity while the life he left behind keeps slipping away.',
    metadata: ['1080p', 'BluRay', 'EN', 'US', 'Sci-Fi', 'Adventure'],
    director: { name: 'Christopher Nolan', role: 'Director', photo: 'https://image.tmdb.org/t/p/w185/xuAIuYSmsUzKlUMBFGVZaWsY3DZ.jpg' },
    cast: [
      { name: 'Matthew McConaughey', role: 'Cooper', photo: 'https://image.tmdb.org/t/p/w185/wJiGedOCZhwMx9DezY8uwbNxmAY.jpg' },
      { name: 'Anne Hathaway', role: 'Brand', photo: 'https://image.tmdb.org/t/p/w185/s6tflSD20MGz04ZR2R1lZvhmC4Y.jpg' },
      { name: 'Jessica Chastain', role: 'Murph', photo: 'https://image.tmdb.org/t/p/w185/lodMzLKSdrPcBry6TdoDsMN3Vge.jpg' }
    ],
    collection: 'Nolan science fiction shelf',
    actions: ['Play', 'Trailer', 'Find sources', 'Details']
  },
  {
    id: 'upgrade-compact',
    section: 'Compact Cards',
    title: 'Princess Mononoke',
    year: '1997',
    rating: '8.3',
    status: 'Low quality',
    statusTone: 'warning',
    poster: 'https://image.tmdb.org/t/p/w500/cMYCDADoLKLbB83g4WnJegaZimC.jpg',
    plot: 'A prince enters a war between forest spirits and humans, where survival depends on seeing both wounds clearly.',
    metadata: ['480p', 'DVD', 'JA', 'JP', 'Animation', 'Fantasy'],
    director: { name: 'Hayao Miyazaki', role: 'Director', photo: 'https://image.tmdb.org/t/p/w185/mG3cfxtA5jqDc7fpKgyzZMKoXDh.jpg' },
    cast: [
      { name: 'Yoji Matsuda', role: 'Ashitaka', photo: '' },
      { name: 'Yuriko Ishida', role: 'San', photo: '' },
      { name: 'Yuko Tanaka', role: 'Eboshi', photo: '' }
    ],
    collection: 'Studio Ghibli',
    actions: ['Play', 'Trailer', 'Upgrade', 'Details']
  },
  {
    id: 'discover-compact',
    section: 'Compact Cards',
    title: 'Dune: Part Two',
    year: '2024',
    rating: '8.1',
    status: 'Not owned',
    statusTone: 'neutral',
    poster: 'https://image.tmdb.org/t/p/w500/1pdfLvkbY9ohJlCjQH2CZjjYVvJ.jpg',
    plot: 'Paul Atreides unites with Chani and the Fremen while choosing between love, revenge, and a terrible future.',
    metadata: ['4K', 'WEB-DL', 'EN', 'US', 'Sci-Fi', 'Drama'],
    director: { name: 'Denis Villeneuve', role: 'Director', photo: 'https://image.tmdb.org/t/p/w185/8WUVHemHFH2ZIP6NWkwlHWsyrEL.jpg' },
    cast: [
      { name: 'Timothee Chalamet', role: 'Paul', photo: 'https://image.tmdb.org/t/p/w185/BE2sdjpgsa2rNTFa66f7upkaOP.jpg' },
      { name: 'Zendaya', role: 'Chani', photo: 'https://image.tmdb.org/t/p/w185/3WdOloHpjtjL96uVOhFRRCcYSwq.jpg' },
      { name: 'Rebecca Ferguson', role: 'Jessica', photo: 'https://image.tmdb.org/t/p/w185/lJloTOheuQSirSLXNA3JHsrMNfH.jpg' }
    ],
    collection: 'Dune Collection',
    actions: ['Trailer', 'Find sources', 'Follow', 'Details']
  },
  {
    id: 'indexer-compact',
    section: 'Compact Cards',
    title: 'Civil War',
    year: '2024',
    rating: '6.9',
    status: 'Indexer',
    statusTone: 'source',
    poster: 'https://image.tmdb.org/t/p/w500/sh7Rg8Er3tFcN9BpKIPOMvALgZd.jpg',
    plot: 'A team of journalists races across a fractured country to document the final days of a collapsing order.',
    metadata: ['2160p', 'WEBRip', 'EN', 'US', 'Drama', 'Thriller'],
    director: { name: 'Alex Garland', role: 'Director', photo: 'https://image.tmdb.org/t/p/w185/1UKNef590A0ZaMnxsscIcWuK1Em.jpg' },
    cast: [
      { name: 'Kirsten Dunst', role: 'Lee', photo: 'https://image.tmdb.org/t/p/w185/wBXvh6PJd0IUVNpvatPC1kzuHtm.jpg' },
      { name: 'Wagner Moura', role: 'Joel', photo: 'https://image.tmdb.org/t/p/w185/9j8W2mT5f5kN9ZbkuG6Ywtcnl7P.jpg' },
      { name: 'Cailee Spaeny', role: 'Jessie', photo: 'https://image.tmdb.org/t/p/w185/30PZqK3ZaxA3n8K8rVw9qFZ8nYz.jpg' }
    ],
    collection: 'A24 shelf',
    actions: ['Trailer', 'Torrent', 'Details']
  },
  {
    id: 'owned-expanded',
    section: 'Expanded Cards',
    title: 'Alien',
    year: '1979',
    rating: '8.2',
    status: 'Owned',
    statusTone: 'owned',
    expanded: true,
    poster: 'https://image.tmdb.org/t/p/w500/vfrQk5IPloGg1v9Rzbh2Eg3VGyM.jpg',
    plot: 'The crew of the Nostromo answers a distress signal and brings aboard a lifeform that turns a silent industrial ship into a closed corridor nightmare.',
    metadata: ['1080p', 'BluRay', 'EN', 'UK/US', 'Horror', 'Sci-Fi'],
    director: { name: 'Ridley Scott', role: 'Director', photo: 'https://image.tmdb.org/t/p/w185/zABJmN9opmqD4orWl3KSdCaSo7Q.jpg' },
    cast: [
      { name: 'Sigourney Weaver', role: 'Ripley', photo: 'https://image.tmdb.org/t/p/w185/flfhep27iBxseZIlxOMHt6zJFX1.jpg' },
      { name: 'Tom Skerritt', role: 'Dallas', photo: 'https://image.tmdb.org/t/p/w185/gf5GyG6YrC0PbLjV3EqPk4VrKQh.jpg' },
      { name: 'Veronica Cartwright', role: 'Lambert', photo: 'https://image.tmdb.org/t/p/w185/8A1sF2WpFZ0qXrYGEldlN10REuD.jpg' },
      { name: 'Harry Dean Stanton', role: 'Brett', photo: 'https://image.tmdb.org/t/p/w185/mjP44mGZgG8G4kQ3JtV2zLQqpzQ.jpg' },
      { name: 'John Hurt', role: 'Kane', photo: 'https://image.tmdb.org/t/p/w185/rpuH2YRLpxJjMxHq4T1Qz6YQlG5.jpg' },
      { name: 'Ian Holm', role: 'Ash', photo: 'https://image.tmdb.org/t/p/w185/zdqBeiL7qH3fUPBVjLfrJ6C9kJg.jpg' }
    ],
    collection: 'Alien Collection',
    actions: ['Play', 'Trailer', 'Find sources', 'Details']
  },
  {
    id: 'discover-expanded',
    section: 'Expanded Cards',
    title: 'Furiosa: A Mad Max Saga',
    year: '2024',
    rating: '7.5',
    status: 'Not owned',
    statusTone: 'neutral',
    expanded: true,
    poster: 'https://image.tmdb.org/t/p/w500/iADOJ8Zymht2JPMoy3R7xceZprc.jpg',
    plot: 'A young Furiosa is taken from the Green Place and pulled through the power games of a wasteland where every alliance has a price.',
    metadata: ['4K', 'WEB-DL', 'EN', 'AU/US', 'Action', 'Adventure'],
    director: { name: 'George Miller', role: 'Director', photo: 'https://image.tmdb.org/t/p/w185/fn8G1rj5dvkSkwu7Ejw7P2QX4X6.jpg' },
    cast: [
      { name: 'Anya Taylor-Joy', role: 'Furiosa', photo: 'https://image.tmdb.org/t/p/w185/jquY7wUp4HQuJkP8XdxJXm9xA2x.jpg' },
      { name: 'Chris Hemsworth', role: 'Dementus', photo: 'https://image.tmdb.org/t/p/w185/jpurJ9jAcLCYjgHHfYF32m3zJYm.jpg' },
      { name: 'Tom Burke', role: 'Praetorian Jack', photo: 'https://image.tmdb.org/t/p/w185/6BqKkNF3c7HJRwVXw8RY9vqE7Lu.jpg' },
      { name: 'Alyla Browne', role: 'Young Furiosa', photo: '' },
      { name: 'Lachy Hulme', role: 'Immortan Joe', photo: '' },
      { name: 'John Howard', role: 'The People Eater', photo: '' }
    ],
    collection: 'Mad Max Collection',
    actions: ['Trailer', 'Find sources', 'Follow', 'Details']
  },
  {
    id: 'indexer-expanded',
    section: 'Expanded Cards',
    title: 'The Matrix',
    year: '1999',
    rating: '8.2',
    status: 'Indexer',
    statusTone: 'source',
    expanded: true,
    poster: 'https://image.tmdb.org/t/p/w500/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg',
    plot: 'A programmer discovers the world around him is a simulation and joins a rebellion that turns doubt, control, and choice into weapons.',
    metadata: ['2160p', 'BluRay', 'EN', 'US/AU', 'Action', 'Sci-Fi'],
    director: { name: 'The Wachowskis', role: 'Directors', photo: '' },
    cast: [
      { name: 'Keanu Reeves', role: 'Neo', photo: 'https://image.tmdb.org/t/p/w185/4D0PpNI0kmP58hgrwGC3wCjxhnm.jpg' },
      { name: 'Laurence Fishburne', role: 'Morpheus', photo: 'https://image.tmdb.org/t/p/w185/8suOhUmPbfKqDQ17jQ1Gy0mI3P4.jpg' },
      { name: 'Carrie-Anne Moss', role: 'Trinity', photo: 'https://image.tmdb.org/t/p/w185/xD4jTA3KmVp5Rq3aHcymL9DUGjD.jpg' },
      { name: 'Hugo Weaving', role: 'Agent Smith', photo: 'https://image.tmdb.org/t/p/w185/8HLQLILZLhDQWO6JDpvY6XJLH75.jpg' },
      { name: 'Joe Pantoliano', role: 'Cypher', photo: 'https://image.tmdb.org/t/p/w185/2cyKk5vlXUJsF8d2Dct1xgLe7sB.jpg' },
      { name: 'Gloria Foster', role: 'Oracle', photo: '' }
    ],
    collection: 'The Matrix Collection',
    actions: ['Trailer', 'Torrent', 'Details']
  }
];







