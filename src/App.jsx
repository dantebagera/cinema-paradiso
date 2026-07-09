import {
  AlertTriangle,
  Bell,
  Bookmark,
  Bot,
  Check,
  CheckCircle2,
  Clapperboard,
  CirclePlus,
  Compass,
  Copy,
  Database,
  Download,
  Eye,
  EyeOff,
  ExternalLink,
  Film,
  Folder,
  HardDrive,
  Home,
  Info,
  Library,
  Link as LinkIcon,
  Loader2,
  MonitorPlay,
  MoreVertical,
  Pencil,
  Play,
  PlugZap,
  Radio,
  RefreshCcw,
  Save,
  ScanSearch,
  Search,
  Server,
  Settings,
  ShieldCheck,
  Sparkles,
  Star,
  Trash2,
  Wand2,
  X
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import headerCropUrl from './assets/header.png';
import logoUrl from './assets/logo.svg';
import motifCropUrl from './assets/styleguide-motif-crop.png';
import MetadataAuthorityPanel from './components/MetadataAuthorityPanel.jsx';
import IdentityReviewPanel from './components/IdentityReviewPanel.jsx';
import MetadataCorrectionModal from './components/MetadataCorrectionModal.jsx';
import PosterEditorModal from './components/PosterEditorModal.jsx';
import { SmartMatchControls, SmartMatchReviewModal } from './components/SmartMatchPanel.jsx';
import { UnifiedMovieCard } from './components/movie-card/MovieCard.jsx';
import {
  cx,
  formatCount,
  getUniqueOptions,
  movieKey,
  sectionFromPath,
  sortFollowedReleases,
  buildStreamTemplateUrl,
  streamTemplateTokens,
  toYouTubeEmbedUrl,
  topBarSearchEnabled,
  torrentPrimaryAction,
  torrentSizeBytes,
  youtubeTrailerSearchUrl
} from './utils/appUtils.js';
import {
  filterIdentityReviewItems,
  filterCleanupItems,
  filterUnmatchedItems,
  metadataStatusChipClass,
  metadataStatusLabel,
  renameModalItem
} from './utils/cleanupUtils.js';
import {
  buildOwnershipMap,
  discoverMoviePayload,
  filterEnrichedIndexerResults,
  listsForDiscoverMovie,
  ownedMovieFor,
  sortTorrentVariants
} from './discoverUtils.js';
import {
  applyPosterOverrideToLibraryItems,
  buildLibraryViewModel,
  buildMovieListViewModel,
  getMovieIdentity,
  getQualityLabel,
  getLocaleTag,
  getRolePeople,
  getTmdbCacheKey,
  isLowQuality,
  listLibraryCoverage,
  listsForItem,
  movieHasSystemState,
  movieIdentityKey,
  moviePayload,
  resolutionRank,
  rootLabel
} from './utils/libraryUtils.js';

const navItems = [
  {
    id: 'home',
    label: 'Home',
    icon: Home,
    accent: 'gold'
  },
  {
    id: 'library',
    label: 'Library',
    icon: Library,
    accent: 'blue'
  },
  {
    id: 'movie-lists',
    label: 'Movie Lists',
    icon: Bookmark,
    accent: 'gold'
  },
  {
    id: 'cleanup',
    label: 'Cleanup',
    icon: ShieldCheck,
    accent: 'amber'
  },
  {
    id: 'discover',
    label: 'Discover',
    icon: Compass,
    accent: 'violet'
  },
  {
    id: 'ai-control',
    label: 'AI Control',
    icon: Bot,
    accent: 'violet',
    experimental: true
  },
  {
    id: 'downloads',
    label: 'Downloads',
    icon: Download,
    accent: 'gold'
  },
  {
    id: 'help',
    label: 'Help',
    icon: Info,
    accent: 'gold'
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: Settings,
    accent: 'cyan'
  }
];

const APP_VERSION = `v${import.meta.env.VITE_APP_VERSION || '0.0.0'}`;

const fallbackMovies = [
  {
    tmdb_id: 155,
    title: 'The Dark Knight',
    year: '2008',
    genres: ['Action', 'Crime', 'Drama'],
    tmdb_rating: '9.0',
    language: 'English',
    country: 'US',
    country_flag: 'US',
    plot: 'Batman raises the stakes in Gotham as a criminal mastermind forces the city to confront chaos, loyalty, and the cost of order.',
    poster_url: ''
  },
  {
    tmdb_id: 27205,
    title: 'Inception',
    year: '2010',
    genres: ['Action', 'Science Fiction'],
    tmdb_rating: '8.4',
    language: 'English',
    country: 'US',
    country_flag: 'US',
    plot: 'A thief who steals secrets through shared dreams is offered a chance to erase his past by planting an idea in a target mind.',
    poster_url: ''
  },
  {
    tmdb_id: 129,
    title: 'Spirited Away',
    year: '2001',
    genres: ['Animation', 'Fantasy'],
    tmdb_rating: '8.5',
    language: 'Japanese',
    country: 'JP',
    country_flag: 'JP',
    plot: 'A young girl enters a mysterious spirit world and must find courage, patience, and a way back to her family.',
    poster_url: ''
  }
];

function playReleaseAlertSound() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();
    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(740, ctx.currentTime);
    oscillator.frequency.setValueAtTime(980, ctx.currentTime + 0.12);
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.12, ctx.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.34);
    oscillator.connect(gain);
    gain.connect(ctx.destination);
    oscillator.start();
    oscillator.stop(ctx.currentTime + 0.36);
    window.setTimeout(() => ctx.close().catch(() => {}), 520);
  } catch {
    // Browsers may block startup audio until the user interacts with the page.
  }
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const raw = await response.text();
  let data = {};
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      if (response.ok) {
        throw new Error('Failed to parse response JSON');
      }
      data = {};
    }
  }
  if (!response.ok || data.error) {
    const error = new Error(data.error || `Request failed: ${response.status}`);
    error.data = data;
    error.status = response.status;
    throw error;
  }
  return data;
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function localDateString(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function isUnreleasedMovie(movie) {
  const releaseDate = String(movie?.release_date || '').trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(releaseDate)) return false;
  return releaseDate > localDateString();
}

const RELEASE_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function formatReleaseDateLabel(value) {
  const releaseDate = String(value || '').trim();
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(releaseDate);
  if (!match) return '';
  const [, year, month, day] = match;
  const monthIndex = Number(month) - 1;
  const dayNumber = Number(day);
  if (monthIndex < 0 || monthIndex > 11 || dayNumber < 1 || dayNumber > 31) return '';
  return `${RELEASE_MONTHS[monthIndex]} ${dayNumber}, ${year}`;
}

async function addMoviePayloadsIndividually(listId, movies) {
  for (const movie of movies || []) {
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie })
    });
  }
}

async function addMoviePayloadsToList(listId, movies) {
  try {
    return await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}/movies/bulk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movies })
    });
  } catch (bulkError) {
    if (bulkError.status === 404) {
      await addMoviePayloadsIndividually(listId, movies);
      return { fallback: 'individual' };
    }
    throw bulkError;
  }
}

function announceCurationChanged() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event('cp-curation-changed'));
  }
}

function announceLibraryChanged(detail = {}) {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('cp-library-changed', { detail }));
  }
}

function announceLibraryReconciled(state) {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('cp-library-reconciled', { detail: state }));
  }
  announceLibraryChanged({ source: 'reconcile', reconcile: state });
}

function reconcileSignature(state) {
  return [
    state?.status || 'idle',
    Number(state?.updated_at || 0),
    Number(state?.checked || 0),
    Number(state?.matched || 0),
    Number(state?.review || 0),
    Number(state?.pending || 0),
    Number(state?.failed || 0)
  ].join(':');
}

function SelectionCheckbox({ checked, onChange, label, className }) {
  return (
    <label className={cx('selection-checkbox', className, checked && 'selection-checkbox-checked')} onClick={(event) => event.stopPropagation()}>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} aria-label={label} />
      <span aria-hidden="true">{checked ? <Check size={14} /> : null}</span>
    </label>
  );
}

function CardLab() {
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

function App() {
  if (typeof window !== 'undefined' && window.location.pathname === '/card-lab') {
    return <CardLab />;
  }

  if (typeof window !== 'undefined' && window.location.pathname === '/styleguide') {
    return <StyleGuide />;
  }

  return <ArchiveApp />;
}

function ArchiveApp() {
  const [activeSection, setActiveSection] = useState(() => (
    typeof window === 'undefined' ? 'home' : sectionFromPath(window.location.pathname, navItems)
  ));
  const [mountedSections, setMountedSections] = useState(() => new Set([activeSection]));
  const [stats, setStats] = useState(null);
  const [movies, setMovies] = useState([]);
  const [ownership, setOwnership] = useState({});
  const [selectedMovie, setSelectedMovie] = useState(null);
  const [details, setDetails] = useState({});
  const [followed, setFollowed] = useState([]);
  const [followedChecking, setFollowedChecking] = useState(false);
  const [loading, setLoading] = useState({ stats: true, movies: true });
  const [toast, setToast] = useState(null);
  const [torrentModal, setTorrentModal] = useState(null);
  const [trailerModal, setTrailerModal] = useState(null);
  const [streamModal, setStreamModal] = useState(null);
  const [streamingConfig, setStreamingConfig] = useState({
    enabled: true,
    label: 'Stream',
    url_template: 'https://streamimdb.ru/embed/movie/{tmdb_id}'
  });
  const [posterEditor, setPosterEditor] = useState(null);
  const [libraryQuery, setLibraryQuery] = useState('');
  const [discoverQuery, setDiscoverQuery] = useState('');
  const [browseQuery, setBrowseQuery] = useState('');
  const [discoverActiveTab, setDiscoverActiveTab] = useState('explore');
  const [discoverSearchRequest, setDiscoverSearchRequest] = useState(0);
  const [cleanupInitialTab, setCleanupInitialTab] = useState('duplicates');
  const [homeLists, setHomeLists] = useState([]);
  const sourceSearchTokenRef = useRef(0);
  const libraryReconcileSignatureRef = useRef('');

  const notify = useCallback((message, tone = 'success') => {
    setToast({ message, tone });
    window.clearTimeout(window.__cpToastTimer);
    window.__cpToastTimer = window.setTimeout(() => setToast(null), 3200);
  }, []);

  useEffect(() => {
    setMountedSections((sections) => new Set([...sections, activeSection]));
  }, [activeSection]);

  const refreshHealthStats = useCallback(async () => {
    try {
      setStats(await fetchJson('/api/stats'));
    } catch (error) {
      notify(`Stats unavailable: ${error.message}`, 'error');
    }
  }, [notify]);

  useEffect(() => {
    window.addEventListener('cp-library-changed', refreshHealthStats);
    return () => window.removeEventListener('cp-library-changed', refreshHealthStats);
  }, [refreshHealthStats]);

  const loadHomeLists = useCallback(async () => {
    try {
      const data = await fetchJson('/api/user/lists');
      setHomeLists(data.lists || []);
    } catch {
      setHomeLists([]);
    }
  }, []);

  useEffect(() => {
    loadHomeLists();
    window.addEventListener('cp-curation-changed', loadHomeLists);
    return () => window.removeEventListener('cp-curation-changed', loadHomeLists);
  }, [loadHomeLists]);

  async function toggleHomeSystemList(systemType, movie, owned) {
    const payload = discoverMoviePayload(movie, owned);
    const active = listsForDiscoverMovie(movie, homeLists, owned).some((list) => (
      list.system_type === systemType || list.id === systemType
    ));
    await fetchJson(`/api/user/system-lists/${encodeURIComponent(systemType)}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie: payload, active: !active })
    });
    await loadHomeLists();
    announceCurationChanged();
    notify(`${movie.title} ${active ? 'removed from' : 'added to'} ${systemType === 'watched' ? 'Watched' : 'Watchlist'}`);
  }

  useEffect(() => {
    let cancelled = false;
    let timer = 0;
    function scheduleNext(status) {
      timer = window.setTimeout(checkReconcile, status === 'running' ? 2000 : 5000);
    }
    async function checkReconcile() {
      try {
        const state = await fetchJson('/api/library/reconcile');
        if (cancelled) return;
        const status = state.status || 'idle';
        const signature = reconcileSignature(state);
        const isNewCompletedRun = status === 'completed' && signature !== libraryReconcileSignatureRef.current;
        if (isNewCompletedRun) {
          libraryReconcileSignatureRef.current = signature;
          announceLibraryReconciled(state);
        }
        if (isNewCompletedRun && state.matched > 0) {
          notify(`${formatCount(state.matched)} new movie${state.matched === 1 ? '' : 's'} identified`, 'success');
        }
        scheduleNext(status);
      } catch {
        // Startup reconciliation is non-blocking; Library still exposes manual Rescan Files.
        if (!cancelled) timer = window.setTimeout(checkReconcile, 10000);
      }
    }
    fetchJson('/api/library/reconcile', { method: 'POST' })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) checkReconcile();
      });
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [notify]);

  useEffect(() => {
    let cancelled = false;
    async function loadStats() {
      setLoading((state) => ({ ...state, stats: true }));
      try {
        const data = await fetchJson('/api/stats');
        if (!cancelled) setStats(data);
      } catch (error) {
        if (!cancelled) notify(`Stats unavailable: ${error.message}`, 'error');
      } finally {
        if (!cancelled) setLoading((state) => ({ ...state, stats: false }));
      }
    }
    loadStats();
    return () => {
      cancelled = true;
    };
  }, [notify]);

  useEffect(() => {
    let cancelled = false;
    async function loadMovies() {
      setLoading((state) => ({ ...state, movies: true }));
      try {
        const data = await fetchJson('/api/tmdb/discover?list=trending_week&page=1');
        const results = (data.results && data.results.length ? data.results : fallbackMovies).slice(0, 8);
        if (cancelled) return;
        setMovies(results);
        setSelectedMovie(results[0] || null);
        try {
          const check = await fetchJson('/api/library/check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              movies: results.map((movie) => ({ tmdb_id: movie.tmdb_id || '', imdb_id: movie.imdb_id || '', title: movie.title, year: movie.year || '' }))
            })
          });
          if (!cancelled) {
            setOwnership(buildOwnershipMap(check.results || []));
          }
        } catch {
          if (!cancelled) setOwnership({});
        }
      } catch (error) {
        if (!cancelled) {
          setMovies(fallbackMovies);
          setSelectedMovie(fallbackMovies[0]);
          notify(`Discover feed unavailable: ${error.message}`, 'error');
        }
      } finally {
        if (!cancelled) setLoading((state) => ({ ...state, movies: false }));
      }
    }
    loadMovies();
    return () => {
      cancelled = true;
    };
  }, [notify]);

  useEffect(() => {
    let cancelled = false;
    async function loadFollowedReleases() {
      setFollowedChecking(true);
      try {
        const initial = await fetchJson('/api/user/followed-releases');
        let serverMovies = initial.movies || [];
        let legacy = [];
        try {
          legacy = JSON.parse(localStorage.getItem('cp.followedMovies') || '[]');
        } catch {
          legacy = [];
        }
        if (legacy.length && !serverMovies.length) {
          for (const movie of legacy) {
            await fetchJson('/api/user/followed-releases', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ movie })
            });
          }
          localStorage.removeItem('cp.followedMovies');
        }
        const checked = await fetchJson('/api/user/followed-releases/check', { method: 'POST' });
        if (cancelled) return;
        serverMovies = sortFollowedReleases(checked.movies || []);
        setFollowed(serverMovies);
        if ((checked.newly_available || []).length) {
          notify(`${formatCount(checked.newly_available.length)} followed release${checked.newly_available.length === 1 ? '' : 's'} now available`, 'success');
          playReleaseAlertSound();
        }
        if ((checked.removed_owned || []).length) {
          notify(`${formatCount(checked.removed_owned.length)} followed release${checked.removed_owned.length === 1 ? '' : 's'} already in library`, 'neutral');
        }
      } catch (error) {
        if (!cancelled) notify(`Release watchlist unavailable: ${error.message}`, 'error');
      } finally {
        if (!cancelled) setFollowedChecking(false);
      }
    }
    loadFollowedReleases();
    return () => { cancelled = true; };
  }, [notify]);

  useEffect(() => {
    if (!selectedMovie?.tmdb_id || details[selectedMovie.tmdb_id]) return;
    let cancelled = false;
    async function loadDetails() {
      try {
        const data = await fetchJson(`/api/tmdb/details?tmdb_id=${encodeURIComponent(selectedMovie.tmdb_id)}`);
        if (!cancelled) setDetails((state) => ({ ...state, [selectedMovie.tmdb_id]: data }));
      } catch {
        if (!cancelled) setDetails((state) => ({ ...state, [selectedMovie.tmdb_id]: { cast: [], trailer_url: '' } }));
      }
    }
    loadDetails();
    return () => {
      cancelled = true;
    };
  }, [selectedMovie, details]);

  const selectedDetails = selectedMovie?.tmdb_id ? details[selectedMovie.tmdb_id] : null;
  const selectedMovieWithDetails = selectedMovie ? { ...selectedMovie, release_date: selectedMovie.release_date || selectedDetails?.release_date || '' } : null;
  const selectedOwnership = selectedMovieWithDetails ? ownedMovieFor(selectedMovieWithDetails, ownership) : null;
  const streamingAvailable = Boolean(streamingConfig.enabled && String(streamingConfig.url_template || '').trim());
  const streamingLabel = String(streamingConfig.label || '').trim() || 'Stream';

  useEffect(() => {
    let cancelled = false;
    fetchJson('/api/streaming/config')
      .then((config) => {
        if (!cancelled) setStreamingConfig(config);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    function handlePopState() {
      setActiveSection(sectionFromPath(window.location.pathname, navItems));
    }
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  function selectSection(id) {
    if (typeof window === 'undefined') return;
    setActiveSection(id);
    const path = id === 'home' ? '/' : `/${id}`;
    if (window.location.pathname !== path) {
      window.history.pushState({}, '', path);
    }
  }

  function reviewUnmatchedMetadata() {
    setCleanupInitialTab('unmatched');
    selectSection('cleanup');
  }

  function openCleanupTab(tab) {
    setCleanupInitialTab(tab);
    selectSection('cleanup');
  }

  async function toggleFollow(movie) {
    const key = movieKey(movie);
    const existing = followed.find((item) => movieKey(item) === key);
    const payload = { title: movie.title, year: movie.year, tmdb_id: movie.tmdb_id, poster_url: movie.poster_url, release_date: movie.release_date || '' };
    try {
      const data = await fetchJson('/api/user/followed-releases', {
        method: existing ? 'DELETE' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ movie: existing || payload })
      });
      setFollowed(sortFollowedReleases(data.movies || []));
      notify(existing ? `${movie.title} removed from release watchlist` : `${movie.title} added to release watchlist`, existing ? 'neutral' : 'success');
    } catch (error) {
      notify(`Release watchlist update failed: ${error.message}`, 'error');
    }
  }

  async function playLocal(path) {
    try {
      await fetchJson('/api/open-file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });
      notify('Opening local file');
    } catch (error) {
      notify(`Could not play file: ${error.message}`, 'error');
    }
  }

  async function streamMovie(movie) {
    const template = String(streamingConfig.url_template || '').trim();
    if (!streamingConfig.enabled || !template) return;
    try {
      const ids = {
        tmdb_id: movie?.tmdb_id,
        imdb_id: movie?.imdb_id
      };
      if (streamTemplateTokens(template).includes('imdb_id') && !ids.imdb_id) {
        if (!ids.tmdb_id) throw new Error('Missing TMDB ID for IMDB lookup');
        const data = await fetchJson(`/api/tmdb/imdb_id?tmdb_id=${encodeURIComponent(ids.tmdb_id)}`);
        ids.imdb_id = data.imdb_id;
      }
      const embedUrl = buildStreamTemplateUrl(template, ids);
      setStreamModal({
        title: movie?.title || streamingLabel,
        year: movie?.year || '',
        embedUrl
      });
    } catch (error) {
      notify(`Stream unavailable: ${error.message}`, 'error');
    }
  }

  function openTrailerModal(movie, trailerUrl = '') {
    const title = movie?.title || 'Trailer';
    const year = movie?.year || '';
    setTrailerModal({
      title,
      year,
      sourceUrl: trailerUrl,
      embedUrl: toYouTubeEmbedUrl(trailerUrl),
      searchUrl: youtubeTrailerSearchUrl(title, year)
    });
  }

  async function findTorrent(movie, upgrade = false) {
    const title = movie?.title || '';
    const year = movie?.year || '';
    if (!title) return;
    const searchToken = sourceSearchTokenRef.current + 1;
    sourceSearchTokenRef.current = searchToken;
    setTorrentModal({ title, year, upgrade, loading: true, error: '', variants: [], sourceSearch: null });
    try {
      const payload = { title, year };
      if (movie?.imdb_id) payload.imdb_id = movie.imdb_id;
      if (movie?.tmdb_id) payload.tmdb_id = movie.tmdb_id;
      let data = await fetchJson('/api/explore/search/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      while (sourceSearchTokenRef.current === searchToken) {
        const running = data.status === 'running';
        setTorrentModal({
          title,
          year,
          upgrade,
          loading: running,
          error: data.status === 'error' ? (data.error || 'Source search failed') : '',
          variants: data.variants || [],
          sourceSearch: data
        });
        if (!running || !data.search_id) break;
        await wait(1000);
        data = await fetchJson(`/api/explore/search/jobs/${encodeURIComponent(data.search_id)}`);
      }
    } catch (error) {
      if (sourceSearchTokenRef.current !== searchToken) return;
      setTorrentModal({ title, year, upgrade, loading: false, error: error.message, variants: [] });
    }
  }

  async function searchTorrents(query) {
    const q = String(query || '').trim();
    if (!q) return;
    sourceSearchTokenRef.current += 1;
    setTorrentModal({ title: q, year: '', upgrade: false, loading: true, error: '', variants: [] });
    try {
      const data = await fetchJson(`/api/prowlarr/search?q=${encodeURIComponent(q)}`);
      setTorrentModal({ title: q, year: '', upgrade: false, loading: false, error: '', variants: data.results || [] });
    } catch (error) {
      setTorrentModal({ title: q, year: '', upgrade: false, loading: false, error: error.message, variants: [] });
    }
  }

  function closeTorrentModal() {
    sourceSearchTokenRef.current += 1;
    setTorrentModal(null);
  }

  function updateOwnedPoster(path, posterUrl) {
    setOwnership((state) => Object.fromEntries(
      Object.entries(state).map(([key, value]) => [
        key,
        value?.path === path ? { ...value, poster_url: posterUrl } : value
      ])
    ));
  }

  return (
    <div className="app-shell">
      <Sidebar
        activeSection={activeSection}
        onSelect={selectSection}
      />
      <main className={cx('workspace', activeSection === 'home' && 'workspace-home', activeSection === 'downloads' && 'workspace-downloads')}>
        {activeSection !== 'home' && activeSection !== 'library' && activeSection !== 'movie-lists' && activeSection !== 'cleanup' && activeSection !== 'discover' && activeSection !== 'ai-control' && activeSection !== 'help' && activeSection !== 'settings' && (
          <TopBar
            activeSection={activeSection}
            stats={stats}
            libraryQuery={libraryQuery}
            onLibraryQueryChange={setLibraryQuery}
            discoverQuery={discoverQuery}
            onDiscoverQueryChange={setDiscoverQuery}
            browseQuery={browseQuery}
            onBrowseQueryChange={setBrowseQuery}
            discoverActiveTab={discoverActiveTab}
            onDiscoverSearch={() => {
              setActiveSection('discover');
              setDiscoverSearchRequest((value) => value + 1);
            }}
          />
        )}
        {mountedSections.has('home') && (
          <div className="workspace-panel" hidden={activeSection !== 'home'}>
            <HomeWorkspace
              stats={stats}
              loading={loading}
              movies={movies}
              ownership={ownership}
              followed={followed}
              followedChecking={followedChecking}
              selectedMovie={selectedMovieWithDetails}
              selectedOwnership={selectedOwnership}
              selectedDetails={selectedDetails}
              onSelectSection={selectSection}
              onOpenCleanup={openCleanupTab}
              onSelectMovie={setSelectedMovie}
              onPlay={playLocal}
              onStream={streamMovie}
              streamingAvailable={streamingAvailable}
              streamingLabel={streamingLabel}
              onFindTorrent={findTorrent}
              onTrailer={openTrailerModal}
              onFollow={toggleFollow}
              userLists={homeLists}
              onToggleSystemList={toggleHomeSystemList}
              onEditPoster={(owned, movie) => setPosterEditor({ path: owned.path, title: movie.title })}
            />
          </div>
        )}
        {mountedSections.has('library') && (
          <div className="workspace-panel" hidden={activeSection !== 'library'}>
            <LibraryWorkspace
              onPlay={playLocal}
              onFindTorrent={findTorrent}
              onOpenTrailer={openTrailerModal}
              notify={notify}
              query={libraryQuery}
              setQuery={setLibraryQuery}
              onReviewUnmatched={reviewUnmatchedMetadata}
              isActive={activeSection === 'library'}
            />
          </div>
        )}
        {mountedSections.has('movie-lists') && (
          <div className="workspace-panel" hidden={activeSection !== 'movie-lists'}>
            <MovieListsWorkspace
              notify={notify}
              onPlay={playLocal}
              onFindTorrent={findTorrent}
              onOpenTrailer={openTrailerModal}
              onStream={streamMovie}
              streamingAvailable={streamingAvailable}
              streamingLabel={streamingLabel}
              followed={followed}
              onFollow={toggleFollow}
              onEditPoster={(owned, movie) => setPosterEditor({ path: owned.path, title: movie.title })}
            />
          </div>
        )}
        {mountedSections.has('discover') && (
          <div className="workspace-panel" hidden={activeSection !== 'discover'}>
            <DiscoverWorkspace
              followed={followed}
              notify={notify}
              onPlay={playLocal}
              onStream={streamMovie}
              streamingAvailable={streamingAvailable}
              streamingLabel={streamingLabel}
              onFindTorrent={findTorrent}
              onOpenTrailer={openTrailerModal}
              onManualTorrentSearch={searchTorrents}
              onFollow={toggleFollow}
              tmdbQuery={discoverQuery}
              setTmdbQuery={setDiscoverQuery}
              browseQuery={browseQuery}
              setBrowseQuery={setBrowseQuery}
              searchRequest={discoverSearchRequest}
              activeTab={discoverActiveTab}
              setActiveTab={setDiscoverActiveTab}
            />
          </div>
        )}
        {mountedSections.has('downloads') && (
          <div className="workspace-panel" hidden={activeSection !== "downloads"}>
            <DownloadsWorkspace />
          </div>
        )}
        {mountedSections.has('ai-control') && (
          <div className="workspace-panel" hidden={activeSection !== 'ai-control'}>
            <AIControlWorkspace
              followed={followed}
              notify={notify}
              onPlay={playLocal}
              onStream={streamMovie}
              streamingAvailable={streamingAvailable}
              streamingLabel={streamingLabel}
              onFindTorrent={findTorrent}
              onOpenTrailer={openTrailerModal}
              onFollow={toggleFollow}
              onEditPoster={(owned, movie) => setPosterEditor({ path: owned.path, title: movie.title })}
            />
          </div>
        )}
        {mountedSections.has('help') && (
          <div className="workspace-panel" hidden={!(activeSection === 'help')}>
            <HelpWorkspace />
          </div>
        )}
        {mountedSections.has('cleanup') && (
          <div className="workspace-panel" hidden={activeSection !== 'cleanup'}>
            <MigrationWorkspace
              section="cleanup"
              notify={notify}
              onPlay={playLocal}
              onFindTorrent={findTorrent}
              cleanupInitialTab={cleanupInitialTab}
              onReviewUnmatched={reviewUnmatchedMetadata}
              onReviewIdentities={() => openCleanupTab('identity')}
              onHealthChanged={refreshHealthStats}
              onStreamingConfigChanged={setStreamingConfig}
            />
          </div>
        )}
        {mountedSections.has('settings') && (
          <div className="workspace-panel" hidden={activeSection !== 'settings'}>
            <MigrationWorkspace
              section="settings"
              notify={notify}
              onPlay={playLocal}
              onFindTorrent={findTorrent}
              cleanupInitialTab={cleanupInitialTab}
              onReviewUnmatched={reviewUnmatchedMetadata}
              onReviewIdentities={() => openCleanupTab('identity')}
              onHealthChanged={refreshHealthStats}
              onStreamingConfigChanged={setStreamingConfig}
            />
          </div>
        )}
        {!['home', 'library', 'movie-lists', 'cleanup', 'discover', 'downloads', 'ai-control', 'help', 'settings'].includes(activeSection) && (
          <MigrationWorkspace
            section={activeSection}
            notify={notify}
            onPlay={playLocal}
            onFindTorrent={findTorrent}
            cleanupInitialTab={cleanupInitialTab}
            onReviewUnmatched={reviewUnmatchedMetadata}
            onReviewIdentities={() => openCleanupTab('identity')}
            onHealthChanged={refreshHealthStats}
            onStreamingConfigChanged={setStreamingConfig}
          />
        )}
      </main>
      {toast && (
        <div className={cx('toast', `toast-${toast.tone}`)} role="status">
          {toast.message}
        </div>
      )}
      {torrentModal && (
        <TorrentModal
          state={torrentModal}
          notify={notify}
          onClose={closeTorrentModal}
        />
      )}
      {trailerModal && (
        <TrailerModal
          state={trailerModal}
          onClose={() => setTrailerModal(null)}
        />
      )}
      {streamModal && (
        <StreamPlayerModal
          state={streamModal}
          onClose={() => setStreamModal(null)}
        />
      )}
      {posterEditor && (
        <PosterEditorModal
          item={posterEditor}
          notify={notify}
          onClose={() => setPosterEditor(null)}
          onSaved={(posterUrl) => updateOwnedPoster(posterEditor.path, posterUrl)}
        />
      )}
    </div>
  );
}

function Sidebar({ activeSection, onSelect }) {
  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="brand-lockup">
        <img src={logoUrl} alt="" className="brand-mark" />
        <div>
          <div className="brand-title">Cinema</div>
          <div className="brand-title brand-title-accent">Paradiso</div>
        </div>
      </div>
      <nav className="nav-stack">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = activeSection === item.id;
          return (
            <div key={item.id} className="nav-group">
              <button
                className={cx('nav-item', active && 'nav-item-active', `accent-${item.accent}`)}
                onClick={() => onSelect(item.id)}
                type="button"
              >
                <span className="nav-icon-wrap"><Icon size={20} /></span>
                <span className="nav-label">
                  {item.label}
                  {item.experimental && <ExperimentalBadge className="ai-control-nav-badge" />}
                </span>
              </button>
            </div>
          );
        })}
      </nav>
      <div className="sidebar-footer">
        <div className="sidebar-footer-status">
          <span className="status-dot" />
          <span>Local-first archive</span>
        </div>
        <span className="sidebar-version">{APP_VERSION}</span>
      </div>
    </aside>
  );
}

function ExperimentalBadge({ className = '' }) {
  return <span className={cx('experimental-badge', className)}>Experimental</span>;
}

let torrentHandlingConfigPromise = null;

function loadTorrentHandlingConfig(force = false) {
  if (force || !torrentHandlingConfigPromise) {
    torrentHandlingConfigPromise = fetchJson('/api/qbittorrent/config').catch((error) => {
      torrentHandlingConfigPromise = null;
      throw error;
    });
  }
  return torrentHandlingConfigPromise;
}

function TorrentActions({ variant, movieTitle, movieYear, notify, primary = false }) {
  const action = torrentPrimaryAction(variant);
  const magnetUrl = action.kind === 'magnet' ? action.url : '';
  const downloadUrl = action.kind === 'torrent' ? action.url : '';
  const [mode, setMode] = useState('embedded');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadTorrentHandlingConfig()
      .then((config) => {
        if (!cancelled) setMode(config.mode || 'embedded');
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  async function handlePrimary() {
    if (action.kind === 'none' || action.kind === 'source') return;
    setBusy(true);
    try {
      const config = await loadTorrentHandlingConfig();
      setMode(config.mode || 'embedded');
      if (config.mode === 'system') {
        if (!magnetUrl) {
          notify('This result has no magnet link. Use Open source page instead.', 'error');
          return;
        }
        window.location.href = magnetUrl;
        return;
      }
      const job = await fetchJson('/api/qbittorrent/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          magnet_url: magnetUrl,
          download_url: downloadUrl,
          title: movieTitle || '',
          year: movieYear || '',
          release_title: variant.title || '',
          indexer: variant.indexer || ''
        })
      });
      if (job.already_exists) {
        const status = job.state === 'imported' ? 'already imported' : 'already added';
        notify(`${variant.title || movieTitle} ${status}`);
        return;
      }
      notify(`${variant.title || movieTitle} download added`);
    } catch (error) {
      notify(`qBittorrent submission failed: ${error.message}`, 'error');
    } finally {
      setBusy(false);
    }
  }

  const canSubmit = action.kind === 'magnet' || (action.kind === 'torrent' && mode === 'embedded');
  return (
    <div className="torrent-action-group">
      {canSubmit ? (
        <button type="button" className={cx('btn', primary ? 'btn-primary' : 'btn-secondary')} onClick={handlePrimary} disabled={busy}>
          {busy ? <Loader2 size={15} className="spin" /> : <Download size={15} />}
          {mode === 'system' ? 'Open magnet' : 'Download'}
        </button>
      ) : action.kind === 'torrent' ? (
        <span className="torrent-no-link">No magnet</span>
      ) : null}
      {mode === 'embedded' && magnetUrl ? (
        <a className="btn btn-secondary" href={magnetUrl}>
          <ExternalLink size={15} /> Open externally
        </a>
      ) : null}
      {variant.info_url ? (
        <a className="btn btn-secondary" href={variant.info_url} target="_blank" rel="noreferrer">
          <ExternalLink size={15} /> Open source page
        </a>
      ) : null}
      {action.kind === 'none' ? <span className="torrent-no-link">No link</span> : null}
    </div>
  );
}

function TrailerModal({ state, onClose }) {
  const { title, year, embedUrl, searchUrl } = state;
  const titleLabel = [title, year].filter(Boolean).join(' ');

  return (
    <div className="modal-backdrop trailer-backdrop" role="presentation" onClick={onClose}>
      <section className="trailer-dialog" role="dialog" aria-modal="true" aria-label={`Trailer for ${titleLabel}`} onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header trailer-dialog-header">
          <div>
            <p className="screen-kicker">Trailer</p>
            <h2>{titleLabel}</h2>
          </div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Stop trailer">
            <X size={18} />
          </button>
        </div>
        {embedUrl ? (
          <div className="trailer-player-shell">
            <iframe
              key={embedUrl}
              title={`${titleLabel} trailer`}
              src={embedUrl}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
            />
          </div>
        ) : (
          <div className="trailer-missing">
            <Film size={32} />
            <h3>No embeddable trailer found</h3>
            <p>YouTube search results cannot be embedded as a player, but you can open the search externally.</p>
            <a className="btn btn-secondary" href={searchUrl} target="_blank" rel="noreferrer">
              <ExternalLink size={15} /> Open YouTube search
            </a>
          </div>
        )}
      </section>
    </div>
  );
}

function StreamPlayerModal({ state, onClose }) {
  const { title, year, embedUrl } = state;
  const titleLabel = [title, year].filter(Boolean).join(' ');
  const [streamStatusVisible, setStreamStatusVisible] = useState(true);
  const [streamLoaded, setStreamLoaded] = useState(false);
  const [streamSlow, setStreamSlow] = useState(false);

  useEffect(() => {
    setStreamStatusVisible(true);
    setStreamLoaded(false);
    setStreamSlow(false);
    const slowTimer = window.setTimeout(() => setStreamSlow(true), 12000);
    const hideTimer = window.setTimeout(() => setStreamStatusVisible(false), 30000);
    return () => {
      window.clearTimeout(slowTimer);
      window.clearTimeout(hideTimer);
    };
  }, [embedUrl]);

  const statusTitle = streamLoaded ? 'Preparing stream...' : 'Loading stream...';
  const statusDetail = streamSlow
    ? 'This stream is taking longer than usual. You can keep waiting or close the player.'
    : 'The player can take a moment to initialize.';

  return (
    <div className="modal-backdrop trailer-backdrop" role="presentation" onClick={onClose}>
      <section className="trailer-dialog stream-dialog" role="dialog" aria-modal="true" aria-label={`Stream ${titleLabel}`} onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header trailer-dialog-header">
          <div>
            <p className="screen-kicker">Streaming</p>
            <h2>{titleLabel}</h2>
          </div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close stream">
            <X size={18} />
          </button>
        </div>
        <div className="trailer-player-shell stream-player-shell">
          {streamStatusVisible && (
            <div className={`stream-loading-overlay ${streamLoaded ? 'is-compact' : ''}`} role="status" aria-live="polite">
              <Loader2 size={28} className="spin" />
              <strong>{statusTitle}</strong>
              <span className="stream-loading-bar" aria-hidden="true"><span /></span>
              <small>{statusDetail}</small>
            </div>
          )}
          <iframe
            key={embedUrl}
            title={`${titleLabel} stream`}
            src={embedUrl}
            allow="autoplay; fullscreen; picture-in-picture; encrypted-media"
            onLoad={() => setStreamLoaded(true)}
            allowFullScreen
          />
        </div>
      </section>
    </div>
  );
}

function TorrentModal({ state, onClose, notify }) {
  const initialQuery = `${state.title || ''} ${state.year || ''}`.trim();
  const [manualQuery, setManualQuery] = useState(initialQuery);
  const [titleFilter, setTitleFilter] = useState('');
  const [resolutionFilter, setResolutionFilter] = useState('all');
  const [indexerFilter, setIndexerFilter] = useState('all');
  const [sortMode, setSortMode] = useState('size-desc');
  const [variants, setVariants] = useState(state.variants || []);
  const [loading, setLoading] = useState(state.loading);
  const [error, setError] = useState(state.error || '');
  const [sourceSearch, setSourceSearch] = useState(state.sourceSearch || null);

  useEffect(() => {
    setManualQuery(`${state.title || ''} ${state.year || ''}`.trim());
    setVariants(state.variants || []);
    setLoading(state.loading);
    setError(state.error || '');
    setSourceSearch(state.sourceSearch || null);
    setTitleFilter('');
    setResolutionFilter('all');
    setIndexerFilter('all');
    setSortMode('size-desc');
  }, [state]);

  const indexers = useMemo(() => getUniqueOptions(variants, (variant) => variant.indexer), [variants]);
  const resolutions = useMemo(() => {
    const preferred = ['4K', '1080p', '720p', '480p', 'Unknown'];
    const found = getUniqueOptions(variants, (variant) => variant.resolution || 'Unknown');
    return preferred.filter((value) => found.includes(value)).concat(found.filter((value) => !preferred.includes(value)));
  }, [variants]);

  const filteredVariants = useMemo(() => {
    const q = titleFilter.trim().toLowerCase();
    const rows = variants.filter((variant) => {
      if (q && !String(variant.title || '').toLowerCase().includes(q)) return false;
      if (resolutionFilter !== 'all' && (variant.resolution || 'Unknown') !== resolutionFilter) return false;
      if (indexerFilter !== 'all' && variant.indexer !== indexerFilter) return false;
      return true;
    });
    const sorted = [...rows];
    sorted.sort((a, b) => {
      if (sortMode === 'size-asc') return torrentSizeBytes(a) - torrentSizeBytes(b);
      if (sortMode === 'seeders-desc') return Number(b.seeders || 0) - Number(a.seeders || 0);
      if (sortMode === 'seeders-asc') return Number(a.seeders || 0) - Number(b.seeders || 0);
      if (sortMode === 'resolution-desc') return resolutionRank(b.resolution) - resolutionRank(a.resolution) || Number(b.seeders || 0) - Number(a.seeders || 0);
      if (sortMode === 'title-asc') return String(a.title || '').localeCompare(String(b.title || ''));
      return torrentSizeBytes(b) - torrentSizeBytes(a);
    });
    return sorted;
  }, [variants, titleFilter, resolutionFilter, indexerFilter, sortMode]);

  const stillSearching = loading || sourceSearch?.status === 'running';
  const pendingIndexers = [
    ...(sourceSearch?.searching_indexers || []),
    ...(sourceSearch?.pending_indexers || [])
  ].filter(Boolean);
  const timedOutIndexers = sourceSearch?.timed_out_indexers || [];

  async function runManualSearch(event) {
    event.preventDefault();
    const q = manualQuery.trim();
    if (!q) return;
    setLoading(true);
    setError('');
    setSourceSearch(null);
    try {
      const data = await fetchJson(`/api/prowlarr/search?q=${encodeURIComponent(q)}`);
      setVariants(data.results || []);
      setTitleFilter('');
      setResolutionFilter('all');
      setIndexerFilter('all');
      setSortMode('size-desc');
    } catch (searchError) {
      setVariants([]);
      setError(searchError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="torrent-dialog" role="dialog" aria-modal="true" aria-label="Torrent results" onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <p className="screen-kicker">{state.upgrade ? 'Upgrade search' : 'Source search'}</p>
            <h2>{state.upgrade ? 'Upgrade sources' : 'Sources'}: {state.title}{state.year ? ` (${state.year})` : ''}</h2>
          </div>
          <span className="torrent-count">{formatCount(filteredVariants.length)} results</span>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close torrent results">
            <X size={18} />
          </button>
        </div>

        <form className="torrent-search-row" onSubmit={runManualSearch}>
          <label className="library-search">
            <Search size={17} />
            <input value={manualQuery} onChange={(event) => setManualQuery(event.target.value)} placeholder="Manual torrent search..." />
          </label>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? <Loader2 size={15} className="spin" /> : <Search size={15} />} Search
          </button>
        </form>

        <div className="torrent-filter-row">
          <label className="library-search">
            <Search size={17} />
            <input value={titleFilter} onChange={(event) => setTitleFilter(event.target.value)} placeholder="Filter by title..." />
          </label>
          <select value={resolutionFilter} onChange={(event) => setResolutionFilter(event.target.value)}>
            <option value="all">All resolutions</option>
            {resolutions.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
          <select value={indexerFilter} onChange={(event) => setIndexerFilter(event.target.value)}>
            <option value="all">All indexers</option>
            {indexers.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
          <select value={sortMode} onChange={(event) => setSortMode(event.target.value)}>
            <option value="size-desc">Size largest</option>
            <option value="size-asc">Size smallest</option>
            <option value="seeders-desc">Seeders most</option>
            <option value="seeders-asc">Seeders least</option>
            <option value="resolution-desc">Resolution best</option>
            <option value="title-asc">Title A-Z</option>
          </select>
        </div>

        {stillSearching && filteredVariants.length ? (
          <div className="source-search-progress" role="status" aria-live="polite">
            <Loader2 size={16} className="spin" />
            <span>
              <strong>Still searching</strong>
              <small>
                {pendingIndexers.length
                  ? `Checking ${pendingIndexers.slice(0, 4).join(', ')}${pendingIndexers.length > 4 ? ` and ${pendingIndexers.length - 4} more` : ''}.`
                  : 'Waiting for remaining indexers.'}
              </small>
            </span>
          </div>
        ) : null}

        {!stillSearching && timedOutIndexers.length ? (
          <div className="source-search-progress source-search-progress-muted">
            <AlertTriangle size={15} />
            <span>
              <strong>Some indexers timed out</strong>
              <small>{timedOutIndexers.slice(0, 4).join(', ')}{timedOutIndexers.length > 4 ? ` and ${timedOutIndexers.length - 4} more` : ''}</small>
            </span>
          </div>
        ) : null}

        {stillSearching && !filteredVariants.length ? (
          <div className="dialog-loading">
            <Loader2 size={20} className="spin" />
            <span className="dialog-loading-copy">
              <strong>Connecting to Prowlarr indexers...</strong>
              <small>This may take some time while source aliases and indexers respond.</small>
            </span>
          </div>
        ) : error ? (
          <div className="dialog-error">{error}</div>
        ) : filteredVariants.length ? (
          <div className="torrent-result-list">
            {filteredVariants.map((variant, index) => {
              return (
                <article className="torrent-result" key={`${variant.title}-${index}`}>
                  <span className="torrent-quality">{variant.resolution || 'Unknown'}</span>
                  <div className="torrent-title-block">
                    <strong>{variant.title}</strong>
                    <span>
                      <strong className="torrent-seeders">Seeders {formatCount(variant.seeders)}</strong>
                      <span>{variant.size_human || '?'}</span>
                      <span>{variant.indexer || 'Unknown indexer'}</span>
                    </span>
                  </div>
                  <TorrentActions
                    variant={variant}
                    movieTitle={state.title}
                    movieYear={state.year}
                    notify={notify}
                  />
                </article>
              );
            })}
          </div>
        ) : (
          <div className="empty-state">
            <strong>No sources found.</strong>
            <span>Prowlarr returned no usable movie releases for this title.</span>
          </div>
        )}
      </section>
    </div>
  );
}

function TopBar({
  activeSection,
  stats,
  libraryQuery,
  onLibraryQueryChange,
  discoverQuery,
  onDiscoverQueryChange,
  browseQuery,
  onBrowseQueryChange,
  discoverActiveTab,
  onDiscoverSearch
}) {
  const section = navItems.find((item) => item.id === activeSection);
  const isLibrary = activeSection === 'library';
  const isDiscover = activeSection === 'discover';
  const isDownloads = activeSection === 'downloads';
  const isBrowseSearch = isDiscover && discoverActiveTab === 'browse';
  const isExploreSearch = isDiscover && discoverActiveTab === 'explore';
  const searchEnabled = topBarSearchEnabled(activeSection, discoverActiveTab);
  const searchValue = isLibrary ? libraryQuery : isBrowseSearch ? browseQuery : isExploreSearch ? discoverQuery : '';
  const searchPlaceholder = isLibrary
    ? 'Search your offline library...'
    : isBrowseSearch
      ? 'Search movie indexers...'
      : isExploreSearch
        ? 'Search TMDB discovery...'
        : isDiscover
          ? 'Use the AI prompt below...'
          : 'Search movies, actions, TMDB...';
  return (
    <header className="topbar">
      <div>
        <p className="screen-kicker">Cinematic archive console</p>
        <div className="topbar-title-row">
          <h1>
            {section?.label || 'Home'}
            {isLibrary && <span className="offline-badge">Offline</span>}
          </h1>
          {activeSection === 'downloads' && (
            <span className="downloads-title-credit">
              <img src="/qbittorrent/images/qbittorrent32.png" alt="" />
              <span>Powered by qBittorrent</span>
            </span>
          )}
        </div>
      </div>
      {!isDownloads && (
        <form
          className={cx('command-search', !searchEnabled && 'command-search-inactive')}
          aria-disabled={!searchEnabled}
          onSubmit={(event) => {
            event.preventDefault();
            if (searchEnabled && (isExploreSearch || isBrowseSearch)) onDiscoverSearch();
          }}
        >
          <Search size={17} />
          <input
            aria-label={isLibrary ? 'Search offline library' : isBrowseSearch ? 'Search movie indexers' : isExploreSearch ? 'Search TMDB discovery' : 'Command search'}
            value={searchValue}
            onChange={(event) => {
              if (isLibrary) onLibraryQueryChange(event.target.value);
              if (isExploreSearch) onDiscoverQueryChange(event.target.value);
              if (isBrowseSearch) onBrowseQueryChange(event.target.value);
            }}
            placeholder={searchPlaceholder}
            disabled={!searchEnabled}
          />
          {searchEnabled && <kbd>{isExploreSearch || isBrowseSearch ? 'Enter' : 'Ctrl K'}</kbd>}
        </form>
      )}
      {!isDownloads && (
        <div className="topbar-stat">
          <Database size={16} />
          <span>{formatCount(stats?.total_files)} files</span>
        </div>
      )}
    </header>
  );
}

function DownloadsWorkspace() {
  return (
    <section className="downloads-workspace" aria-label="Downloads powered by qBittorrent">
      <iframe
        className="downloads-frame"
        title="qBittorrent Downloads"
        src="/qbittorrent/"
      />
    </section>
  );
}

const manualSections = [
  {
    key: 'quick-start',
    title: 'Quick Start',
    summary: 'Start here on a new install: configure at least one movie library root, save Settings, then let CP build its local view of your archive.',
    details: [
      {
        title: 'What CP does',
        items: [
          'Reads the movie folders you add in Settings and builds a local archive view.',
          'Uses optional services only when you configure them: Plex, Prowlarr, TMDB, Ollama, and qBittorrent.',
          'Shows Ready states and connection tests in Settings so you can see what is configured.'
        ]
      },
      {
        title: 'What CP will not do',
        items: [
          'It will not require Plex, TMDB, Ollama, or Prowlarr just to browse local files.',
          'It will not rename or delete movie files unless you use a specific cleanup action.',
          'It will not make incomplete torrents visible as finished movies.'
        ]
      },
      {
        title: 'Common mistakes',
        items: [
          'Expecting torrent search before Prowlarr is configured and tested.',
          'Putting incomplete downloads inside a movie library folder.',
          'Editing settings fields but forgetting to save before testing the integration.'
        ]
      }
    ]
  },
  {
    key: 'home-dashboard',
    title: 'Home dashboard',
    summary: 'Home is the command dashboard: library health, followed releases, selected movie details, and fast paths into cleanup or discovery.',
    details: [
      {
        title: 'What CP does',
        items: [
          'Shows archive counts, health signals, and followed release alerts.',
          'Lets you open local playback, find sources, follow a release, or jump into cleanup from one place.',
          'Uses TMDB details when available to enrich the highlighted movie.'
        ]
      },
      {
        title: 'What CP will not do',
        items: [
          'It will not scan every external service unless that service is configured.',
          'It will not change your library just because a health warning appears.',
          'It will not replace detailed Library or Cleanup workflows.'
        ]
      },
      {
        title: 'Common mistakes',
        items: [
          'Treating Home as the only place to manage files; use Library and Cleanup for deeper work.',
          'Assuming followed releases are downloads; they are alerts until you choose a source.',
          'Ignoring Ready states when a card depends on an optional integration.'
        ]
      }
    ]
  },
  {
    key: 'library-workspace',
    title: 'Library workspace',
    summary: 'Library is for browsing and inspecting your accepted archive: movie view, file view, filters, posters, metadata, and playback actions.',
    details: [
      {
        title: 'What CP does',
        items: [
          'Groups files into movie identities when metadata is available.',
          'Shows quality, language, country, location, and local file details for archive decisions.',
          'Lets you play files, edit posters, correct metadata, mark Watched or Watchlist, use bulk selection, and search for sources or upgrades.'
        ]
      },
      {
        title: 'What CP will not do',
        items: [
          'It will not assume every unmatched file is safe to rename.',
          'It will not edit Plex metadata directly from normal browsing.',
          'It will not move downloads into the library until qBittorrent completion handling says the payload is complete.'
        ]
      },
      {
        title: 'Common mistakes',
        items: [
          'Looking for unknown files only in Movie View; File View is better for raw file inspection.',
          'Expecting metadata to be perfect when folder names are messy.',
          'Using upgrade search before confirming the existing file identity is correct.'
        ]
      }
    ]
  },
  {
    key: 'movie-lists-workspace',
    title: 'Movie Lists workspace',
    summary: 'Movie Lists is the mixed owned and wanted list area: custom lists, protected system lists, missing titles, upgrade candidates, copy/export, and source fulfillment previews.',
    details: [
      {
        title: 'What CP does',
        items: [
          'Keeps Watched and Watchlist as protected system lists while still allowing custom user lists.',
          'Shows owned, missing, and upgrade candidates together so a list can be reviewed as a real acquisition plan.',
          'Supports bulk selection, Add to List, Copy selected to a folder, and Find missing or Find upgrades previews.'
        ]
      },
      {
        title: 'What CP will not do',
        items: [
          'It will not delete movie files when you delete a custom list.',
          'It will not treat a Watchlist item as owned until the library actually contains a matched local file.',
          'It will not submit list fulfillment without showing the review dialog first.'
        ]
      },
      {
        title: 'Common mistakes',
        items: [
          'Using Library filters for wanted movies; Movie Lists is where owned and missing titles can live together.',
          'Expecting protected Watched or Watchlist lists to be renamed or deleted like custom lists.',
          'Running fulfillment before choosing trusted release indexers and download defaults in Settings.'
        ]
      }
    ]
  },
  {
    key: 'cleanup-workspace',
    title: 'Cleanup workspace',
    summary: 'Cleanup is the maintenance area for duplicates, low-quality items, unmatched metadata, and identity review before any destructive action.',
    details: [
      {
        title: 'What CP does',
        items: [
          'Surfaces duplicate candidates, low-quality files, unmatched metadata, and identity conflicts.',
          'Keeps review steps visible so you can inspect before acting.',
          'Uses safer delete behavior through the system recycle bin when deletion is supported.'
        ]
      },
      {
        title: 'What CP will not do',
        items: [
          'It will not silently delete movie contents.',
          'It will not automatically rename folders from torrent names in this release.',
          'It will not treat metadata suggestions as user approval.'
        ]
      },
      {
        title: 'Common mistakes',
        items: [
          'Deleting duplicates before checking resolution, source, audio, and subtitles.',
          'Using cleanup as a download organizer; downloads should finish first, then be reviewed.',
          'Assuming unmatched means bad; unmatched often means the folder name needs human review.'
        ]
      }
    ]
  },
  {
    key: 'discover-workspace',
    title: 'Discover workspace',
    summary: 'Discover is for finding movies and torrent sources: TMDB exploration, Prowlarr indexer browsing, random picks, and owned/unowned checks.',
    details: [
      {
        title: 'What CP does',
        items: [
          'Explores TMDB lists and details when a TMDB key is configured.',
          'Browses Prowlarr indexers and searches torrent results when Prowlarr is configured.',
          'Marks whether discovered movies appear to already exist in your local library.',
          'Uses the in-app trailer modal, Streaming Link actions, unreleased labels, IMDb-first source searches, alternative-title fallback, and progressive per-indexer results.'
        ]
      },
      {
        title: 'What CP will not do',
        items: [
          'It will not download from Prowlarr by opening a random browser window.',
          'It will not bypass indexer availability, Prowlarr errors, or missing API keys.',
          'It will not force a torrent into your system default client when embedded qBittorrent mode is selected.',
          'It will not show Stream or source actions for unreleased unowned movies just because TMDB can display the title.'
        ]
      },
      {
        title: 'Common mistakes',
        items: [
          'Using Browse Indexer before adding and testing indexers inside Prowlarr.',
          'Confusing TMDB discovery with torrent availability; they are different sources.',
          'Closing an empty pop-up instead of reporting it; CP should submit through server routes, not random windows.'
        ]
      }
    ]
  },
  {
    key: 'ai-control-workspace',
    title: 'AI Control workspace',
    summary: 'AI Control is experimental: it turns plain-language movie commands into reviewable CP plans for finding, listing, downloading, and cleanup.',
    details: [
      {
        title: 'What CP does',
        items: [
          'Builds a preview plan before any action runs.',
          'Can show validated find results as tables or movie cards, then reuse normal trailer, Streaming Link, source, follow, and poster actions.',
          'Uses AI Control trusted indexers and configured limits when a command plans downloads.'
        ]
      },
      {
        title: 'What CP will not do',
        items: [
          'It will not execute a command automatically from the prompt box.',
          'It will not delete without the extra confirmation phrase when a dangerous batch action requires one.',
          'It will not treat creative AI suggestions as factual identities without TMDB validation.'
        ]
      },
      {
        title: 'Common mistakes',
        items: [
          'Typing a broad command and expecting instant results; CP checks TMDB, the local library, and trusted indexers first.',
          'Forgetting AI Control can be disabled from Settings.',
          'Assuming Ollama-curated lists are guaranteed factual; they are creative suggestions that CP still validates.'
        ]
      }
    ]
  },
  {
    key: 'downloads-workspace',
    title: 'Downloads workspace',
    summary: 'Downloads embeds the original qBittorrent WebUI while CP orchestrates CP-created submissions, folder policy, completion refresh, and safe handoff.',
    details: [
      {
        title: 'What CP does',
        items: [
          'Sends CP magnet links and approved torrent files to the embedded qBittorrent runtime.',
          'Uses the configured completed download folder, or the first library root when no folder is selected.',
          'After 100%, removes the torrent from qBittorrent without deleting data, then moves the completed payload into the library.'
        ]
      },
      {
        title: 'What CP will not do',
        items: [
          'It will not rename torrent folders during download.',
          'It will not move incomplete payloads into the movie library.',
          'It will not interfere with torrents you open manually in your separate default qBittorrent client.'
        ]
      },
      {
        title: 'Common mistakes',
        items: [
          'Expecting the embedded client and your system default client to share the same profile.',
          'Changing files underneath qBittorrent before CP completion handling runs.',
          'Forgetting that qBittorrent’s visible UI is intentionally the original qBittorrent interface.'
        ]
      }
    ]
  },
  {
    key: 'settings-workspace',
    title: 'Settings workspace',
    summary: 'Settings is where CP stores library roots, user data location, integration URLs, API keys, qBittorrent mode, download folder policy, Streaming Link, and AI Control policy.',
    details: [
      {
        title: 'What CP does',
        items: [
          'Saves configuration in CP config storage and shows Ready states for supported integrations.',
          'Provides Test saved buttons for services where a live connection test matters.',
          'Controls whether CP uses embedded qBittorrent or the classic system torrent-client behavior.',
          'Manages trusted release indexers, list download defaults, Streaming Link templates, Ollama candidate limits, and AI Control trusted indexers.'
        ]
      },
      {
        title: 'What CP will not do',
        items: [
          'It will not guess secret API keys or Plex tokens.',
          'It will not automatically install optional services like Plex, Prowlarr, TMDB accounts, or Ollama.',
          'It will not auto-update bundled qBittorrent in version 2.7.0.'
        ]
      },
      {
        title: 'Common mistakes',
        items: [
          'Testing unsaved values and thinking the saved integration is broken.',
          'Using a remote path without considering what qBittorrent can actually see.',
          'Leaving the completed folder empty without realizing CP will use the first library root.'
        ]
      }
    ]
  },
  {
    key: 'safety-rules',
    title: 'Safety rules',
    summary: 'CP is intentionally conservative: local-first browsing, explicit settings, no silent renaming, no hidden dependency installs, and no arbitrary download URL submission.',
    details: [
      {
        title: 'What CP does',
        items: [
          'Treats movie files, metadata, torrent links, and external service responses as data that must be handled deliberately.',
          'Keeps qBittorrent incomplete downloads outside the finished library flow.',
          'Constrains torrent-file retrieval to configured Prowlarr results instead of accepting arbitrary browser URLs.',
          'Lets trusted release indexers decide followed-release availability instead of trusting every noisy source.'
        ]
      },
      {
        title: 'What CP will not do',
        items: [
          'It will not silently modify Plex metadata, Prowlarr data, or movie contents.',
          'It will not use a browser-submitted random URL as a server-side torrent fetch target.',
          'It will not hide qBittorrent credit or restyle the qBittorrent WebUI as if CP wrote it.'
        ]
      },
      {
        title: 'Common mistakes',
        items: [
          'Trying to make automation do identity decisions that still need human review.',
          'Mixing temporary download folders with finished movie library folders.',
          'Assuming external tools are CP bugs before checking their Ready state and local WebUI.'
        ]
      }
    ]
  }
];

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

const helpSections = [
  {
    key: 'plex',
    title: 'Plex',
    status: 'Optional',
    summary: 'Use Plex if you want CP to read Plex metadata, match server items, and use Plex-related library workflows.',
    links: [
      ['Download Plex Media Server', 'https://www.plex.tv/media-server-downloads/'],
      ['Find X-Plex-Token', 'https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/']
    ],
    steps: [
      'Install Plex Media Server and create a movie library.',
      'Open Plex Web App and sign in.',
      'Open any library item XML and copy the X-Plex-Token from the URL.',
      'Open CP Settings, paste the local Plex URL and token, then use Test saved.'
    ],
    settingsHash: 'plex'
  },
  {
    key: 'prowlarr',
    title: 'Prowlarr',
    status: 'Optional, required for torrent search',
    summary: 'Use Prowlarr if you want CP to search torrent indexers, check followed releases, preview list fulfillment, and submit results to embedded qBittorrent.',
    links: [
      ['Download Prowlarr', 'https://prowlarr.com/'],
      ['Prowlarr Quick Start', 'https://wiki.servarr.com/prowlarr/quick-start-guide']
    ],
    steps: [
      'Install Prowlarr and open its local WebUI, usually http://127.0.0.1:9696.',
      'Add and test indexers inside Prowlarr.',
      'Copy the API key from Prowlarr Settings > General.',
      'Open CP Settings, paste the Prowlarr URL and API key, then use Test saved.',
      'Open Trusted indexers to choose which sources can mark followed releases available; YTS/YIFY is the default trusted release source when available.'
    ],
    settingsHash: 'prowlarr'
  },
  {
    key: 'tmdb',
    title: 'TMDB',
    status: 'Recommended',
    summary: 'Use TMDB for posters, plots, cast, discovery lists, trailers, and richer movie matching.',
    links: [
      ['TMDB API Getting Started', 'https://developer.themoviedb.org/reference/intro/getting-started'],
      ['TMDB Authentication', 'https://developer.themoviedb.org/docs/authentication-application']
    ],
    steps: [
      'Create or sign in to a TMDB account.',
      'Open account settings and request an API key.',
      'Copy the v3 API key used by CP.',
      'Open CP Settings, paste the TMDB key, then use Test saved.',
      'Use the adult metadata-search toggle only when you want matching workflows to include adult titles.'
    ],
    settingsHash: 'tmdb'
  },
  {
    key: 'streaming',
    title: 'Streaming Link',
    status: 'Optional',
    summary: 'Use Streaming Link if you want CP movie cards and detail panels to open an embedded stream provider from a configurable URL template.',
    links: [
      ['TMDB API Getting Started', 'https://developer.themoviedb.org/reference/intro/getting-started']
    ],
    steps: [
      'Open CP Settings and find Streaming Link.',
      'Enable Stream buttons and choose the button label shown on movie cards.',
      'Set a safe http or https URL template using {tmdb_id} or {imdb_id}.',
      'Save Streaming; CP hides Stream buttons when the setting is disabled or the movie is unreleased and unowned.'
    ],
    settingsHash: 'streaming'
  },
  {
    key: 'ollama',
    title: 'Ollama',
    status: 'Optional',
    summary: 'Use Ollama if you want local AI recommendations or optional Ollama-curated lists without sending your library to a cloud service.',
    links: [
      ['Download Ollama', 'https://ollama.com/'],
      ['Ollama Quickstart', 'https://docs.ollama.com/quickstart'],
      ['Ollama Model Library', 'https://ollama.com/library']
    ],
    steps: [
      'Install Ollama.',
      'Run or pull a model from the Ollama library.',
      'Confirm Ollama is available at http://localhost:11434.',
      'Open CP Settings, set the Ollama URL/model and candidate limit, then use Test saved.'
    ],
    settingsHash: 'ollama'
  },
  {
    key: 'ai-control',
    title: 'AI Control',
    status: 'Experimental',
    summary: 'Use AI Control if you want plain-language commands to become reviewable CP plans for finding, listing, downloading, and cleanup.',
    links: [
      ['Download Ollama', 'https://ollama.com/'],
      ['Ollama Model Library', 'https://ollama.com/library']
    ],
    steps: [
      'Configure Ollama first if you want AI-assisted interpretation or Ollama-curated lists.',
      'Open CP Settings and enable AI Control Experimental.',
      'Set max matched movies, max download searches, and whether Ollama-curated lists are allowed.',
      'Open AI Control trusted indexers to choose which Prowlarr sources may be used for download planning.',
      'Use the AI Control workspace to preview a command, review the plan, then confirm only if it is correct.'
    ],
    settingsHash: 'ai-control'
  },
  {
    key: 'qbittorrent',
    title: 'qBittorrent',
    status: 'Bundled in CP 2.7.0',
    summary: 'CP Downloads is powered by the original qBittorrent WebUI using a tested portable runtime bundled with the 2.7.0 release.',
    links: [
      ['qBittorrent Official Website', 'https://www.qbittorrent.org/'],
      ['qBittorrent Downloads', 'https://www.qbittorrent.org/download']
    ],
    steps: [
      'Use CP Settings to choose embedded qBittorrent or your system default client.',
      'Set the completed movie folder or leave it empty to use the first CP library folder.',
      'Keep incomplete downloads outside movie library folders.',
      'Open Downloads from the sidebar to see the original qBittorrent WebUI inside CP.'
    ],
    settingsHash: 'qbittorrent'
  }
];

function HelpWorkspace() {
  return (
    <section className="help-workspace" aria-label="Cinema Paradiso Help">
      <div className="help-intro">
        <p className="eyebrow">APP MANUAL & SETUP GUIDE</p>
        <h2>Help</h2>
        <p>
          Use this page as the Cinema Paradiso Manual first, then as the setup guide for optional services.
          Settings remains the place for Ready states, connection tests, and saved configuration.
        </p>
      </div>
      <div className="help-section-heading">
        <p className="eyebrow">APP MANUAL</p>
        <h3>Cinema Paradiso Manual</h3>
        <p>Each section below explains when to use the workspace, what CP controls, what it deliberately avoids, and the mistakes that usually create confusion.</p>
      </div>
      <div className="manual-section-stack">
        {manualSections.map((section) => (
          <article className="manual-card" key={section.key}>
            <header className="manual-card-header">
              <span className="manual-tag">{section.title}</span>
              <h3>{section.title}</h3>
              <p>{section.summary}</p>
            </header>
            <div className="manual-detail-grid">
              {section.details.map((detail) => (
                <div className="manual-detail" key={`${section.key}-${detail.title}`}>
                  <h4>{detail.title}</h4>
                  <ul>
                    {detail.items.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
      <div className="help-section-heading">
        <p className="eyebrow">OPTIONAL INTEGRATIONS</p>
        <h3>Dependency setup</h3>
        <p>These integrations are optional pieces around Cinema Paradiso. Install only what matches the workflows you want to use.</p>
      </div>
      <div className="help-grid">
        {helpSections.map((section) => (
          <article className="help-card" key={section.key}>
            <header className="help-card-header">
              <div>
                <span className="help-status-pill">{section.status}</span>
                <h3>{section.title}</h3>
              </div>
              <a className="btn btn-secondary help-settings-link" href={`/settings#settings-${section.settingsHash}`}>Open Settings</a>
            </header>
            <p>{section.summary}</p>
            <ol className="help-step-list">
              {section.steps.map((step) => <li key={step}>{step}</li>)}
            </ol>
            <div className="help-link-row">
              {section.links.map(([label, url]) => (
                <a key={url} href={url} target="_blank" rel="noreferrer">
                  <ExternalLink size={14} /> {label}
                </a>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function HomeWorkspace(props) {
  const {
    stats,
    loading,
    movies,
    ownership,
    followed,
    followedChecking,
    selectedMovie,
    selectedOwnership,
    selectedDetails,
    onSelectSection,
    onOpenCleanup,
    onSelectMovie,
    onPlay,
    onStream,
    streamingAvailable,
    streamingLabel,
    onFindTorrent,
    onTrailer,
    onFollow,
    userLists,
    onToggleSystemList,
    onEditPoster
  } = props;
  const [releaseDrawerOpen, setReleaseDrawerOpen] = useState(false);

  return (
    <div className="home-grid">
      <section className="hero-panel">
        <img className="home-hero-art" src={headerCropUrl} alt="" aria-hidden="true" />
        <div className="hero-copy">
          <h1 className="hero-page-title">Home</h1>
          <p className="screen-kicker">Cinematic archive console</p>
          <h2>Your movie archive, under command.</h2>
          <p>
            Cinema Paradiso brings local files, Plex metadata, cleanup tools, torrent sources, TMDB discovery,
            live streaming, and AI recommendations into one private console built for collectors who manage real libraries.
          </p>
        </div>
      </section>

      <HealthPanel stats={stats} loading={loading.stats} onOpenCleanup={onOpenCleanup} />
      <ReleasePanel
        followed={followed}
        checking={followedChecking}
        onSelectMovie={onSelectMovie}
        onViewAll={() => setReleaseDrawerOpen(true)}
      />

      <section className="movie-rail">
        <div className="section-heading">
          <div>
            <p className="screen-kicker">Discover</p>
            <h3>Trending movies with archive-aware actions</h3>
          </div>
          <button type="button" className="ghost-link" onClick={() => onSelectSection('discover')}>
            Open Discover
          </button>
        </div>
        {loading.movies ? (
          <div className="skeleton-stack">
            <div className="movie-card skeleton-card" />
            <div className="movie-card skeleton-card" />
            <div className="movie-card skeleton-card" />
          </div>
        ) : (
          <div className="movie-list">
            {movies.slice(0, 5).map((movie) => {
              const owned = ownedMovieFor(movie, ownership);
              return (
                <SmartMovieCard
                  key={movieKey(movie)}
                  movie={movie}
                  owned={owned}
                  selected={movieKey(movie) === movieKey(selectedMovie || {})}
                  followed={followed.some((item) => movieKey(item) === movieKey(movie))}
                  watched={listsForDiscoverMovie(movie, userLists, owned).some((list) => list.system_type === 'watched')}
                  watchlisted={listsForDiscoverMovie(movie, userLists, owned).some((list) => list.system_type === 'watchlist')}
                  details={movieKey(movie) === movieKey(selectedMovie || {}) ? selectedDetails : null}
                  onSelect={() => onSelectMovie(movie)}
                  onPlay={onPlay}
                  onStream={onStream}
                  streamingAvailable={streamingAvailable}
                  streamingLabel={streamingLabel}
                  onFindTorrent={onFindTorrent}
                  onTrailer={onTrailer}
                  onFollow={onFollow}
                  onToggleWatched={owned ? () => onToggleSystemList('watched', movie, owned) : undefined}
                  onToggleWatchlist={() => onToggleSystemList('watchlist', movie, owned)}
                  onEditPoster={owned ? () => onEditPoster(owned, movie) : undefined}
                />
              );
            })}
          </div>
        )}
      </section>

      <MovieInspector
        movie={selectedMovie}
        owned={selectedOwnership}
        details={selectedDetails}
        followed={followed.some((item) => movieKey(item) === movieKey(selectedMovie || {}))}
        watched={listsForDiscoverMovie(selectedMovie || {}, userLists, selectedOwnership).some((list) => list.system_type === 'watched')}
        watchlisted={listsForDiscoverMovie(selectedMovie || {}, userLists, selectedOwnership).some((list) => list.system_type === 'watchlist')}
        onClose={() => onSelectMovie(null)}
        onPlay={onPlay}
        onStream={onStream}
        streamingAvailable={streamingAvailable}
        streamingLabel={streamingLabel}
        onFindTorrent={onFindTorrent}
        onTrailer={onTrailer}
        onFollow={onFollow}
        onToggleWatched={selectedOwnership ? () => onToggleSystemList('watched', selectedMovie, selectedOwnership) : undefined}
        onToggleWatchlist={selectedMovie ? () => onToggleSystemList('watchlist', selectedMovie, selectedOwnership) : undefined}
        onEditPoster={selectedOwnership ? () => onEditPoster(selectedOwnership, selectedMovie) : undefined}
      />
      {releaseDrawerOpen && (
        <FollowedReleasesDrawer
          followed={followed}
          checking={followedChecking}
          selectedMovie={selectedMovie}
          onClose={() => setReleaseDrawerOpen(false)}
          onSelectMovie={onSelectMovie}
          onFindTorrent={onFindTorrent}
          onUnfollow={onFollow}
        />
      )}
    </div>
  );
}

function HealthPanel({ stats, loading, onOpenCleanup }) {
  const cards = [
    {
      label: 'Files',
      value: stats?.total_files,
      detail: `${formatCount(stats?.unique_titles)} unique titles`,
      icon: HardDrive,
      tone: 'blue'
    },
    {
      label: 'Low quality',
      value: stats?.low_quality_count,
      detail: 'below 1080p',
      icon: AlertTriangle,
      tone: 'amber',
      tab: 'low'
    },
    {
      label: 'Duplicates',
      value: stats?.duplicate_groups,
      detail: `${formatCount(stats?.extra_copies)} extra copies`,
      icon: Trash2,
      tone: 'red',
      tab: 'duplicates'
    },
    {
      label: 'Unmatched',
      value: stats?.unmatched_count,
      detail: 'files without accepted metadata',
      icon: LinkIcon,
      tone: 'violet',
      tab: 'unmatched'
    },
    {
      label: 'Identity review',
      value: stats?.identity_review_count,
      detail: `${formatCount(stats?.identity_review_recommended)} recommended corrections`,
      icon: ScanSearch,
      tone: 'cyan',
      tab: 'identity'
    }
  ];

  return (
    <section className="health-panel">
      <div className="section-heading">
        <div>
          <p className="screen-kicker">Library health</p>
          <h3>Offline archive status</h3>
        </div>
        {loading && <Loader2 className="spin" size={18} />}
      </div>
      <div className="health-cards">
        {cards.map((card) => {
          const Icon = card.icon;
          const Card = card.tab ? 'button' : 'article';
          return (
            <Card
              type={card.tab ? 'button' : undefined}
              key={card.label}
              className={cx('health-card', card.tab && 'health-card-action', `tone-${card.tone}`)}
              onClick={card.tab ? () => onOpenCleanup(card.tab) : undefined}
            >
              <Icon size={18} />
              <strong>{loading ? '...' : formatCount(card.value)}</strong>
              <span>{card.label}</span>
              <small>{card.detail}</small>
            </Card>
          );
        })}
      </div>
    </section>
  );
}

function releaseStatusLabel(movie) {
  if (movie.status === 'available') return 'Available';
  if (movie.status === 'owned') return 'Owned';
  return 'Watching';
}

function ReleasePanel({ followed, checking, onSelectMovie, onViewAll }) {
  const preview = sortFollowedReleases(followed).slice(0, 3);
  return (
    <section className="release-panel">
      <div className="section-heading">
        <div>
          <p className="screen-kicker">Release watchlist</p>
          <h3>Followed movies and upgrade signals</h3>
        </div>
        <div className="release-heading-actions">
          {checking ? <Loader2 className="spin" size={17} /> : <Bell size={18} />}
          {followed.length > 3 && (
            <button type="button" className="ghost-link ghost-link-small" onClick={onViewAll}>
              View all
            </button>
          )}
        </div>
      </div>
      <div className="release-list">
        {preview.length ? preview.map((movie, index) => (
          <button
            className={cx('release-item', `release-item-${movie.status || 'watching'}`)}
            key={`${movie.tmdb_id || movie.title}-${index}`}
            onClick={() => onSelectMovie(movie)}
            type="button"
          >
            <span className="release-pulse" />
            <span>
              <strong>{movie.title}</strong>
              <small>{movie.year || 'Unknown year'}</small>
            </span>
            <em>{releaseStatusLabel(movie)}</em>
          </button>
        )) : (
          <div className="empty-state">
            <strong>No followed releases yet.</strong>
            <span>Use Follow on a Discover card to watch for a proper WEB-DL or Blu-ray copy.</span>
          </div>
        )}
      </div>
    </section>
  );
}

function FollowedReleasesDrawer({ followed, checking, selectedMovie, onClose, onSelectMovie, onFindTorrent, onUnfollow }) {
  const [filter, setFilter] = useState('all');
  const sorted = sortFollowedReleases(followed);
  const visible = sorted.filter((movie) => filter === 'all' || (movie.status || 'watching') === filter);
  const availableCount = sorted.filter((movie) => movie.status === 'available').length;

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="followed-drawer" role="dialog" aria-modal="true" aria-label="Followed releases" onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <p className="screen-kicker">Release watchlist</p>
            <h2>Followed Releases</h2>
          </div>
          <span className={cx('release-drawer-count', availableCount > 0 && 'release-drawer-count-hot')}>
            {checking ? 'Checking...' : `${formatCount(availableCount)} available`}
          </span>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close followed releases">
            <X size={18} />
          </button>
        </div>

        <div className="release-filter-row">
          {['all', 'available', 'watching'].map((value) => (
            <button
              key={value}
              type="button"
              className={cx('release-filter-chip', filter === value && 'release-filter-chip-active')}
              onClick={() => setFilter(value)}
            >
              {value === 'all' ? 'All' : value === 'available' ? 'Available' : 'Watching'}
            </button>
          ))}
        </div>

        <div className="followed-list-full">
          {visible.length ? visible.map((movie, index) => (
            <div
              key={`${movie.tmdb_id || movie.title}-${index}`}
              className={cx(
                'followed-row',
                `followed-row-${movie.status || 'watching'}`,
                movieKey(movie) === movieKey(selectedMovie || {}) && 'followed-row-selected'
              )}
            >
              <button type="button" onClick={() => onSelectMovie(movie)}>
                <span className="followed-thumb">
                  {movie.poster_url ? <img src={movie.poster_url} alt="" loading="lazy" /> : <Film size={18} />}
                </span>
                <span>
                  <strong>{movie.title}</strong>
                  <small>{movie.year || 'Unknown year'}</small>
                </span>
                <em>{releaseStatusLabel(movie)}</em>
              </button>
              {movie.status === 'available' && (
                <button type="button" className="btn btn-secondary btn-green-outline" onClick={() => onFindTorrent(movie)}>
                  <Search size={15} /> Sources
                </button>
              )}
              <button
                type="button"
                className="followed-delete-button"
                onClick={() => onUnfollow(movie)}
                aria-label={`Remove ${movie.title} from followed releases`}
                title="Remove from watchlist"
              >
                <Trash2 size={15} />
              </button>
            </div>
          )) : (
            <div className="empty-state">
              <strong>No followed releases in this filter.</strong>
              <span>Available movies are always sorted to the top when the backend finds a proper WEB or Blu-ray source.</span>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function SmartMovieCard(props) {
  const {
    movie, owned, selected, followed, details, watched, watchlisted,
    onSelect, onPlay, onStream, streamingAvailable, streamingLabel, onFindTorrent, onFollow,
    onTrailer, onToggleWatched, onToggleWatchlist, onEditPoster
  } = props;
  const lowQuality = owned && isLowQuality(owned.resolution);
  const unreleased = !owned && isUnreleasedMovie(movie);
  const genres = (movie.genres || []).slice(0, 2);
  const posterMovie = owned?.poster_url ? { ...movie, poster_url: owned.poster_url } : movie;

  return (
    <UnifiedMovieCard
      className="home-smart-movie-card"
      title={movie.title}
      year={movie.year}
      posterUrl={posterMovie.poster_url}
      rating={movie.tmdb_rating}
      voteCount={formatVoteCount(movie.tmdb_vote_count)}
      chips={genres}
      mutedChips={[movie.language, movie.country_flag || movie.country, owned?.resolution, owned?.size_human]}
      statusLabel={owned ? (lowQuality ? 'Upgrade candidate' : '') : (unreleased ? 'Unreleased' : (followed ? 'Following' : 'Not in library'))}
      statusTone={owned ? (lowQuality ? 'warning' : 'neutral') : (unreleased ? 'warning' : 'missing')}
      ownedBadge={Boolean(owned)}
      selected={selected}
      onToggle={onSelect}
      showPlayOverlay={Boolean(owned?.path)}
      onPlay={owned?.path ? () => onPlay(owned.path) : undefined}
      cornerControls={(
        <>
          <PosterStateControls
            title={movie.title}
            watched={watched}
            watchlisted={watchlisted}
            onToggleWatched={owned ? onToggleWatched : undefined}
            onToggleWatchlist={onToggleWatchlist}
          />
          <PosterEditButton title={movie.title} onEdit={owned ? onEditPoster : undefined} />
        </>
      )}
    />
  );
}

function MovieInspector({
  movie, owned, details, followed, watched, watchlisted,
  onClose, onPlay, onStream, streamingAvailable, streamingLabel, onFindTorrent, onFollow,
  onTrailer, onToggleWatched, onToggleWatchlist, onEditPoster
}) {
  if (!movie) {
    return (
      <aside className="inspector inspector-empty">
        <Sparkles size={22} />
        <h3>Select a movie</h3>
        <p>Movie details, cast, trailer, and archive actions will appear here.</p>
      </aside>
    );
  }

  const lowQuality = owned && isLowQuality(owned.resolution);
  const unreleased = !owned && isUnreleasedMovie(movie);
  const releaseDateLabel = unreleased ? formatReleaseDateLabel(movie.release_date) : '';
  const cast = details?.cast || [];
  const trailerUrl = details?.trailer_url || '';

  return (
    <aside className="inspector">
      <button className="inspector-close" type="button" onClick={onClose} aria-label="Close movie details">
        <X size={17} />
      </button>
      <div className="inspector-hero">
        <Poster
          movie={owned?.poster_url ? { ...movie, poster_url: owned.poster_url } : movie}
          large
          onEditPoster={owned ? onEditPoster : undefined}
          watched={watched}
          watchlisted={watchlisted}
          onToggleWatched={owned ? onToggleWatched : undefined}
          onToggleWatchlist={onToggleWatchlist}
        />
        <div>
          <p className="screen-kicker">Selected movie</p>
          <h3>{movie.title}</h3>
          <div className="inspector-meta">
            <span>{movie.year || 'Unknown year'}</span>
            <Rating value={movie.tmdb_rating} votes={movie.tmdb_vote_count} />
            {unreleased && <span>Unreleased</span>}
            {releaseDateLabel && <span>Releases {releaseDateLabel}</span>}
            {movie.language && <span>{movie.language}</span>}
            {(movie.country_flag || movie.country) && <span>{movie.country_flag || movie.country}</span>}
          </div>
        </div>
      </div>
      <p className="plot-text">{movie.plot || 'No plot summary is available yet.'}</p>
      <div className="chip-row">
        {(movie.genres || []).slice(0, 5).map((genre) => <span className="chip" key={genre}>{genre}</span>)}
      </div>
      <div className="cast-strip">
        <span className="mini-label">Top cast</span>
        {details ? (
          cast.length ? cast.slice(0, 5).map((person) => (
            <span key={person.name} className="cast-chip">{person.name}</span>
          )) : <small>No cast data found.</small>
        ) : (
          <small>Loading cast...</small>
        )}
      </div>
      <div className="inspector-actions">
        {owned ? (
          <>
            <button type="button" className="btn btn-primary btn-green" onClick={() => onPlay(owned.path)}>
              <Play size={15} /> Play from HDD
            </button>
            {lowQuality && (
              <button type="button" className="btn btn-secondary" onClick={() => onFindTorrent(movie, true)}>
                <Wand2 size={15} /> Find upgrade
              </button>
            )}
          </>
        ) : (
          <>
            {!unreleased && (
              <button type="button" className="btn btn-primary" onClick={() => onFindTorrent(movie)}>
                <Search size={15} /> Find torrent
              </button>
            )}
            <button type="button" className="btn btn-secondary" onClick={() => onFollow(movie)}>
              <Bell size={15} /> {followed ? 'Following' : 'Follow release'}
            </button>
          </>
        )}
        {!unreleased && streamingAvailable && (
          <button type="button" className="btn btn-secondary" onClick={() => onStream(movie)}>
            <MonitorPlay size={15} /> {streamingLabel}
          </button>
        )}
        {details && (
          <button type="button" className="btn btn-secondary" onClick={() => onTrailer(movie, trailerUrl)}>
            <Film size={15} /> Play trailer
          </button>
        )}
      </div>
    </aside>
  );
}

function PosterEditButton({ title, onEdit }) {
  if (!onEdit) return null;
  return (
    <button
      type="button"
      className="poster-edit-trigger"
      aria-label={`Edit poster for ${title || 'movie'}`}
      title="Edit poster"
      onClick={(event) => {
        event.stopPropagation();
        onEdit();
      }}
    >
      <Pencil size={17} />
    </button>
  );
}

function PosterStateControls({
  title,
  watched,
  watchlisted,
  onToggleWatched,
  onToggleWatchlist,
  notify
}) {
  if (!onToggleWatched && !onToggleWatchlist) return null;
  return (
    <>
      {onToggleWatched && (
        <button
          type="button"
          className={cx('poster-state-control', 'poster-state-watched', watched && 'poster-state-control-active')}
          aria-label={watched ? `Mark ${title} as unwatched` : `Mark ${title} as watched`}
          title={watched ? 'Mark as unwatched' : 'Mark as watched'}
          onClick={(event) => {
            event.stopPropagation();
            onToggleWatched();
          }}
        >
          <Check size={17} />
        </button>
      )}
      {onToggleWatchlist && (
        <button
          type="button"
          className={cx('poster-state-control', 'poster-state-watchlist', watchlisted && 'poster-state-control-active')}
          aria-label={watchlisted ? `Remove ${title} from watchlist` : `Add ${title} to watchlist`}
          title={watchlisted ? 'Remove from watchlist' : 'Add to watchlist'}
          onClick={(event) => {
            event.stopPropagation();
            onToggleWatchlist();
          }}
        >
          <Bookmark size={16} fill={watchlisted ? 'currentColor' : 'none'} />
        </button>
      )}
    </>
  );
}

function Poster({
  movie,
  large,
  onEditPoster,
  watched,
  watchlisted,
  onToggleWatched,
  onToggleWatchlist,
  selected,
  onSelect,
  selectionClassName
}) {
  return (
    <div className={cx('poster', large && 'poster-large')}>
      {movie.poster_url ? (
        <img src={movie.poster_url} alt={`${movie.title} poster`} loading="lazy" />
      ) : (
        <Film size={large ? 42 : 28} />
      )}
      <PosterStateControls
        title={movie.title}
        watched={watched}
        watchlisted={watchlisted}
        onToggleWatched={onToggleWatched}
        onToggleWatchlist={onToggleWatchlist}
      />
      <PosterEditButton title={movie.title} onEdit={onEditPoster} />
      {onSelect && (
        <SelectionCheckbox
          className={selectionClassName}
          checked={Boolean(selected)}
          onChange={onSelect}
          label={`Select ${movie.title}`}
        />
      )}
    </div>
  );
}

const discoverLists = [
  { value: 'trending_week', label: 'Trending Week' },
  { value: 'trending_today', label: 'Trending Today' },
  { value: 'now_playing', label: 'Now Playing' },
  { value: 'upcoming', label: 'Upcoming' },
  { value: 'popular', label: 'Popular' },
  { value: 'top_rated', label: 'Top Rated' },
  { value: 'best_all_time', label: 'Best All Time' }
];

const discoverGenres = [
  { value: '', label: 'All genres' },
  { value: '28', label: 'Action' },
  { value: '12', label: 'Adventure' },
  { value: '16', label: 'Animation' },
  { value: '35', label: 'Comedy' },
  { value: '80', label: 'Crime' },
  { value: '99', label: 'Documentary' },
  { value: '18', label: 'Drama' },
  { value: '10751', label: 'Family' },
  { value: '14', label: 'Fantasy' },
  { value: '27', label: 'Horror' },
  { value: '9648', label: 'Mystery' },
  { value: '10749', label: 'Romance' },
  { value: '878', label: 'Sci-Fi' },
  { value: '53', label: 'Thriller' },
  { value: '10752', label: 'War' }
];

function DiscoverWorkspace({
  followed,
  notify,
  onPlay,
  onStream,
  streamingAvailable,
  streamingLabel,
  onFindTorrent,
  onOpenTrailer,
  onManualTorrentSearch,
  onFollow,
  tmdbQuery,
  setTmdbQuery,
  browseQuery,
  setBrowseQuery,
  searchRequest,
  activeTab,
  setActiveTab
}) {
  const [discoverList, setDiscoverList] = useState('trending_week');
  const [discoverGenre, setDiscoverGenre] = useState('');
  const [discoverMinVotes, setDiscoverMinVotes] = useState('0');
  const [discoverYearFrom, setDiscoverYearFrom] = useState('');
  const [discoverYearTo, setDiscoverYearTo] = useState('');
  const [discoverMinRating, setDiscoverMinRating] = useState('0');
  const [discoverSort, setDiscoverSort] = useState('auto');
  const [discoverResults, setDiscoverResults] = useState([]);
  const [discoverPage, setDiscoverPage] = useState(1);
  const [discoverTotalPages, setDiscoverTotalPages] = useState(1);
  const [discoverTotalResults, setDiscoverTotalResults] = useState(0);
  const [discoverMode, setDiscoverMode] = useState('discover');
  const [discoverLoading, setDiscoverLoading] = useState(false);
  const [discoverError, setDiscoverError] = useState('');
  const [browseRows, setBrowseRows] = useState([]);
  const [browseHiddenCount, setBrowseHiddenCount] = useState(0);
  const [browseLoading, setBrowseLoading] = useState(false);
  const [browseError, setBrowseError] = useState('');
  const [browseHasLoaded, setBrowseHasLoaded] = useState(false);
  const [browseMode, setBrowseMode] = useState('idle');
  const [browseResolution, setBrowseResolution] = useState('all');
  const [browseIndexer, setBrowseIndexer] = useState('all');
  const [browseIndexerOptions, setBrowseIndexerOptions] = useState([]);
  const [browseIndexerLoading, setBrowseIndexerLoading] = useState(false);
  const [browseSort, setBrowseSort] = useState('seeders-desc');
  const [selectedVariants, setSelectedVariants] = useState({});
  const [pickPrompt, setPickPrompt] = useState('');
  const [pickResults, setPickResults] = useState([]);
  const [pickModel, setPickModel] = useState('');
  const [pickLoading, setPickLoading] = useState(false);
  const [pickError, setPickError] = useState('');
  const [ownership, setOwnership] = useState({});
  const [detailsCache, setDetailsCache] = useState({});
  const [collectionCache, setCollectionCache] = useState({});
  const [userLists, setUserLists] = useState([]);
  const [expandedMovieKey, setExpandedMovieKey] = useState('');
  const [listEditorTarget, setListEditorTarget] = useState(null);
  const [discoverContext, setDiscoverContext] = useState(null);
  const [discoverHistory, setDiscoverHistory] = useState([]);
  const [pickContext, setPickContext] = useState(null);
  const [pickHistory, setPickHistory] = useState([]);
  const [posterEditor, setPosterEditor] = useState(null);
  const [selectedDiscoverKeys, setSelectedDiscoverKeys] = useState(() => new Set());
  const discoverRequestSeq = useRef(0);

  function updateOwnedPoster(path, posterUrl) {
    setOwnership((state) => Object.fromEntries(
      Object.entries(state).map(([key, value]) => [
        key,
        value?.path === path ? { ...value, poster_url: posterUrl } : value
      ])
    ));
  }

  async function checkOwnership(movies) {
    const payload = (movies || [])
      .filter((movie) => movie?.title)
      .map((movie) => ({ tmdb_id: movie.tmdb_id || '', imdb_id: movie.imdb_id || '', title: movie.title, year: movie.year || '' }));
    if (!payload.length) return;
    try {
      const check = await fetchJson('/api/library/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ movies: payload })
      });
      setOwnership((state) => ({ ...state, ...buildOwnershipMap(check.results || []) }));
    } catch {
      // Ownership is best effort for online discovery.
    }
  }

  const loadUserLists = useCallback(async () => {
    try {
      const data = await fetchJson('/api/user/lists');
      setUserLists(data.lists || []);
    } catch (error) {
      notify(`Lists unavailable: ${error.message}`, 'error');
    }
  }, [notify]);

  useEffect(() => {
    loadUserLists();
    window.addEventListener('cp-curation-changed', loadUserLists);
    return () => window.removeEventListener('cp-curation-changed', loadUserLists);
  }, [loadUserLists]);

  function discoverBaseLabel() {
    if (discoverMode === 'search' && tmdbQuery.trim()) return `Search: ${tmdbQuery.trim()}`;
    const listLabel = discoverLists.find((item) => item.value === discoverList)?.label || 'Discover Home';
    const genreLabel = discoverGenres.find((item) => item.value === discoverGenre)?.label || '';
    return genreLabel && discoverGenre ? `${listLabel} / ${genreLabel}` : listLabel;
  }

  function currentDiscoverSnapshot() {
    return {
      label: discoverContext?.label || discoverBaseLabel(),
      context: discoverContext,
      results: discoverResults,
      page: discoverPage,
      totalPages: discoverTotalPages,
      totalResults: discoverTotalResults,
      mode: discoverMode,
      query: tmdbQuery,
      list: discoverList,
      genre: discoverGenre,
      minVotes: discoverMinVotes,
      yearFrom: discoverYearFrom,
      yearTo: discoverYearTo,
      minRating: discoverMinRating,
      sort: discoverSort
    };
  }

  function currentPickSnapshot() {
    return {
      label: pickContext?.label || (pickResults.length ? 'AI Picks' : 'Pick My Movie'),
      context: pickContext,
      results: pickResults,
      model: pickModel
    };
  }

  function restoreDiscoverSnapshot(snapshot, nextHistory) {
    setDiscoverResults(snapshot.results || []);
    setDiscoverPage(snapshot.page || 1);
    setDiscoverTotalPages(snapshot.totalPages || 1);
    setDiscoverTotalResults(snapshot.totalResults || 0);
    setDiscoverMode(snapshot.mode || 'discover');
    setDiscoverContext(snapshot.context || null);
    setDiscoverMinVotes(snapshot.minVotes || '0');
    setDiscoverYearFrom(snapshot.yearFrom || '');
    setDiscoverYearTo(snapshot.yearTo || '');
    setDiscoverMinRating(snapshot.minRating || '0');
    setDiscoverSort(snapshot.sort || 'auto');
    setDiscoverError('');
    setDiscoverHistory(nextHistory || []);
    setExpandedMovieKey('');
    checkOwnership(snapshot.results || []);
  }

  function restorePickSnapshot(snapshot, nextHistory) {
    setPickResults(snapshot.results || []);
    setPickModel(snapshot.model || pickModel);
    setPickContext(snapshot.context || null);
    setPickError('');
    setPickHistory(nextHistory || []);
    setExpandedMovieKey('');
    checkOwnership(snapshot.results || []);
  }

  function resetDiscoverPath() {
    if (discoverHistory.length) {
      restoreDiscoverSnapshot(discoverHistory[0], []);
      return;
    }
    setDiscoverContext(null);
    setExpandedMovieKey('');
    loadDiscover({ append: false, search: discoverMode === 'search' ? tmdbQuery : '' });
  }

  function resetPickPath() {
    if (pickHistory.length) {
      restorePickSnapshot(pickHistory[0], []);
    }
  }

  async function fetchListMovies(list) {
    const movies = list?.movies || [];
    const enriched = [];
    for (let index = 0; index < movies.length; index += 6) {
      const batch = await Promise.all(movies.slice(index, index + 6).map(async (movie) => {
        if (movie?.genres?.length || movie?.plot) return movie;
        try {
          const query = `${movie.title || ''} ${movie.year || ''}`.trim();
          if (!query) return movie;
          const data = await fetchJson(`/api/tmdb/search?q=${encodeURIComponent(query)}&page=1&include_adult=false`);
          const match = (data.results || []).find((candidate) => (
            movie.tmdb_id && String(candidate.tmdb_id) === String(movie.tmdb_id)
          )) || (data.results || []).find((candidate) => (
            movie.year && String(candidate.year || '') === String(movie.year)
          )) || (data.results || [])[0];
          return match ? { ...match, path: movie.path || match.path || '' } : movie;
        } catch {
          return movie;
        }
      }));
      enriched.push(...batch);
    }
    return enriched;
  }

  async function loadDiscover({ append = false, search = '', page } = {}) {
    const query = String(search || '').trim();
    const nextPage = page || (append ? discoverPage + 1 : 1);
    const requestSeq = discoverRequestSeq.current + 1;
    discoverRequestSeq.current = requestSeq;
    setDiscoverLoading(true);
    setDiscoverError('');
    if (!append) {
      setDiscoverResults([]);
      setDiscoverContext(null);
      setDiscoverHistory([]);
      setExpandedMovieKey('');
    }
    try {
      let url = '';
      if (query) {
        url = `/api/tmdb/search?q=${encodeURIComponent(query)}&page=${nextPage}&page_size=40&include_adult=false`;
        if (discoverMinVotes !== '0') url += `&min_votes=${encodeURIComponent(discoverMinVotes)}`;
      } else {
        url = `/api/tmdb/discover?list=${encodeURIComponent(discoverList)}&page=${nextPage}&page_size=40`;
        if (discoverGenre) url += `&genre=${encodeURIComponent(discoverGenre)}`;
        if (discoverMinVotes !== '0') url += `&min_votes=${encodeURIComponent(discoverMinVotes)}`;
        if (discoverYearFrom.trim()) url += `&year_from=${encodeURIComponent(discoverYearFrom.trim())}`;
        if (discoverYearTo.trim()) url += `&year_to=${encodeURIComponent(discoverYearTo.trim())}`;
        if (discoverMinRating !== '0') url += `&min_rating=${encodeURIComponent(discoverMinRating)}`;
        if (discoverSort !== 'auto') url += `&sort=${encodeURIComponent(discoverSort)}`;
      }
      const data = await fetchJson(url);
      if (requestSeq !== discoverRequestSeq.current) return;
      const nextResults = data.results || [];
      setDiscoverResults((state) => (append ? [...state, ...nextResults] : nextResults));
      setDiscoverPage(data.page || nextPage);
      setDiscoverTotalPages(data.total_pages || 1);
      setDiscoverTotalResults(data.total_results || nextResults.length);
      setDiscoverMode(query ? 'search' : 'discover');
      checkOwnership(nextResults);
    } catch (error) {
      if (requestSeq !== discoverRequestSeq.current) return;
      setDiscoverError(error.message);
      if (!append) setDiscoverResults([]);
    } finally {
      if (requestSeq === discoverRequestSeq.current) {
        setDiscoverLoading(false);
      }
    }
  }

  async function loadContextPage(target, context, { append = false } = {}) {
    if (!context?.baseUrl) return;
    const isPick = target === 'pick';
    const currentPage = isPick ? (context.page || 1) : discoverPage;
    const nextPage = append ? currentPage + 1 : 1;
    const separator = context.baseUrl.includes('?') ? '&' : '?';
    const url = `${context.baseUrl}${separator}page=${nextPage}`;
    if (isPick) {
      setPickLoading(true);
      setPickError('');
    } else {
      setDiscoverLoading(true);
      setDiscoverError('');
    }
    try {
      const data = await fetchJson(url);
      const nextResults = data.results || [];
      const nextContext = {
        ...context,
        page: data.page || nextPage,
        totalPages: data.total_pages || 1
      };
      if (isPick) {
        setPickResults((state) => (append ? [...state, ...nextResults] : nextResults));
        setPickContext(nextContext);
      } else {
        setDiscoverResults((state) => (append ? [...state, ...nextResults] : nextResults));
        setDiscoverPage(data.page || nextPage);
        setDiscoverTotalPages(data.total_pages || 1);
        setDiscoverTotalResults(data.total_results || nextResults.length);
        setDiscoverContext(nextContext);
        setDiscoverMode(context.type || 'related');
      }
      checkOwnership(nextResults);
    } catch (error) {
      if (isPick) setPickError(error.message);
      else setDiscoverError(error.message);
    } finally {
      if (isPick) setPickLoading(false);
      else setDiscoverLoading(false);
    }
  }

  async function browsePerson(target, movie, role, person) {
    if (!person?.id) return;
    const isPick = target === 'pick';
    const labelRole = role === 'director' ? 'Director' : 'Actor';
    const context = {
      type: 'person',
      label: `${movie.title || 'Movie'} > ${labelRole}: ${person.name}`,
      baseUrl: `/api/tmdb/person_movies?person_id=${encodeURIComponent(person.id)}&role=${encodeURIComponent(role)}`,
      emptyText: `No TMDB movies found for ${person.name}.`
    };
    const snapshot = isPick ? currentPickSnapshot() : currentDiscoverSnapshot();
    if (isPick) setPickHistory((history) => [...history, snapshot]);
    else setDiscoverHistory((history) => [...history, snapshot]);
    setExpandedMovieKey('');
    await loadContextPage(target, context, { append: false });
  }

  async function browseCollection(target, movie, collection) {
    if (!collection?.id) return;
    const isPick = target === 'pick';
    if (isPick) {
      setPickLoading(true);
      setPickError('');
    } else {
      setDiscoverLoading(true);
      setDiscoverError('');
    }
    try {
      let collectionData = collection?.parts?.length ? collection : collectionCache[collection.id];
      if (!collectionData?.parts?.length) {
        collectionData = await fetchJson(`/api/tmdb/collection?collection_id=${encodeURIComponent(collection.id)}`);
        setCollectionCache((state) => ({ ...state, [collection.id]: collectionData }));
      }
      const results = collectionData.parts || [];
      const context = {
        type: 'collection',
        label: `${movie.title || 'Movie'} > ${collectionData.name || collection.name}`,
        emptyText: `No TMDB collection movies found for ${collectionData.name || collection.name}.`
      };
      const snapshot = isPick ? currentPickSnapshot() : currentDiscoverSnapshot();
      if (isPick) {
        setPickHistory((history) => [...history, snapshot]);
        setPickResults(results);
        setPickContext(context);
      } else {
        setDiscoverHistory((history) => [...history, snapshot]);
        setDiscoverResults(results);
        setDiscoverPage(1);
        setDiscoverTotalPages(1);
        setDiscoverTotalResults(results.length);
        setDiscoverMode('collection');
        setDiscoverContext(context);
      }
      setExpandedMovieKey('');
      checkOwnership(results);
    } catch (error) {
      if (isPick) setPickError(error.message);
      else setDiscoverError(error.message);
    } finally {
      if (isPick) setPickLoading(false);
      else setDiscoverLoading(false);
    }
  }

  async function browseList(target, movie, list) {
    const fullList = userLists.find((item) => item.id === list?.id) || list;
    if (!fullList?.id) return;
    const isPick = target === 'pick';
    if (isPick) {
      setPickLoading(true);
      setPickError('');
    } else {
      setDiscoverLoading(true);
      setDiscoverError('');
    }
    try {
      const results = await fetchListMovies(fullList);
      const context = {
        type: 'list',
        label: `${movie.title || 'Movie'} > List: ${fullList.name}`,
        emptyText: `No movies found in ${fullList.name}.`
      };
      const snapshot = isPick ? currentPickSnapshot() : currentDiscoverSnapshot();
      if (isPick) {
        setPickHistory((history) => [...history, snapshot]);
        setPickResults(results);
        setPickContext(context);
      } else {
        setDiscoverHistory((history) => [...history, snapshot]);
        setDiscoverResults(results);
        setDiscoverPage(1);
        setDiscoverTotalPages(1);
        setDiscoverTotalResults(results.length);
        setDiscoverMode('list');
        setDiscoverContext(context);
      }
      setExpandedMovieKey('');
      checkOwnership(results);
    } catch (error) {
      if (isPick) setPickError(error.message);
      else setDiscoverError(error.message);
    } finally {
      if (isPick) setPickLoading(false);
      else setDiscoverLoading(false);
    }
  }

  async function openTrailer(movie) {
    if (!movie?.tmdb_id) {
      onOpenTrailer(movie, '');
      return;
    }
    try {
      let details = detailsCache[movie.tmdb_id];
      if (!details) {
        details = await fetchJson(`/api/tmdb/details?tmdb_id=${encodeURIComponent(movie.tmdb_id)}`);
        setDetailsCache((state) => ({ ...state, [movie.tmdb_id]: details }));
      }
      onOpenTrailer(movie, details.trailer_url || '');
    } catch {
      onOpenTrailer(movie, '');
    }
  }

  async function loadDiscoverDetails(movie) {
    if (!movie?.tmdb_id) return null;
    const id = String(movie.tmdb_id);
    let details = detailsCache[id];
    if (!details) {
      setDetailsCache((state) => ({ ...state, [id]: { loading: true, cast: [], directors: [], collection: {}, trailer_url: '' } }));
      try {
        details = await fetchJson(`/api/tmdb/details?tmdb_id=${encodeURIComponent(id)}`);
        setDetailsCache((state) => ({ ...state, [id]: details }));
      } catch (error) {
        details = { error: error.message, cast: [], directors: [], collection: {}, trailer_url: '' };
        setDetailsCache((state) => ({ ...state, [id]: details }));
      }
    }
    if (details?.collection?.id && !collectionCache[details.collection.id]) {
      fetchJson(`/api/tmdb/collection?collection_id=${encodeURIComponent(details.collection.id)}`)
        .then((collectionData) => setCollectionCache((state) => ({ ...state, [details.collection.id]: collectionData })))
        .catch(() => {});
    }
    return details;
  }

  function toggleMovieDetails(movie) {
    const key = movieKey(movie);
    const nextKey = expandedMovieKey === key ? '' : key;
    setExpandedMovieKey(nextKey);
    if (nextKey) loadDiscoverDetails(movie);
  }

  async function createDiscoverList(name) {
    const created = await fetchJson('/api/user/lists', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    await loadUserLists();
    announceCurationChanged();
    notify(`List created: ${created.name}`);
    return created;
  }

  async function addDiscoverMovieToList(listId, movie) {
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie })
    });
    await loadUserLists();
    announceCurationChanged();
    notify('Movie added to list');
  }

  async function addDiscoverMoviesToList(listId, movies) {
    const payloads = (movies || []).map((movie) => moviePayload(movie));
    await addMoviePayloadsToList(listId, payloads);
    await loadUserLists();
    announceCurationChanged();
    notify(`${formatCount(payloads.length)} movie${payloads.length === 1 ? '' : 's'} added to list`);
    setSelectedDiscoverKeys(new Set());
  }

  async function removeDiscoverMovieFromList(listId, movie) {
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie })
    });
    await loadUserLists();
    announceCurationChanged();
    notify('Movie removed from list');
  }

  async function toggleDiscoverSystemList(systemType, movie, owned) {
    const payload = discoverMoviePayload(movie, owned);
    const currentLists = listsForDiscoverMovie(movie, userLists, owned);
    const active = currentLists.some((list) => list.system_type === systemType || list.id === systemType);
    await fetchJson(`/api/user/system-lists/${encodeURIComponent(systemType)}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie: payload, active: !active })
    });
    await loadUserLists();
    announceCurationChanged();
    notify(`${movie.title} ${active ? 'removed from' : 'added to'} ${systemType === 'watched' ? 'Watched' : 'Watchlist'}`);
  }

  async function fetchIndexerMetadata(row) {
    try {
      const params = new URLSearchParams({ title: row.parsed_title || row.title || '' });
      if (row.parsed_year) params.set('year', row.parsed_year);
      const metadata = await fetchJson(`/api/metadata?${params.toString()}`);
      return { ...row, metadata };
    } catch {
      return { ...row, metadata: {} };
    }
  }

  const loadBrowseIndexers = useCallback(async () => {
    setBrowseIndexerLoading(true);
    try {
      const data = await fetchJson('/api/explore/indexers');
      setBrowseIndexerOptions(data.indexers || []);
    } catch (error) {
      setBrowseError((current) => current || `Indexer list unavailable: ${error.message}`);
    } finally {
      setBrowseIndexerLoading(false);
    }
  }, []);

  async function loadBrowse({ query = browseQuery } = {}) {
    const search = String(query || '').trim();
    setBrowseLoading(true);
    setBrowseError('');
    setBrowseHasLoaded(true);
    setBrowseMode(search ? 'search' : 'latest');
    setBrowseHiddenCount(0);
    setBrowseRows([]);
    setSelectedVariants({});
    setSelectedDiscoverKeys(new Set());
    try {
      const params = new URLSearchParams();
      if (search) {
        params.set('q', search);
      } else {
        params.set('latest', '1');
      }
      if (browseIndexer !== 'all') {
        params.set('indexer_id', browseIndexer);
      }
      const url = `/api/explore/browse?${params.toString()}`;
      const data = await fetchJson(url);
      if (data.indexers?.length) setBrowseIndexerOptions(data.indexers);
      const rows = data.results || [];
      const baseRows = filterEnrichedIndexerResults(rows);
      setBrowseRows(baseRows);
      setBrowseHiddenCount(baseRows.length);
      checkOwnership(baseRows);
      const enriched = [];
      for (let index = 0; index < rows.length; index += 8) {
        const batch = await Promise.all(rows.slice(index, index + 8).map(fetchIndexerMetadata));
        enriched.push(...batch);
        const filtered = filterEnrichedIndexerResults([...enriched, ...rows.slice(index + 8)]);
        setBrowseRows(filtered);
        setBrowseHiddenCount(filtered.filter((row) => !row.metadata || !row.metadata.tmdb_id).length);
      }
      const filtered = filterEnrichedIndexerResults(enriched);
      setBrowseRows(filtered);
      setBrowseHiddenCount(filtered.filter((row) => !row.metadata || !row.metadata.tmdb_id).length);
      checkOwnership(filtered);
    } catch (error) {
      setBrowseError(error.message);
    } finally {
      setBrowseLoading(false);
    }
  }

  async function askPickMyMovie(event) {
    event.preventDefault();
    const prompt = pickPrompt.trim();
    if (!prompt) {
      setPickError('Describe what you want to watch first.');
      return;
    }
    setPickLoading(true);
    setPickError('');
    setPickResults([]);
    setPickContext(null);
    setPickHistory([]);
    setExpandedMovieKey('');
    try {
      const data = await fetchJson('/api/ollama/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });
      const results = data.results || [];
      setPickResults(results);
      setPickModel(data.model || '');
      checkOwnership(results);
      notify(`${formatCount(results.length)} recommendations returned`, 'success');
    } catch (error) {
      setPickError(error.message);
    } finally {
      setPickLoading(false);
    }
  }

  useEffect(() => {
    loadDiscover({ append: false, search: '' });
  }, [discoverList, discoverGenre, discoverMinVotes, discoverYearFrom, discoverYearTo, discoverMinRating, discoverSort]);

  useEffect(() => {
    if (!searchRequest) return;
    if (activeTab === 'browse') {
      loadBrowse({ query: browseQuery });
    } else if (activeTab === 'explore') {
      loadDiscover({ append: false, search: tmdbQuery, page: 1 });
    }
  }, [searchRequest]);

  useEffect(() => {
    if (activeTab === 'browse') {
      setBrowseError('');
      if (!browseIndexerOptions.length && !browseIndexerLoading) {
        loadBrowseIndexers();
      }
    }
  }, [activeTab, browseIndexerOptions.length, browseIndexerLoading, loadBrowseIndexers]);

  useEffect(() => {
    if (browseIndexer === 'all' || !browseIndexerOptions.length) return;
    if (!browseIndexerOptions.some((indexer) => String(indexer.id) === String(browseIndexer))) {
      setBrowseIndexer('all');
    }
  }, [browseIndexer, browseIndexerOptions]);

  const selectedBrowseIndexerName = useMemo(() => {
    if (browseIndexer === 'all') return 'All indexers';
    return browseIndexerOptions.find((indexer) => String(indexer.id) === String(browseIndexer))?.name || 'Selected indexer';
  }, [browseIndexer, browseIndexerOptions]);

  const filteredBrowseRows = useMemo(() => {
    const rows = browseRows.filter((movie) => {
      if (browseResolution !== 'all' && !movie.variants.some((variant) => (variant.resolution || 'Unknown') === browseResolution)) return false;
      if (browseIndexer !== 'all' && selectedBrowseIndexerName !== 'Selected indexer' && !movie.variants.some((variant) => variant.indexer === selectedBrowseIndexerName)) return false;
      return true;
    });
    const sorted = [...rows];
    sorted.sort((a, b) => {
      if (browseSort === 'title-asc') return String(a.title || '').localeCompare(String(b.title || ''));
      if (browseSort === 'year-desc') return String(b.year || '').localeCompare(String(a.year || ''));
      if (browseSort === 'quality-desc') return resolutionRank(b.best_resolution) - resolutionRank(a.best_resolution) || b.best_seeders - a.best_seeders;
      return b.best_seeders - a.best_seeders;
    });
    return sorted;
  }, [browseRows, browseResolution, browseIndexer, browseSort, selectedBrowseIndexerName]);

  const activeDiscoverSelectionMovies = activeTab === 'pick'
    ? pickResults
    : activeTab === 'explore'
      ? discoverResults
      : activeTab === 'browse' ? filteredBrowseRows : [];
  const selectedDiscoverMovies = useMemo(() => (
    activeDiscoverSelectionMovies
      .map((movie) => discoverMoviePayload(movie, ownedMovieFor(movie, ownership)))
      .filter((movie) => selectedDiscoverKeys.has(movieIdentityKey(movie)))
  ), [activeDiscoverSelectionMovies, ownership, selectedDiscoverKeys]);
  const allDiscoverResultsSelected = activeDiscoverSelectionMovies.length > 0 && activeDiscoverSelectionMovies.every((movie) => {
    const payload = discoverMoviePayload(movie, ownedMovieFor(movie, ownership));
    return selectedDiscoverKeys.has(movieIdentityKey(payload));
  });

  function toggleDiscoverSelection(movie, owned, checked) {
    const key = movieIdentityKey(discoverMoviePayload(movie, owned));
    setSelectedDiscoverKeys((current) => {
      const next = new Set(current);
      if (checked) next.add(key);
      else next.delete(key);
      return next;
    });
  }

  function selectAllDiscoverResults() {
    setSelectedDiscoverKeys(new Set(activeDiscoverSelectionMovies.map((movie) => movieIdentityKey(discoverMoviePayload(movie, ownedMovieFor(movie, ownership))))));
  }

  function clearDiscoverSelection() {
    setSelectedDiscoverKeys(new Set());
  }

  const tabs = [
    { id: 'explore', label: 'Explore Movies', icon: Compass },
    { id: 'browse', label: 'Browse Indexers', icon: Radio },
    { id: 'pick', label: 'Pick My Movie', icon: Bot }
  ];

  function backDiscoverPath() {
    if (!discoverHistory.length) return;
    const previous = discoverHistory[discoverHistory.length - 1];
    restoreDiscoverSnapshot(previous, discoverHistory.slice(0, -1));
  }

  function jumpDiscoverPath(index) {
    const snapshot = discoverHistory[index];
    if (!snapshot) return;
    restoreDiscoverSnapshot(snapshot, discoverHistory.slice(0, index));
  }

  function backPickPath() {
    if (!pickHistory.length) return;
    const previous = pickHistory[pickHistory.length - 1];
    restorePickSnapshot(previous, pickHistory.slice(0, -1));
  }

  function jumpPickPath(index) {
    const snapshot = pickHistory[index];
    if (!snapshot) return;
    restorePickSnapshot(snapshot, pickHistory.slice(0, index));
  }

  function runDiscoverSearch(event) {
    event.preventDefault();
    if (activeTab === 'browse') {
      loadBrowse({ query: browseQuery });
      return;
    }
    loadDiscover({ append: false, search: tmdbQuery, page: 1 });
  }

  return (
    <section className="discover-workspace">
      <header className="library-header discover-header">
        <div>
          <p className="screen-kicker">Online discovery</p>
          <h2>Discover</h2>
          <p>TMDB discovery, live indexer availability, and local Ollama recommendations with archive-aware actions.</p>
        </div>
        <div className="settings-summary">
          <strong>{formatCount(discoverResults.length + browseRows.length + pickResults.length)}</strong>
          <span>loaded titles</span>
        </div>
      </header>

      <div className="discover-tabs" role="tablist" aria-label="Discover tools">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              type="button"
              key={tab.id}
              className={cx(activeTab === tab.id && 'discover-tab-active')}
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon size={16} /> {tab.label}
            </button>
          );
        })}
      </div>

      {activeTab !== 'pick' && (
        <form className="discover-search-panel" onSubmit={runDiscoverSearch}>
          <label className="library-search discover-main-search">
            <Search size={17} />
            <input
              value={activeTab === 'browse' ? browseQuery : tmdbQuery}
              onChange={(event) => (activeTab === 'browse' ? setBrowseQuery : setTmdbQuery)(event.target.value)}
              placeholder={activeTab === 'browse' ? 'Search movie indexers...' : 'Search TMDB discovery...'}
              aria-label={activeTab === 'browse' ? 'Search movie indexers' : 'Search TMDB discovery'}
            />
          </label>
          <button type="submit" className="btn btn-primary discover-search-submit" disabled={activeTab === 'browse' ? browseLoading : discoverLoading}>
            {(activeTab === 'browse' ? browseLoading : discoverLoading) ? <Loader2 size={15} className="spin" /> : <Search size={15} />} Search
          </button>
        </form>
      )}

      {activeTab === 'explore' && (
        <section className="discover-panel">
          <DiscoverPathBar
            history={discoverHistory}
            currentLabel={discoverContext?.label}
            resetLabel="Discover Home"
            onBack={backDiscoverPath}
            onReset={resetDiscoverPath}
            onCrumb={jumpDiscoverPath}
          />
          <div className="discover-toolbar">
            <select value={discoverList} onChange={(event) => setDiscoverList(event.target.value)}>
              {discoverLists.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
            <select value={discoverGenre} onChange={(event) => setDiscoverGenre(event.target.value)}>
              {discoverGenres.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
            <select value={discoverMinVotes} onChange={(event) => setDiscoverMinVotes(event.target.value)}>
              <option value="0">Any votes</option>
              <option value="500">500+ votes</option>
              <option value="1000">1,000+ votes</option>
              <option value="5000">5,000+ votes</option>
              <option value="10000">10,000+ votes</option>
            </select>
            <input className="library-mini-input" value={discoverYearFrom} onChange={(event) => setDiscoverYearFrom(event.target.value)} placeholder="Year from" inputMode="numeric" />
            <input className="library-mini-input" value={discoverYearTo} onChange={(event) => setDiscoverYearTo(event.target.value)} placeholder="Year to" inputMode="numeric" />
            <select value={discoverMinRating} onChange={(event) => setDiscoverMinRating(event.target.value)}>
              <option value="0">Any rating</option>
              <option value="6">6+</option>
              <option value="7">7+</option>
              <option value="8">8+</option>
              <option value="8.5">8.5+</option>
            </select>
            <select value={discoverSort} onChange={(event) => setDiscoverSort(event.target.value)}>
              <option value="auto">List default sort</option>
              <option value="popularity.desc">Popularity</option>
              <option value="vote_average.desc">Rating</option>
              <option value="vote_count.desc">Most voted</option>
              <option value="primary_release_date.desc">Release date</option>
            </select>
            <button type="button" className="btn btn-secondary" onClick={() => loadDiscover({ append: false, search: discoverMode === 'search' ? tmdbQuery : '' })} disabled={discoverLoading}>
              <RefreshCcw size={15} /> Refresh
            </button>
            {discoverMode === 'search' && (
              <button type="button" className="btn btn-secondary" onClick={() => { setTmdbQuery(''); loadDiscover({ append: false, search: '', page: 1 }); }}>
                <X size={15} /> Clear search
              </button>
            )}
            <span className="discover-count">{formatCount(discoverTotalResults || discoverResults.length)} titles</span>
          </div>
          {discoverResults.length > 0 && (
            <div className="bulk-selection-bar discover-bulk-selection">
              <SelectionCheckbox
                className="discover-selection-master"
                checked={allDiscoverResultsSelected}
                onChange={(checked) => { if (checked) selectAllDiscoverResults(); else clearDiscoverSelection(); }}
                label="Select all discover results"
              />
              <span>{selectedDiscoverMovies.length ? `${formatCount(selectedDiscoverMovies.length)} selected` : 'Select movies'}</span>
              <button type="button" className="mini-action" onClick={selectAllDiscoverResults}>Select all results</button>
              <button type="button" className="mini-action" onClick={clearDiscoverSelection} disabled={!selectedDiscoverMovies.length}>Clear</button>
              <button type="button" className="mini-action" onClick={() => setListEditorTarget({ bulkItems: selectedDiscoverMovies })} disabled={!selectedDiscoverMovies.length}>
                <CirclePlus size={13} /> Add to list
              </button>
            </div>
          )}

          <DiscoverResultGrid
            error={discoverError}
            loading={discoverLoading && !discoverResults.length}
            emptyText={discoverContext?.emptyText || 'No TMDB movies match this view.'}
          >
            {discoverResults.map((movie, index) => {
              const owned = ownedMovieFor(movie, ownership);
              return (
                <DiscoverMovieCard
                  key={`${movie.tmdb_id || movie.title}-${movie.year}-${index}`}
                  movie={movie}
                  owned={owned}
                  followed={followed.some((item) => movieKey(item) === movieKey(movie))}
                  expanded={expandedMovieKey === movieKey(movie)}
                  details={movie.tmdb_id ? detailsCache[String(movie.tmdb_id)] : null}
                  collection={movie.tmdb_id && detailsCache[String(movie.tmdb_id)]?.collection?.id ? collectionCache[detailsCache[String(movie.tmdb_id)].collection.id] || detailsCache[String(movie.tmdb_id)].collection : {}}
                  itemLists={listsForDiscoverMovie(movie, userLists, owned)}
                  watched={listsForDiscoverMovie(movie, userLists, owned).some((list) => list.system_type === 'watched')}
                  watchlisted={listsForDiscoverMovie(movie, userLists, owned).some((list) => list.system_type === 'watchlist')}
                  onToggleWatched={owned ? () => toggleDiscoverSystemList('watched', movie, owned) : undefined}
                  onToggleWatchlist={() => toggleDiscoverSystemList('watchlist', movie, owned)}
                  selected={selectedDiscoverKeys.has(movieIdentityKey(discoverMoviePayload(movie, owned)))}
                  onSelect={(checked) => toggleDiscoverSelection(movie, owned, checked)}
                  onPlay={onPlay}
                  onStream={onStream}
                  streamingAvailable={streamingAvailable}
                  streamingLabel={streamingLabel}
                  onFindTorrent={onFindTorrent}
                  onFollow={onFollow}
                  onTrailer={openTrailer}
                  onToggleDetails={() => toggleMovieDetails(movie)}
                  onPersonBrowse={(role, person) => browsePerson('explore', movie, role, person)}
                  onCollectionBrowse={(collectionItem) => browseCollection('explore', movie, collectionItem)}
                  onListBrowse={(list) => browseList('explore', movie, list)}
                  onEditLists={() => setListEditorTarget(discoverMoviePayload(movie, owned))}
                  onRemoveFromList={(listId) => removeDiscoverMovieFromList(listId, discoverMoviePayload(movie, owned))}
                  onEditPoster={owned ? () => setPosterEditor({ path: owned.path, title: movie.title }) : undefined}
                />
              );
            })}
          </DiscoverResultGrid>

          {discoverResults.length > 0 && !discoverContext?.baseUrl && (
            <LibraryPagination
              page={discoverPage}
              totalPages={discoverTotalPages}
              total={discoverTotalResults || discoverResults.length}
              pageStart={(discoverPage - 1) * 40}
              pageEnd={(discoverPage - 1) * 40 + discoverResults.length}
              onPageChange={(nextPage) => loadDiscover({ append: false, search: discoverMode === 'search' ? tmdbQuery : '', page: nextPage })}
            />
          )}

          {discoverResults.length > 0 && discoverContext?.baseUrl && discoverPage < discoverTotalPages && discoverPage < 10 && (
            <button type="button" className="load-more-button" onClick={() => loadContextPage('explore', discoverContext, { append: true })} disabled={discoverLoading}>
              {discoverLoading ? <Loader2 size={15} className="spin" /> : <CirclePlus size={15} />} Load more
            </button>
          )}
        </section>
      )}

      {activeTab === 'browse' && (
        <section className="discover-panel">
          <div className="discover-toolbar">
            <select value={browseResolution} onChange={(event) => setBrowseResolution(event.target.value)}>
              <option value="all">All qualities</option>
              <option value="4K">4K</option>
              <option value="1080p">1080p</option>
              <option value="720p">720p</option>
              <option value="480p">480p</option>
              <option value="Unknown">Unknown</option>
            </select>
            <select value={browseIndexer} onChange={(event) => setBrowseIndexer(event.target.value)}>
              <option value="all">All indexers</option>
              {browseIndexerOptions.map((indexer) => <option key={indexer.id} value={indexer.id}>{indexer.name}</option>)}
            </select>
            <select value={browseSort} onChange={(event) => setBrowseSort(event.target.value)}>
              <option value="seeders-desc">Seeders most</option>
              <option value="quality-desc">Quality best</option>
              <option value="year-desc">Year newest</option>
              <option value="title-asc">Title A-Z</option>
            </select>
            <button type="button" className="btn btn-secondary" onClick={() => loadBrowse({ query: browseMode === 'latest' ? '' : browseQuery })} disabled={browseLoading || (!browseQuery.trim() && browseMode !== 'latest' && !browseHasLoaded)}>
              {browseLoading ? <Loader2 size={15} className="spin" /> : <RefreshCcw size={15} />} Refresh
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => loadBrowse({ query: '' })} disabled={browseLoading}>
              {browseLoading && browseMode === 'latest' ? <Loader2 size={15} className="spin" /> : <Radio size={15} />} Load latest
            </button>
            <span className="discover-count">
              <span className="discover-filter-label">Indexer source</span>
              {browseMode === 'search' && browseQuery.trim() ? `Search: ${browseQuery.trim()} / ${selectedBrowseIndexerName} - ` : browseMode === 'latest' ? `Latest / ${selectedBrowseIndexerName} - ` : ''}
              {formatCount(filteredBrowseRows.length)} movies
              {browseHiddenCount > 0 ? `, ${formatCount(browseHiddenCount)} without TMDB details` : ''}
              {browseIndexerLoading ? ', loading sources' : ''}
            </span>
          </div>

          {filteredBrowseRows.length > 0 && (
            <div className="bulk-selection-bar discover-bulk-selection">
              <SelectionCheckbox
                className="discover-selection-master"
                checked={allDiscoverResultsSelected}
                onChange={(checked) => { if (checked) selectAllDiscoverResults(); else clearDiscoverSelection(); }}
                label="Select all browse indexer results"
              />
              <span>{selectedDiscoverMovies.length ? `${formatCount(selectedDiscoverMovies.length)} selected` : 'Select movies'}</span>
              <button type="button" className="mini-action" onClick={selectAllDiscoverResults}>Select all results</button>
              <button type="button" className="mini-action" onClick={clearDiscoverSelection} disabled={!selectedDiscoverMovies.length}>Clear</button>
              <button type="button" className="mini-action" onClick={() => setListEditorTarget({ bulkItems: selectedDiscoverMovies })} disabled={!selectedDiscoverMovies.length}>
                <CirclePlus size={13} /> Add to list
              </button>
            </div>
          )}

          {!browseHasLoaded && !browseLoading ? (
            <div className="empty-state discover-empty">
              <strong>Search indexers by movie title.</strong>
              <span>Choose an indexer source, use the top search for a targeted search, or click Load latest for a broad Prowlarr browse that may take longer.</span>
            </div>
          ) : (
            <DiscoverResultGrid
              error={browseError}
              loading={browseLoading && !browseRows.length}
              emptyText={browseMode === 'latest' ? `Latest feed for ${selectedBrowseIndexerName} timed out or returned no movies. Try a title search or switch source.` : `No ${selectedBrowseIndexerName} movies found for this search. Switch to All indexers to search every source.`}
              className="discover-indexer-grid"
            >
              {filteredBrowseRows.map((movie) => {
                const selectedIndex = selectedVariants[movie.parsed_title] || 0;
                const owned = ownedMovieFor(movie, ownership);
                return (
                  <IndexerMovieCard
                    key={`${movie.parsed_title}-${movie.parsed_year}`}
                    movie={movie}
                    selectedIndex={selectedIndex}
                    owned={owned}
                    expanded={expandedMovieKey === movieKey(movie)}
                    details={movie.tmdb_id ? detailsCache[String(movie.tmdb_id)] : null}
                    collection={movie.tmdb_id && detailsCache[String(movie.tmdb_id)]?.collection?.id ? collectionCache[detailsCache[String(movie.tmdb_id)].collection.id] || detailsCache[String(movie.tmdb_id)].collection : {}}
                    itemLists={listsForDiscoverMovie(movie, userLists, owned)}
                    watched={listsForDiscoverMovie(movie, userLists, owned).some((list) => list.system_type === 'watched')}
                    watchlisted={listsForDiscoverMovie(movie, userLists, owned).some((list) => list.system_type === 'watchlist')}
                    onToggleWatched={owned ? () => toggleDiscoverSystemList('watched', movie, owned) : undefined}
                    onToggleWatchlist={() => toggleDiscoverSystemList('watchlist', movie, owned)}
                    selected={selectedDiscoverKeys.has(movieIdentityKey(discoverMoviePayload(movie, owned)))}
                    onSelect={(checked) => toggleDiscoverSelection(movie, owned, checked)}
                    notify={notify}
                    onVariantSelect={(index) => setSelectedVariants((state) => ({ ...state, [movie.parsed_title]: index }))}
                    onPlay={onPlay}
                    onStream={onStream}
                    streamingAvailable={streamingAvailable}
                    streamingLabel={streamingLabel}
                    onFindTorrent={onFindTorrent}
                    onTrailer={openTrailer}
                    onToggleDetails={() => toggleMovieDetails(movie)}
                    onEditLists={() => setListEditorTarget(discoverMoviePayload(movie, owned))}
                    onRemoveFromList={(listId) => removeDiscoverMovieFromList(listId, discoverMoviePayload(movie, owned))}
                    onEditPoster={owned ? () => setPosterEditor({ path: owned.path, title: movie.title }) : undefined}
                  />
                );
              })}
            </DiscoverResultGrid>
          )}
        </section>
      )}

      {activeTab === 'pick' && (
        <section className="discover-panel pick-panel-react">
          <form className="pick-prompt-panel" onSubmit={askPickMyMovie}>
            <div>
              <p className="screen-kicker">Local AI curator</p>
              <h3>Describe what you want to watch</h3>
              <p>Use a mood, memory, actor, era, half-remembered plot, or a specific kind of night.</p>
            </div>
            <textarea
              value={pickPrompt}
              onChange={(event) => setPickPrompt(event.target.value)}
              onKeyDown={(event) => {
                if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') askPickMyMovie(event);
              }}
              placeholder="Something funny but a little sad, maybe an indie movie with a warm ending..."
              rows={5}
            />
            <button type="submit" className="btn btn-primary btn-violet" disabled={pickLoading}>
              {pickLoading ? <Loader2 size={15} className="spin" /> : <Bot size={15} />} Ask AI
            </button>
            {pickModel && <p className="discover-inline-status"><CheckCircle2 size={15} /> Results from {pickModel}</p>}
            {pickError && <p className="discover-inline-status discover-inline-error"><AlertTriangle size={15} /> {pickError}</p>}
          </form>

          <DiscoverPathBar
            history={pickHistory}
            currentLabel={pickContext?.label}
            resetLabel="AI Picks"
            onBack={backPickPath}
            onReset={resetPickPath}
            onCrumb={jumpPickPath}
          />
          {pickResults.length > 0 && (
            <div className="bulk-selection-bar discover-bulk-selection">
              <SelectionCheckbox
                className="discover-selection-master"
                checked={allDiscoverResultsSelected}
                onChange={(checked) => { if (checked) selectAllDiscoverResults(); else clearDiscoverSelection(); }}
                label="Select all AI pick results"
              />
              <span>{selectedDiscoverMovies.length ? `${formatCount(selectedDiscoverMovies.length)} selected` : 'Select movies'}</span>
              <button type="button" className="mini-action" onClick={selectAllDiscoverResults}>Select all results</button>
              <button type="button" className="mini-action" onClick={clearDiscoverSelection} disabled={!selectedDiscoverMovies.length}>Clear</button>
              <button type="button" className="mini-action" onClick={() => setListEditorTarget({ bulkItems: selectedDiscoverMovies })} disabled={!selectedDiscoverMovies.length}>
                <CirclePlus size={13} /> Add to list
              </button>
            </div>
          )}

          <DiscoverResultGrid
            error={pickError && pickResults.length ? pickError : ''}
            loading={pickLoading && !pickResults.length}
            emptyText={pickContext?.emptyText || 'No recommendations yet. Ask Ollama for a mood or memory.'}
          >
            {pickResults.map((movie) => {
              const owned = ownedMovieFor(movie, ownership);
              return (
                <DiscoverMovieCard
                  key={`${movie.title}-${movie.year}`}
                  movie={movie}
                  reason={movie.reason}
                  owned={owned}
                  followed={followed.some((item) => movieKey(item) === movieKey(movie))}
                  expanded={expandedMovieKey === movieKey(movie)}
                  details={movie.tmdb_id ? detailsCache[String(movie.tmdb_id)] : null}
                  collection={movie.tmdb_id && detailsCache[String(movie.tmdb_id)]?.collection?.id ? collectionCache[detailsCache[String(movie.tmdb_id)].collection.id] || detailsCache[String(movie.tmdb_id)].collection : {}}
                  itemLists={listsForDiscoverMovie(movie, userLists, owned)}
                  watched={listsForDiscoverMovie(movie, userLists, owned).some((list) => list.system_type === 'watched')}
                  watchlisted={listsForDiscoverMovie(movie, userLists, owned).some((list) => list.system_type === 'watchlist')}
                  onToggleWatched={owned ? () => toggleDiscoverSystemList('watched', movie, owned) : undefined}
                  onToggleWatchlist={() => toggleDiscoverSystemList('watchlist', movie, owned)}
                  selected={selectedDiscoverKeys.has(movieIdentityKey(discoverMoviePayload(movie, owned)))}
                  onSelect={(checked) => toggleDiscoverSelection(movie, owned, checked)}
                  onPlay={onPlay}
                  onStream={onStream}
                  streamingAvailable={streamingAvailable}
                  streamingLabel={streamingLabel}
                  onFindTorrent={onFindTorrent}
                  onFollow={onFollow}
                  onTrailer={openTrailer}
                  onToggleDetails={() => toggleMovieDetails(movie)}
                  onPersonBrowse={(role, person) => browsePerson('pick', movie, role, person)}
                  onCollectionBrowse={(collectionItem) => browseCollection('pick', movie, collectionItem)}
                  onListBrowse={(list) => browseList('pick', movie, list)}
                  onEditLists={() => setListEditorTarget(discoverMoviePayload(movie, owned))}
                  onRemoveFromList={(listId) => removeDiscoverMovieFromList(listId, discoverMoviePayload(movie, owned))}
                  onEditPoster={owned ? () => setPosterEditor({ path: owned.path, title: movie.title }) : undefined}
                />
              );
            })}
          </DiscoverResultGrid>
          {pickContext?.baseUrl && pickContext.page < pickContext.totalPages && (
            <button type="button" className="load-more-button" onClick={() => loadContextPage('pick', pickContext, { append: true })} disabled={pickLoading}>
              {pickLoading ? <Loader2 size={15} className="spin" /> : <CirclePlus size={15} />} Load more
            </button>
          )}
        </section>
      )}

      {listEditorTarget && (
        <ListEditorModal
          item={listEditorTarget.bulkItems ? null : listEditorTarget}
          bulkItems={listEditorTarget.bulkItems || []}
          items={[]}
          lists={userLists}
          onClose={() => setListEditorTarget(null)}
          onCreate={createDiscoverList}
          onAdd={addDiscoverMovieToList}
          onAddBulk={addDiscoverMoviesToList}
        />
      )}
      {posterEditor && (
        <PosterEditorModal
          item={posterEditor}
          notify={notify}
          onClose={() => setPosterEditor(null)}
          onSaved={(posterUrl) => updateOwnedPoster(posterEditor.path, posterUrl)}
        />
      )}
    </section>
  );
}

function DiscoverResultGrid({ error, loading, emptyText, className, children }) {
  const items = Array.isArray(children) ? children.filter(Boolean) : children ? [children] : [];
  if (loading) {
    return (
      <div className={cx('discover-grid', className)}>
        <div className="movie-card skeleton-card" />
        <div className="movie-card skeleton-card" />
        <div className="movie-card skeleton-card" />
      </div>
    );
  }
  if (error) {
    return <div className="empty-state discover-empty"><strong>Could not load this view.</strong><span>{error}</span></div>;
  }
  if (!items.length) {
    return <div className="empty-state discover-empty"><strong>{emptyText}</strong><span>Check Settings if this depends on TMDB, Prowlarr, or Ollama.</span></div>;
  }
  return <div className={cx('discover-grid', className)}>{items}</div>;
}

function DiscoverPathBar({ history = [], currentLabel, resetLabel, onBack, onReset, onCrumb }) {
  if (!history.length && !currentLabel) return null;
  return (
    <div className="discover-path-bar" aria-label="Discovery path">
      <button type="button" className="mini-action" onClick={onBack} disabled={!history.length}>
        Back
      </button>
      <div className="discover-crumbs">
        {history.map((item, index) => (
          <button type="button" key={`${item.label}-${index}`} onClick={() => onCrumb(index)}>
            {item.label}
          </button>
        ))}
        {currentLabel && <span>{currentLabel}</span>}
      </div>
      <button type="button" className="mini-action" onClick={onReset}>
        <RefreshCcw size={13} /> {resetLabel}
      </button>
    </div>
  );
}

function DiscoverMovieCard({
  movie,
  reason,
  owned,
  followed,
  expanded,
  details,
  collection,
  itemLists,
  onPlay,
  onStream,
  streamingAvailable,
  streamingLabel,
  onFindTorrent,
  onFollow,
  onTrailer,
  onToggleDetails,
  onPersonBrowse,
  onCollectionBrowse,
  onListBrowse,
  onEditLists,
  onRemoveFromList,
  onEditPoster,
  watched,
  watchlisted,
  onToggleWatched,
  onToggleWatchlist,
  selected,
  onSelect
}) {
  const lowQuality = owned && isLowQuality(owned.resolution);
  const unreleased = !owned && isUnreleasedMovie(movie);
  const posterMovie = owned?.poster_url ? { ...movie, poster_url: owned.poster_url } : movie;
  return (
    <UnifiedMovieCard
      className={cx('discover-movie-card', expanded && 'discover-card-expanded')}
      title={movie.title}
      year={movie.year}
      posterUrl={posterMovie.poster_url}
      rating={movie.tmdb_rating}
      voteCount={formatVoteCount(movie.tmdb_vote_count)}
      chips={(movie.genres || []).slice(0, 2)}
      mutedChips={[
        movie.language,
        movie.country_flag || movie.country,
        owned?.resolution,
        owned?.size_human
      ]}
      statusLabel={owned ? (lowQuality ? 'Upgrade candidate' : '') : (unreleased ? 'Unreleased' : (followed ? 'Following' : 'Not in library'))}
      statusTone={owned ? (lowQuality ? 'warning' : 'neutral') : (unreleased ? 'warning' : 'missing')}
      ownedBadge={Boolean(owned)}
      expanded={expanded}
      onToggle={onToggleDetails}
      showPlayOverlay={Boolean(owned)}
      onPlay={owned?.path ? () => onPlay(owned.path) : undefined}
      cornerControls={(
        <>
          <PosterStateControls
            title={movie.title}
            watched={watched}
            watchlisted={watchlisted}
            onToggleWatched={owned ? onToggleWatched : undefined}
            onToggleWatchlist={onToggleWatchlist}
          />
          <PosterEditButton title={movie.title} onEdit={owned ? onEditPoster : undefined} />
          <SelectionCheckbox
            className="discover-selection-checkbox"
            checked={Boolean(selected)}
            onChange={onSelect}
            label={`Select ${movie.title}`}
          />
        </>
      )}
    >
      {expanded && (
        <>
          {reason && <p className="ai-reason"><Sparkles size={14} /> {reason}</p>}
          <p className="movie-card-plot discover-plot-visible">{movie.plot || 'No plot summary is available yet.'}</p>
          <div className="card-actions">
            {owned ? (
              <>
                <button type="button" className="btn btn-primary btn-green" onClick={() => onPlay(owned.path)}>
                  <Play size={15} /> Play
                </button>
                {lowQuality && (
                  <button type="button" className="btn btn-secondary" onClick={() => onFindTorrent(movie, true)}>
                    <Wand2 size={15} /> Find upgrade
                  </button>
                )}
              </>
            ) : (
              <>
                {!unreleased && (
                  <button type="button" className="btn btn-primary" onClick={() => onFindTorrent(movie)}>
                    <Search size={15} /> Find sources
                  </button>
                )}
                {!unreleased && streamingAvailable && (
                  <button type="button" className="btn btn-secondary btn-green-outline" onClick={() => onStream(movie)}>
                    <MonitorPlay size={15} /> {streamingLabel}
                  </button>
                )}
              </>
            )}
            <button type="button" className="btn btn-secondary" onClick={() => onTrailer(movie)}>
              <Film size={15} /> Trailer
            </button>
            {!owned && (
              <button type="button" className="btn btn-secondary" onClick={() => onFollow(movie)}>
                <Bell size={15} /> {followed ? 'Following' : 'Follow'}
              </button>
            )}
          </div>
          <MovieExpandedDetails
            movie={movie}
            details={details}
            collection={collection}
            itemLists={itemLists}
            directors={movie.directors}
            cast={movie.cast}
            onPersonBrowse={onPersonBrowse}
            onCollectionBrowse={onCollectionBrowse}
            onListBrowse={onListBrowse}
            onEditLists={onEditLists}
            onRemoveFromList={onRemoveFromList}
          />
        </>
      )}
    </UnifiedMovieCard>
  );
}

function MovieFactChips({ movie, owned, lowQuality }) {
  return (
    <>
      <div className="chip-row">
        {(movie.genres || []).slice(0, 3).map((genre) => <span className="chip" key={genre}>{genre}</span>)}
        {movie.language && <span className="chip chip-muted">{movie.language}</span>}
        {(movie.country_flag || movie.country) && <span className="chip chip-muted">{movie.country_flag || movie.country}</span>}
      </div>
      <div className="ownership-row">
        {owned ? (
          <span className={cx('status-badge', lowQuality ? 'status-warning' : 'status-owned')}>
            <CheckCircle2 size={14} />
            Owned - {owned.resolution || 'Unknown'} - {owned.size_human || 'local file'}
          </span>
        ) : (
          <span className="status-badge status-missing">
            <Radio size={14} />
            Not in library
          </span>
        )}
      </div>
    </>
  );
}

function IndexerMovieCard({
  movie,
  selectedIndex,
  owned,
  expanded,
  details,
  collection,
  itemLists,
  notify,
  onVariantSelect,
  onPlay,
  onStream,
  streamingAvailable,
  streamingLabel,
  onFindTorrent,
  onTrailer,
  onToggleDetails,
  onEditLists,
  onRemoveFromList,
  onEditPoster,
  watched,
  watchlisted,
  onToggleWatched,
  onToggleWatchlist,
  selected,
  onSelect
}) {
  const lowQuality = owned && isLowQuality(owned.resolution);
  const variants = sortTorrentVariants(movie.variants || []);
  const selectedVariant = variants[selectedIndex] || variants[0] || {};
  const posterMovie = owned?.poster_url ? { ...movie, poster_url: owned.poster_url } : movie;

  return (
    <UnifiedMovieCard
      className={cx('indexer-card', expanded && 'discover-card-expanded')}
      title={movie.title}
      year={movie.year}
      posterUrl={posterMovie.poster_url}
      rating={movie.tmdb_rating}
      voteCount={formatVoteCount(movie.tmdb_vote_count)}
      chips={(movie.genres || []).slice(0, 2)}
      mutedChips={[
        selectedVariant.resolution || movie.best_resolution,
        selectedVariant.indexer,
        owned?.resolution,
        owned?.size_human
      ]}
      statusLabel={owned ? (lowQuality ? 'Upgrade candidate' : '') : `${formatCount(selectedVariant.seeders)} seeders`}
      statusTone={owned ? (lowQuality ? 'warning' : 'neutral') : 'neutral'}
      ownedBadge={Boolean(owned)}
      expanded={expanded}
      onToggle={onToggleDetails}
      showPlayOverlay={Boolean(owned)}
      onPlay={owned?.path ? () => onPlay(owned.path) : undefined}
      cornerControls={(
        <>
          <PosterStateControls
            title={movie.title}
            watched={watched}
            watchlisted={watchlisted}
            onToggleWatched={owned ? onToggleWatched : undefined}
            onToggleWatchlist={onToggleWatchlist}
          />
          <PosterEditButton title={movie.title} onEdit={owned ? onEditPoster : undefined} />
          <SelectionCheckbox
            className="discover-selection-checkbox"
            checked={Boolean(selected)}
            onChange={onSelect}
            label={`Select ${movie.title}`}
          />
        </>
      )}
    >
      {expanded && (
        <>
          <div className="variant-stack" aria-label={`Available releases for ${movie.title}`}>
            {variants.map((variant, index) => (
              <button
                type="button"
                key={`${variant.title}-${index}`}
                className={cx('variant-option', index === selectedIndex && 'variant-option-active')}
                onClick={() => onVariantSelect(index)}
              >
                <strong>{variant.resolution || 'Unknown'}</strong>
                <span><span className="torrent-seeders">Seeders {formatCount(variant.seeders)}</span></span>
                <span>{variant.size_human || '?'}</span>
                <small>{variant.indexer || 'Unknown tracker'}</small>
              </button>
            ))}
          </div>
          <p className="movie-card-plot discover-plot-visible">{movie.plot || 'No plot summary is available yet.'}</p>
          <MovieExpandedDetails
            movie={movie}
            details={details}
            collection={collection}
            itemLists={itemLists}
            onEditLists={onEditLists}
            onRemoveFromList={onRemoveFromList}
          />
          <div className="indexer-action-row indexer-action-row-expanded">
            <div className="indexer-selected-meta">
              <strong>{formatCount(selectedVariant.seeders)} seeders</strong>
              <span>{selectedVariant.indexer || 'Unknown tracker'}</span>
              <small>{selectedVariant.size_human || '?'}</small>
            </div>
            <TorrentActions
              variant={selectedVariant}
              movieTitle={movie.title || movie.parsed_title}
              movieYear={movie.year || movie.parsed_year}
              notify={notify}
              primary
            />
            {owned ? (
              <button type="button" className="btn btn-primary btn-green" onClick={() => onPlay(owned.path)}>
                <Play size={15} /> Play
              </button>
            ) : streamingAvailable ? (
              <button type="button" className="btn btn-secondary btn-green-outline" onClick={() => onStream(movie)}>
                <MonitorPlay size={15} /> {streamingLabel}
              </button>
            ) : null}
            {lowQuality ? (
              <button type="button" className="btn btn-secondary" onClick={() => onFindTorrent(movie, true)}>
                <Wand2 size={15} /> Find upgrade
              </button>
            ) : (
              <button type="button" className="btn btn-secondary" onClick={() => onFindTorrent(movie)}>
                <Search size={15} /> Find sources
              </button>
            )}
            <button type="button" className="btn btn-secondary" onClick={() => onTrailer(movie)}>
              <Film size={15} /> Trailer
            </button>
          </div>
        </>
      )}
    </UnifiedMovieCard>
  );
}

function MovieExpandedDetails({
  movie,
  details,
  collection,
  itemLists = [],
  directors,
  cast,
  onPersonBrowse,
  onCollectionBrowse,
  onListBrowse,
  onEditLists,
  onRemoveFromList,
  onEditCollection,
  onResetCollection,
  emptyListText = 'Not in any user list yet.'
}) {
  const loading = details?.loading;
  const expandedDirectors = directors?.length ? directors : details?.directors?.length ? details.directors : details?.director?.name ? [details.director] : [];
  const expandedCast = (cast?.length ? cast : details?.cast || []).slice(0, 6);
  const activeCollection = collection?.id ? collection : details?.collection || {};
  const releaseDate = movie?.release_date || details?.release_date || '';
  const releaseDateLabel = isUnreleasedMovie({ release_date: releaseDate }) ? formatReleaseDateLabel(releaseDate) : '';
  const canBrowsePeople = Boolean(onPersonBrowse);
  const canBrowseCollection = Boolean(onCollectionBrowse);
  const canBrowseLists = Boolean(onListBrowse);
  const collectionDetail = Number.isFinite(activeCollection.owned_count)
    ? `${formatCount(activeCollection.owned_count)} owned${activeCollection.unresolved_count ? `, ${formatCount(activeCollection.unresolved_count)} need identity review` : ''}`
    : `${formatCount((activeCollection.parts || []).length)} movies, ${activeCollection.source || 'TMDB'} collection`;

  return (
    <div className="movie-expanded-details">
      {loading ? (
        <div className="people-loading"><Loader2 size={15} className="spin" /> Loading TMDB details...</div>
      ) : details?.error ? (
        <p className="discover-detail-error"><AlertTriangle size={15} /> {details.error}</p>
      ) : (
        <>
          {(details?.tagline || details?.runtime || releaseDateLabel) && (
            <div className="movie-expanded-facts">
              {releaseDateLabel && <div><span>Release date</span><strong>Releases {releaseDateLabel}</strong></div>}
              {details?.tagline && <div><span>Tagline</span><strong>{details.tagline}</strong></div>}
              {details?.runtime && <div><span>Runtime</span><strong>{details.runtime} min</strong></div>}
            </div>
          )}
          <div className="people-panel movie-expanded-people-panel">
            <div className="director-panel">
              <span className="mini-label">Director</span>
              {expandedDirectors.length ? (
                expandedDirectors.slice(0, 2).map((person) => (
                  canBrowsePeople ? (
                    <button type="button" className="director-person" key={person.id || person.name} onClick={() => onPersonBrowse('director', person)}>
                      <PersonAvatar person={person} />
                      <span>
                        <strong>{person.name}</strong>
                        <small>Show directed movies</small>
                      </span>
                    </button>
                  ) : (
                    <div className="director-person discover-person-static" key={person.id || person.name}>
                    <PersonAvatar person={person} />
                    <span>
                      <strong>{person.name}</strong>
                      <small>Director</small>
                    </span>
                    </div>
                  )
                ))
              ) : (
                <small>No director data found.</small>
              )}
            </div>
            <div className="cast-panel">
              <span className="mini-label">Top cast</span>
              {expandedCast.length ? (
                <div className="person-grid">
                  {expandedCast.map((person) => (
                    canBrowsePeople ? (
                      <button type="button" className="person-card" key={`${person.id || person.name}-${person.character || ''}`} onClick={() => onPersonBrowse('actor', person)}>
                        <PersonAvatar person={person} />
                        <strong>{person.name}</strong>
                        <small>{person.character || 'Cast'}</small>
                      </button>
                    ) : (
                      <div className="person-card discover-person-static" key={`${person.id || person.name}-${person.character || ''}`}>
                        <PersonAvatar person={person} />
                        <strong>{person.name}</strong>
                        <small>{person.character || 'Cast'}</small>
                      </div>
                    )
                  ))}
                </div>
              ) : (
                <small>No cast data found.</small>
              )}
            </div>
            {activeCollection?.id && (
              <div className="collection-panel">
                {canBrowseCollection ? (
                  <button type="button" className="collection-main-action" onClick={() => onCollectionBrowse(activeCollection)}>
                    <Clapperboard size={17} />
                    <span>
                      <strong>{activeCollection.name}</strong>
                      <small>{collectionDetail}</small>
                    </span>
                  </button>
                ) : (
                  <div className="collection-main-action discover-collection-static">
                    <Clapperboard size={17} />
                    <span>
                      <strong>{activeCollection.name}</strong>
                      <small>{collectionDetail}</small>
                    </span>
                  </div>
                )}
                {onEditCollection ? (
                  <div className="collection-actions">
                    <button type="button" className="mini-action" onClick={() => onEditCollection(activeCollection)}>Edit</button>
                    {activeCollection.is_edited && onResetCollection ? (
                      <button type="button" className="mini-action mini-action-danger" onClick={() => onResetCollection(activeCollection)}>
                        <RefreshCcw size={13} /> Reset
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            )}
            <div className="lists-panel">
              <div className="lists-panel-header">
                <span className="mini-label">Lists</span>
                {onEditLists ? <button type="button" className="mini-action" onClick={onEditLists}>Add to list</button> : null}
              </div>
              {itemLists.length ? (
                <div className="list-chip-row">
                  {itemLists.map((list) => (
                    <span className="list-chip" key={list.id}>
                      <button type="button" onClick={canBrowseLists ? () => onListBrowse(list) : undefined}>{list.name}</button>
                      {onRemoveFromList ? (
                        <button type="button" aria-label={`Remove ${movie.title} from ${list.name}`} onClick={() => onRemoveFromList(list.id)}>
                          <Trash2 size={13} />
                        </button>
                      ) : null}
                    </span>
                  ))}
                </div>
              ) : (
                <small>{emptyListText}</small>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function formatVoteCount(value) {
  const count = Number(value || 0);
  if (!count) return '';
  if (count >= 1000) return `${(count / 1000).toFixed(count >= 10000 ? 0 : 1)}k votes`;
  return `${formatCount(count)} votes`;
}

function Rating({ value, votes }) {
  if (!value) return null;
  const voteLabel = formatVoteCount(votes);
  return (
    <span className="rating">
      <Star size={14} fill="currentColor" />
      {value}{voteLabel ? ` - ${voteLabel}` : ''}
    </span>
  );
}

const aiControlExamples = [
  'Find Tom Cruise movies I own',
  'Create a list of top rated sci-fi from 2010',
  'Download unowned Nolan movies in 1080p',
  'Delete files larger than 10 GB'
];

const aiControlPreviewStages = [
  'Understanding request with Ollama...',
  'Contacting TMDB...',
  'Checking your library...',
  'Searching trusted indexers...',
  'Preparing review...'
];

function AIControlWorkspace({
  followed = [],
  notify,
  onPlay,
  onStream,
  streamingAvailable,
  streamingLabel,
  onFindTorrent,
  onOpenTrailer,
  onFollow,
  onEditPoster
}) {
  const [prompt, setPrompt] = useState('');
  const [aiControlPlan, setAiControlPlan] = useState(null);
  const [aiControlBusy, setAiControlBusy] = useState(false);
  const [aiControlError, setAiControlError] = useState('');
  const [aiControlLoadingStep, setAiControlLoadingStep] = useState(null);
  const [aiControlCardView, setAiControlCardView] = useState(false);
  const aiControlStageTimersRef = useRef([]);

  function clearAiControlStageTimers() {
    aiControlStageTimersRef.current.forEach((timer) => window.clearTimeout(timer));
    aiControlStageTimersRef.current = [];
  }

  function startAiControlPreviewProgress() {
    clearAiControlStageTimers();
    setAiControlLoadingStep(0);
    aiControlStageTimersRef.current = aiControlPreviewStages.slice(1).map((_, index) => (
      window.setTimeout(() => setAiControlLoadingStep(index + 1), 1800 + index * 2600)
    ));
  }

  useEffect(() => () => clearAiControlStageTimers(), []);

  async function previewAiControlCommand(event) {
    event.preventDefault();
    const command = prompt.trim();
    if (!command) {
      setAiControlError('Enter a command first.');
      return;
    }
    setAiControlBusy(true);
    setAiControlError('');
    setAiControlCardView(false);
    startAiControlPreviewProgress();
    try {
      const data = await fetchJson('/api/ai-control/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: command })
      });
      setAiControlPlan(data);
      if (data.state === 'valid_plan') {
        notify(data.message || 'AI Control preview ready', 'success');
      } else {
        notify(data.message || 'AI Control needs clarification', 'neutral');
      }
    } catch (error) {
      setAiControlError(error.message);
      notify(`AI Control preview failed: ${error.message}`, 'error');
    } finally {
      clearAiControlStageTimers();
      setAiControlLoadingStep(null);
      setAiControlBusy(false);
    }
  }

  async function executeAiControlPlan() {
    if (!aiControlPlan?.plan_id) return;
    setAiControlBusy(true);
    setAiControlError('');
    setAiControlLoadingStep(null);
    try {
      const data = await fetchJson('/api/ai-control/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan_id: aiControlPlan.plan_id })
      });
      setAiControlPlan(data);
      notify(data.message || 'AI Control action executed', 'success');
    } catch (error) {
      setAiControlError(error.message);
      notify(`AI Control execute failed: ${error.message}`, 'error');
    } finally {
      setAiControlBusy(false);
    }
  }

  function useExample(example) {
    setPrompt(example);
    setAiControlError('');
  }

  return (
    <section className="ai-control-workspace">
      <header className="library-header ai-control-header">
        <div>
          <p className="screen-kicker">AI command console</p>
          <h2>AI Control <ExperimentalBadge /></h2>
          <p>Turn plain-language movie commands into reviewable CP actions for finding, lists, downloads, and cleanup.</p>
        </div>
      </header>

      <form className="ai-control-command" onSubmit={previewAiControlCommand}>
        <label className="ai-control-prompt">
          <span>Command</span>
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Tell CP what to find, list, download, or delete..."
            rows={4}
          />
        </label>
        <div className="ai-control-command-actions">
          <button type="submit" className="btn btn-primary btn-violet" disabled={aiControlBusy}>
            {aiControlBusy ? <Loader2 size={15} className="spin" /> : <Sparkles size={15} />} Preview command
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => { setPrompt(''); setAiControlPlan(null); setAiControlError(''); setAiControlCardView(false); }} disabled={aiControlBusy}>
            <X size={15} /> Clear
          </button>
        </div>
      </form>

      <div className="ai-control-guide">
        <div className="ai-control-example-row">
          {aiControlExamples.map((example) => (
            <button type="button" className="mini-action" key={example} onClick={() => useExample(example)}>
              {example}
            </button>
          ))}
        </div>
        <strong>No action runs automatically. Every result is reviewed before you confirm it.</strong>
      </div>

      {aiControlBusy && aiControlLoadingStep !== null && (
        <div className="ai-control-progress" role="status" aria-live="polite">
          <Loader2 size={16} className="spin" />
          <div>
            <strong>{aiControlPreviewStages[aiControlLoadingStep]}</strong>
            <small>Large actor/director requests can take a while because CP reviews TMDB, your library, and trusted indexers before showing a plan.</small>
          </div>
        </div>
      )}

      {aiControlError && (
        <div className="library-status library-status-error">
          <AlertTriangle size={16} />
          <span>{aiControlError}</span>
        </div>
      )}

      <AIControlResult
        aiControlPlan={aiControlPlan}
        busy={aiControlBusy}
        onExecute={executeAiControlPlan}
        aiControlCardView={aiControlCardView}
        setAiControlCardView={setAiControlCardView}
        followed={followed}
        notify={notify}
        onPlay={onPlay}
        onStream={onStream}
        streamingAvailable={streamingAvailable}
        streamingLabel={streamingLabel}
        onFindTorrent={onFindTorrent}
        onOpenTrailer={onOpenTrailer}
        onFollow={onFollow}
        onEditPoster={onEditPoster}
      />
    </section>
  );
}

function AIControlResult({
  aiControlPlan,
  busy,
  onExecute,
  aiControlCardView,
  setAiControlCardView,
  followed,
  notify,
  onPlay,
  onStream,
  streamingAvailable,
  streamingLabel,
  onFindTorrent,
  onOpenTrailer,
  onFollow,
  onEditPoster
}) {
  const plan = aiControlPlan;
  const [currentPage, setCurrentPage] = useState(1);
  const [aiControlDangerPhrase, setAiControlDangerPhrase] = useState('');
  const planKey = `${plan?.plan_id || ''}-${plan?.summary || ''}-${plan?.message || ''}`;

  useEffect(() => {
    setCurrentPage(1);
    setAiControlDangerPhrase('');
    setAiControlCardView(false);
  }, [planKey, setAiControlCardView]);

  if (!plan) {
    return (
      <div className="empty-state library-empty ai-control-empty">
        <Bot size={30} />
        <strong>No command preview yet.</strong>
        <span>Use an example or type a command to see the reviewed plan here.</span>
      </div>
    );
  }
  const ready = plan.state === 'valid_plan';
  const rows = plan.items || [];
  const blocked = plan.blocked || [];
  const pageSize = Number(plan.page_size || 50);
  const totalMatches = Number(plan.total_matches || rows.length);
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const pageStart = (safeCurrentPage - 1) * pageSize;
  const visibleRows = rows.slice(pageStart, pageStart + pageSize);
  const pageLabel = rows.length > pageSize
    ? `Showing ${formatCount(pageStart + 1)}-${formatCount(Math.min(pageStart + pageSize, rows.length))} of ${formatCount(totalMatches)}`
    : `${formatCount(totalMatches)} total`;
  const requiresDeletePhrase = ready && plan.action === 'delete' && plan.requires_extra_confirmation;
  const deletePhraseConfirmed = !requiresDeletePhrase || aiControlDangerPhrase.trim() === String(plan.confirmation_phrase || '').trim();
  const canDisplayCards = ready && plan.action === 'find' && visibleRows.length > 0;
  return (
    <section className={cx('ai-control-result', ready ? 'ai-control-result-ready' : 'ai-control-result-blocked')}>
      <div className="ai-control-result-header">
        <div>
          <p className="screen-kicker">{plan.state || 'AI Control'}</p>
          <h3>{plan.summary || plan.message || 'Command result'}</h3>
          {plan.message && <p>{plan.message}</p>}
        </div>
        <div className="ai-control-result-actions">
          {canDisplayCards && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                if (aiControlCardView) setAiControlCardView(false);
                else setAiControlCardView(true);
              }}
            >
              {aiControlCardView ? <RefreshCcw size={15} /> : <Film size={15} />} {aiControlCardView ? 'Back to table' : 'Display as cards'}
            </button>
          )}
          <button
            type="button"
            className="btn btn-primary"
            onClick={onExecute}
            disabled={!aiControlPlan?.plan_id || busy || !ready || !deletePhraseConfirmed}
          >
            {busy ? <Loader2 size={15} className="spin" /> : <Check size={15} />} Confirm action
          </button>
        </div>
      </div>
      {ready && (
        <AIControlPagination
          pageLabel={pageLabel}
          currentPage={safeCurrentPage}
          totalPages={totalPages}
          onPrevious={() => setCurrentPage((page) => Math.max(1, page - 1))}
          onNext={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
        />
      )}
      {requiresDeletePhrase && (
        <label className="ai-control-danger-confirm">
          <span>Type the confirmation phrase before deleting this batch.</span>
          <strong>{plan.confirmation_phrase}</strong>
          <input
            value={aiControlDangerPhrase}
            onChange={(event) => setAiControlDangerPhrase(event.target.value)}
            placeholder="Type the confirmation phrase"
          />
        </label>
      )}
      {canDisplayCards && aiControlCardView ? (
        <AIControlCardResults
          plan={plan}
          rows={visibleRows}
          followed={followed}
          notify={notify}
          onPlay={onPlay}
          onStream={onStream}
          streamingAvailable={streamingAvailable}
          streamingLabel={streamingLabel}
          onFindTorrent={onFindTorrent}
          onOpenTrailer={onOpenTrailer}
          onFollow={onFollow}
          onEditPoster={onEditPoster}
        />
      ) : (
        !aiControlCardView && visibleRows.length > 0 && <AIControlTable rows={visibleRows} action={plan.action} />
      )}
      {blocked.length > 0 && (
        <div className="ai-control-blocked">
          <h4>Blocked or skipped</h4>
          <AIControlTable rows={blocked} action={plan.action} compact />
        </div>
      )}
    </section>
  );
}

function AIControlPagination({ pageLabel, currentPage, totalPages, onPrevious, onNext }) {
  return (
    <div className="ai-control-pagination">
      <span>{pageLabel}</span>
      {totalPages > 1 && (
        <div>
          <button type="button" className="mini-action" onClick={onPrevious} disabled={currentPage <= 1}>
            Previous page
          </button>
          <strong>{formatCount(currentPage)} / {formatCount(totalPages)}</strong>
          <button type="button" className="mini-action" onClick={onNext} disabled={currentPage >= totalPages}>
            Next page
          </button>
        </div>
      )}
    </div>
  );
}

function AIControlCardResults({
  plan,
  rows,
  followed,
  notify,
  onPlay,
  onStream,
  streamingAvailable,
  streamingLabel,
  onFindTorrent,
  onOpenTrailer,
  onFollow,
  onEditPoster
}) {
  const [ownership, setOwnership] = useState(() => buildAiControlOwnershipMap(rows));
  const [userLists, setUserLists] = useState([]);
  const [detailsCache, setDetailsCache] = useState({});
  const [collectionCache, setCollectionCache] = useState({});
  const [expandedMovieKey, setExpandedMovieKey] = useState('');
  const [selectedAiControlKeys, setSelectedAiControlKeys] = useState(() => new Set());
  const [listEditorTarget, setListEditorTarget] = useState(null);
  const movies = rows || [];

  const loadUserLists = useCallback(async () => {
    try {
      const data = await fetchJson('/api/user/lists');
      setUserLists(data.lists || []);
    } catch (error) {
      notify?.(`Lists unavailable: ${error.message}`, 'error');
    }
  }, [notify]);

  useEffect(() => {
    loadUserLists();
    window.addEventListener('cp-curation-changed', loadUserLists);
    return () => window.removeEventListener('cp-curation-changed', loadUserLists);
  }, [loadUserLists]);

  useEffect(() => {
    setOwnership(buildAiControlOwnershipMap(movies));
    setSelectedAiControlKeys(new Set());
    setExpandedMovieKey('');
    checkAiControlOwnership(movies);
  }, [plan?.summary]);

  async function checkAiControlOwnership(items) {
    const payload = (items || [])
      .filter((movie) => movie?.title)
      .map((movie) => ({ tmdb_id: movie.tmdb_id || '', imdb_id: movie.imdb_id || '', title: movie.title, year: movie.year || '' }));
    if (!payload.length) return;
    try {
      const check = await fetchJson('/api/library/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ movies: payload })
      });
      setOwnership((state) => ({ ...state, ...buildOwnershipMap(check.results || []) }));
    } catch {
      // AI Control card view can still render without best-effort ownership enrichment.
    }
  }

  async function loadAiControlDetails(movie) {
    if (!movie?.tmdb_id) return null;
    const id = String(movie.tmdb_id);
    let details = detailsCache[id];
    if (!details) {
      setDetailsCache((state) => ({ ...state, [id]: { loading: true, cast: [], directors: [], collection: {}, trailer_url: '' } }));
      try {
        details = await fetchJson(`/api/tmdb/details?tmdb_id=${encodeURIComponent(id)}`);
        setDetailsCache((state) => ({ ...state, [id]: details }));
      } catch (error) {
        details = { error: error.message, cast: [], directors: [], collection: {}, trailer_url: '' };
        setDetailsCache((state) => ({ ...state, [id]: details }));
      }
    }
    if (details?.collection?.id && !collectionCache[details.collection.id]) {
      fetchJson(`/api/tmdb/collection?collection_id=${encodeURIComponent(details.collection.id)}`)
        .then((collectionData) => setCollectionCache((state) => ({ ...state, [details.collection.id]: collectionData })))
        .catch(() => {});
    }
    return details;
  }

  function toggleAiControlDetails(movie) {
    const key = movieKey(movie);
    const nextKey = expandedMovieKey === key ? '' : key;
    setExpandedMovieKey(nextKey);
    if (nextKey) loadAiControlDetails(movie);
  }

  async function openAiControlTrailer(movie) {
    if (!movie?.tmdb_id) {
      onOpenTrailer(movie, '');
      return;
    }
    const details = await loadAiControlDetails(movie);
    onOpenTrailer(movie, details?.trailer_url || '');
  }

  async function createAiControlList(name) {
    const created = await fetchJson('/api/user/lists', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    await loadUserLists();
    announceCurationChanged();
    notify?.(`List created: ${created.name}`);
    return created;
  }

  async function addAiControlMovieToList(listId, movie) {
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie: moviePayload(movie) })
    });
    await loadUserLists();
    announceCurationChanged();
    notify?.('Movie added to list');
  }

  async function addAiControlMoviesToList(listId, moviesToAdd) {
    await addMoviePayloadsToList(listId, (moviesToAdd || []).map((movie) => moviePayload(movie)));
    await loadUserLists();
    announceCurationChanged();
    notify?.(`${formatCount((moviesToAdd || []).length)} movie${(moviesToAdd || []).length === 1 ? '' : 's'} added to list`);
    setSelectedAiControlKeys(new Set());
  }

  async function removeAiControlMovieFromList(listId, movie) {
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie: moviePayload(movie) })
    });
    await loadUserLists();
    announceCurationChanged();
    notify?.('Movie removed from list');
  }

  async function toggleAiControlSystemList(systemType, movie, owned) {
    const payload = discoverMoviePayload(movie, owned);
    const currentLists = listsForDiscoverMovie(movie, userLists, owned);
    const active = currentLists.some((list) => list.system_type === systemType || list.id === systemType);
    await fetchJson(`/api/user/system-lists/${encodeURIComponent(systemType)}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie: payload, active: !active })
    });
    await loadUserLists();
    announceCurationChanged();
    notify?.(`${movie.title} ${active ? 'removed from' : 'added to'} ${systemType === 'watched' ? 'Watched' : 'Watchlist'}`);
  }

  function toggleAiControlSelection(movie, owned, checked) {
    const key = movieIdentityKey(discoverMoviePayload(movie, owned));
    setSelectedAiControlKeys((current) => {
      const next = new Set(current);
      if (checked) next.add(key);
      else next.delete(key);
      return next;
    });
  }

  function selectAllAiControlMovies() {
    setSelectedAiControlKeys(new Set(movies.map((movie) => movieIdentityKey(discoverMoviePayload(movie, ownedMovieFor(movie, ownership))))));
  }

  function clearAiControlSelection() {
    setSelectedAiControlKeys(new Set());
  }

  const selectedAiControlMovies = useMemo(() => (
    movies
      .map((movie) => discoverMoviePayload(movie, ownedMovieFor(movie, ownership)))
      .filter((movie) => selectedAiControlKeys.has(movieIdentityKey(movie)))
  ), [movies, ownership, selectedAiControlKeys]);
  const allAiControlMoviesSelected = movies.length > 0 && movies.every((movie) => (
    selectedAiControlKeys.has(movieIdentityKey(discoverMoviePayload(movie, ownedMovieFor(movie, ownership))))
  ));

  return (
    <div className="ai-control-card-results">
      <div className="bulk-selection-bar discover-bulk-selection ai-control-card-toolbar">
        <SelectionCheckbox
          className="discover-selection-master"
          checked={allAiControlMoviesSelected}
          onChange={(checked) => { if (checked) selectAllAiControlMovies(); else clearAiControlSelection(); }}
          label="Select all AI Control results"
        />
        <span>{selectedAiControlMovies.length ? `${formatCount(selectedAiControlMovies.length)} selected` : `${formatCount(movies.length)} AI Control result${movies.length === 1 ? '' : 's'}`}</span>
        <button type="button" className="mini-action" onClick={selectAllAiControlMovies}>Select all results</button>
        <button type="button" className="mini-action" onClick={clearAiControlSelection} disabled={!selectedAiControlMovies.length}>Clear</button>
        <button type="button" className="mini-action" onClick={() => setListEditorTarget({ bulkItems: selectedAiControlMovies })} disabled={!selectedAiControlMovies.length}>
          <CirclePlus size={13} /> Add selected to list
        </button>
      </div>

      <DiscoverResultGrid emptyText="No AI Control movies are available for card display.">
        {movies.map((movie, index) => {
          const owned = ownedMovieFor(movie, ownership) || (movie.path ? movie : null);
          const key = movieIdentityKey(discoverMoviePayload(movie, owned));
          const details = movie.tmdb_id ? detailsCache[String(movie.tmdb_id)] : null;
          const collection = movie.tmdb_id && details?.collection?.id ? collectionCache[details.collection.id] || details.collection : {};
          const movieWithDetails = details ? { ...movie, plot: movie.plot || details.plot || '', release_date: movie.release_date || details.release_date || '' } : movie;
          return (
            <DiscoverMovieCard
              key={`${movie.tmdb_id || movie.path || movie.title}-${movie.year}-${index}`}
              movie={movieWithDetails}
              owned={owned}
              followed={followed.some((item) => movieKey(item) === movieKey(movie))}
              expanded={expandedMovieKey === movieKey(movie)}
              details={details}
              collection={collection}
              itemLists={listsForDiscoverMovie(movie, userLists, owned)}
              watched={listsForDiscoverMovie(movie, userLists, owned).some((list) => list.system_type === 'watched')}
              watchlisted={listsForDiscoverMovie(movie, userLists, owned).some((list) => list.system_type === 'watchlist')}
              onToggleWatched={owned ? () => toggleAiControlSystemList('watched', movie, owned) : undefined}
              onToggleWatchlist={() => toggleAiControlSystemList('watchlist', movie, owned)}
              selected={selectedAiControlKeys.has(key)}
              onSelect={(checked) => toggleAiControlSelection(movie, owned, checked)}
              onPlay={onPlay}
              onStream={onStream}
              streamingAvailable={streamingAvailable}
              streamingLabel={streamingLabel}
              onFindTorrent={onFindTorrent}
              onFollow={onFollow}
              onTrailer={openAiControlTrailer}
              onToggleDetails={() => toggleAiControlDetails(movie)}
              onEditLists={() => setListEditorTarget(discoverMoviePayload(movie, owned))}
              onRemoveFromList={(listId) => removeAiControlMovieFromList(listId, discoverMoviePayload(movie, owned))}
              onEditPoster={owned?.path ? () => onEditPoster?.(owned, movie) : undefined}
            />
          );
        })}
      </DiscoverResultGrid>

      {listEditorTarget && (
        <ListEditorModal
          item={listEditorTarget.bulkItems ? null : listEditorTarget}
          bulkItems={listEditorTarget.bulkItems || []}
          items={[]}
          lists={userLists}
          onClose={() => setListEditorTarget(null)}
          onCreate={createAiControlList}
          onAdd={addAiControlMovieToList}
          onAddBulk={addAiControlMoviesToList}
        />
      )}
    </div>
  );
}

function buildAiControlOwnershipMap(movies) {
  return buildOwnershipMap((movies || [])
    .filter((movie) => movie?.path)
    .map((movie) => ({ ...movie, found: true })));
}

function AIControlTable({ rows, action, compact = false }) {
  return (
    <div className={cx('ai-control-table', compact && 'ai-control-table-compact')}>
      <div className="ai-control-table-head">
        <span>Movie</span>
        <span>{action === 'delete' ? 'Path' : action === 'download' ? 'Source' : 'Source'}</span>
        <span>Status</span>
        <span>Reason</span>
      </div>
      {rows.map((row, index) => (
        <div className="ai-control-table-row" key={`${row.path || row.tmdb_id || row.title}-${index}`}>
          <span>
            <strong>{row.title || row.variant?.title || 'Untitled'}</strong>
            <small>{row.year || row.size_gb ? [row.year, row.size_gb ? `${row.size_gb} GB` : ''].filter(Boolean).join(' - ') : 'No year'}</small>
          </span>
          <span title={row.path || row.variant?.title || row.source || row.reason || ''}>
            {row.path || row.variant?.indexer || row.source || row.reason || 'Review'}
          </span>
          <span>{row.status || 'ready'}</span>
          <span title={row.reason || ''}>{row.reason || (row.status === 'ready' ? 'Ready for review' : 'Review')}</span>
        </div>
      ))}
    </div>
  );
}

function MovieListsWorkspace({
  notify,
  onPlay,
  onFindTorrent,
  onOpenTrailer,
  onStream,
  streamingAvailable,
  streamingLabel,
  followed = [],
  onFollow,
  onEditPoster
}) {
  const [libraryItems, setLibraryItems] = useState([]);
  const [lists, setLists] = useState([]);
  const [selectedListId, setSelectedListId] = useState('');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedKeys, setSelectedKeys] = useState(() => new Set());
  const [newListName, setNewListName] = useState('');
  const [renameValue, setRenameValue] = useState('');
  const [expandedKey, setExpandedKey] = useState('');
  const [detailsCache, setDetailsCache] = useState({});
  const [collectionCache, setCollectionCache] = useState({});
  const [listEditorTarget, setListEditorTarget] = useState(null);
  const [copyMovies, setCopyMovies] = useState(null);
  const [tmdbAddOpen, setTmdbAddOpen] = useState(false);
  const [metadataCorrection, setMetadataCorrection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [fulfillment, setFulfillment] = useState(null);

  const selectedList = lists.find((list) => list.id === selectedListId) || lists[0] || null;
  const model = useMemo(() => buildMovieListViewModel({
    libraryItems,
    list: selectedList,
    query,
    statusFilter
  }), [libraryItems, selectedList, query, statusFilter]);
  const selectedRows = model.rows.filter((row) => selectedKeys.has(row.identityKey));
  const allRowsSelected = model.rows.length > 0 && model.rows.every((row) => selectedKeys.has(row.identityKey));
  const selectedListIsSystem = Boolean(selectedList?.system_type);
  const selectedCopyMovies = selectedRows.map((row) => (row.ownedItem ? moviePayload(row.ownedItem) : movieListRowMovie(row)));

  const loadMovieLists = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [libraryData, listsData] = await Promise.all([
        fetchJson('/api/library'),
        fetchJson('/api/user/lists')
      ]);
      setLibraryItems(libraryData.items || []);
      const nextLists = listsData.lists || [];
      setLists(nextLists);
      setSelectedListId((current) => (nextLists.some((list) => list.id === current) ? current : nextLists[0]?.id || ''));
    } catch (loadError) {
      setError(loadError.message);
      notify?.(`Movie lists unavailable: ${loadError.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    loadMovieLists();
    window.addEventListener('cp-curation-changed', loadMovieLists);
    window.addEventListener('cp-library-reconciled', loadMovieLists);
    return () => {
      window.removeEventListener('cp-curation-changed', loadMovieLists);
      window.removeEventListener('cp-library-reconciled', loadMovieLists);
    };
  }, [loadMovieLists]);

  useEffect(() => {
    setSelectedKeys(new Set());
    setExpandedKey('');
  }, [selectedListId, query, statusFilter]);

  useEffect(() => {
    setRenameValue(selectedList?.name || '');
  }, [selectedList?.id, selectedList?.name]);

  function toggleRow(row, checked) {
    setSelectedKeys((current) => {
      const next = new Set(current);
      if (checked) next.add(row.identityKey);
      else next.delete(row.identityKey);
      return next;
    });
  }

  function selectAllVisible() {
    setSelectedKeys(new Set(model.rows.map((row) => row.identityKey)));
  }

  function clearSelection() {
    setSelectedKeys(new Set());
  }

  function movieListRowMovie(row) {
    return row.movie || {
      tmdb_id: row.tmdb_id || '',
      imdb_id: row.imdb_id || '',
      title: row.title,
      year: row.year,
      poster_url: row.poster_url
    };
  }

  async function loadMovieListDetails(row) {
    const movie = movieListRowMovie(row);
    const id = String(movie.tmdb_id || row.ownedPayload?.tmdb_id || '');
    if (!id) return null;
    let details = detailsCache[id];
    if (!details) {
      setDetailsCache((state) => ({ ...state, [id]: { loading: true, cast: [], directors: [], collection: {}, trailer_url: '' } }));
      try {
        details = await fetchJson(`/api/tmdb/details?tmdb_id=${encodeURIComponent(id)}`);
        setDetailsCache((state) => ({ ...state, [id]: details }));
      } catch (detailsError) {
        details = { error: detailsError.message, cast: [], directors: [], collection: {}, trailer_url: '' };
        setDetailsCache((state) => ({ ...state, [id]: details }));
      }
    }
    if (details?.collection?.id && !collectionCache[details.collection.id]) {
      fetchJson(`/api/tmdb/collection?collection_id=${encodeURIComponent(details.collection.id)}`)
        .then((collectionData) => setCollectionCache((state) => ({ ...state, [details.collection.id]: collectionData })))
        .catch(() => {});
    }
    return details;
  }

  function toggleMovieListDetails(row) {
    const nextKey = expandedKey === row.identityKey ? '' : row.identityKey;
    setExpandedKey(nextKey);
    if (nextKey) loadMovieListDetails(row);
  }

  async function openMovieListTrailer(row) {
    const movie = movieListRowMovie(row);
    try {
      const details = await loadMovieListDetails(row);
      onOpenTrailer(movie, details?.trailer_url || '');
    } catch {
      onOpenTrailer(movie, '');
    }
  }

  async function createList(name) {
    const created = await fetchJson('/api/user/lists', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    setNewListName('');
    setSelectedListId(created.id);
    await loadMovieLists();
    announceCurationChanged();
    notify?.(`List created: ${created.name}`);
    return created;
  }

  async function createListFromRail(event) {
    event.preventDefault();
    const name = newListName.trim();
    if (!name) return;
    await createList(name);
  }

  async function renameSelectedList(event) {
    event.preventDefault();
    if (!selectedList || selectedListIsSystem || !renameValue.trim()) return;
    const renamed = await fetchJson(`/api/user/lists/${encodeURIComponent(selectedList.id)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: renameValue.trim() })
    });
    await loadMovieLists();
    announceCurationChanged();
    notify?.(`List renamed: ${renamed.name}`);
  }

  async function deleteSelectedList() {
    if (!selectedList || selectedListIsSystem) return;
    if (!window.confirm(`Delete list "${selectedList.name}"? Movies will not be deleted from Library.`)) return;
    await fetchJson(`/api/user/lists/${encodeURIComponent(selectedList.id)}`, { method: 'DELETE' });
    setSelectedListId('');
    await loadMovieLists();
    announceCurationChanged();
    notify?.('List deleted');
  }

  async function addMovieToList(listId, item) {
    const movie = item?.ownedItem ? moviePayload(item.ownedItem) : moviePayload(item);
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie })
    });
    await loadMovieLists();
    announceCurationChanged();
    notify?.('Movie added to list');
  }

  async function addMoviesToList(listId, movies) {
    await addMoviePayloadsToList(listId, movies.map((movie) => moviePayload(movie)));
    await loadMovieLists();
    announceCurationChanged();
    notify?.(`${formatCount(movies.length)} movie${movies.length === 1 ? '' : 's'} added to list`);
  }

  async function removeMovieFromList(listId, movie) {
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie })
    });
    await loadMovieLists();
    announceCurationChanged();
    notify?.('Movie removed from list');
  }

  async function removeSelectedFromActiveList() {
    if (!selectedList || !selectedRows.length) return;
    for (const row of selectedRows) {
      await removeMovieFromList(selectedList.id, row.ownedItem ? moviePayload(row.ownedItem) : movieListRowMovie(row));
    }
    setSelectedKeys(new Set());
    notify?.(`${formatCount(selectedRows.length)} movie${selectedRows.length === 1 ? '' : 's'} removed from ${selectedList.name}`);
  }

  async function addTmdbMovieToSelectedList(movie) {
    if (!selectedList) return;
    await addMovieToList(selectedList.id, movie);
    setTmdbAddOpen(false);
  }

  async function toggleMovieListSystemList(systemType, row) {
    const owned = row.ownedItem ? moviePayload(row.ownedItem) : null;
    const movie = movieListRowMovie(row);
    const currentLists = row.ownedItem ? listsForItem(row.ownedItem, lists) : listsForDiscoverMovie(movie, lists, owned);
    const active = currentLists.some((list) => list.system_type === systemType || list.id === systemType);
    await fetchJson(`/api/user/system-lists/${encodeURIComponent(systemType)}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie: discoverMoviePayload(movie, owned), active: !active })
    });
    await loadMovieLists();
    announceCurationChanged();
    notify?.(`${row.title} ${active ? 'removed from' : 'added to'} ${systemType === 'watched' ? 'Watched' : 'Watchlist'}`);
  }

  function selectListFromCard(list) {
    if (list?.id) setSelectedListId(list.id);
  }

  async function openFulfillment(action, forcedRows = null) {
    if (!selectedList) return;
    const candidates = forcedRows || (selectedRows.length ? selectedRows : model.allRows.filter((row) => (
      action === 'missing' ? row.status === 'missing' : row.status === 'upgrade'
    )));
    if (!candidates.length) {
      notify?.(action === 'missing' ? 'No missing movies to find.' : 'No upgrade candidates to find.', 'neutral');
      return;
    }
    setFulfillment({ action, loading: true, rows: [], error: '', title: action === 'missing' ? 'Find missing sources' : 'Find upgrade sources' });
    try {
      const data = await fetchJson('/api/user/lists/fulfillment/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          movies: candidates.map((row) => ({
            tmdb_id: row.tmdb_id || row.ownedPayload?.tmdb_id || '',
            imdb_id: row.imdb_id || row.ownedPayload?.imdb_id || '',
            title: row.title,
            year: row.year,
            poster_url: row.poster_url,
            path: row.ownedItem?.path || ''
          }))
        })
      });
      setFulfillment({
        action,
        loading: false,
        rows: data.rows || [],
        blocked: data.blocked || [],
        defaults: data.defaults || {},
        error: '',
        title: action === 'missing' ? 'Find missing sources' : 'Find upgrade sources'
      });
    } catch (previewError) {
      setFulfillment((current) => ({ ...current, loading: false, error: previewError.message }));
    }
  }

  return (
    <section className="library-workspace movie-lists-workspace">
      <header className="library-header movie-lists-header">
        <div>
          <p className="screen-kicker">Mixed owned and wanted lists</p>
          <h2>Movie Lists</h2>
          <p>Review full lists here. Library stays offline-only; this page shows owned, missing, and upgrade candidates together.</p>
        </div>
        <div className="movie-list-summary-strip" aria-label="Selected list summary">
          <span><strong>{formatCount(model.stats.total)}</strong>Total</span>
          <span><strong>{formatCount(model.stats.owned)}</strong>Owned</span>
          <span><strong>{formatCount(model.stats.missing)}</strong>Missing</span>
          <span><strong>{formatCount(model.stats.upgrades)}</strong>Upgrades</span>
        </div>
      </header>

      <form className="library-search-panel movie-lists-search" onSubmit={(event) => event.preventDefault()}>
        <label className="search-field library-main-search">
          <Search size={18} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search the selected list..." />
        </label>
        <button type="submit" className="btn btn-primary library-search-submit"><Search size={16} /> Search</button>
      </form>

      <div className="movie-lists-layout">
        <aside className="movie-lists-rail" aria-label="Movie lists">
          <form className="movie-list-create-inline" onSubmit={createListFromRail}>
            <input value={newListName} onChange={(event) => setNewListName(event.target.value)} placeholder="New list name..." />
            <button type="submit" className="mini-action" disabled={!newListName.trim()}>
              <CirclePlus size={13} /> New list
            </button>
          </form>
          {lists.length ? lists.map((list) => (
            <button
              type="button"
              key={list.id}
              className={cx('movie-list-rail-item', selectedList?.id === list.id && 'movie-list-rail-item-active')}
              onClick={() => setSelectedListId(list.id)}
            >
              <span>{list.name}</span>
              <small>{formatCount((list.movies || []).length)} movies</small>
            </button>
          )) : (
            <div className="empty-state"><strong>No lists yet.</strong><span>Create lists from Library or Discover.</span></div>
          )}
        </aside>

        <div className="movie-lists-main">
          <form className="movie-list-management-bar" onSubmit={renameSelectedList}>
            <input
              value={renameValue}
              onChange={(event) => setRenameValue(event.target.value)}
              disabled={!selectedList || selectedListIsSystem}
              placeholder="No list selected"
              aria-label="Selected list name"
            />
            <button type="submit" className="mini-action" disabled={!selectedList || selectedListIsSystem || !renameValue.trim()}>
              <Pencil size={13} /> Rename list
            </button>
            <button type="button" className="mini-action" onClick={() => setTmdbAddOpen(true)} disabled={!selectedList}>
              <Search size={13} /> Add movie
            </button>
            <button type="button" className="mini-action mini-action-danger" onClick={deleteSelectedList} disabled={!selectedList || selectedListIsSystem}>
              <Trash2 size={13} /> Delete list
            </button>
          </form>

          <div className="library-toolbar movie-lists-filterbar">
            {[
              ['all', 'All'],
              ['owned', 'Owned'],
              ['missing', 'Missing'],
              ['upgrade', 'Upgrade candidates']
            ].map(([value, label]) => (
              <button type="button" key={value} className={cx('filter-chip-button', statusFilter === value && 'filter-chip-button-active')} onClick={() => setStatusFilter(value)}>
                {label}
              </button>
            ))}
          </div>

          {model.rows.length > 0 && (
            <div className="bulk-selection-bar movie-lists-bulk">
              <SelectionCheckbox
                className="movie-lists-select-all"
                checked={allRowsSelected}
                onChange={(checked) => { if (checked) selectAllVisible(); else clearSelection(); }}
                label="Select all visible list movies"
              />
              <span>{selectedRows.length ? `${formatCount(selectedRows.length)} selected` : 'Select movies'}</span>
              <button type="button" className="mini-action" onClick={clearSelection} disabled={!selectedRows.length}>Clear</button>
              <button type="button" className="mini-action" onClick={() => setCopyMovies(selectedCopyMovies)} disabled={!selectedRows.length}>
                <Copy size={13} /> Copy selected to...
              </button>
              <button type="button" className="mini-action mini-action-danger" onClick={removeSelectedFromActiveList} disabled={!selectedRows.length || !selectedList}>
                <Trash2 size={13} /> Remove selected
              </button>
              <button type="button" className="mini-action" onClick={() => openFulfillment('missing')} disabled={!selectedList || !model.allRows.some((row) => row.status === 'missing')}>
                <Download size={13} /> Find missing
              </button>
              <button type="button" className="mini-action" onClick={() => openFulfillment('upgrade')} disabled={!selectedList || !model.allRows.some((row) => row.status === 'upgrade')}>
                <Wand2 size={13} /> Find upgrades
              </button>
            </div>
          )}

          {error ? <div className="library-status library-status-error"><AlertTriangle size={16} /> {error}</div> : null}
          {loading ? (
            <div className="empty-state"><strong>Loading movie lists...</strong><span>Reading Library ownership and saved lists.</span></div>
          ) : selectedList ? (
            model.rows.length ? (
              <div className="library-results library-movie-results movie-lists-card-grid">
                {model.rows.map((row) => {
                  const movie = movieListRowMovie(row);
                  const tmdbId = String(movie.tmdb_id || row.ownedPayload?.tmdb_id || '');
                  const details = tmdbId ? detailsCache[tmdbId] : null;
                  const collection = tmdbId && details?.collection?.id ? collectionCache[details.collection.id] || details.collection : {};
                  const rowLists = row.ownedItem ? listsForItem(row.ownedItem, lists) : listsForDiscoverMovie(movie, lists, null);
                  const watched = rowLists.some((list) => list.system_type === 'watched');
                  const watchlisted = rowLists.some((list) => list.system_type === 'watchlist');
                  if (row.ownedItem) {
                    return (
                      <LibraryMovieCard
                        key={row.identityKey}
                        item={row.ownedItem}
                        expanded={expandedKey === row.identityKey}
                        details={details}
                        collection={collection}
                        itemLists={rowLists}
                        onToggle={() => toggleMovieListDetails(row)}
                        onPlay={onPlay}
                        onFindTorrent={onFindTorrent}
                        onTrailer={() => openMovieListTrailer(row)}
                        onListFilter={selectListFromCard}
                        onEditLists={() => setListEditorTarget({ item: row.ownedItem })}
                        onRemoveFromList={(listId) => removeMovieFromList(listId, moviePayload(row.ownedItem))}
                        onEditPoster={onEditPoster ? () => onEditPoster(row.ownedItem, movie) : undefined}
                        onCorrectMetadata={() => setMetadataCorrection(row.ownedItem)}
                        watched={watched}
                        watchlisted={watchlisted}
                        onToggleWatched={() => toggleMovieListSystemList('watched', row)}
                        onToggleWatchlist={() => toggleMovieListSystemList('watchlist', row)}
                        selected={selectedKeys.has(row.identityKey)}
                        onSelect={(checked) => toggleRow(row, checked)}
                      />
                    );
                  }
                  return (
                    <DiscoverMovieCard
                      key={row.identityKey}
                      movie={movie}
                      owned={null}
                      followed={followed.some((item) => movieKey(item) === movieKey(movie))}
                      expanded={expandedKey === row.identityKey}
                      details={details}
                      collection={collection}
                      itemLists={rowLists}
                      watched={watched}
                      watchlisted={watchlisted}
                      onToggleWatchlist={() => toggleMovieListSystemList('watchlist', row)}
                      selected={selectedKeys.has(row.identityKey)}
                      onSelect={(checked) => toggleRow(row, checked)}
                      onPlay={onPlay}
                      onStream={onStream}
                      streamingAvailable={streamingAvailable}
                      streamingLabel={streamingLabel}
                      onFindTorrent={onFindTorrent}
                      onFollow={onFollow}
                      onTrailer={() => openMovieListTrailer(row)}
                      onToggleDetails={() => toggleMovieListDetails(row)}
                      onListBrowse={selectListFromCard}
                      onEditLists={() => setListEditorTarget(movie)}
                      onRemoveFromList={(listId) => removeMovieFromList(listId, movie)}
                    />
                  );
                })}
              </div>
            ) : (
              <div className="empty-state"><strong>No movies match this view.</strong><span>Change the search or filter chip.</span></div>
            )
          ) : (
            <div className="empty-state"><strong>No list selected.</strong><span>Create or select a list first.</span></div>
          )}
        </div>
      </div>

      {fulfillment && (
        <MovieListFulfillmentDialog
          state={fulfillment}
          setState={setFulfillment}
          onClose={() => setFulfillment(null)}
          notify={notify}
        />
      )}
      {listEditorTarget && (
        <ListEditorModal
          item={listEditorTarget.item || listEditorTarget}
          bulkItems={listEditorTarget.bulkItems || []}
          items={libraryItems}
          lists={lists}
          onClose={() => setListEditorTarget(null)}
          onCreate={createList}
          onAdd={addMovieToList}
          onAddBulk={addMoviesToList}
        />
      )}
      {copyMovies && (
        <ExportCopyDialog
          movies={copyMovies}
          onClose={() => setCopyMovies(null)}
          notify={notify}
        />
      )}
      {tmdbAddOpen && selectedList && (
        <TmdbListAddDialog
          list={selectedList}
          onAdd={addTmdbMovieToSelectedList}
          onClose={() => setTmdbAddOpen(false)}
        />
      )}
      {metadataCorrection && (
        <MetadataCorrectionModal
          item={metadataCorrection}
          notify={notify}
          resetLabel="Reset to provider metadata"
          onClose={() => setMetadataCorrection(null)}
          onSaved={() => loadMovieLists()}
        />
      )}
    </section>
  );
}

function MovieListFulfillmentDialog({ state, setState, onClose, notify }) {
  const readyRows = (state.rows || []).filter((row) => row.status === 'ready');
  const selectedCount = readyRows.filter((row) => row.selected !== false).length;

  function updateRows(updater) {
    setState((current) => ({ ...current, rows: updater(current.rows || []) }));
  }

  function setAllRows(selected) {
    updateRows((rows) => rows.map((row) => (row.status === 'ready' ? { ...row, selected } : row)));
  }

  function setSelectedQuality(quality) {
    updateRows((rows) => rows.map((row) => (
      row.status === 'ready' && row.selected !== false ? { ...row, quality } : row
    )));
  }

  async function submitSelected() {
    setState((current) => ({ ...current, submitting: true, error: '' }));
    try {
      const data = await fetchJson('/api/user/lists/fulfillment/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows: state.rows || [] })
      });
      notify?.(`Submitted ${formatCount(data.submitted_count || 0)} movie${Number(data.submitted_count || 0) === 1 ? '' : 's'} to qBittorrent`);
      onClose();
    } catch (submitError) {
      setState((current) => ({ ...current, submitting: false, error: submitError.message }));
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="torrent-dialog movie-list-fulfillment-dialog" role="dialog" aria-modal="true" aria-label={state.title || 'Movie list fulfillment'} onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <p className="screen-kicker">Trusted source review</p>
            <h2>{state.title || 'Review sources'}</h2>
          </div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close source review">
            <X size={18} />
          </button>
        </div>

        {state.loading ? (
          <div className="source-loading-panel"><Loader2 size={20} className="spin" /><strong>Finding trusted sources...</strong><span>This may take some time depending on selected indexers.</span></div>
        ) : (
          <>
            <div className="bulk-selection-bar movie-list-review-actions">
              <span>{formatCount(selectedCount)} selected for download</span>
              <button type="button" className="mini-action" onClick={() => setAllRows(true)}>Select all</button>
              <button type="button" className="mini-action" onClick={() => setAllRows(false)}>Select none</button>
              <button type="button" className="mini-action" onClick={() => setSelectedQuality('1080p')}>Set selected to 1080p</button>
              <button type="button" className="mini-action" onClick={() => setSelectedQuality('4K')}>Set selected to 4K</button>
            </div>
            {state.error ? <div className="library-status library-status-error"><AlertTriangle size={16} /> {state.error}</div> : null}
            <div className="movie-list-review-table">
              <div className="movie-list-review-head">
                <span>Pick</span>
                <span>Movie</span>
                <span>Release</span>
                <span>Indexer</span>
                <span>Quality</span>
                <span>Status</span>
              </div>
              {(state.rows || []).map((row, index) => (
                <div className="movie-list-review-row" key={`${row.tmdb_id || row.title}-${index}`}>
                  <SelectionCheckbox
                    checked={row.status === 'ready' && row.selected !== false}
                    onChange={(checked) => updateRows((rows) => rows.map((item, itemIndex) => itemIndex === index ? { ...item, selected: checked } : item))}
                    label={`Select ${row.title}`}
                  />
                  <span><strong>{row.title}</strong><small>{row.year || 'Unknown year'}</small></span>
                  <span title={row.variant?.title || row.reason || ''}>{row.variant?.title || row.reason || 'No release'}</span>
                  <span>{row.variant?.indexer || '-'}</span>
                  <select
                    value={row.quality || state.defaults?.quality || '1080p'}
                    disabled={row.status !== 'ready'}
                    onChange={(event) => updateRows((rows) => rows.map((item, itemIndex) => itemIndex === index ? { ...item, quality: event.target.value } : item))}
                  >
                    <option value="1080p">1080p</option>
                    <option value="4K">4K</option>
                  </select>
                  <span>{row.status === 'ready' ? [row.variant?.size_human, row.variant?.seeders ? `${row.variant.seeders} seeders` : ''].filter(Boolean).join(' - ') || 'Ready' : row.reason || row.status}</span>
                </div>
              ))}
            </div>
            {state.blocked?.length ? (
              <p className="settings-empty-note">{formatCount(state.blocked.length)} movie{state.blocked.length === 1 ? '' : 's'} had no trusted source.</p>
            ) : null}
          </>
        )}

        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-primary" onClick={submitSelected} disabled={state.loading || state.submitting || !selectedCount}>
            {state.submitting ? <Loader2 size={15} className="spin" /> : <Download size={15} />} Submit selected to qBittorrent
          </button>
        </div>
      </section>
    </div>
  );
}

function TmdbListAddDialog({ list, onAdd, onClose }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [addingKey, setAddingKey] = useState('');

  async function searchTmdb(event) {
    event.preventDefault();
    const search = query.trim();
    if (!search) return;
    setLoading(true);
    setError('');
    setResults([]);
    try {
      const data = await fetchJson(`/api/tmdb/search?q=${encodeURIComponent(search)}&page=1&include_adult=false`);
      setResults((data.results || []).slice(0, 12));
    } catch (searchError) {
      setError(searchError.message);
    } finally {
      setLoading(false);
    }
  }

  async function addResult(movie) {
    const key = String(movie.tmdb_id || movieIdentityKey(movie));
    setAddingKey(key);
    setError('');
    try {
      await onAdd(movie);
    } catch (addError) {
      setError(addError.message);
      setAddingKey('');
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="torrent-dialog tmdb-list-add-dialog" role="dialog" aria-modal="true" aria-label={`Add movie to ${list.name}`} onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <p className="screen-kicker">Add movie</p>
            <h2>{list.name}</h2>
          </div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close add movie dialog">
            <X size={18} />
          </button>
        </div>
        <form className="library-search-panel tmdb-list-add-search" onSubmit={searchTmdb}>
          <label className="library-search library-main-search">
            <Search size={17} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search TMDB movies..." />
          </label>
          <button type="submit" className="btn btn-primary" disabled={!query.trim() || loading}>
            {loading ? <Loader2 size={15} className="spin" /> : <Search size={15} />} Search
          </button>
        </form>
        {error ? <p className="settings-inline-status settings-inline-error"><AlertTriangle size={15} /><span>{error}</span></p> : null}
        <div className="tmdb-list-add-results">
          {results.length ? results.map((movie) => {
            const key = String(movie.tmdb_id || movieIdentityKey(movie));
            return (
              <article className="tmdb-list-add-row" key={key}>
                <span className="match-result-poster">
                  {movie.poster_url ? <img src={movie.poster_url} alt="" loading="lazy" /> : <Film size={18} />}
                </span>
                <div>
                  <strong>{movie.title || 'Untitled'}</strong>
                  <span>{movie.year || 'Unknown year'}</span>
                  <small>{movie.plot || 'No plot summary available.'}</small>
                </div>
                <button type="button" className="btn btn-secondary" onClick={() => addResult(movie)} disabled={Boolean(addingKey)}>
                  {addingKey === key ? <Loader2 size={15} className="spin" /> : <CirclePlus size={15} />} Add to list
                </button>
              </article>
            );
          }) : (
            <div className="empty-state">
              <strong>Search TMDB to add a movie.</strong>
              <span>Owned movies will render as Library cards after they match your archive; missing movies stay Discover-style.</span>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function LibraryWorkspace({ onPlay, onFindTorrent, onOpenTrailer, notify, query, setQuery, onReviewUnmatched, isActive }) {
  const pageSize = 40;
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [mode, setMode] = useState(() => (
    typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('view') === 'file' ? 'file' : 'movie'
  ));
  const [qualityFilter, setQualityFilter] = useState('all');
  const [plexFilter, setPlexFilter] = useState('all');
  const [sortMode, setSortMode] = useState('added');
  const [genreFilter, setGenreFilter] = useState('all');
  const [resolutionFilter, setResolutionFilter] = useState('all');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [languageFilter, setLanguageFilter] = useState('all');
  const [countryFilter, setCountryFilter] = useState('all');
  const [yearFrom, setYearFrom] = useState('');
  const [yearTo, setYearTo] = useState('');
  const [minRating, setMinRating] = useState('all');
  const [sizeFilter, setSizeFilter] = useState('all');
  const [viewingStateFilter, setViewingStateFilter] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [expandedPath, setExpandedPath] = useState('');
  const [tmdbCache, setTmdbCache] = useState({});
  const [collectionCache, setCollectionCache] = useState({});
  const [userLists, setUserLists] = useState([]);
  const [roleFilter, setRoleFilter] = useState(null);
  const [collectionFilter, setCollectionFilter] = useState(null);
  const [listFilter, setListFilter] = useState(null);
  const [metadataStatus, setMetadataStatus] = useState('');
  const [collectionEditor, setCollectionEditor] = useState(null);
  const [listEditor, setListEditor] = useState(null);
  const [listsManagerOpen, setListsManagerOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [posterEditor, setPosterEditor] = useState(null);
  const [metadataCorrection, setMetadataCorrection] = useState(null);
  const [showAdultMovies, setShowAdultMovies] = useState(true);
  const [selectedLibraryKeys, setSelectedLibraryKeys] = useState(() => new Set());
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [libraryStale, setLibraryStale] = useState(false);

  const loadLibrary = useCallback(async (forceScan = false, options = {}) => {
    const quiet = Boolean(options.quiet);
    setLoading(true);
    setError('');
    setStatus(forceScan ? 'Rescanning library folders...' : 'Loading library...');
    try {
      const data = await fetchJson(forceScan ? '/api/library?force_scan=1' : '/api/library');
      setItems(data.items || []);
      setCurrentPage(1);
      setLibraryStale(false);
      if (forceScan) {
        const discovered = Number(data.new_files || 0);
        const identified = Number(data.metadata_matched || 0);
        const pending = Number(data.metadata_pending || 0);
        const summary = [
          discovered ? `${formatCount(discovered)} new file${discovered === 1 ? '' : 's'}` : '',
          identified ? `${formatCount(identified)} identified` : '',
          pending ? `${formatCount(pending)} still copying` : ''
        ].filter(Boolean).join(' · ');
        setStatus(summary || 'Rescan complete — no changes found');
        notify(summary || 'Library rescan complete — no changes found', discovered || identified ? 'success' : 'neutral');
        announceLibraryChanged({ source: 'manual-rescan', library: data });
      } else {
        setStatus('');
        if (!quiet) notify(`${formatCount(data.count)} library files loaded`, 'success');
      }
    } catch (loadError) {
      setError(loadError.message);
      notify(`Library unavailable: ${loadError.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    loadLibrary(false);
  }, [loadLibrary]);

  useEffect(() => {
    function handleLibraryChanged(event) {
      if (event.detail?.source === 'manual-rescan') {
        setLibraryStale(false);
        return;
      }
      if (isActive) {
        setLibraryStale(true);
        return;
      }
      loadLibrary(false, { quiet: true });
    }
    window.addEventListener('cp-library-changed', handleLibraryChanged);
    return () => window.removeEventListener('cp-library-changed', handleLibraryChanged);
  }, [isActive, loadLibrary]);

  useEffect(() => {
    if (!isActive && libraryStale) {
      loadLibrary(false, { quiet: true });
    }
  }, [isActive, libraryStale, loadLibrary]);

  async function refreshStaleLibrary() {
    setLibraryStale(false);
    await loadLibrary(false);
  }

  useEffect(() => {
    let cancelled = false;
    async function loadLibraryPreferences() {
      try {
        const data = await fetchJson('/api/config');
        if (!cancelled) setShowAdultMovies(data.show_adult_movies !== false);
      } catch {
        if (!cancelled) setShowAdultMovies(true);
      }
    }
    loadLibraryPreferences();
    return () => { cancelled = true; };
  }, []);

  const loadUserLists = useCallback(async () => {
    try {
      const data = await fetchJson('/api/user/lists');
      setUserLists(data.lists || []);
    } catch (listsError) {
      notify(`Lists unavailable: ${listsError.message}`, 'error');
    }
  }, [notify]);

  useEffect(() => {
    loadUserLists();
    window.addEventListener('cp-curation-changed', loadUserLists);
    return () => window.removeEventListener('cp-curation-changed', loadUserLists);
  }, [loadUserLists]);

  useEffect(() => {
    setCurrentPage(1);
    setExpandedPath('');
  }, [query]);

  useEffect(() => {
    if (!loading) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const data = await fetchJson('/api/library/status');
        if (data.status) setStatus(data.status);
      } catch {
        // Status is non-critical; the main library request carries the error.
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [loading]);

  const optionSets = useMemo(() => ({
    genres: getUniqueOptions(items, (item) => item.canonical_metadata?.genres?.length ? item.canonical_metadata.genres : item.plex_genres || []),
    sources: getUniqueOptions(items, (item) => item.rip_source),
    languages: getUniqueOptions(items, (item) => item.canonical_metadata?.language || item.plex_language),
    countries: getUniqueOptions(items, (item) => item.canonical_metadata?.country_flag || item.canonical_metadata?.country || item.plex_country_flag || item.plex_country)
  }), [items]);

  const {
    filteredItems,
    totalPages,
    safePage,
    pageStart,
    pageEnd,
    visibleItems,
    stats
  } = useMemo(() => buildLibraryViewModel({
    items,
    pageSize,
    currentPage,
    query,
    qualityFilter,
    plexFilter,
    sortMode,
    genreFilter,
    resolutionFilter,
    sourceFilter,
    languageFilter,
    countryFilter,
    yearFrom,
    yearTo,
    minRating,
    sizeFilter,
    mode,
    roleFilter,
    collectionFilter,
    listFilter,
    lists: userLists,
    viewingStateFilter,
    tmdbCache,
    showAdultMovies
  }), [items, query, qualityFilter, plexFilter, sortMode, genreFilter, resolutionFilter, sourceFilter, languageFilter, countryFilter, yearFrom, yearTo, minRating, sizeFilter, mode, roleFilter, collectionFilter, listFilter, userLists, viewingStateFilter, tmdbCache, showAdultMovies, currentPage]);

  const selectedLibraryItems = useMemo(() => (
    items.filter((item) => selectedLibraryKeys.has(movieIdentityKey(moviePayload(item))))
  ), [items, selectedLibraryKeys]);
  const listMissingCoverage = useMemo(() => (
    listFilter ? listLibraryCoverage(items, listFilter) : null
  ), [items, listFilter]);
  const allFilteredLibrarySelected = filteredItems.length > 0 && filteredItems.every((item) => selectedLibraryKeys.has(movieIdentityKey(moviePayload(item))));

  function toggleLibrarySelection(item, checked) {
    const key = movieIdentityKey(moviePayload(item));
    setSelectedLibraryKeys((current) => {
      const next = new Set(current);
      if (checked) next.add(key);
      else next.delete(key);
      return next;
    });
  }

  function selectAllFilteredLibrary() {
    setSelectedLibraryKeys(new Set(filteredItems.map((item) => movieIdentityKey(moviePayload(item)))));
  }

  function clearLibrarySelection() {
    setSelectedLibraryKeys(new Set());
  }

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
      setExpandedPath('');
    }
  }, [currentPage, totalPages]);

  useEffect(() => {
    if (mode !== 'movie' && selectedLibraryKeys.size) {
      setSelectedLibraryKeys(new Set());
    }
  }, [mode, selectedLibraryKeys.size]);

  function resetLibraryPage() {
    setCurrentPage(1);
    setExpandedPath('');
  }

  function resetAllLibraryFilters() {
    setQuery('');
    setQualityFilter('all');
    setPlexFilter('all');
    setSortMode('added');
    setGenreFilter('all');
    setResolutionFilter('all');
    setSourceFilter('all');
    setLanguageFilter('all');
    setCountryFilter('all');
    setYearFrom('');
    setYearTo('');
    setMinRating('all');
    setSizeFilter('all');
    setViewingStateFilter('all');
    setRoleFilter(null);
    setCollectionFilter(null);
    setListFilter(null);
    setMetadataStatus('');
    setSelectedLibraryKeys(new Set());
    resetLibraryPage();
  }

  function goToLibraryPage(page) {
    const nextPage = Math.min(Math.max(1, page), totalPages);
    setCurrentPage(nextPage);
    setExpandedPath('');
  }

  async function loadTmdbDetails(item, openTrailer = false) {
    const identity = getMovieIdentity(item);
    const cacheKey = getTmdbCacheKey(item);
    let details = tmdbCache[cacheKey];
    if (!details) {
      setTmdbCache((cache) => ({ ...cache, [cacheKey]: { loading: true, cast: [], trailer_url: '' } }));
      try {
        let tmdbId = item.tmdb_id;
        if (!tmdbId) {
          const search = await fetchJson(`/api/tmdb/search?q=${encodeURIComponent(identity.title)}&page=1`);
          const result = (search.results || []).find((movie) => String(movie.year || '') === String(identity.year || '')) || (search.results || [])[0];
          if (!result?.tmdb_id) throw new Error('No TMDB match found');
          tmdbId = result.tmdb_id;
        }
        details = await fetchJson(`/api/tmdb/details?tmdb_id=${encodeURIComponent(tmdbId)}`);
        setTmdbCache((cache) => ({ ...cache, [cacheKey]: details }));
        if (details.collection?.id && !collectionCache[details.collection.id]) {
          fetchJson(`/api/library/collection/${encodeURIComponent(details.collection.id)}`)
            .then((collectionData) => setCollectionCache((cache) => ({ ...cache, [details.collection.id]: collectionData })))
            .catch(() => {});
        }
      } catch (detailsError) {
        details = { cast: [], trailer_url: '', error: detailsError.message };
        setTmdbCache((cache) => ({ ...cache, [cacheKey]: details }));
      }
    }
    if (openTrailer) {
      onOpenTrailer({ title: identity.title, year: identity.year }, details.trailer_url || '');
    }
    return details;
  }

  function applyRoleFilter(role, person) {
    setRoleFilter({
      role,
      id: person.id || '',
      name: person.name || ''
    });
    setQuery('');
    setCollectionFilter(null);
    resetLibraryPage();
    setMetadataStatus('');
  }

  async function applyCollectionFilter(collection) {
    if (!collection?.id) return;
    setRoleFilter(null);
    setListFilter(null);
    setQuery('');
    resetLibraryPage();
    setMetadataStatus(`Loading ${collection.name} collection...`);
    setCollectionFilter({ ...collection, parts: [] });
    try {
      const data = await fetchJson(`/api/library/collection/${encodeURIComponent(collection.id)}`);
      setCollectionCache((cache) => ({ ...cache, [data.id || collection.id]: data }));
      setCollectionFilter({
        id: data.id || collection.id,
        name: data.name || collection.name,
        parts: data.parts || [],
        owned_paths: data.owned_paths || [],
        owned_count: Number(data.owned_count || 0),
        unresolved_count: Number(data.unresolved_count || 0),
        unresolved_parts: data.unresolved_parts || [],
        conflicts: data.conflicts || [],
        source: data.source,
        is_edited: data.is_edited
      });
      setMetadataStatus('');
    } catch (collectionError) {
      setMetadataStatus(`Collection unavailable: ${collectionError.message}`);
    }
  }

  function clearMetadataFilters() {
    setRoleFilter(null);
    setCollectionFilter(null);
    setListFilter(null);
    setMetadataStatus('');
    resetLibraryPage();
  }

  function applyListFilter(list) {
    setRoleFilter(null);
    setCollectionFilter(null);
    setListFilter(list);
    setQuery('');
    resetLibraryPage();
  }

  async function saveCollectionOverride(collection, parts) {
    await fetchJson('/api/user/collection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        collection_id: collection.id,
        original: collection,
        parts
      })
    });
    const data = await fetchJson(`/api/library/collection/${encodeURIComponent(collection.id)}`);
    setCollectionCache((cache) => ({ ...cache, [collection.id]: data }));
    setCollectionFilter((filter) => (filter?.id === collection.id ? { ...data } : filter));
    setCollectionEditor(null);
    notify(`Collection saved as user edited`);
  }

  async function resetCollection(collection) {
    await fetchJson(`/api/user/collection/${encodeURIComponent(collection.id)}/reset`, { method: 'POST' });
    const data = await fetchJson(`/api/library/collection/${encodeURIComponent(collection.id)}?refresh=1`);
    setCollectionCache((cache) => ({ ...cache, [collection.id]: data }));
    setCollectionFilter((filter) => (filter?.id === collection.id ? { ...data } : filter));
    notify('Collection reset to TMDB');
  }

  async function createList(name) {
    const created = await fetchJson('/api/user/lists', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    await loadUserLists();
    announceCurationChanged();
    notify(`List created: ${created.name}`);
    return created;
  }

  async function addMovieToList(listId, item) {
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie: moviePayload(item) })
    });
    await loadUserLists();
    announceCurationChanged();
    notify('Movie added to list');
  }

  async function addDiscoverMoviesToList(listId, movies) {
    await addMoviePayloadsToList(listId, movies);
    await loadUserLists();
    announceCurationChanged();
    notify(`${formatCount((movies || []).length)} movie${(movies || []).length === 1 ? '' : 's'} added to list`);
    setSelectedDiscoverKeys(new Set());
  }

  async function addMoviesToList(listId, movies) {
    const payloads = (movies || []).map((movie) => moviePayload(movie));
    await addMoviePayloadsToList(listId, payloads);
    await loadUserLists();
    announceCurationChanged();
    notify(`${formatCount((movies || []).length)} movie${(movies || []).length === 1 ? '' : 's'} added to list`);
    setSelectedLibraryKeys(new Set());
  }

  async function renameList(listId, name) {
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    await loadUserLists();
    announceCurationChanged();
    notify('List renamed');
  }

  async function deleteList(listId) {
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}`, { method: 'DELETE' });
    if (listFilter?.id === listId) setListFilter(null);
    await loadUserLists();
    announceCurationChanged();
    notify('List deleted');
  }

  async function removeMovieFromList(listId, item) {
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie: moviePayload(item) })
    });
    await loadUserLists();
    announceCurationChanged();
    notify('Movie removed from list');
  }

  async function toggleSystemList(systemType, item) {
    const active = movieHasSystemState(item, userLists, systemType);
    await fetchJson(`/api/user/system-lists/${encodeURIComponent(systemType)}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie: moviePayload(item), active: !active })
    });
    await loadUserLists();
    announceCurationChanged();
    notify(`${getMovieIdentity(item).title} ${active ? 'removed from' : 'added to'} ${systemType === 'watched' ? 'Watched' : 'Watchlist'}`);
  }

  async function submitRename(event) {
    event.preventDefault();
    if (!renameTarget) return;
    const form = new FormData(event.currentTarget);
    const title = String(form.get('title') || '').trim();
    const year = String(form.get('year') || '').trim();
    if (!title) {
      notify('Title is required', 'error');
      return;
    }
    try {
      const data = await fetchJson('/api/rename-file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: renameTarget.path, title, year })
      });
      setItems((current) => current.map((item) => (
        item.path === renameTarget.path
          ? { ...item, path: data.new_path, filename: data.new_filename, title: `${title}${year ? ` (${year})` : ''}` }
          : item
      )));
      setRenameTarget(null);
      notify(`Renamed to ${data.new_filename}`);
    } catch (renameError) {
      notify(`Rename failed: ${renameError.message}`, 'error');
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    try {
      await fetchJson('/api/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: deleteTarget.path, trash: true })
      });
      setItems((current) => current.filter((item) => item.path !== deleteTarget.path));
      setDeleteTarget(null);
      notify('Moved file to Recycle Bin');
    } catch (deleteError) {
      notify(`Delete failed: ${deleteError.message}`, 'error');
    }
  }

  function applyPosterToSharedMovie(item, posterUrl, override) {
    setItems((current) => applyPosterOverrideToLibraryItems(current, item, posterUrl, override));
  }

  return (
    <section className="library-workspace">
      <div className="library-header">
        <div>
          <p className="screen-kicker">Local archive</p>
          <h2>{mode === 'movie' ? 'Movie View' : 'File View'}</h2>
          <p>{mode === 'movie' ? 'Choose what to watch using movie metadata, quality, rating, genre, country, and language.' : 'Manage local files with filename, path, Plex status, quality, rename, delete, and source search actions.'}</p>
        </div>
        <div className="library-header-actions">
          <div className="library-view-row">
            <div className="segmented-control library-view-switch" aria-label="Library mode">
              <button type="button" className={cx(mode === 'movie' && 'segment-active')} onClick={() => { setMode('movie'); resetLibraryPage(); }}>
                <Clapperboard size={18} /> Movie View
              </button>
              <button type="button" className={cx(mode === 'file' && 'segment-active')} onClick={() => { setMode('file'); resetLibraryPage(); }}>
                <Folder size={18} /> File View
              </button>
            </div>
          </div>
          <div className="library-action-row">
            <button type="button" className="btn btn-secondary" onClick={() => loadLibrary(true)} disabled={loading}>
              {loading ? <Loader2 size={15} className="spin" /> : <Database size={15} />} Rescan Files
            </button>
            {stats.unmatched > 0 && (
              <button type="button" className="btn btn-primary btn-violet" onClick={onReviewUnmatched}>
                <LinkIcon size={15} /> Review Unmatched
              </button>
            )}
            <button type="button" className="btn btn-secondary" onClick={() => setListEditor({ item: null })}>
              <CirclePlus size={15} /> New list
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setListsManagerOpen(true)}>
              <Library size={15} /> My Lists
            </button>
          </div>
          {libraryStale && (
            <div className="library-stale-notice" role="status">
              <span>Library changed. Refresh view</span>
              <button type="button" className="btn btn-secondary" onClick={refreshStaleLibrary} disabled={loading}>
                {loading ? <Loader2 size={15} className="spin" /> : <RefreshCcw size={15} />} Refresh view
              </button>
            </div>
          )}
        </div>
      </div>

      <form className="library-search-panel" onSubmit={(event) => { event.preventDefault(); resetLibraryPage(); }}>
        <label className="library-search library-main-search">
          <Search size={17} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search your offline library..." />
        </label>
        <button type="submit" className="btn btn-primary library-search-submit">
          <Search size={15} /> Search
        </button>
      </form>

      <div className={cx('library-toolbar library-filter-toolbar', !filtersOpen && 'library-filter-toolbar-collapsed')}>
        {!filtersOpen ? (
          <>
            <span>Filters collapsed: quality, resolution, source, genre, viewing state, language, country, year, rating, sort</span>
            <button type="button" className="btn btn-secondary" onClick={() => setFiltersOpen(true)}>
              Open Filters
            </button>
          </>
        ) : (
          <>
            <select value={qualityFilter} onChange={(event) => { setQualityFilter(event.target.value); resetLibraryPage(); }}>
              <option value="all">All qualities</option>
              <option value="upgrade">Upgrade candidates</option>
              <option value="good">1080p and above</option>
              <option value="4k">4K only</option>
            </select>
            <select value={resolutionFilter} onChange={(event) => { setResolutionFilter(event.target.value); resetLibraryPage(); }}>
              <option value="all">All resolutions</option>
              <option value="4k">4K</option>
              <option value="1080p">1080p</option>
              <option value="720p">720p</option>
              <option value="below-720p">Below 720p</option>
            </select>
            <select value={sourceFilter} onChange={(event) => { setSourceFilter(event.target.value); resetLibraryPage(); }}>
              <option value="all">All sources</option>
              {optionSets.sources.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
            {mode === 'movie' ? (
              <>
            <select value={genreFilter} onChange={(event) => { setGenreFilter(event.target.value); resetLibraryPage(); }}>
              <option value="all">All genres</option>
              {optionSets.genres.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
            <select value={viewingStateFilter} onChange={(event) => { setViewingStateFilter(event.target.value); resetLibraryPage(); }}>
              <option value="all">All viewing states</option>
              <option value="watched">Watched</option>
              <option value="unwatched">Unwatched</option>
              <option value="watchlist">Watchlist</option>
            </select>
            <select value={languageFilter} onChange={(event) => { setLanguageFilter(event.target.value); resetLibraryPage(); }}>
              <option value="all">All languages</option>
              {optionSets.languages.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
            <select value={countryFilter} onChange={(event) => { setCountryFilter(event.target.value); resetLibraryPage(); }}>
              <option value="all">All countries</option>
              {optionSets.countries.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
            <input className="library-mini-input" value={yearFrom} onChange={(event) => { setYearFrom(event.target.value); resetLibraryPage(); }} placeholder="Year from" inputMode="numeric" />
            <input className="library-mini-input" value={yearTo} onChange={(event) => { setYearTo(event.target.value); resetLibraryPage(); }} placeholder="Year to" inputMode="numeric" />
            <select value={minRating} onChange={(event) => { setMinRating(event.target.value); resetLibraryPage(); }}>
              <option value="all">Any rating</option>
              <option value="6">6+</option>
              <option value="7">7+</option>
              <option value="8">8+</option>
            </select>
            <select value={sortMode} onChange={(event) => { setSortMode(event.target.value); resetLibraryPage(); }}>
              <option value="added">Sort by newly added</option>
              <option value="title">Sort by title</option>
              <option value="rating">Sort by rating</option>
              <option value="year-desc">Year newest</option>
              <option value="year-asc">Year oldest</option>
              <option value="quality">Sort by quality</option>
            </select>
              </>
            ) : (
              <>
            <select value={plexFilter} onChange={(event) => { setPlexFilter(event.target.value); resetLibraryPage(); }}>
              <option value="all">All Plex states</option>
              <option value="matched">Plex matched</option>
              <option value="unmatched">Unmatched</option>
            </select>
            <select value={genreFilter} onChange={(event) => { setGenreFilter(event.target.value); resetLibraryPage(); }}>
              <option value="all">All genres</option>
              {optionSets.genres.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
            <select value={sizeFilter} onChange={(event) => { setSizeFilter(event.target.value); resetLibraryPage(); }}>
              <option value="all">All sizes</option>
              <option value="small">Small files</option>
              <option value="large">Large files</option>
            </select>
            <select value={sortMode} onChange={(event) => { setSortMode(event.target.value); resetLibraryPage(); }}>
              <option value="added">Sort by newly added</option>
              <option value="filename">Sort by filename</option>
              <option value="title">Sort by movie title</option>
              <option value="quality">Sort by resolution</option>
              <option value="size">Sort by file size</option>
              <option value="plex">Sort by Plex status</option>
              <option value="source">Sort by source</option>
            </select>
              </>
            )}
            <button type="button" className="btn btn-secondary library-reset-filters" onClick={resetAllLibraryFilters}>
              <RefreshCcw size={15} /> Reset filters
            </button>
            <button type="button" className="btn btn-secondary library-hide-filters" onClick={() => setFiltersOpen(false)}>
              <X size={15} /> Hide Filters
            </button>
          </>
        )}
      </div>

      {(loading || status || error) && (
        <div className={cx('library-status', error && 'library-status-error')}>
          {loading && <Loader2 size={16} className="spin" />}
          <span>{error || status || 'Loading library...'}</span>
        </div>
      )}

      {(roleFilter || collectionFilter || listFilter || metadataStatus) && (
        <div className="metadata-filter-bar">
          {metadataStatus && (
            <span className="metadata-filter-status">
              <Loader2 size={14} className={metadataStatus.startsWith('Loading') ? 'spin' : ''} />
              {metadataStatus}
            </span>
          )}
          {roleFilter && (
            <button type="button" className="metadata-filter-chip" onClick={clearMetadataFilters}>
              {roleFilter.role === 'director' ? 'Director' : 'Actor'}: {roleFilter.name}
              <X size={14} />
            </button>
          )}
          {collectionFilter && (
            <button type="button" className="metadata-filter-chip" onClick={clearMetadataFilters}>
              Collection: {collectionFilter.name}
              {Number.isFinite(collectionFilter.owned_count) && ` · ${formatCount(collectionFilter.owned_count)} owned`}
              {collectionFilter.unresolved_count > 0 && ` · ${formatCount(collectionFilter.unresolved_count)} need identity review`}
              <X size={14} />
            </button>
          )}
          {listFilter && (
            <button type="button" className="metadata-filter-chip" onClick={clearMetadataFilters}>
              List: {listFilter.name}
              <X size={14} />
            </button>
          )}
          {listMissingCoverage?.missingCount > 0 && (
            <span className="list-missing-warning">
              <AlertTriangle size={14} />
              {formatCount(listMissingCoverage.matched)} of {formatCount(listMissingCoverage.total)} list movies found in Library.
              {' '}Missing: {listMissingCoverage.missingMovies.slice(0, 5).map((movie) => movie.title || 'Untitled').join(', ')}
              {listMissingCoverage.missingCount > 5 && `, +${formatCount(listMissingCoverage.missingCount - 5)} more`}
            </span>
          )}
        </div>
      )}

      {!loading && !error && (
        <>
          {mode === 'movie' && filteredItems.length > 0 && (
            <div className="bulk-selection-bar library-bulk-selection">
              <SelectionCheckbox
                className="library-selection-master"
                checked={allFilteredLibrarySelected}
                onChange={(checked) => { if (checked) selectAllFilteredLibrary(); else clearLibrarySelection(); }}
                label="Select all filtered library movies"
              />
              <span>{selectedLibraryItems.length ? `${formatCount(selectedLibraryItems.length)} selected` : 'Select movies'}</span>
              <button type="button" className="mini-action" onClick={selectAllFilteredLibrary}>
                Select all filtered
              </button>
              <button type="button" className="mini-action" onClick={clearLibrarySelection} disabled={!selectedLibraryItems.length}>
                Clear
              </button>
              <button type="button" className="mini-action" onClick={() => setListEditor({ items: selectedLibraryItems })} disabled={!selectedLibraryItems.length}>
                <CirclePlus size={13} /> Add to list
              </button>
            </div>
          )}
          <LibraryPagination
            total={filteredItems.length}
            page={safePage}
            totalPages={totalPages}
            pageStart={pageStart}
            pageEnd={pageEnd}
            onPageChange={goToLibraryPage}
          />
          {visibleItems.length ? (
            <div className={cx('library-results', mode === 'movie' ? 'library-movie-results' : 'library-file-results')}>
              {visibleItems.map((item) => (
                mode === 'movie' ? (
                  <LibraryMovieCard
                    key={item.path}
                    item={item}
                    expanded={expandedPath === item.path}
                    details={tmdbCache[getTmdbCacheKey(item)]}
                    collection={(() => {
                      const details = tmdbCache[getTmdbCacheKey(item)];
                      return details?.collection?.id ? collectionCache[details.collection.id] || details.collection : {};
                    })()}
                    itemLists={listsForItem(item, userLists)}
                    onToggle={() => {
                      const next = expandedPath === item.path ? '' : item.path;
                      setExpandedPath(next);
                      if (next) loadTmdbDetails(item, false);
                    }}
                    onPlay={onPlay}
                    onFindTorrent={onFindTorrent}
                    onTrailer={() => loadTmdbDetails(item, true)}
                    onPersonFilter={applyRoleFilter}
                    onCollectionFilter={applyCollectionFilter}
                    onEditCollection={(collection) => setCollectionEditor({ collection, item })}
                    onResetCollection={resetCollection}
                    onListFilter={applyListFilter}
                    onEditLists={() => setListEditor({ item })}
                    onRemoveFromList={(listId) => removeMovieFromList(listId, item)}
                    onEditPoster={() => setPosterEditor({ item, path: item.path, title: getMovieIdentity(item).title })}
                    onCorrectMetadata={() => setMetadataCorrection(item)}
                    watched={movieHasSystemState(item, userLists, 'watched')}
                    watchlisted={movieHasSystemState(item, userLists, 'watchlist')}
                    onToggleWatched={() => toggleSystemList('watched', item)}
                    onToggleWatchlist={() => toggleSystemList('watchlist', item)}
                    selected={selectedLibraryKeys.has(movieIdentityKey(moviePayload(item)))}
                    onSelect={(checked) => toggleLibrarySelection(item, checked)}
                  />
                ) : (
                  <LibraryFileRow
                    key={item.path}
                    item={item}
                    expanded={expandedPath === item.path}
                    onToggle={() => setExpandedPath((path) => (path === item.path ? '' : item.path))}
                    onPlay={onPlay}
                    onFindTorrent={onFindTorrent}
                    onRename={() => setRenameTarget(item)}
                    onDelete={() => setDeleteTarget(item)}
                  />
                )
              ))}
            </div>
          ) : (
            <div className="empty-state library-empty">
              <strong>No {mode === 'movie' ? 'movies' : 'files'} match these filters.</strong>
              <span>Clear search or change the active filters.</span>
            </div>
          )}
          <LibraryPagination
            total={filteredItems.length}
            page={safePage}
            totalPages={totalPages}
            pageStart={pageStart}
            pageEnd={pageEnd}
            onPageChange={goToLibraryPage}
          />
        </>
      )}

      {renameTarget && (
        <LibraryRenameModal
          item={renameTarget}
          onClose={() => setRenameTarget(null)}
          onSubmit={submitRename}
        />
      )}
      {deleteTarget && (
        <ConfirmDialog
          title="Move file to Recycle Bin?"
          body={deleteTarget.path}
          confirmLabel="Move to Recycle Bin"
          danger
          onCancel={() => setDeleteTarget(null)}
          onConfirm={confirmDelete}
        />
      )}
      {collectionEditor && (
        <CollectionEditorModal
          collection={collectionEditor.collection}
          items={items}
          onClose={() => setCollectionEditor(null)}
          onSave={saveCollectionOverride}
        />
      )}
      {listEditor && (
        <ListEditorModal
          item={listEditor.item}
          bulkItems={listEditor.items || []}
          items={items}
          lists={userLists}
          onClose={() => setListEditor(null)}
          onCreate={createList}
          onAdd={addMovieToList}
          onAddBulk={addMoviesToList}
        />
      )}
      {listsManagerOpen && (
        <MyListsManagerModal
          lists={userLists}
          items={items}
          onClose={() => setListsManagerOpen(false)}
          onCreate={createList}
          onRename={renameList}
          onDelete={deleteList}
          onAdd={addMovieToList}
          onRemove={removeMovieFromList}
          onFilter={applyListFilter}
          notify={notify}
        />
      )}
      {posterEditor && (
        <PosterEditorModal
          item={posterEditor}
          notify={notify}
          onClose={() => setPosterEditor(null)}
          onSaved={(posterUrl, override) => applyPosterToSharedMovie(posterEditor.item, posterUrl, override)}
        />
      )}
      {metadataCorrection && (
        <MetadataCorrectionModal
          item={metadataCorrection}
          notify={notify}
          resetLabel="Reset to provider metadata"
          onClose={() => setMetadataCorrection(null)}
          onSaved={() => loadLibrary(false)}
        />
      )}
    </section>
  );
}

function LibraryPagination({ total, page, totalPages, pageStart, pageEnd, onPageChange }) {
  if (totalPages <= 1 || total <= 0) return null;
  return (
    <nav className="library-pagination" aria-label="Library pagination">
      <button type="button" className="btn btn-secondary" onClick={() => onPageChange(page - 1)} disabled={page <= 1}>
        Previous
      </button>
      <div className="library-page-status">
        <strong>Page {formatCount(page)} of {formatCount(totalPages)}</strong>
        <span>Showing {formatCount(pageStart + 1)}-{formatCount(pageEnd)} of {formatCount(total)}</span>
      </div>
      <button type="button" className="btn btn-secondary" onClick={() => onPageChange(page + 1)} disabled={page >= totalPages}>
        Next
      </button>
    </nav>
  );
}

function LibraryStat({ icon: Icon, label, value, tone, onClick }) {
  const content = (
    <>
      <Icon size={18} />
      <strong>{value}</strong>
      <span>{label}</span>
    </>
  );
  if (onClick) {
    return (
      <button type="button" className={cx('library-stat', 'library-stat-action', `tone-${tone}`)} onClick={onClick}>
        {content}
      </button>
    );
  }
  return (
    <article className={cx('library-stat', `tone-${tone}`)}>
      {content}
    </article>
  );
}

function PersonAvatar({ person }) {
  const initial = String(person?.name || '?').trim().slice(0, 1).toUpperCase() || '?';
  return (
    <span className="person-avatar" aria-hidden="true">
      {person?.profile_url ? <img src={person.profile_url} alt="" loading="lazy" /> : initial}
    </span>
  );
}

function LibraryMovieCard({
  item,
  expanded,
  details,
  collection,
  itemLists,
  onToggle,
  onPlay,
  onFindTorrent,
  onTrailer,
  onPersonFilter,
  onCollectionFilter,
  onEditCollection,
  onResetCollection,
  onListFilter,
  onEditLists,
  onRemoveFromList,
  onEditPoster,
  onCorrectMetadata,
  watched,
  watchlisted,
  onToggleWatched,
  onToggleWatchlist,
  selected,
  onSelect
}) {
  const identity = getMovieIdentity(item);
  const canonical = item.canonical_metadata || {};
  const lowQuality = isLowQuality(item.resolution);
  const genres = (canonical.genres?.length ? canonical.genres : item.plex_genres || []).slice(0, expanded ? 10 : 3);
  const directors = getRolePeople(item, details, 'director');
  const cast = getRolePeople(item, details, 'actor').slice(0, 6);
  const locale = getLocaleTag(item);
  const movieForSearch = {
    title: identity.title,
    year: identity.year,
    imdb_id: canonical.imdb_id || item.imdb_id || '',
    tmdb_id: canonical.tmdb_id || item.tmdb_id || ''
  };
  const posterUrl = canonical.poster_url || item.plex_poster || '';

  return (
    <UnifiedMovieCard
      className={cx('library-movie-card', expanded && 'library-movie-card-expanded')}
      title={identity.title}
      year={identity.year}
      posterUrl={posterUrl}
      rating={canonical.rating || item.plex_rating}
      voteCount={formatVoteCount(canonical.tmdb_vote_count)}
      chips={genres.slice(0, 2)}
      mutedChips={[locale, getQualityLabel(item), item.size_human]}
      statusLabel={lowQuality ? 'Upgrade candidate' : ''}
      statusTone={lowQuality ? 'warning' : 'neutral'}
      ownedBadge
      expanded={expanded}
      selected={selected}
      onToggle={onToggle}
      showPlayOverlay={Boolean(item.path)}
      onPlay={() => onPlay(item.path)}
      cornerControls={(
        <>
          <PosterStateControls
            title={identity.title}
            watched={watched}
            watchlisted={watchlisted}
            onToggleWatched={onToggleWatched}
            onToggleWatchlist={onToggleWatchlist}
          />
          <PosterEditButton title={identity.title} onEdit={onEditPoster} />
          <SelectionCheckbox
            className="library-selection-checkbox"
            checked={Boolean(selected)}
            onChange={onSelect}
            label={`Select ${identity.title}`}
          />
        </>
      )}
    >
      {expanded && (
        <>
          <p className="library-summary movie-summary-expanded">
            {canonical.summary || canonical.plot || item.plex_summary || 'No plot summary is available yet.'}
          </p>
          <div className="library-card-actions">
            <button type="button" className="btn btn-primary btn-green" onClick={() => onPlay(item.path)}>
              <Play size={15} /> Play
            </button>
            <button type="button" className="btn btn-secondary" onClick={onTrailer}>
              <Film size={15} /> Trailer
            </button>
            <button type="button" className="btn btn-secondary" onClick={onCorrectMetadata}>
              <Pencil size={15} /> Correct metadata
            </button>
            {lowQuality && (
              <button type="button" className="btn btn-upgrade" onClick={() => onFindTorrent(movieForSearch, true)}>
                <Wand2 size={15} /> Find upgrade
              </button>
            )}
          </div>
          <MovieExpandedDetails
            movie={{ title: identity.title, year: identity.year }}
            details={details}
            collection={collection}
            itemLists={itemLists}
            directors={directors}
            cast={cast}
            onPersonBrowse={onPersonFilter}
            onCollectionBrowse={onCollectionFilter}
            onListBrowse={onListFilter}
            onEditLists={onEditLists}
            onRemoveFromList={onRemoveFromList}
            onEditCollection={onEditCollection}
            onResetCollection={onResetCollection}
            emptyListText="No user lists yet."
          />
        </>
      )}
    </UnifiedMovieCard>
  );
}

function CollectionEditorModal({ collection, items, onClose, onSave }) {
  const [parts, setParts] = useState(collection.parts || []);
  const [search, setSearch] = useState('');
  const partKeys = useMemo(() => new Set(parts.map((movie) => movieIdentityKey(movie))), [parts]);
  const candidates = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items
      .filter((item) => {
        const payload = moviePayload(item);
        if (partKeys.has(movieIdentityKey(payload))) return false;
        if (!q) return false;
        return `${payload.title} ${payload.year}`.toLowerCase().includes(q);
      })
      .slice(0, 12);
  }, [items, partKeys, search]);

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="torrent-dialog curation-dialog" role="dialog" aria-modal="true" aria-label="Edit collection" onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <p className="screen-kicker">Edit collection</p>
            <h2>{collection.name}</h2>
          </div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close collection editor">
            <X size={18} />
          </button>
        </div>
        <p className="dialog-body-path">Saving changes marks this collection as made by User. Reset restores the TMDB version.</p>
        <label className="library-search curation-search">
          <Search size={17} />
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search local movies to add..." />
        </label>
        {candidates.length > 0 && (
          <div className="curation-candidates">
            {candidates.map((item) => {
              const payload = moviePayload(item);
              return (
                <button type="button" key={item.path} onClick={() => { setParts((current) => [...current, payload]); setSearch(''); }}>
                  <CirclePlus size={15} />
                  {payload.title}{payload.year ? ` (${payload.year})` : ''}
                </button>
              );
            })}
          </div>
        )}
        <div className="curation-list">
          {parts.map((movie) => (
            <div className="curation-row" key={movieIdentityKey(movie)}>
              <span>{movie.title}{movie.year ? ` (${movie.year})` : ''}</span>
              <button type="button" className="mini-action mini-action-danger" onClick={() => setParts((current) => current.filter((item) => movieIdentityKey(item) !== movieIdentityKey(movie)))}>
                <Trash2 size={13} /> Remove
              </button>
            </div>
          ))}
        </div>
        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-primary" onClick={() => onSave(collection, parts)}>Save collection</button>
        </div>
      </section>
    </div>
  );
}

function ListEditorModal({ item, bulkItems = [], items, lists, onClose, onCreate, onAdd, onAddBulk }) {
  const [name, setName] = useState('');
  const [selected, setSelected] = useState(() => (bulkItems.length ? bulkItems : item ? [item] : []));
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const selectedKeys = useMemo(() => new Set(selected.map((movie) => movieIdentityKey(moviePayload(movie)))), [selected]);
  const selectedPayloads = useMemo(() => selected.map((movie) => moviePayload(movie)), [selected]);
  const canAddWatched = selectedPayloads.length > 0 && selectedPayloads.every((movie) => movie.path);
  const candidates = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return [];
    return items
      .filter((movie) => {
        if (selectedKeys.has(movieIdentityKey(moviePayload(movie)))) return false;
        const payload = moviePayload(movie);
        return `${payload.title} ${payload.year} ${movie.filename || ''}`.toLowerCase().includes(q);
      })
      .slice(0, 12);
  }, [items, search, selectedKeys]);

  async function submitCreate(event) {
    event.preventDefault();
    const cleanName = name.trim();
    if (!cleanName) return;
    setBusy(true);
    setError('');
    try {
      const created = await onCreate(cleanName);
      if (onAddBulk && selected.length > 1) {
        await onAddBulk(created.id, selected);
      } else {
        for (const movie of selected) {
          await onAdd(created.id, movie);
        }
      }
      setName('');
      onClose();
    } catch (submitError) {
      setError(submitError.message || 'Could not add movies to list');
    } finally {
      setBusy(false);
    }
  }

  async function addExisting(listId) {
    if (!selected.length) return;
    setBusy(true);
    setError('');
    try {
      if (onAddBulk && selected.length > 1) {
        await onAddBulk(listId, selected);
      } else {
        await onAdd(listId, selected[0]);
      }
      onClose();
    } catch (addError) {
      setError(addError.message || 'Could not add movies to list');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="small-dialog" role="dialog" aria-modal="true" aria-label="List editor" onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <p className="screen-kicker">User lists</p>
            <h2>{selected.length > 1 ? 'Add selected movies to list' : item ? 'Add movie to list' : 'Create list'}</h2>
          </div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close list editor">
            <X size={18} />
          </button>
        </div>
        <form onSubmit={submitCreate}>
          <label className="dialog-field">
            <span>New list name</span>
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="My Best, Marvel Universe..." />
          </label>
          {selected.length > 0 && (
            <p className="dialog-body-path list-editor-selection-summary">
              {formatCount(selectedPayloads.length)} selected movie{selectedPayloads.length === 1 ? '' : 's'} will be added.
            </p>
          )}
          {!item && !bulkItems.length && (
            <>
              <label className="library-search curation-search">
                <Search size={17} />
                <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search local movies to add..." />
              </label>
              {candidates.length > 0 && (
                <div className="curation-candidates">
                  {candidates.map((movie) => {
                    const payload = moviePayload(movie);
                    return (
                      <button type="button" key={movie.path} onClick={() => { setSelected((current) => [...current, movie]); setSearch(''); }}>
                        <CirclePlus size={15} />
                        {payload.title}{payload.year ? ` (${payload.year})` : ''}
                      </button>
                    );
                  })}
                </div>
              )}
              <div className="curation-list">
                {selected.map((movie) => {
                  const payload = moviePayload(movie);
                  return (
                    <div className="curation-row" key={movie.path}>
                      <span>{payload.title}{payload.year ? ` (${payload.year})` : ''}</span>
                      <button type="button" className="mini-action mini-action-danger" onClick={() => setSelected((current) => current.filter((entry) => entry.path !== movie.path))}>
                        <Trash2 size={13} /> Remove
                      </button>
                    </div>
                  );
                })}
              </div>
            </>
          )}
          {error && <p className="dialog-error list-editor-error"><AlertTriangle size={14} /> {error}</p>}
          <div className="dialog-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={busy || !name.trim() || (!item && selected.length === 0)}>
              {busy ? <Loader2 size={15} className="spin" /> : <CirclePlus size={15} />} Create
            </button>
          </div>
        </form>
        {selected.length > 0 && lists.length > 0 && (
          <div className="existing-list-picker">
            <span className="mini-label">Existing lists</span>
            {lists.filter((list) => canAddWatched || list.system_type !== 'watched').map((list) => (
              <button type="button" key={list.id} onClick={() => addExisting(list.id)} disabled={busy}>
                {list.name}
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function MyListsManagerModal({ lists, items, onClose, onCreate, onRename, onDelete, onAdd, onRemove, onFilter, notify }) {
  const [selectedId, setSelectedId] = useState(lists[0]?.id || '');
  const [newName, setNewName] = useState('');
  const [renameValue, setRenameValue] = useState('');
  const [search, setSearch] = useState('');
  const [tmdbCandidates, setTmdbCandidates] = useState([]);
  const [tmdbLoading, setTmdbLoading] = useState(false);
  const [selectedMovieKeys, setSelectedMovieKeys] = useState(() => new Set());
  const [copyMovies, setCopyMovies] = useState(null);
  const selectedList = lists.find((list) => list.id === selectedId) || lists[0] || null;
  const listMovieKeys = useMemo(() => new Set((selectedList?.movies || []).map((movie) => movieIdentityKey(movie))), [selectedList]);
  const selectedMovies = useMemo(() => (
    (selectedList?.movies || []).filter((movie) => selectedMovieKeys.has(movieIdentityKey(movie)))
  ), [selectedList, selectedMovieKeys]);
  const allListMoviesSelected = Boolean((selectedList?.movies || []).length) && (selectedList?.movies || []).every((movie) => selectedMovieKeys.has(movieIdentityKey(movie)));
  const candidates = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q || !selectedList) return [];
    return items
      .filter((item) => {
        const payload = moviePayload(item);
        if (listMovieKeys.has(movieIdentityKey(payload))) return false;
        return `${payload.title} ${payload.year} ${item.filename || ''}`.toLowerCase().includes(q);
      })
      .slice(0, 12);
  }, [items, listMovieKeys, search, selectedList]);

  useEffect(() => {
    if (!selectedList && lists[0]) setSelectedId(lists[0].id);
    if (selectedList) setRenameValue(selectedList.name || '');
  }, [lists, selectedList]);

  useEffect(() => {
    setSelectedMovieKeys(new Set());
  }, [selectedId]);

  async function submitCreate(event) {
    event.preventDefault();
    const created = await onCreate(newName);
    setNewName('');
    setSelectedId(created.id);
  }

  async function submitRename(event) {
    event.preventDefault();
    if (!selectedList || !renameValue.trim()) return;
    await onRename(selectedList.id, renameValue.trim());
  }

  async function deleteSelected() {
    if (!selectedList) return;
    await onDelete(selectedList.id);
    const remaining = lists.filter((list) => list.id !== selectedList.id);
    setSelectedId(remaining[0]?.id || '');
  }

  function toggleListMovie(movie, checked) {
    const key = movieIdentityKey(movie);
    setSelectedMovieKeys((current) => {
      const next = new Set(current);
      if (checked) next.add(key);
      else next.delete(key);
      return next;
    });
  }

  function selectAllListMovies() {
    setSelectedMovieKeys(new Set((selectedList?.movies || []).map((movie) => movieIdentityKey(movie))));
  }

  function clearListSelection() {
    setSelectedMovieKeys(new Set());
  }

  async function removeSelectedMovies() {
    if (!selectedList || !selectedMovies.length) return;
    for (const movie of selectedMovies) {
      await onRemove(selectedList.id, movie);
    }
    setSelectedMovieKeys(new Set());
  }

  async function searchTmdbWatchlist() {
    if (selectedList?.system_type !== 'watchlist' || !search.trim()) return;
    setTmdbLoading(true);
    try {
      const data = await fetchJson(`/api/tmdb/search?q=${encodeURIComponent(search.trim())}&page=1&include_adult=false`);
      setTmdbCandidates((data.results || []).slice(0, 12));
    } finally {
      setTmdbLoading(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="torrent-dialog curation-dialog" role="dialog" aria-modal="true" aria-label="My lists" onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <p className="screen-kicker">Library lists</p>
            <h2>My Lists</h2>
          </div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close my lists">
            <X size={18} />
          </button>
        </div>
        <div className="lists-manager-grid">
          <aside className="lists-manager-sidebar">
            <form onSubmit={submitCreate} className="list-create-inline">
              <input value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="New list name..." />
              <button type="submit" className="mini-action" disabled={!newName.trim()}><CirclePlus size={13} /> Create</button>
            </form>
            {lists.length ? lists.map((list) => (
              <button type="button" key={list.id} className={cx('list-manager-item', selectedList?.id === list.id && 'list-manager-item-active')} onClick={() => setSelectedId(list.id)}>
                <span>{list.name}</span>
                <small>{formatCount((list.movies || []).length)} movies</small>
              </button>
            )) : <small>No lists yet.</small>}
          </aside>
          <div className="lists-manager-detail">
            {selectedList ? (
              <>
                <form className="list-rename-row" onSubmit={submitRename}>
                  <input value={renameValue} onChange={(event) => setRenameValue(event.target.value)} disabled={Boolean(selectedList?.system_type)} />
                  {selectedList?.system_type ? <span className="chip chip-muted">System list</span> : <button type="submit" className="mini-action">Rename</button>}
                  <button type="button" className="mini-action" onClick={() => onFilter(selectedList)}>Filter</button>
                  {!selectedList?.system_type && (
                    <button type="button" className="mini-action mini-action-danger" onClick={deleteSelected}>
                      <Trash2 size={13} /> Delete
                    </button>
                  )}
                </form>
                <label className="library-search curation-search">
                  <Search size={17} />
                  <input value={search} onChange={(event) => { setSearch(event.target.value); setTmdbCandidates([]); }} placeholder={selectedList.system_type === 'watchlist' ? 'Search local movies or TMDB...' : 'Search local movies to add...'} />
                </label>
                {selectedList.system_type === 'watchlist' && search.trim() && (
                  <button type="button" className="mini-action" onClick={searchTmdbWatchlist} disabled={tmdbLoading}>
                    {tmdbLoading ? <Loader2 size={13} className="spin" /> : <Search size={13} />} Search TMDB to add to Watchlist
                  </button>
                )}
                {candidates.length > 0 && (
                  <div className="curation-candidates">
                    {candidates.map((item) => {
                      const payload = moviePayload(item);
                      return (
                        <button type="button" key={item.path} onClick={() => { onAdd(selectedList.id, item); setSearch(''); }}>
                          <CirclePlus size={15} />
                          {payload.title}{payload.year ? ` (${payload.year})` : ''}
                        </button>
                      );
                    })}
                  </div>
                )}
                {tmdbCandidates.length > 0 && selectedList.system_type === 'watchlist' && (
                  <div className="curation-candidates">
                    {tmdbCandidates.map((movie) => {
                      const owned = items.some((item) => movieIdentityKey(moviePayload(item)) === movieIdentityKey(movie));
                      return (
                        <button type="button" key={movie.tmdb_id || movieIdentityKey(movie)} onClick={() => { onAdd(selectedList.id, movie); setSearch(''); setTmdbCandidates([]); }}>
                          <CirclePlus size={15} />
                          {movie.title}{movie.year ? ` (${movie.year})` : ''} · {owned ? 'Owned' : 'Not owned'}
                        </button>
                      );
                    })}
                  </div>
                )}
                {(selectedList.movies || []).length > 0 && (
                  <div className="bulk-selection-bar list-bulk-selection">
                    <SelectionCheckbox
                      className="list-select-all"
                      checked={allListMoviesSelected}
                      onChange={(checked) => { if (checked) selectAllListMovies(); else clearListSelection(); }}
                      label={`Select all movies in ${selectedList.name}`}
                    />
                    <span>{selectedMovies.length ? `${formatCount(selectedMovies.length)} selected` : 'Select list movies'}</span>
                    <button type="button" className="mini-action" onClick={selectAllListMovies}>Select all</button>
                    <button type="button" className="mini-action" onClick={clearListSelection} disabled={!selectedMovies.length}>Clear</button>
                    <button type="button" className="mini-action mini-action-danger" onClick={removeSelectedMovies} disabled={!selectedMovies.length}>
                      <Trash2 size={13} /> Remove selected
                    </button>
                    <button type="button" className="mini-action" onClick={() => setCopyMovies(selectedMovies)} disabled={!selectedMovies.length}>
                      <Copy size={13} /> Copy selected to...
                    </button>
                  </div>
                )}
                <div className="curation-list">
                  {(selectedList.movies || []).map((movie) => (
                    <div className="curation-row" key={movieIdentityKey(movie)}>
                      <SelectionCheckbox
                        className="list-row-checkbox"
                        checked={selectedMovieKeys.has(movieIdentityKey(movie))}
                        onChange={(checked) => toggleListMovie(movie, checked)}
                        label={`Select ${movie.title}`}
                      />
                      <span>{movie.title}{movie.year ? ` (${movie.year})` : ''}</span>
                      <button type="button" className="mini-action mini-action-danger" onClick={() => onRemove(selectedList.id, movie)}>
                        <Trash2 size={13} /> Remove
                      </button>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="empty-state">
                <strong>No list selected.</strong>
                <span>Create a list to start curating movies.</span>
              </div>
            )}
          </div>
        </div>
        {copyMovies && (
          <ExportCopyDialog
            movies={copyMovies}
            onClose={() => setCopyMovies(null)}
            notify={notify}
          />
        )}
      </section>
    </div>
  );
}

function ExportCopyDialog({ movies, onClose, notify }) {
  const [destination, setDestination] = useState('');
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [folderBrowserOpen, setFolderBrowserOpen] = useState(false);
  const localCount = movies.filter((movie) => movie.path).length;
  const completed = job && ['completed', 'completed_with_errors', 'failed', 'cancelled'].includes(job.status);
  const percent = job?.bytes_total ? Math.min(100, Math.round((Number(job.bytes_done || 0) / Number(job.bytes_total || 1)) * 100)) : 0;

  useEffect(() => {
    if (!job?.id || completed) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const next = await fetchJson(`/api/library/export-jobs/${encodeURIComponent(job.id)}`);
        setJob(next);
        if (['completed', 'completed_with_errors'].includes(next.status)) {
          notify?.(`Copied ${formatCount(next.copied_count || 0)} movie file${Number(next.copied_count || 0) === 1 ? '' : 's'}`);
        }
      } catch (pollError) {
        setError(pollError.message);
      }
    }, 900);
    return () => window.clearInterval(timer);
  }, [job?.id, completed, notify]);

  async function startCopy(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const created = await fetchJson('/api/library/export-jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ movies, destination })
      });
      setJob(created);
    } catch (copyError) {
      setError(copyError.message);
    } finally {
      setBusy(false);
    }
  }

  async function cancelCopy() {
    if (!job?.id) return;
    try {
      const cancelled = await fetchJson(`/api/library/export-jobs/${encodeURIComponent(job.id)}/cancel`, { method: 'POST' });
      setJob(cancelled);
      notify?.('Copy job cancelled', 'neutral');
    } catch (cancelError) {
      setError(cancelError.message);
    }
  }

  return (
    <>
      <div className="modal-backdrop export-copy-backdrop" role="presentation" onClick={onClose}>
        <form className="small-dialog export-copy-dialog" role="dialog" aria-modal="true" aria-label="Copy selected movies" onClick={(event) => event.stopPropagation()} onSubmit={startCopy}>
          <div className="dialog-header">
            <div>
              <p className="screen-kicker">Export list movies</p>
              <h2>Copy selected to...</h2>
            </div>
            <button type="button" className="inspector-close" onClick={onClose} aria-label="Close copy dialog">
              <X size={18} />
            </button>
          </div>
          <p className="dialog-body-path">
            {formatCount(movies.length)} selected, {formatCount(localCount)} local file{localCount === 1 ? '' : 's'} available to copy. Existing files are skipped.
          </p>
          <label className="dialog-field">
            <span>Destination folder</span>
            <div className="folder-path-row">
              <input value={destination} onChange={(event) => setDestination(event.target.value)} placeholder="E:\\Friend USB\\Movies or \\\\server\\share\\movies" disabled={Boolean(job && !completed)} />
              <button type="button" className="btn btn-secondary" onClick={() => setFolderBrowserOpen(true)} disabled={Boolean(job && !completed)}>
                <Folder size={15} /> Browse...
              </button>
            </div>
          </label>
          {job && (
            <div className="export-progress">
              <div className="export-progress-track"><span style={{ width: `${percent}%` }} /></div>
              <p>
                <strong>{job.status}</strong>
                <span>{formatCount(job.copied_count || 0)} copied, {formatCount(job.skipped_count || 0)} skipped, {formatCount(job.failed_count || 0)} failed</span>
              </p>
              {job.current && <small>Copying {job.current}</small>}
            </div>
          )}
          {error && <p className="dialog-error"><AlertTriangle size={14} /> {error}</p>}
          <div className="dialog-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Close</button>
            {job && !completed ? (
              <button type="button" className="btn btn-secondary" onClick={cancelCopy}>Cancel copy</button>
            ) : (
              <button type="submit" className="btn btn-primary" disabled={busy || !destination.trim() || !movies.length}>
                {busy ? <Loader2 size={15} className="spin" /> : <Copy size={15} />} Start copy
              </button>
            )}
          </div>
        </form>
      </div>
      {folderBrowserOpen && (
        <FolderBrowserDialog
          initialPath={destination}
          onClose={() => setFolderBrowserOpen(false)}
          onSelect={(path) => {
            setDestination(path);
            setFolderBrowserOpen(false);
          }}
        />
      )}
    </>
  );
}

function FolderBrowserDialog({ initialPath, onSelect, onClose }) {
  const [manualPath, setManualPath] = useState(initialPath || '');
  const [data, setData] = useState({ current_path: '', parent: '', roots: [], entries: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadFolder = useCallback(async (path = '') => {
    const clean = String(path || '').trim();
    setLoading(true);
    setError('');
    try {
      const suffix = clean ? `?path=${encodeURIComponent(clean)}` : '';
      const next = await fetchJson(`/api/system/folders${suffix}`);
      setData(next);
      if (next.current_path) setManualPath(next.current_path);
    } catch (browseError) {
      setError(browseError.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFolder(initialPath || '');
  }, [initialPath, loadFolder]);

  const roots = data.roots || [];
  const entries = data.entries || [];

  return (
    <div className="modal-backdrop folder-browser-backdrop" role="presentation" onClick={onClose}>
      <div className="small-dialog folder-browser-dialog" role="dialog" aria-modal="true" aria-label="Browse destination folder" onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <p className="screen-kicker">Copy destination</p>
            <h2>Browse folders</h2>
          </div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close folder browser">
            <X size={18} />
          </button>
        </div>
        <form className="folder-browser-path-form" onSubmit={(event) => { event.preventDefault(); loadFolder(manualPath); }}>
          <input value={manualPath} onChange={(event) => setManualPath(event.target.value)} placeholder="Type a folder path or network share" />
          <button type="submit" className="btn btn-secondary" disabled={loading}>
            {loading ? <Loader2 size={15} className="spin" /> : <Search size={15} />} Open
          </button>
        </form>
        {data.current_path && (
          <div className="folder-current-path">
            <span>{data.current_path}</span>
            <button type="button" className="btn btn-primary" onClick={() => onSelect(data.current_path)}>
              <CheckCircle2 size={15} /> Use this folder
            </button>
          </div>
        )}
        {error && <p className="dialog-error"><AlertTriangle size={14} /> {error}</p>}
        <div className="folder-browser-grid">
          <div>
            <h3>Quick locations</h3>
            <div className="folder-browser-list">
              {roots.map((entry) => (
                <button type="button" key={entry.path} onClick={() => loadFolder(entry.path)}>
                  <HardDrive size={15} /> <span>{entry.name}</span>
                </button>
              ))}
            </div>
          </div>
          <div>
            <h3>Folders</h3>
            <div className="folder-browser-list">
              {data.parent && (
                <button type="button" onClick={() => loadFolder(data.parent)}>
                  <Folder size={15} /> <span>..</span>
                </button>
              )}
              {entries.map((entry) => (
                <button type="button" key={entry.path} onClick={() => loadFolder(entry.path)}>
                  <Folder size={15} /> <span>{entry.name}</span>
                </button>
              ))}
              {!loading && !entries.length && !data.parent && (
                <span className="folder-browser-empty">Choose a quick location or type a path.</span>
              )}
              {!loading && data.current_path && !entries.length && (
                <span className="folder-browser-empty">No child folders.</span>
              )}
            </div>
          </div>
        </div>
        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-primary" onClick={() => onSelect(data.current_path)} disabled={!data.current_path}>
            <CheckCircle2 size={15} /> Select folder
          </button>
        </div>
      </div>
    </div>
  );
}

function LibraryFileRow({ item, expanded, onToggle, onPlay, onFindTorrent, onRename, onDelete }) {
  const identity = getMovieIdentity(item);
  const lowQuality = isLowQuality(item.resolution);
  const movieForSearch = { title: identity.title, year: identity.year, imdb_id: item.imdb_id || '', tmdb_id: item.tmdb_id || '' };
  return (
    <article className={cx('library-file-row', expanded && 'library-file-row-expanded')}>
      <div className="file-row-main">
        <div className="file-row-title">
          <strong>{item.filename}</strong>
          <span>{identity.title}{identity.year ? ` (${identity.year})` : ''}</span>
        </div>
        <div className="file-row-path" title={item.path}>{item.path}</div>
        <div className="file-row-meta">
          <span className={cx('chip', lowQuality && 'chip-warning')}>{item.resolution || 'Unknown'}</span>
          <span className="chip chip-muted">{item.rip_source || 'Unknown source'}</span>
          <span className="chip chip-muted">{item.size_human || '?'}</span>
          {item.library_root && <span className="chip chip-muted">{rootLabel(item.library_root)}</span>}
          <span className={cx('chip', item.plex_matched ? 'status-owned' : 'status-missing')}>{item.plex_matched ? 'Matched' : 'Unmatched'}</span>
          {(item.plex_genres || []).slice(0, 2).map((genre) => <span className="chip chip-muted" key={genre}>{genre}</span>)}
          {getLocaleTag(item) && <span className="chip chip-muted">{getLocaleTag(item)}</span>}
        </div>
      </div>
      <div className="file-row-actions">
        <button type="button" className="btn btn-primary btn-green" onClick={() => onPlay(item.path)}>
          <Play size={15} /> Play
        </button>
        <button type="button" className={cx('btn', lowQuality ? 'btn-upgrade' : 'btn-secondary')} onClick={() => onFindTorrent(movieForSearch, lowQuality)}>
          <Wand2 size={15} /> {lowQuality ? 'Find upgrade' : 'Find sources'}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onRename}>
          <Clapperboard size={15} /> Rename
        </button>
        <button type="button" className="btn btn-danger" onClick={onDelete}>
          <Trash2 size={15} /> Delete
        </button>
        <button type="button" className="btn btn-secondary" onClick={onToggle}>
          <Info size={15} /> {expanded ? 'Less' : 'Details'}
        </button>
      </div>
      {expanded && (
        <div className="file-expanded-panel">
          <div><span>Full path</span><strong>{item.path}</strong></div>
          <div><span>Plex title</span><strong>{item.plex_title || 'Not matched'}</strong></div>
          <div><span>Plex year</span><strong>{item.plex_year || 'Unknown'}</strong></div>
          <div><span>Language</span><strong>{item.plex_language || 'Unknown'}</strong></div>
          <div><span>Country</span><strong>{item.plex_country || item.plex_country_flag || 'Unknown'}</strong></div>
          <div><span>Size</span><strong>{item.size_human || '?'} ({formatCount(item.size)} bytes)</strong></div>
          <div><span>Genres</span><strong>{(item.plex_genres || []).join(', ') || 'None'}</strong></div>
          <div className="file-expanded-summary"><span>Summary</span><strong>{item.plex_summary || 'No summary available'}</strong></div>
        </div>
      )}
    </article>
  );
}

function LibraryRenameModal({ item, onClose, onSubmit }) {
  const identity = getMovieIdentity(item);
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <form className="small-dialog" onSubmit={onSubmit} role="dialog" aria-modal="true" aria-label="Rename file" onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <p className="screen-kicker">Rename file</p>
            <h2>{item.filename}</h2>
          </div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close rename dialog">
            <X size={18} />
          </button>
        </div>
        <label className="dialog-field">
          <span>Movie title</span>
          <input name="title" defaultValue={identity.title} />
        </label>
        <label className="dialog-field">
          <span>Year</span>
          <input name="year" defaultValue={identity.year} inputMode="numeric" />
        </label>
        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary">Rename</button>
        </div>
      </form>
    </div>
  );
}

function ConfirmDialog({ title, body, confirmLabel, danger, onCancel, onConfirm }) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onCancel}>
      <section className="small-dialog" role="dialog" aria-modal="true" aria-label={title} onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <p className="screen-kicker">Confirm action</p>
            <h2>{title}</h2>
          </div>
          <button type="button" className="inspector-close" onClick={onCancel} aria-label="Close dialog">
            <X size={18} />
          </button>
        </div>
        <p className="dialog-body-path">{body}</p>
        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
          <button type="button" className={cx('btn', danger ? 'btn-danger' : 'btn-primary')} onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </section>
    </div>
  );
}

function MigrationWorkspace({ section, notify, onPlay, onFindTorrent, cleanupInitialTab, onReviewUnmatched, onReviewIdentities, onHealthChanged, onStreamingConfigChanged }) {
  if (section === 'cleanup') {
    return (
      <CleanupWorkspace
        notify={notify}
        onPlay={onPlay}
        onFindTorrent={onFindTorrent}
        initialTab={cleanupInitialTab}
        onHealthChanged={onHealthChanged}
      />
    );
  }
  if (section === 'settings') {
    return <SettingsWorkspace notify={notify} onReviewUnmatched={onReviewUnmatched} onReviewIdentities={onReviewIdentities} onStreamingConfigChanged={onStreamingConfigChanged} />;
  }
  const meta = {
    library: {
      icon: Library,
      title: 'Library workspace',
      body: 'Local browsing belongs here: list and grid views, filtering, search, play, rename, upgrade search, and Plex status.',
      actions: ['List and grid', 'Filter by quality', 'Play stays primary']
    },
    cleanup: {
      icon: ShieldCheck,
      title: 'Cleanup workspace',
      body: 'Offline maintenance belongs here: duplicates, Smart Clean, low-quality files, and unmatched metadata fixes.',
      actions: ['Duplicates', 'Low quality', 'Metadata fixes']
    },
    discover: {
      icon: Compass,
      title: 'Discover workspace',
      body: 'Online discovery belongs here: TMDB lists, Browse Torrents, Pick My Movie, and followed release checks.',
      actions: ['TMDB lists', 'Browse torrents', 'Follow releases']
    },
    settings: {
      icon: Settings,
      title: 'Settings workspace',
      body: 'Integrations should become a proper system panel with Plex, Prowlarr, TMDB, and Ollama status instead of a cramped dropdown.',
      actions: ['Plex status', 'Prowlarr status', 'API privacy']
    }
  }[section];
  const Icon = meta.icon;
  return (
    <section className="migration-panel">
      <Icon size={28} />
      <h2>{meta.title}</h2>
      <p>{meta.body}</p>
      <div className="migration-actions">
        {meta.actions.map((action, index) => (
          <span key={action} className={cx('action-pill', index === 0 && 'action-pill-primary')}>
            {action}
          </span>
        ))}
      </div>
      <a href="/legacy" className="legacy-fallback">Open old interface fallback</a>
    </section>
  );
}

const cleanupTabs = [
  { id: 'duplicates', label: 'Duplicates', icon: ShieldCheck },
  { id: 'smart', label: 'Smart Clean', icon: Wand2 },
  { id: 'low', label: 'Low Quality', icon: AlertTriangle },
  { id: 'unmatched', label: 'Unmatched Metadata', icon: LinkIcon },
  { id: 'identity', label: 'Identity Review', icon: ScanSearch }
];

function CleanupWorkspace({ notify, onPlay, onFindTorrent, initialTab = 'duplicates', onHealthChanged }) {
  const [activeTab, setActiveTab] = useState(initialTab);
  const [loading, setLoading] = useState({});
  const [errors, setErrors] = useState({});
  const [data, setData] = useState({ duplicates: [], smart: [], low: [], unmatched: [] });
  const [selected, setSelected] = useState({ duplicates: new Set(), smart: new Set(), low: new Set(), unmatched: new Set() });
  const [filters, setFilters] = useState({ query: '', resolution: 'all', source: 'all', plex: 'all', identity: 'all' });
  const [confirmAction, setConfirmAction] = useState(null);
  const [renameTarget, setRenameTarget] = useState(null);
  const [matchModal, setMatchModal] = useState(null);
  const [rowStatus, setRowStatus] = useState({});
  const [smartMatchJob, setSmartMatchJob] = useState(null);
  const [lastSmartMatchJob, setLastSmartMatchJob] = useState(null);
  const [identityAudit, setIdentityAudit] = useState(null);
  const [identityApprovedProposal, setIdentityApprovedProposal] = useState(null);
  const [identityHealthJob, setIdentityHealthJob] = useState('');
  const [ollamaAvailable, setOllamaAvailable] = useState(false);
  const [smartMatchProviders, setSmartMatchProviders] = useState({ tmdb: true, plex: true });

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  const loadCleanup = useCallback(async (forcePlex = false) => {
    const suffix = forcePlex ? '?force_plex=1' : '';
    setLoading({ duplicates: true, smart: true, low: true, unmatched: true, identity: true });
    setErrors({});
    const requests = await Promise.allSettled([
      fetchJson(`/api/duplicates${suffix}`),
      fetchJson('/api/smart-scan'),
      fetchJson(`/api/low-quality${suffix}`),
      fetchJson(`/api/fix-unmatched${suffix}`),
      fetchJson('/api/metadata/identity-audit')
    ]);
    const [duplicates, smart, low, unmatched, identity] = requests;
    setData({
      duplicates: duplicates.status === 'fulfilled' ? duplicates.value.duplicates || [] : [],
      smart: smart.status === 'fulfilled' ? smart.value.recommendations || [] : [],
      low: low.status === 'fulfilled' ? low.value.items || [] : [],
      unmatched: unmatched.status === 'fulfilled' ? unmatched.value.items || [] : []
    });
    if (identity.status === 'fulfilled') setIdentityAudit(identity.value);
    setSelected({ duplicates: new Set(), smart: new Set(), low: new Set(), unmatched: new Set() });
    setErrors({
      duplicates: duplicates.status === 'rejected' ? duplicates.reason.message : '',
      smart: smart.status === 'rejected' ? smart.reason.message : '',
      low: low.status === 'rejected' ? low.reason.message : '',
      unmatched: unmatched.status === 'rejected' ? unmatched.reason.message : '',
      identity: identity.status === 'rejected' ? identity.reason.message : ''
    });
    setLoading({ duplicates: false, smart: false, low: false, unmatched: false, identity: false });
  }, []);

  useEffect(() => {
    loadCleanup(false);
  }, [loadCleanup]);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([
      fetchJson('/api/ollama/config'),
      fetchJson('/api/metadata/smart-match')
    ]).then(([ollama, smart]) => {
      if (cancelled) return;
      if (ollama.status === 'fulfilled') {
        setOllamaAvailable(Boolean(ollama.value.url && ollama.value.model));
      }
      if (smart.status === 'fulfilled') {
        setSmartMatchProviders(smart.value.providers || { tmdb: true, plex: true });
        if (['running', 'paused'].includes(smart.value.status) && smart.value.id) {
          setSmartMatchJob(smart.value);
        } else if (smart.value.status === 'completed' && smart.value.id) {
          setLastSmartMatchJob(smart.value);
        }
      }
    })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (identityAudit?.status !== 'running' || !identityAudit.id) return undefined;
    const timer = window.setInterval(async () => {
      try {
        setIdentityAudit(await fetchJson(`/api/metadata/identity-audit/${encodeURIComponent(identityAudit.id)}`));
      } catch (pollError) {
        setErrors((state) => ({ ...state, identity: pollError.message }));
      }
    }, 900);
    return () => window.clearInterval(timer);
  }, [identityAudit?.id, identityAudit?.status]);

  useEffect(() => {
    if (identityAudit?.status !== 'completed' || !identityAudit.id || identityHealthJob === identityAudit.id) return;
    setIdentityHealthJob(identityAudit.id);
    onHealthChanged();
  }, [identityAudit?.id, identityAudit?.status, identityHealthJob, onHealthChanged]);

  const duplicateFiles = useMemo(() => data.duplicates.flatMap((group) => group.files || []), [data.duplicates]);
  const selectableDuplicatePaths = useMemo(() => data.duplicates.flatMap((group) => (group.files || []).slice(1).map((file) => file.path)), [data.duplicates]);
  const smartSelectablePaths = useMemo(() => data.smart.filter((item) => item.delete_path && !item.skipped).map((item) => item.delete_path), [data.smart]);

  const optionSets = useMemo(() => ({
    lowResolutions: getUniqueOptions(data.low, (item) => item.resolution),
    lowSources: getUniqueOptions(data.low, (item) => item.rip_source)
  }), [data.low]);

  const filteredLow = useMemo(() => filterCleanupItems(data.low, filters), [data.low, filters]);
  const filteredUnmatched = useMemo(() => filterUnmatchedItems(data.unmatched, filters), [data.unmatched, filters]);
  const filteredIdentity = useMemo(
    () => filterIdentityReviewItems(identityAudit?.proposals || [], filters),
    [identityAudit?.proposals, filters]
  );
  const filteredDuplicates = useMemo(() => {
    const q = filters.query.trim().toLowerCase();
    if (!q) return data.duplicates;
    return data.duplicates.filter((group) => {
      const haystack = [
        group.title,
        ...(group.files || []).flatMap((file) => [file.filename, file.path, file.plex_title, file.plex_year])
      ].filter(Boolean).join(' ').toLowerCase();
      return haystack.includes(q);
    });
  }, [data.duplicates, filters.query]);
  const filteredSmart = useMemo(() => {
    const q = filters.query.trim().toLowerCase();
    if (!q) return data.smart;
    return data.smart.filter((item) => [item.movie, item.delete_filename, item.keep_filename, item.reason].filter(Boolean).join(' ').toLowerCase().includes(q));
  }, [data.smart, filters.query]);

  const summary = {
    duplicates: data.duplicates.length,
    duplicateFiles: Math.max(0, duplicateFiles.length - data.duplicates.length),
    smart: smartSelectablePaths.length,
    low: data.low.length,
    pending: data.unmatched.filter((item) => item.metadata_status === 'pending').length,
    unmatched: data.unmatched.filter((item) => item.metadata_status !== 'pending').length
    ,
    identity: (identityAudit?.proposals || []).length
  };

  function updateFilter(key, value) {
    setFilters((state) => ({ ...state, [key]: value }));
  }

  function toggleSelected(tab, path, checked) {
    setSelected((state) => {
      const next = new Set(state[tab]);
      if (checked) next.add(path);
      else next.delete(path);
      return { ...state, [tab]: next };
    });
  }

  function setSelectedPaths(tab, paths, checked) {
    setSelected((state) => {
      const next = new Set(state[tab]);
      paths.forEach((path) => {
        if (checked) next.add(path);
        else next.delete(path);
      });
      return { ...state, [tab]: next };
    });
  }

  function requestDelete(tab, paths, title) {
    const uniquePaths = [...new Set(paths.filter(Boolean))];
    if (!uniquePaths.length) return;
    const preview = uniquePaths.slice(0, 5).join('\n');
    const extra = uniquePaths.length > 5 ? `\n...and ${uniquePaths.length - 5} more` : '';
    setConfirmAction({
      type: 'delete',
      tab,
      paths: uniquePaths,
      title,
      body: `${uniquePaths.length} file${uniquePaths.length === 1 ? '' : 's'} will move to the Recycle Bin.\n\n${preview}${extra}`
    });
  }

  function requestFixPath(item) {
    setConfirmAction({
      type: 'fix-path',
      item,
      title: 'Move file for metadata scan?',
      body: `Fix Path will move this file or its movie folder within the library root, then refresh metadata scan paths.\n\n${item.path}`
    });
  }

  async function runConfirmedAction() {
    if (!confirmAction) return;
    if (confirmAction.type === 'delete') {
      await deletePaths(confirmAction.tab, confirmAction.paths);
    } else if (confirmAction.type === 'fix-path') {
      await fixPath(confirmAction.item);
    }
    setConfirmAction(null);
  }

  async function deletePaths(tab, paths) {
    let deleted = 0;
    const failed = [];
    for (const path of paths) {
      try {
        await fetchJson('/api/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path, trash: true })
        });
        deleted += 1;
      } catch (error) {
        failed.push(error.message);
      }
    }
    if (deleted) {
      removeDeletedPaths(paths);
      notify(`${deleted} file${deleted === 1 ? '' : 's'} moved to Recycle Bin`);
    }
    failed.forEach((message) => notify(`Delete failed: ${message}`, 'error'));
    setSelected((state) => ({ ...state, [tab]: new Set() }));
  }

  function removeDeletedPaths(paths) {
    const pathSet = new Set(paths);
    setData((state) => ({
      duplicates: state.duplicates
        .map((group) => ({ ...group, files: (group.files || []).filter((file) => !pathSet.has(file.path)) }))
        .filter((group) => (group.files || []).length > 1),
      smart: state.smart.filter((item) => !pathSet.has(item.delete_path)),
      low: state.low.filter((item) => !pathSet.has(item.path)),
      unmatched: state.unmatched.filter((item) => !pathSet.has(item.path))
    }));
  }

  async function submitRename(event) {
    event.preventDefault();
    if (!renameTarget) return;
    const form = new FormData(event.currentTarget);
    const title = String(form.get('title') || '').trim();
    const year = String(form.get('year') || '').trim();
    if (!title) {
      notify('Title is required', 'error');
      return;
    }
    try {
      const result = await fetchJson('/api/rename-file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: renameTarget.path, title, year })
      });
      setData((state) => ({
        ...state,
        unmatched: state.unmatched.map((item) => item.path === renameTarget.path ? {
          ...item,
          path: result.new_path,
          filename: result.new_filename,
          suggested_title: title,
          suggested_year: year
        } : item)
      }));
      setRenameTarget(null);
      notify(`Renamed to ${result.new_filename}`);
    } catch (error) {
      notify(`Rename failed: ${error.message}`, 'error');
    }
  }

  async function fixPath(item) {
    setRowStatus((state) => ({ ...state, [item.path]: { tone: 'neutral', text: 'Moving file...' } }));
    try {
      const result = await fetchJson('/api/fix-path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: item.path })
      });
      setRowStatus((state) => ({ ...state, [result.new_path || item.path]: { tone: 'success', text: `Moved to ${result.new_path}` } }));
      setData((state) => ({
        ...state,
        unmatched: state.unmatched.map((entry) => entry.path === item.path ? { ...entry, path: result.new_path || entry.path, fixable_path: false } : entry)
      }));
      notify('File moved, metadata rescan requested');
    } catch (error) {
      setRowStatus((state) => ({ ...state, [item.path]: { tone: 'error', text: error.message } }));
      notify(`Fix Path failed: ${error.message}`, 'error');
    }
  }

  function openPlexMatch(item, context = 'unmatched') {
    setMatchModal({
      provider: 'plex',
      context,
      item,
      ratingKey: item.rating_key || '',
      title: item.suggested_title || item.current?.title || item.candidate?.title || '',
      year: item.suggested_year || item.current?.year || item.candidate?.year || '',
      loading: false,
      scanBusy: false,
      scanRequested: false,
      needsPlexScan: false,
      applying: '',
      error: '',
      results: []
    });
  }

  function openTmdbMatch(item, context = 'unmatched') {
    setMatchModal({
      provider: 'tmdb',
      context,
      item,
      title: item.suggested_title || item.current?.title || item.tmdb_title || item.candidate?.title || '',
      year: item.suggested_year || item.current?.year || item.tmdb_year || item.candidate?.year || '',
      loading: false,
      applying: '',
      error: '',
      results: []
    });
  }

  async function runPlexMatchSearch() {
    if (!matchModal?.item?.path) return;
    setMatchModal((state) => ({ ...state, loading: true, error: '', results: [] }));
    try {
      const params = new URLSearchParams({
        path: matchModal.item.path,
        title: matchModal.title,
        year: matchModal.year
      });
      if (matchModal.ratingKey) params.set('rating_key', matchModal.ratingKey);
      if (matchModal.context === 'identity') params.set('force_search', '1');
      const result = await fetchJson(`/api/plex/match-search?${params.toString()}`);
      setMatchModal((state) => ({
        ...state,
        loading: false,
        needsPlexScan: false,
        ratingKey: result.rating_key || state.ratingKey,
        results: result.results || []
      }));
    } catch (error) {
      setMatchModal((state) => ({
        ...state,
        loading: false,
        needsPlexScan: error.data?.code === 'plex_item_not_indexed',
        error: error.message
      }));
    }
  }

  async function searchPlexMatch(event) {
    event.preventDefault();
    await runPlexMatchSearch();
  }

  async function requestPlexScanAndRetry() {
    if (!matchModal?.item?.path) return;
    setMatchModal((state) => ({ ...state, scanBusy: true, error: '' }));
    try {
      await fetchJson('/api/plex/force-scan', { method: 'POST' });
      await new Promise((resolve) => window.setTimeout(resolve, 1500));
      setMatchModal((state) => ({ ...state, scanRequested: true }));
      await runPlexMatchSearch();
      setMatchModal((state) => ({ ...state, scanBusy: false }));
    } catch (error) {
      setMatchModal((state) => ({ ...state, scanBusy: false, scanRequested: true, error: error.message }));
    }
  }

  async function searchTmdbMatch(event) {
    event.preventDefault();
    if (!matchModal?.item) return;
    setMatchModal((state) => ({ ...state, loading: true, error: '', results: [] }));
    try {
      const query = String(matchModal.title || '').trim();
      const tmdbParams = new URLSearchParams({ page: '1', metadata_context: 'unmatched' });
      tmdbParams.set('q', query || matchModal.item.filename);
      if (String(matchModal.year || '').trim()) {
        tmdbParams.set('year', matchModal.year.trim());
      }
      const result = await fetchJson(`/api/tmdb/search?${tmdbParams.toString()}`);
      setMatchModal((state) => ({ ...state, loading: false, results: result.results || [] }));
    } catch (error) {
      setMatchModal((state) => ({ ...state, loading: false, error: error.message }));
    }
  }

  async function applyPlexMatch(match) {
    const ratingKey = matchModal?.ratingKey || matchModal?.item?.rating_key;
    if (!ratingKey || !match?.guid) return;
    setMatchModal((state) => ({ ...state, applying: match.guid, error: '' }));
    try {
      await fetchJson('/api/plex/match-apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: matchModal.item.path,
          rating_key: ratingKey,
          guid: match.guid,
          name: match.name || match.title,
          year: match.year || '',
          poster_url: match.poster_url || '',
          summary: match.summary || ''
        })
      });
      setRowStatus((state) => ({ ...state, [matchModal.item.path]: { tone: 'success', text: `Plex match applied: ${match.name}` } }));
      if (matchModal.context === 'identity') {
        setIdentityApprovedProposal({
          ...matchModal.item,
          candidate: {
            plex_guid: match.guid,
            title: match.name || match.title,
            year: match.year || ''
          }
        });
        setIdentityAudit(await fetchJson('/api/metadata/identity-audit'));
      } else {
        setData((state) => ({
          ...state,
          unmatched: state.unmatched.filter((item) => item.path !== matchModal.item.path)
        }));
      }
      setMatchModal(null);
      onHealthChanged();
      notify('Plex match applied');
    } catch (error) {
      setMatchModal((state) => ({ ...state, applying: '', error: error.message }));
    }
  }

  async function applyTmdbMatch(match) {
    if (!matchModal?.item?.path || !match?.tmdb_id) return;
    setMatchModal((state) => ({ ...state, applying: String(match.tmdb_id), error: '' }));
    try {
      await fetchJson('/api/tmdb/match-apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: matchModal.item.path, tmdb_id: match.tmdb_id, movie: match })
      });
      if (matchModal.context === 'identity') {
        setIdentityApprovedProposal({ ...matchModal.item, candidate: match });
        setIdentityAudit(await fetchJson('/api/metadata/identity-audit'));
      } else {
        setData((state) => ({
          ...state,
          unmatched: state.unmatched.filter((item) => item.path !== matchModal.item.path)
        }));
      }
      setRowStatus((state) => ({ ...state, [matchModal.item.path]: { tone: 'success', text: `TMDB match applied: ${match.title}` } }));
      setMatchModal(null);
      onHealthChanged();
      notify('TMDB match applied');
    } catch (error) {
      setMatchModal((state) => ({ ...state, applying: '', error: error.message }));
    }
  }

  async function startIdentityAudit() {
    if (!window.confirm('Start a new identity scan? Current scan progress and displayed results will be cleared. Previously verified unchanged movies will remain skipped.')) return;
    try {
      setIdentityAudit(await fetchJson('/api/metadata/identity-audit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      }));
      setErrors((state) => ({ ...state, identity: '' }));
    } catch (auditError) {
      setErrors((state) => ({ ...state, identity: auditError.message }));
    }
  }

  async function pauseIdentityAudit() {
    if (!identityAudit?.id) return;
    try {
      setIdentityAudit(await fetchJson(`/api/metadata/identity-audit/${encodeURIComponent(identityAudit.id)}/pause`, {
        method: 'POST'
      }));
    } catch (auditError) {
      setErrors((state) => ({ ...state, identity: auditError.message }));
    }
  }

  async function resumeIdentityAudit() {
    if (!identityAudit?.id) return;
    try {
      setIdentityAudit(await fetchJson(`/api/metadata/identity-audit/${encodeURIComponent(identityAudit.id)}/resume`, {
        method: 'POST'
      }));
      setErrors((state) => ({ ...state, identity: '' }));
    } catch (auditError) {
      setErrors((state) => ({ ...state, identity: auditError.message }));
    }
  }

  async function refreshIdentityAudit() {
    try {
      setIdentityAudit(await fetchJson('/api/metadata/identity-audit'));
    } catch (auditError) {
      setErrors((state) => ({ ...state, identity: auditError.message }));
    }
  }

  const activeSelectedCount = selected[activeTab]?.size || 0;

  return (
    <section className="cleanup-workspace">
      <div className="library-header cleanup-header">
        <div>
          <p className="screen-kicker">Offline maintenance</p>
          <h2>Cleanup <span className="offline-badge">Offline</span></h2>
          <p>Review duplicate copies, safe cleanup recommendations, low-quality files, and files without accepted metadata before touching local files.</p>
        </div>
        <div className="library-header-actions">
          <div className="library-action-row">
            <button type="button" className="btn btn-secondary" onClick={() => loadCleanup(false)}>
              <RefreshCcw size={15} /> Refresh
            </button>
            {activeSelectedCount > 0 && (
              <button type="button" className="btn btn-danger" onClick={() => requestDelete(activeTab, [...selected[activeTab]], `Move ${activeSelectedCount} selected file${activeSelectedCount === 1 ? '' : 's'} to Recycle Bin?`)}>
                <Trash2 size={15} /> Delete selected ({activeSelectedCount})
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="library-stat-strip cleanup-stat-strip">
        <LibraryStat icon={ShieldCheck} label="Duplicate groups" value={formatCount(summary.duplicates)} tone="amber" />
        <LibraryStat icon={Trash2} label="Extra copies" value={formatCount(summary.duplicateFiles)} tone="red" />
        <LibraryStat icon={Wand2} label="Smart picks" value={formatCount(summary.smart)} tone="green" />
        <LibraryStat icon={AlertTriangle} label="Low quality" value={formatCount(summary.low)} tone="amber" />
        {summary.pending > 0 && <LibraryStat icon={Loader2} label="Metadata pending" value={formatCount(summary.pending)} tone="amber" />}
        <LibraryStat icon={LinkIcon} label="Unmatched metadata" value={formatCount(summary.unmatched)} tone="violet" />
        <LibraryStat icon={ScanSearch} label="Identity review" value={formatCount(summary.identity)} tone="cyan" onClick={() => setActiveTab('identity')} />
      </div>

      <div className="cleanup-tabs" role="tablist" aria-label="Cleanup workspace tabs">
        {cleanupTabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button type="button" role="tab" aria-selected={activeTab === tab.id} className={cx(activeTab === tab.id && 'cleanup-tab-active')} key={tab.id} onClick={() => setActiveTab(tab.id)}>
              <Icon size={16} /> {tab.label}
            </button>
          );
        })}
      </div>

      <div className="library-toolbar cleanup-toolbar">
        <label className="library-search cleanup-search">
          <Search size={17} />
          <input value={filters.query} onChange={(event) => updateFilter('query', event.target.value)} placeholder="Search files, paths, Plex titles..." />
        </label>
        {(activeTab === 'low' || activeTab === 'unmatched' || activeTab === 'identity') && (
          <>
            {activeTab === 'low' && (
              <>
                <select value={filters.resolution} onChange={(event) => updateFilter('resolution', event.target.value)}>
                  <option value="all">All resolutions</option>
                  {optionSets.lowResolutions.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
                <select value={filters.source} onChange={(event) => updateFilter('source', event.target.value)}>
                  <option value="all">All sources</option>
                  {optionSets.lowSources.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </>
            )}
            {activeTab === 'unmatched' ? (
              <select value={filters.plex} onChange={(event) => updateFilter('plex', event.target.value)}>
                <option value="all">All unmatched</option>
                <option value="plex-unmatched">Plex unmatched</option>
                <option value="tmdb-unmatched">TMDB unmatched</option>
                <option value="pending">Pending metadata</option>
                <option value="conflict">Conflict</option>
                <option value="needs_review">Needs review</option>
              </select>
            ) : activeTab === 'identity' ? (
              <select value={filters.identity} onChange={(event) => updateFilter('identity', event.target.value)}>
                <option value="all">All identity reviews</option>
                <option value="recommended">Recommended corrections</option>
                <option value="review">Needs review</option>
                <option value="weak">Weak matches</option>
              </select>
            ) : (
              <select value={filters.plex} onChange={(event) => updateFilter('plex', event.target.value)}>
                <option value="all">All Plex states</option>
                <option value="matched">Plex matched</option>
                <option value="unmatched">Plex unmatched</option>
              </select>
            )}
          </>
        )}
      </div>

      {errors[activeTab] && (
        <div className="library-status library-status-error">
          <AlertTriangle size={16} />
          <span>{errors[activeTab]}</span>
        </div>
      )}

      {loading[activeTab] ? (
        <div className="library-status">
          <Loader2 size={16} className="spin" />
          <span>Loading {cleanupTabs.find((tab) => tab.id === activeTab)?.label}...</span>
        </div>
      ) : (
        <>
          {activeTab === 'duplicates' && (
            <DuplicatesCleanupTab groups={filteredDuplicates} selected={selected.duplicates} selectablePaths={selectableDuplicatePaths} onToggle={toggleSelected} onSelectPaths={setSelectedPaths} onDelete={requestDelete} />
          )}
          {activeTab === 'smart' && (
            <SmartCleanupTab recommendations={filteredSmart} selected={selected.smart} selectablePaths={smartSelectablePaths} onToggle={toggleSelected} onSelectPaths={setSelectedPaths} onDelete={requestDelete} />
          )}
          {activeTab === 'low' && (
            <LowQualityCleanupTab items={filteredLow} selected={selected.low} onToggle={toggleSelected} onDelete={requestDelete} onFindTorrent={onFindTorrent} />
          )}
          {activeTab === 'unmatched' && (
            <UnmatchedCleanupTab
              items={filteredUnmatched}
              selected={selected.unmatched}
              rowStatus={rowStatus}
              onToggle={toggleSelected}
              onPlay={onPlay}
              onDelete={requestDelete}
              onRename={setRenameTarget}
              onFixPath={requestFixPath}
              onPlexMatch={openPlexMatch}
              onTmdbMatch={openTmdbMatch}
              plexAvailable={smartMatchProviders.plex !== false}
              smartControls={selected.unmatched.size > 0 ? (
                <SmartMatchControls
                  selectedPaths={[...selected.unmatched]}
                  ollamaAvailable={ollamaAvailable}
                  providers={smartMatchProviders}
                  onStarted={setSmartMatchJob}
                  notify={notify}
                />
              ) : null}
              lastSmartMatchControl={lastSmartMatchJob ? (
                <button type="button" className="btn btn-secondary" onClick={() => setSmartMatchJob(lastSmartMatchJob)}>
                  Open last Smart Match review
                </button>
              ) : null}
            />
          )}
          {activeTab === 'identity' && (
            <IdentityReviewPanel
              audit={identityAudit}
              items={filteredIdentity}
              loading={Boolean(loading.identity)}
              error={errors.identity}
              plexAvailable={smartMatchProviders.plex !== false}
              onStart={startIdentityAudit}
              onPause={pauseIdentityAudit}
              onResume={resumeIdentityAudit}
              onRefresh={refreshIdentityAudit}
              onAuditChanged={setIdentityAudit}
              onPlay={onPlay}
              onTmdbMatch={(proposal) => openTmdbMatch(proposal, 'identity')}
              onPlexMatch={(proposal) => openPlexMatch(proposal, 'identity')}
              onHealthChanged={onHealthChanged}
              externalApproved={identityApprovedProposal}
              onExternalApprovedConsumed={() => setIdentityApprovedProposal(null)}
              notify={notify}
            />
          )}
        </>
      )}

      {confirmAction && (
        <ConfirmDialog
          title={confirmAction.title}
          body={confirmAction.body}
          confirmLabel={confirmAction.type === 'delete' ? 'Move to Recycle Bin' : 'Move file'}
          danger={confirmAction.type === 'delete'}
          onCancel={() => setConfirmAction(null)}
          onConfirm={runConfirmedAction}
        />
      )}
      {renameTarget && (
        <LibraryRenameModal
          item={renameModalItem(renameTarget)}
          onClose={() => setRenameTarget(null)}
          onSubmit={submitRename}
        />
      )}
      {matchModal && (
        matchModal.provider === 'tmdb' ? (
          <TmdbMatchModal
            state={matchModal}
            onClose={() => setMatchModal(null)}
            onChange={(patch) => setMatchModal((state) => ({ ...state, ...patch }))}
            onSearch={searchTmdbMatch}
            onApply={applyTmdbMatch}
          />
        ) : (
          <PlexMatchModal
            state={matchModal}
            onClose={() => setMatchModal(null)}
            onChange={(patch) => setMatchModal((state) => ({ ...state, ...patch }))}
            onSearch={searchPlexMatch}
            onScanRetry={requestPlexScanAndRetry}
            onApply={applyPlexMatch}
          />
        )
      )}
      {smartMatchJob && (
        <SmartMatchReviewModal
          job={smartMatchJob}
          items={data.unmatched}
          onJobChange={setSmartMatchJob}
          onClose={() => setSmartMatchJob(null)}
          onApplied={(paths) => {
            const applied = new Set(paths);
            setData((state) => ({ ...state, unmatched: state.unmatched.filter((item) => !applied.has(item.path)) }));
            setSelected((state) => ({ ...state, unmatched: new Set() }));
          }}
          onTmdbMatch={(item) => { setSmartMatchJob(null); openTmdbMatch(item); }}
          onPlexMatch={(item) => { setSmartMatchJob(null); openPlexMatch(item); }}
          plexAvailable={smartMatchProviders.plex !== false}
          notify={notify}
        />
      )}
    </section>
  );
}

function DuplicatesCleanupTab({ groups, selected, selectablePaths, onToggle, onSelectPaths, onDelete }) {
  const visibleSelectable = groups.flatMap((group) => (group.files || []).slice(1).map((file) => file.path));
  return (
    <div className="cleanup-panel">
      <CleanupSelectionBar
        label={`${formatCount(groups.length)} duplicate groups`}
        selectedCount={selected.size}
        selectableCount={visibleSelectable.length}
        onSelectAll={() => onSelectPaths('duplicates', visibleSelectable, true)}
        onClear={() => onSelectPaths('duplicates', selectablePaths, false)}
      />
      {groups.length ? groups.map((group) => (
        <article className="duplicate-group-card" key={group.title}>
          <header>
            <div>
              <h3>{group.title}</h3>
              <p>{formatCount((group.files || []).length)} copies found. The first file is ranked as the best copy.</p>
            </div>
            <button type="button" className="btn btn-danger" onClick={() => onDelete('duplicates', (group.files || []).slice(1).map((file) => file.path), `Move duplicate copies for ${group.title} to Recycle Bin?`)}>
              <Trash2 size={15} /> Delete extras
            </button>
          </header>
          <div className="cleanup-file-list">
            {(group.files || []).map((file, index) => (
              <CleanupFileRow
                key={file.path}
                item={file}
                selected={selected.has(file.path)}
                selectable={index > 0}
                badge={index === 0 ? 'Best copy' : 'Duplicate'}
                onToggle={(checked) => onToggle('duplicates', file.path, checked)}
                onDelete={() => onDelete('duplicates', [file.path], `Move ${file.filename} to Recycle Bin?`)}
              />
            ))}
          </div>
        </article>
      )) : <CleanupEmpty title="No duplicate groups match this view." text="Refresh or adjust search when new files are added." />}
    </div>
  );
}

function SmartCleanupTab({ recommendations, selected, selectablePaths, onToggle, onSelectPaths, onDelete }) {
  return (
    <div className="cleanup-panel">
      <CleanupSelectionBar
        label={`${formatCount(recommendations.length)} smart recommendations`}
        selectedCount={selected.size}
        selectableCount={recommendations.filter((item) => item.delete_path && !item.skipped).length}
        onSelectAll={() => onSelectPaths('smart', recommendations.filter((item) => item.delete_path && !item.skipped).map((item) => item.delete_path), true)}
        onClear={() => onSelectPaths('smart', selectablePaths, false)}
      />
      {recommendations.length ? (
        <div className="smart-clean-list">
          {recommendations.map((item, index) => {
            const selectable = Boolean(item.delete_path && !item.skipped);
            return (
              <article className={cx('smart-clean-card', item.skipped && 'smart-clean-skipped')} key={`${item.movie}-${item.delete_filename}-${index}`}>
                <label className="cleanup-check">
                  <input type="checkbox" disabled={!selectable} checked={selectable && selected.has(item.delete_path)} onChange={(event) => onToggle('smart', item.delete_path, event.target.checked)} />
                  <span>{selectable ? 'Select' : 'Review'}</span>
                </label>
                <div className="smart-clean-body">
                  <div className="cleanup-title-line">
                    <h3>{item.movie}</h3>
                    <span className={cx('chip', item.skipped ? 'chip-warning' : 'status-owned')}>{item.skipped ? 'Manual review' : 'Recommended'}</span>
                  </div>
                  <div className="smart-compare-grid">
                    <div>
                      <span>Delete candidate</span>
                      <strong>{item.delete_filename}</strong>
                      <small>{[item.delete_resolution, item.delete_rip, item.delete_size].filter(Boolean).join(' | ')}</small>
                    </div>
                    <div>
                      <span>Keep copy</span>
                      <strong>{item.keep_filename}</strong>
                      <small>{[item.keep_resolution, item.keep_rip, item.keep_size].filter(Boolean).join(' | ')}</small>
                    </div>
                  </div>
                  <p>{item.reason}</p>
                </div>
                {selectable && (
                  <button type="button" className="btn btn-danger" onClick={() => onDelete('smart', [item.delete_path], `Move ${item.delete_filename} to Recycle Bin?`)}>
                    <Trash2 size={15} /> Delete
                  </button>
                )}
              </article>
            );
          })}
        </div>
      ) : <CleanupEmpty title="No smart cleanup recommendations match this view." text="Skipped files remain manual review items and are never selected automatically." />}
    </div>
  );
}

function LowQualityCleanupTab({ items, selected, onToggle, onDelete, onFindTorrent }) {
  return (
    <div className="cleanup-panel">
      <CleanupSelectionBar
        label={`${formatCount(items.length)} low-quality files`}
        selectedCount={selected.size}
        selectableCount={items.length}
        onSelectAll={() => items.forEach((item) => onToggle('low', item.path, true))}
        onClear={() => items.forEach((item) => onToggle('low', item.path, false))}
      />
      {items.length ? (
        <div className="cleanup-file-list">
          {items.map((item) => {
            const identity = getMovieIdentity(item);
            return (
              <CleanupFileRow
                key={item.path}
                item={item}
                selected={selected.has(item.path)}
                selectable
                badge="Upgrade candidate"
                onToggle={(checked) => onToggle('low', item.path, checked)}
                onDelete={() => onDelete('low', [item.path], `Move ${item.filename} to Recycle Bin?`)}
                actions={(
                  <button type="button" className="btn btn-upgrade" onClick={() => onFindTorrent({ title: identity.title, year: identity.year, imdb_id: item.imdb_id || '', tmdb_id: item.tmdb_id || '' }, true)}>
                    <Wand2 size={15} /> Find sources
                  </button>
                )}
              />
            );
          })}
        </div>
      ) : <CleanupEmpty title="No low-quality files match this view." text="Use Refresh after adding or replacing files." />}
    </div>
  );
}

function UnmatchedCleanupTab({ items, selected, rowStatus, onToggle, onPlay, onDelete, onRename, onFixPath, onPlexMatch, onTmdbMatch, plexAvailable, smartControls, lastSmartMatchControl }) {
  return (
    <div className="cleanup-panel">
      <CleanupSelectionBar
        label={`${formatCount(items.length)} unmatched files`}
        selectedCount={selected.size}
        selectableCount={items.length}
        onSelectAll={() => items.forEach((item) => onToggle('unmatched', item.path, true))}
        onClear={() => items.forEach((item) => onToggle('unmatched', item.path, false))}
      />
      {smartControls}
      {lastSmartMatchControl && <div className="cleanup-secondary-action">{lastSmartMatchControl}</div>}
      {items.length ? (
        <div className="cleanup-file-list">
          {items.map((item) => (
            <article className="cleanup-file-row unmatched-row" key={item.path}>
              <label className="cleanup-check">
                <input type="checkbox" checked={selected.has(item.path)} onChange={(event) => onToggle('unmatched', item.path, event.target.checked)} />
                <span>Select</span>
              </label>
              <div className="cleanup-file-main">
                <div className="cleanup-title-line">
                  <h3>{item.filename}</h3>
                  <span className={cx('chip', metadataStatusChipClass(item))}>{metadataStatusLabel(item)}</span>
                </div>
                <div className="cleanup-path" title={item.path}>{item.path}</div>
                <div className="cleanup-meta-row">
                  <span className="chip chip-muted">{item.resolution || 'Unknown'}</span>
                  <span className="chip chip-muted">{item.rip_source || 'Unknown source'}</span>
                  <span className="chip chip-muted">{item.file_size || '?'}</span>
                  {item.library_root && <span className="chip chip-muted">{rootLabel(item.library_root)}</span>}
                  {item.fixable_path && <span className="chip chip-warning">Folder depth {item.depth}</span>}
                </div>
                <p className="cleanup-hint">{item.metadata_hint || item.plex_hint || 'No metadata hint available.'}</p>
                {rowStatus[item.path] && <p className={cx('cleanup-row-status', `cleanup-row-${rowStatus[item.path].tone}`)}>{rowStatus[item.path].text}</p>}
              </div>
              <div className="cleanup-row-actions">
                <button type="button" className="btn btn-primary btn-green" onClick={() => onPlay(item.path)}>
                  <Play size={15} /> Play file
                </button>
                <button type="button" className="btn btn-primary btn-violet" onClick={() => onTmdbMatch(item)}>
                  <Search size={15} /> Search TMDB
                </button>
                {plexAvailable ? (
                  <button type="button" className="btn btn-secondary" onClick={() => onPlexMatch(item)}>
                    <Clapperboard size={15} /> Search Plex
                  </button>
                ) : item.fixable_path ? (
                  <button type="button" className="btn btn-secondary" onClick={() => onFixPath(item)}>
                    <Folder size={15} /> Fix path
                  </button>
                ) : (
                  <span className="cleanup-action-note">Plex optional</span>
                )}
                <button type="button" className="btn btn-secondary" onClick={() => onRename(item)}>
                  <Clapperboard size={15} /> Rename
                </button>
                <button type="button" className="btn btn-danger" onClick={() => onDelete('unmatched', [item.path], `Move ${item.filename} to Recycle Bin?`)}>
                  <Trash2 size={15} /> Delete
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : <CleanupEmpty title="No unmatched metadata files match this view." text="Search TMDB or refresh metadata when new files are added." />}
    </div>
  );
}

function CleanupSelectionBar({ label, selectedCount, selectableCount, onSelectAll, onClear }) {
  return (
    <div className="cleanup-selection-bar">
      <span>{label}</span>
      <strong>{formatCount(selectedCount)} selected</strong>
      <div>
        <button type="button" className="mini-action" onClick={onSelectAll} disabled={!selectableCount}>Select all</button>
        <button type="button" className="mini-action" onClick={onClear} disabled={!selectedCount}>Clear</button>
      </div>
    </div>
  );
}

function CleanupFileRow({ item, selected, selectable, badge, onToggle, onDelete, actions }) {
  return (
    <article className="cleanup-file-row">
      <label className="cleanup-check">
        <input type="checkbox" disabled={!selectable} checked={selectable && selected} onChange={(event) => onToggle(event.target.checked)} />
        <span>{selectable ? 'Select' : 'Keep'}</span>
      </label>
      <div className="cleanup-file-main">
        <div className="cleanup-title-line">
          <h3>{item.filename}</h3>
          <span className={cx('chip', badge === 'Best copy' ? 'status-owned' : 'chip-warning')}>{badge}</span>
        </div>
        <div className="cleanup-path" title={item.path}>{item.path}</div>
        <div className="cleanup-meta-row">
          <span className={cx('chip', isLowQuality(item.resolution) && 'chip-warning')}>{item.resolution || 'Unknown'}</span>
          <span className="chip chip-muted">{item.rip_source || 'Unknown source'}</span>
          <span className="chip chip-muted">{item.size_human || item.file_size || '?'}</span>
          {item.library_root && <span className="chip chip-muted">{rootLabel(item.library_root)}</span>}
          <span className={cx('chip', item.plex_matched ? 'status-owned' : 'status-missing')}>{item.plex_matched ? 'Plex matched' : 'Plex unmatched'}</span>
          {item.plex_title && <span className="chip chip-muted">{item.plex_title}{item.plex_year ? ` (${item.plex_year})` : ''}</span>}
        </div>
      </div>
      <div className="cleanup-row-actions">
        {actions}
        {selectable && (
          <button type="button" className="btn btn-danger" onClick={onDelete}>
            <Trash2 size={15} /> Delete
          </button>
        )}
      </div>
    </article>
  );
}

function CleanupEmpty({ title, text }) {
  return (
    <div className="empty-state library-empty cleanup-empty">
      <strong>{title}</strong>
      <span>{text}</span>
    </div>
  );
}

function TmdbMatchModal({ state, onClose, onChange, onSearch, onApply }) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="torrent-dialog cleanup-match-dialog" role="dialog" aria-modal="true" aria-label="TMDB match search" onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <p className="screen-kicker">TMDB match</p>
            <h2>{state.item.filename}</h2>
          </div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close TMDB match dialog">
            <X size={18} />
          </button>
        </div>
        <form className="cleanup-match-form" onSubmit={onSearch}>
          <label className="dialog-field">
            <span>Search title</span>
            <input value={state.title} onChange={(event) => onChange({ title: event.target.value })} />
          </label>
          <label className="dialog-field">
            <span>Year</span>
            <input value={state.year} onChange={(event) => onChange({ year: event.target.value })} inputMode="numeric" />
          </label>
          <button type="submit" className="btn btn-primary btn-violet cleanup-match-submit" disabled={state.loading}>
            {state.loading ? <Loader2 size={15} className="spin" /> : <Search size={15} />} Search TMDB
          </button>
        </form>
        {state.error && <p className="settings-inline-status settings-inline-error"><AlertTriangle size={15} /><span>{state.error}</span></p>}
        <div className="match-result-list">
          {state.results.length ? state.results.map((match) => (
            <article className="match-result-row tmdb-match-result-row" key={match.tmdb_id}>
              <span className="match-result-poster">
                {match.poster_url ? <img src={match.poster_url} alt="" loading="lazy" /> : <Film size={18} />}
              </span>
              <div>
                <strong>{match.title}</strong>
                <span>{match.year || 'Unknown year'} | {match.tmdb_rating ? `${match.tmdb_rating} - ${formatVoteCount(match.tmdb_vote_count) || 'no votes'}` : 'No rating'}</span>
                <small>{match.plot || 'No plot summary available.'}</small>
              </div>
              <button type="button" className="btn btn-secondary" onClick={() => onApply(match)} disabled={Boolean(state.applying)}>
                {state.applying === String(match.tmdb_id) ? <Loader2 size={15} className="spin" /> : <CheckCircle2 size={15} />} Apply match
              </button>
            </article>
          )) : (
            <div className="cleanup-empty-match">Search TMDB, then choose the exact public movie identity.</div>
          )}
        </div>
      </section>
    </div>
  );
}

function PlexMatchModal({ state, onClose, onChange, onSearch, onScanRetry, onApply }) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="torrent-dialog cleanup-match-dialog" role="dialog" aria-modal="true" aria-label="Plex match search" onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header">
          <div>
            <p className="screen-kicker">Plex match</p>
            <h2>{state.item.filename}</h2>
          </div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close Plex match dialog">
            <X size={18} />
          </button>
        </div>
        <form className="cleanup-match-form" onSubmit={onSearch}>
          <label className="dialog-field">
            <span>Search title</span>
            <input value={state.title} onChange={(event) => onChange({ title: event.target.value })} />
          </label>
          <label className="dialog-field">
            <span>Year</span>
            <input value={state.year} onChange={(event) => onChange({ year: event.target.value })} inputMode="numeric" />
          </label>
          <button type="submit" className="btn btn-primary cleanup-match-submit" disabled={state.loading}>
            {state.loading ? <Loader2 size={15} className="spin" /> : <Search size={15} />} Search Plex
          </button>
        </form>
        {state.error && <p className="settings-inline-status settings-inline-error"><AlertTriangle size={15} /><span>{state.error}</span></p>}
        {state.needsPlexScan && (
          <div className="cleanup-match-recovery">
            <span>Plex must index this file before its matching agents can be searched.</span>
            <button type="button" className="btn btn-secondary" onClick={onScanRetry} disabled={state.scanBusy}>
              {state.scanBusy ? <Loader2 size={15} className="spin" /> : <RefreshCcw size={15} />}
              {state.scanRequested ? 'Retry Plex lookup' : 'Request Plex scan'}
            </button>
          </div>
        )}
        <div className="match-result-list">
          {state.results.length ? state.results.map((match) => (
            <article className="match-result-row plex-match-result-row" key={match.guid}>
              <span className="match-result-poster">
                {match.poster_url ? <img src={match.poster_url} alt="" loading="lazy" /> : <Film size={18} />}
              </span>
              <div>
                <strong>{match.title || match.name}</strong>
                <span>
                  {match.year || 'Unknown year'}
                  {match.exact_external_id ? ' · Exact external ID' : ''}
                  {match.rank ? ` · Plex rank ${match.rank}` : ''}
                </span>
                <small>{match.summary || 'No plot summary available.'}</small>
                {match.match_reasons?.length > 0 && (
                  <small className="plex-match-reasons">{match.match_reasons.join(' · ')}</small>
                )}
              </div>
              <button type="button" className="btn btn-secondary" onClick={() => onApply(match)} disabled={Boolean(state.applying)}>
                {state.applying === match.guid ? <Loader2 size={15} className="spin" /> : <CheckCircle2 size={15} />} Apply match
              </button>
            </article>
          )) : (
            <div className="cleanup-empty-match">Search Plex agents, then choose the exact metadata match.</div>
          )}
        </div>
      </section>
    </div>
  );
}

const emptySettingsState = {
  library: { directory: '', directories: [''], showAdultMovies: true },
  appData: { user_data_dir: '', tmdb_cache_dir: '' },
  plex: { url: '', token: '' },
  prowlarr: {
    url: '',
    key: '',
    indexers: [],
    trusted_release_indexers: [],
    download_default_quality: '1080p',
    download_indexer_mode: 'release'
  },
  qbittorrent: {
    mode: 'embedded',
    download_dir: '',
    incomplete_dir: '',
    effective_download_dir: '',
    effective_incomplete_dir: '',
    download_dir_in_library: true,
    installed: false,
    running: false,
    supported: true,
    version: '',
    latest_version: '',
    update_available: false
  },
  tmdb: { key: '', includeAdult: false },
  streaming: {
    enabled: true,
    label: 'Stream',
    url_template: 'https://streamimdb.ru/embed/movie/{tmdb_id}'
  },
  ollama: { url: '', model: '', candidateLimit: 15 },
  aiControl: {
    enabled: true,
    trusted_indexers: [],
    trusted_indexers_configured: false,
    max_matched_movies: 25,
    max_download_searches: 10,
    ollama_curated_lists: false,
    indexers: []
  }
};

function SettingsWorkspace({ notify, onReviewUnmatched, onReviewIdentities, onStreamingConfigChanged }) {
  const [forms, setForms] = useState(emptySettingsState);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState({});
  const [statuses, setStatuses] = useState({});
  const [revealed, setRevealed] = useState({});
  const [trustedIndexerDialogOpen, setTrustedIndexerDialogOpen] = useState(false);
  const [aiControlIndexerDialogOpen, setAiControlIndexerDialogOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadSettings() {
      setLoading(true);
      const requests = await Promise.allSettled([
        fetchJson('/api/config'),
        fetchJson('/api/app-data/config'),
        fetchJson('/api/plex/config'),
        fetchJson('/api/prowlarr/config'),
        fetchJson('/api/qbittorrent/config'),
        fetchJson('/api/tmdb/config'),
        fetchJson('/api/streaming/config'),
        fetchJson('/api/ollama/config'),
        fetchJson('/api/ai-control/config')
      ]);
      if (cancelled) return;
      const [library, appData, plex, prowlarr, qbittorrent, tmdb, streaming, ollama, aiControl] = requests;
      setForms({
        library: library.status === 'fulfilled' ? {
          directory: library.value.directory || '',
          directories: (library.value.directories && library.value.directories.length ? library.value.directories : [library.value.directory || '']).filter((path) => path !== ''),
          showAdultMovies: library.value.show_adult_movies !== false
        } : { directory: '', directories: [''], showAdultMovies: true },
        appData: appData.status === 'fulfilled' ? {
          user_data_dir: appData.value.user_data_dir || '',
          tmdb_cache_dir: appData.value.tmdb_cache_dir || ''
        } : { user_data_dir: '', tmdb_cache_dir: '' },
        plex: plex.status === 'fulfilled' ? { url: plex.value.url || '', token: plex.value.token || '' } : { url: '', token: '' },
        prowlarr: prowlarr.status === 'fulfilled' ? {
          url: prowlarr.value.url || '',
          key: prowlarr.value.key || '',
          indexers: prowlarr.value.indexers || [],
          trusted_release_indexers: prowlarr.value.trusted_release_indexers || [],
          download_default_quality: prowlarr.value.download_default_quality || '1080p',
          download_indexer_mode: prowlarr.value.download_indexer_mode || 'release'
        } : emptySettingsState.prowlarr,
        qbittorrent: qbittorrent.status === 'fulfilled' ? qbittorrent.value : emptySettingsState.qbittorrent,
        tmdb: tmdb.status === 'fulfilled' ? { key: tmdb.value.key || '', includeAdult: Boolean(tmdb.value.include_adult) } : { key: '', includeAdult: false },
        streaming: streaming.status === 'fulfilled' ? {
          enabled: streaming.value.enabled !== false,
          label: streaming.value.label || 'Stream',
          url_template: streaming.value.url_template || ''
        } : emptySettingsState.streaming,
        ollama: ollama.status === 'fulfilled' ? {
          url: ollama.value.url || '',
          model: ollama.value.model || '',
          candidateLimit: ollama.value.candidate_limit || 15
        } : { url: '', model: '', candidateLimit: 15 },
        aiControl: aiControl.status === 'fulfilled' ? {
          enabled: aiControl.value.enabled !== false,
          trusted_indexers: aiControl.value.trusted_indexers || [],
          trusted_indexers_configured: Boolean(aiControl.value.trusted_indexers_configured),
          max_matched_movies: aiControl.value.max_matched_movies || 25,
          max_download_searches: aiControl.value.max_download_searches || 10,
          ollama_curated_lists: Boolean(aiControl.value.ollama_curated_lists),
          indexers: aiControl.value.indexers || []
        } : emptySettingsState.aiControl
      });
      const failed = requests.filter((request) => request.status === 'rejected');
      if (failed.length) {
        setStatuses((state) => ({
          ...state,
          page: { tone: 'error', message: `${failed.length} settings area${failed.length === 1 ? '' : 's'} could not be loaded.` }
        }));
      }
      setLoading(false);
    }
    loadSettings();
    return () => { cancelled = true; };
  }, []);

  function updateField(section, field, value) {
    setForms((state) => ({
      ...state,
      [section]: { ...state[section], [field]: value }
    }));
  }

  function updateTrustedReleaseIndexer(indexerId, checked) {
    setForms((state) => {
      const current = new Set(state.prowlarr.trusted_release_indexers || []);
      if (checked) {
        current.add(indexerId);
      } else {
        current.delete(indexerId);
      }
      return {
        ...state,
        prowlarr: {
          ...state.prowlarr,
          trusted_release_indexers: Array.from(current)
        }
      };
    });
  }

  function updateAiControlTrustedIndexer(indexerId, checked) {
    setForms((state) => {
      const current = new Set(state.aiControl.trusted_indexers || []);
      if (checked) {
        current.add(indexerId);
      } else {
        current.delete(indexerId);
      }
      return {
        ...state,
        aiControl: {
          ...state.aiControl,
          trusted_indexers: Array.from(current)
        }
      };
    });
  }

  function updateLibraryDirectory(index, value) {
    setForms((state) => {
      const directories = [...(state.library.directories || [''])];
      directories[index] = value;
      return {
        ...state,
        library: {
          ...state.library,
          directory: directories.find((path) => path.trim()) || '',
          directories
        }
      };
    });
  }

  function addLibraryDirectory() {
    setForms((state) => ({
      ...state,
      library: {
        ...state.library,
        directories: [...(state.library.directories || ['']), '']
      }
    }));
  }

  function removeLibraryDirectory(index) {
    setForms((state) => {
      const current = state.library.directories || [''];
      const directories = current.filter((_, itemIndex) => itemIndex !== index);
      const nextDirectories = directories.length ? directories : [''];
      return {
        ...state,
        library: {
          ...state.library,
          directory: nextDirectories.find((path) => path.trim()) || '',
          directories: nextDirectories
        }
      };
    });
  }

  function setActionState(key, active) {
    setSaving((state) => ({ ...state, [key]: active }));
  }

  function setCardStatus(key, tone, message, detail = '') {
    setStatuses((state) => ({ ...state, [key]: { tone, message, detail } }));
  }

  async function saveLibrary(event) {
    event.preventDefault();
    setActionState('library-save', true);
    const directories = [...new Set((forms.library.directories || []).map((path) => path.trim()).filter(Boolean))];
    try {
      const data = await fetchJson('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ directories, show_adult_movies: Boolean(forms.library.showAdultMovies) })
      });
      const savedDirectories = data.directories && data.directories.length ? data.directories : [data.directory || ''];
      setForms((state) => ({ ...state, library: { directory: data.directory || savedDirectories[0] || '', directories: savedDirectories, showAdultMovies: data.show_adult_movies !== false } }));
      setCardStatus('library', 'success', 'Library locations saved.', `${savedDirectories.length} folder${savedDirectories.length === 1 ? '' : 's'} configured.`);
      notify('Library locations saved');
    } catch (error) {
      setCardStatus('library', 'error', 'Library locations not saved.', error.message);
    } finally {
      setActionState('library-save', false);
    }
  }

  async function saveAppData(event) {
    event.preventDefault();
    setActionState('appData-save', true);
    try {
      const data = await fetchJson('/api/app-data/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(forms.appData)
      });
      setForms((state) => ({ ...state, appData: { user_data_dir: data.user_data_dir || '', tmdb_cache_dir: data.tmdb_cache_dir || '' } }));
      setCardStatus('appData', 'success', 'App data paths saved.', 'Folders are ready.');
      notify('App data paths saved');
    } catch (error) {
      setCardStatus('appData', 'error', 'App data paths not saved.', error.message);
    } finally {
      setActionState('appData-save', false);
    }
  }

  async function saveIntegration(service) {
    const endpoints = {
      plex: '/api/plex/config',
      prowlarr: '/api/prowlarr/config',
      tmdb: '/api/tmdb/config',
      streaming: '/api/streaming/config',
      ollama: '/api/ollama/config'
    };
    const payloads = {
      plex: { url: forms.plex.url, token: forms.plex.token },
      prowlarr: {
        url: forms.prowlarr.url,
        key: forms.prowlarr.key,
        trusted_release_indexers: forms.prowlarr.trusted_release_indexers || [],
        download_default_quality: forms.prowlarr.download_default_quality || '1080p',
        download_indexer_mode: forms.prowlarr.download_indexer_mode || 'release'
      },
      tmdb: { key: forms.tmdb.key, include_adult: Boolean(forms.tmdb.includeAdult) },
      streaming: {
        enabled: Boolean(forms.streaming.enabled),
        label: forms.streaming.label,
        url_template: forms.streaming.url_template
      },
      ollama: { url: forms.ollama.url, model: forms.ollama.model, candidate_limit: Number(forms.ollama.candidateLimit || 15) }
    };
    setActionState(`${service}-save`, true);
    try {
      const saved = await fetchJson(endpoints[service], {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payloads[service])
      });
      if (service === 'streaming') {
        setForms((state) => ({
          ...state,
          streaming: {
            enabled: saved.enabled !== false,
            label: saved.label || 'Stream',
            url_template: saved.url_template || ''
          }
        }));
        onStreamingConfigChanged?.(saved);
      }
      if (service === 'prowlarr') {
        const config = await fetchJson('/api/prowlarr/config');
        const aiControlConfig = await fetchJson('/api/ai-control/config').catch(() => null);
        setForms((state) => ({
          ...state,
          prowlarr: {
            url: config.url || '',
            key: config.key || '',
            indexers: config.indexers || [],
            trusted_release_indexers: config.trusted_release_indexers || [],
            download_default_quality: config.download_default_quality || '1080p',
            download_indexer_mode: config.download_indexer_mode || 'release'
          },
          aiControl: aiControlConfig ? {
            ...state.aiControl,
            trusted_indexers: aiControlConfig.trusted_indexers || state.aiControl.trusted_indexers || [],
            trusted_indexers_configured: Boolean(aiControlConfig.trusted_indexers_configured),
            indexers: aiControlConfig.indexers || state.aiControl.indexers || []
          } : state.aiControl
        }));
      }
      setCardStatus(service, 'success', `${serviceLabel(service)} settings saved.`, 'Run Test to verify the saved connection.');
      notify(`${serviceLabel(service)} settings saved`);
      return true;
    } catch (error) {
      setCardStatus(service, 'error', `${serviceLabel(service)} settings not saved.`, error.message);
      return false;
    } finally {
      setActionState(`${service}-save`, false);
    }
  }

  async function saveQbittorrent() {
    setActionState('qbittorrent-save', true);
    try {
      const config = await fetchJson('/api/qbittorrent/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: forms.qbittorrent.mode,
          download_dir: forms.qbittorrent.download_dir || '',
          incomplete_dir: forms.qbittorrent.incomplete_dir || ''
        })
      });
      torrentHandlingConfigPromise = Promise.resolve(config);
      setForms((state) => ({ ...state, qbittorrent: { ...state.qbittorrent, ...config } }));
      setCardStatus(
        'qbittorrent',
        config.download_dir_in_library ? 'success' : 'neutral',
        'qBittorrent settings saved.',
        config.download_dir_in_library
          ? `Completed movies move to ${config.effective_download_dir}.`
          : 'The completed folder is outside Cinema Paradiso libraries, so automatic metadata discovery is disabled.'
      );
      notify('qBittorrent settings saved');
    } catch (error) {
      setCardStatus('qbittorrent', 'error', 'qBittorrent settings not saved.', error.message);
    } finally {
      setActionState('qbittorrent-save', false);
    }
  }

  async function saveAiControl(options = {}) {
    const includeTrusted = Boolean(options.includeTrusted);
    setActionState('ai-control-save', true);
    try {
      const payload = {
        enabled: Boolean(forms.aiControl.enabled),
        max_matched_movies: Number(forms.aiControl.max_matched_movies || 25),
        max_download_searches: Number(forms.aiControl.max_download_searches || 10),
        ollama_curated_lists: Boolean(forms.aiControl.ollama_curated_lists)
      };
      if (includeTrusted) {
        payload.trusted_indexers = forms.aiControl.trusted_indexers || [];
      }
      const data = await fetchJson('/api/ai-control/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      setForms((state) => ({
        ...state,
        aiControl: {
          enabled: data.enabled !== false,
          trusted_indexers: data.trusted_indexers || [],
          trusted_indexers_configured: Boolean(data.trusted_indexers_configured),
          max_matched_movies: data.max_matched_movies || 25,
          max_download_searches: data.max_download_searches || 10,
          ollama_curated_lists: Boolean(data.ollama_curated_lists),
          indexers: data.indexers || state.aiControl.indexers || []
        }
      }));
      setCardStatus('ai-control', 'success', 'AI Control settings saved.', 'The experimental command policy is updated.');
      notify('AI Control settings saved');
    } catch (error) {
      setCardStatus('ai-control', 'error', 'AI Control settings not saved.', error.message);
    } finally {
      setActionState('ai-control-save', false);
    }
  }

  async function testIntegration(service) {
    const urls = {
      plex: '/api/plex/test',
      prowlarr: '/api/prowlarr/test',
      tmdb: `/api/tmdb/test?key=${encodeURIComponent(forms.tmdb.key || '')}`,
      ollama: `/api/ollama/test?url=${encodeURIComponent(forms.ollama.url || '')}`
    };
    setActionState(`${service}-test`, true);
    try {
      const data = await fetchJson(urls[service]);
      if (service === 'plex') {
        setCardStatus('plex', 'success', 'Plex connected.', `${formatCount(data.movie_libraries)} movie libraries found.`);
      } else if (service === 'prowlarr') {
        setCardStatus('prowlarr', 'success', 'Prowlarr connected.', `${formatCount(data.indexers)} indexers available.`);
      } else if (service === 'tmdb') {
        setCardStatus('tmdb', 'success', 'TMDB key is valid.', 'Discovery metadata is available.');
      } else {
        setCardStatus('ollama', 'success', 'Ollama is reachable.', 'Local AI recommendations can run.');
      }
    } catch (error) {
      setCardStatus(service, 'error', `${serviceLabel(service)} test failed.`, error.message);
    } finally {
      setActionState(`${service}-test`, false);
    }
  }

  async function runPlexAction(action) {
    const endpoint = action === 'sync' ? '/api/plex/sync' : '/api/plex/force-scan';
    const method = action === 'sync' ? 'GET' : 'POST';
    setActionState(`plex-${action}`, true);
    try {
      const data = await fetchJson(endpoint, { method });
      setCardStatus('plex', 'success', action === 'sync' ? 'Plex cache refreshed.' : 'Plex scan requested.', data.cached ? `${formatCount(data.cached)} files cached.` : 'Plex will refresh its movie sections.');
      notify(action === 'sync' ? 'Plex cache refreshed' : 'Plex scan requested');
    } catch (error) {
      setCardStatus('plex', 'error', action === 'sync' ? 'Plex cache refresh failed.' : 'Plex scan failed.', error.message);
    } finally {
      setActionState(`plex-${action}`, false);
    }
  }

  function trustedIndexerSummary() {
    const trustedIds = new Set((forms.prowlarr.trusted_release_indexers || []).map(String));
    if (!trustedIds.size) return 'None trusted';
    const names = (forms.prowlarr.indexers || [])
      .filter((indexer) => trustedIds.has(String(indexer.id)))
      .map((indexer) => indexer.name || `Indexer ${indexer.id}`);
    if (!names.length) return `${trustedIds.size} trusted`;
    if (names.length === 1) return `${names[0]} trusted`;
    if (names.length === 2) return `${names.join(', ')} trusted`;
    return `${names.length} trusted`;
  }

  function aiControlIndexerSummary() {
    const trustedIds = new Set((forms.aiControl.trusted_indexers || []).map(String));
    if (!trustedIds.size && !forms.aiControl.trusted_indexers_configured) return 'YTS/YIFY default';
    if (!trustedIds.size) return 'None trusted';
    const names = (forms.aiControl.indexers || [])
      .filter((indexer) => trustedIds.has(String(indexer.id)))
      .map((indexer) => indexer.name || `Indexer ${indexer.id}`);
    if (!names.length) return `${trustedIds.size} trusted`;
    if (names.length === 1) return `${names[0]} trusted`;
    if (names.length === 2) return `${names.join(', ')} trusted`;
    return `${names.length} trusted`;
  }

  const summary = [
    { key: 'library', label: 'Library roots', ready: (forms.library.directories || []).some((path) => path.trim()), tone: 'blue' },
    { key: 'plex', label: 'Plex', ready: Boolean(forms.plex.url && forms.plex.token), tone: 'cyan' },
    { key: 'prowlarr', label: 'Prowlarr', ready: Boolean(forms.prowlarr.url && forms.prowlarr.key), tone: 'gold' },
    { key: 'qbittorrent', label: 'qBittorrent', ready: forms.qbittorrent.mode === 'system' || Boolean(forms.qbittorrent.installed), tone: 'gold' },
    { key: 'tmdb', label: 'TMDB', ready: Boolean(forms.tmdb.key), tone: 'green' },
    { key: 'streaming', label: 'Streaming', ready: Boolean(forms.streaming.enabled && forms.streaming.url_template), tone: 'green' },
    { key: 'ollama', label: 'Ollama', ready: Boolean(forms.ollama.url && forms.ollama.model), tone: 'violet' },
    { key: 'ai-control', label: 'AI Control', ready: Boolean(forms.aiControl.enabled), tone: 'violet' }
  ];
  const configuredCount = summary.filter((item) => item.ready).length;

  return (
    <section className="settings-workspace">
      <div className="library-header">
        <div>
          <p className="screen-kicker">System console</p>
          <h2>Settings</h2>
          <p>Configure the local archive root, app data folders, and optional integrations without mixing file cleanup into Movie View.</p>
        </div>
        <div className="settings-summary">
          <strong>{configuredCount} / {summary.length}</strong>
          <span>configured</span>
        </div>
      </div>

      <div className="settings-chip-row" aria-label="Configuration summary">
        {summary.map((item) => (
          <span key={item.key} className={cx('settings-chip', `settings-chip-${item.tone}`, item.ready ? 'settings-chip-ready' : 'settings-chip-missing')}>
            {item.ready ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
            {item.label}
            <small>{item.ready ? 'Ready' : 'Missing'}</small>
          </span>
        ))}
      </div>

      {loading ? (
        <div className="library-status">
          <Loader2 size={16} className="spin" />
          <span>Loading settings...</span>
        </div>
      ) : statuses.page ? (
        <SettingsInlineStatus status={statuses.page} />
      ) : null}

      <MetadataAuthorityPanel
        fetchJson={fetchJson}
        notify={notify}
        onReviewUnmatched={onReviewUnmatched}
        onReviewIdentities={onReviewIdentities}
      />

      <div className="settings-grid">
        <form className="settings-panel settings-panel-wide" onSubmit={saveLibrary}>
          <SettingsPanelHeader icon={Folder} title="Library Locations" label="Offline roots" text="Every folder is scanned as one merged archive for Library, Cleanup, duplicate detection, and Plex matching." />
          <div className="library-location-list">
            {(forms.library.directories && forms.library.directories.length ? forms.library.directories : ['']).map((directory, index) => (
              <label className="dialog-field library-location-field" key={`library-dir-${index}`}>
                <span>{index === 0 ? 'Primary movie folder' : `Movie folder ${index + 1}`}</span>
                <span className="library-location-input">
                  <input value={directory || ''} onChange={(event) => updateLibraryDirectory(index, event.target.value)} placeholder="E:\\Movies" />
                  <button type="button" className="secret-toggle library-location-remove" onClick={() => removeLibraryDirectory(index)} disabled={(forms.library.directories || []).length <= 1} aria-label={`Remove movie folder ${index + 1}`}>
                    <X size={15} />
                  </button>
                </span>
              </label>
            ))}
          </div>
          <label className="settings-checkbox-field">
            <input
              type="checkbox"
              checked={forms.library.showAdultMovies !== false}
              onChange={(event) => updateField('library', 'showAdultMovies', event.target.checked)}
            />
            <span>
              <strong>Show adult movies in Movie View</strong>
              <small>File View and Cleanup still show every local file.</small>
            </span>
          </label>
          <SettingsInlineStatus status={statuses.library} />
          <div className="dialog-actions">
            <button type="button" className="btn btn-secondary" onClick={addLibraryDirectory}>
              <CirclePlus size={15} /> Add location
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving['library-save']}>
              {saving['library-save'] ? <Loader2 size={15} className="spin" /> : <Save size={15} />} Save locations
            </button>
          </div>
        </form>

        <form className="settings-panel settings-panel-wide" onSubmit={saveAppData}>
          <SettingsPanelHeader icon={Database} title="App Data" label="Local storage" text="User lists and edited collections live in data. TMDB cache can be rebuilt when needed." />
          <label className="dialog-field">
            <span>User data folder</span>
            <input value={forms.appData.user_data_dir || ''} onChange={(event) => updateField('appData', 'user_data_dir', event.target.value)} />
          </label>
          <label className="dialog-field">
            <span>TMDB cache folder</span>
            <input value={forms.appData.tmdb_cache_dir || ''} onChange={(event) => updateField('appData', 'tmdb_cache_dir', event.target.value)} />
          </label>
          <SettingsInlineStatus status={statuses.appData} />
          <div className="dialog-actions">
            <button type="submit" className="btn btn-primary" disabled={saving['appData-save']}>
              {saving['appData-save'] ? <Loader2 size={15} className="spin" /> : <Save size={15} />} Save folders
            </button>
          </div>
        </form>
      </div>

      <div className="settings-section-heading">
        <div>
          <h3>Integrations</h3>
          <p>Save credentials first, then test the saved service connection.</p>
        </div>
      </div>

      <div className="settings-integration-grid">
        <IntegrationCard
          id="settings-plex"
          icon={Server}
          title="Plex"
          accent="cyan"
          status={statuses.plex}
          loading={saving}
          fields={(
            <>
              <label className="dialog-field">
                <span>Plex URL</span>
                <input value={forms.plex.url || ''} onChange={(event) => updateField('plex', 'url', event.target.value)} placeholder="http://localhost:32400" />
              </label>
              <SecretField
                label="Plex token"
                value={forms.plex.token || ''}
                revealed={revealed.plex}
                onReveal={() => setRevealed((state) => ({ ...state, plex: !state.plex }))}
                onChange={(value) => updateField('plex', 'token', value)}
              />
            </>
          )}
          actions={(
            <>
              <ActionButton loading={saving['plex-save']} icon={Save} label="Save Plex" onClick={() => saveIntegration('plex')} primary />
              <ActionButton loading={saving['plex-test']} icon={PlugZap} label="Test saved" onClick={() => testIntegration('plex')} />
              <ActionButton loading={saving['plex-sync']} icon={RefreshCcw} label="Refresh Plex Cache" onClick={() => runPlexAction('sync')} />
              <ActionButton loading={saving['plex-scan']} icon={Radio} label="Force Plex Scan" onClick={() => runPlexAction('scan')} />
            </>
          )}
        />

        <IntegrationCard
          id="settings-prowlarr"
          icon={Search}
          title="Prowlarr"
          accent="gold"
          status={statuses.prowlarr}
          fields={(
            <>
              <label className="dialog-field">
                <span>Prowlarr URL</span>
                <input value={forms.prowlarr.url || ''} onChange={(event) => updateField('prowlarr', 'url', event.target.value)} placeholder="http://localhost:9696" />
              </label>
              <SecretField
                label="API key"
                value={forms.prowlarr.key || ''}
                revealed={revealed.prowlarr}
                onReveal={() => setRevealed((state) => ({ ...state, prowlarr: !state.prowlarr }))}
                onChange={(value) => updateField('prowlarr', 'key', value)}
              />
              <p className="trusted-indexer-summary">
                <span>Release watchlist trust</span>
                <strong>{trustedIndexerSummary()}</strong>
              </p>
              <div className="settings-subsection">
                <span className="settings-subsection-title">Automation defaults</span>
                <div className="settings-two-column">
                  <label className="dialog-field">
                    <span>Default download quality</span>
                    <select
                      value={forms.prowlarr.download_default_quality || '1080p'}
                      onChange={(event) => updateField('prowlarr', 'download_default_quality', event.target.value)}
                    >
                      <option value="1080p">1080p</option>
                      <option value="4K">4K</option>
                    </select>
                  </label>
                  <label className="dialog-field">
                    <span>Download trusted indexers</span>
                    <select
                      value={forms.prowlarr.download_indexer_mode || 'release'}
                      onChange={(event) => updateField('prowlarr', 'download_indexer_mode', event.target.value)}
                    >
                      <option value="release">Use release trusted indexers</option>
                      <option value="all">Use all enabled indexers</option>
                    </select>
                  </label>
                </div>
              </div>
            </>
          )}
          actions={(
            <>
              <ActionButton loading={saving['prowlarr-save']} icon={Save} label="Save Prowlarr" onClick={() => saveIntegration('prowlarr')} primary />
              <ActionButton loading={saving['prowlarr-test']} icon={PlugZap} label="Test saved" onClick={() => testIntegration('prowlarr')} />
              <ActionButton loading={false} icon={ShieldCheck} label="Trusted indexers" onClick={() => setTrustedIndexerDialogOpen(true)} />
            </>
          )}
        />

        <IntegrationCard
          id="settings-ai-control"
          icon={Bot}
          title="AI Control Experimental"
          accent="violet"
          status={statuses['ai-control']}
          fields={(
            <>
              <label className="settings-checkbox-field">
                <input
                  type="checkbox"
                  checked={forms.aiControl.enabled !== false}
                  onChange={(event) => updateField('aiControl', 'enabled', event.target.checked)}
                />
                <span>
                  <strong>Enable AI Control</strong>
                  <small>Shows the experimental command workspace in the sidebar.</small>
                </span>
              </label>
              <div className="settings-two-column">
                <label className="dialog-field">
                  <span>Max matched movies</span>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={forms.aiControl.max_matched_movies || 25}
                    onChange={(event) => updateField('aiControl', 'max_matched_movies', event.target.value)}
                  />
                </label>
                <label className="dialog-field">
                  <span>Max download searches</span>
                  <input
                    type="number"
                    min="1"
                    max="50"
                    value={forms.aiControl.max_download_searches || 10}
                    onChange={(event) => updateField('aiControl', 'max_download_searches', event.target.value)}
                  />
                </label>
              </div>
              <p className="settings-runtime-detail">Download quality is fixed to 1080p and delete uses Recycle Bin in v1.</p>
              <label className="settings-checkbox-field">
                <input
                  type="checkbox"
                  checked={Boolean(forms.aiControl.ollama_curated_lists)}
                  onChange={(event) => updateField('aiControl', 'ollama_curated_lists', event.target.checked)}
                />
                <span>
                  <strong>Allow Ollama-curated lists</strong>
                  <small>Creative AI lists are not guaranteed factual. TMDB still confirms saved movie identities.</small>
                </span>
              </label>
              <p className="trusted-indexer-summary">
                <span>AI Control download trust</span>
                <strong>{aiControlIndexerSummary()}</strong>
                <small>YTS/YIFY default when no AI Control-specific selection is saved.</small>
              </p>
            </>
          )}
          actions={(
            <>
              <ActionButton loading={saving['ai-control-save']} icon={Save} label="Save AI Control" onClick={() => saveAiControl()} primary />
              <ActionButton loading={false} icon={ShieldCheck} label="Trusted indexers" onClick={() => setAiControlIndexerDialogOpen(true)} />
            </>
          )}
        />

        <IntegrationCard
          id="settings-qbittorrent"
          icon={Download}
          title="qBittorrent"
          accent="gold"
          status={statuses.qbittorrent}
          fields={(
            <>
              <label className="dialog-field">
                <span>Torrent handling</span>
                <select value={forms.qbittorrent.mode || 'embedded'} onChange={(event) => updateField('qbittorrent', 'mode', event.target.value)}>
                  <option value="embedded">Embedded qBittorrent</option>
                  <option value="system">System default client</option>
                </select>
              </label>
              <label className="dialog-field">
                <span>Movie download folder</span>
                <input
                  value={forms.qbittorrent.download_dir || ''}
                  onChange={(event) => updateField('qbittorrent', 'download_dir', event.target.value)}
                  placeholder="Uses the primary movie folder when empty"
                />
                <small>Resolved: {forms.qbittorrent.effective_download_dir || forms.library.directory || 'Not configured'}</small>
              </label>
              <label className="dialog-field">
                <span>Incomplete downloads folder</span>
                <input
                  value={forms.qbittorrent.incomplete_dir || ''}
                  onChange={(event) => updateField('qbittorrent', 'incomplete_dir', event.target.value)}
                  placeholder="Uses app data/qbittorrent/incomplete when empty"
                />
                <small>Resolved: {forms.qbittorrent.effective_incomplete_dir || 'Saved after configuration'}</small>
              </label>
              {forms.qbittorrent.download_dir_in_library === false ? (
                <p className="settings-path-warning"><AlertTriangle size={14} /> Completed movies outside library roots are not discovered automatically.</p>
              ) : null}
              {forms.qbittorrent.incomplete_dir_in_library ? (
                <p className="settings-path-warning"><AlertTriangle size={14} /> Incomplete downloads cannot be stored inside a movie library.</p>
              ) : null}
              <p className="settings-runtime-detail">
                {forms.qbittorrent.installed
                  ? `Bundled qBittorrent ${forms.qbittorrent.version || 'runtime'} · ${forms.qbittorrent.running ? 'Running' : 'Stopped'}`
                  : forms.qbittorrent.supported === false
                    ? 'Bundled qBittorrent is unavailable in this build.'
                    : 'Bundled qBittorrent runtime will be used when included in the portable release.'}
              </p>
            </>
          )}
          actions={(
            <>
              <ActionButton loading={saving['qbittorrent-save']} icon={Save} label="Save qBittorrent" onClick={saveQbittorrent} primary />
              {forms.qbittorrent.installed ? (
                <ActionButton loading={false} icon={ExternalLink} label="Open Downloads" onClick={() => window.location.assign('/downloads')} />
              ) : null}
            </>
          )}
        />

        <IntegrationCard
          id="settings-tmdb"
          icon={Clapperboard}
          title="TMDB"
          accent="green"
          status={statuses.tmdb}
          fields={(
            <>
              <SecretField
                label="TMDB API key"
                value={forms.tmdb.key || ''}
                revealed={revealed.tmdb}
                onReveal={() => setRevealed((state) => ({ ...state, tmdb: !state.tmdb }))}
                onChange={(value) => updateField('tmdb', 'key', value)}
              />
              <label className="settings-checkbox-field">
                <input
                  type="checkbox"
                  checked={Boolean(forms.tmdb.includeAdult)}
                  onChange={(event) => updateField('tmdb', 'includeAdult', event.target.checked)}
                />
                <span>
                  <strong>Include adult titles in metadata search</strong>
                  <small>Used for matching and Unmatched Metadata search, not normal Discover browsing.</small>
                </span>
              </label>
            </>
          )}
          actions={(
            <>
              <ActionButton loading={saving['tmdb-save']} icon={Save} label="Save TMDB" onClick={() => saveIntegration('tmdb')} primary />
              <ActionButton loading={saving['tmdb-test']} icon={PlugZap} label="Test key" onClick={() => testIntegration('tmdb')} />
            </>
          )}
        />

        <IntegrationCard
          id="settings-streaming"
          icon={MonitorPlay}
          title="Streaming Link"
          accent="green"
          status={statuses.streaming}
          fields={(
            <>
              <label className="settings-checkbox-field">
                <input
                  type="checkbox"
                  checked={forms.streaming.enabled !== false}
                  onChange={(event) => updateField('streaming', 'enabled', event.target.checked)}
                />
                <span>
                  <strong>Enable Stream buttons</strong>
                  <small>When disabled, Stream is hidden from movie cards and details.</small>
                </span>
              </label>
              <label className="dialog-field">
                <span>Button label</span>
                <input value={forms.streaming.label || ''} onChange={(event) => updateField('streaming', 'label', event.target.value)} placeholder="Stream" />
              </label>
              <label className="dialog-field">
                <span>URL template</span>
                <input value={forms.streaming.url_template || ''} onChange={(event) => updateField('streaming', 'url_template', event.target.value)} placeholder="https://streamimdb.ru/embed/movie/{tmdb_id}" />
                <small>Use {'{tmdb_id}'} or {'{imdb_id}'} where the provider expects the movie ID. Example: https://streamimdb.ru/embed/movie/{'{tmdb_id}'}.</small>
                <small>If you use {'{imdb_id}'}, CP resolves it from TMDB first.</small>
              </label>
            </>
          )}
          actions={(
            <ActionButton loading={saving['streaming-save']} icon={Save} label="Save Streaming" onClick={() => saveIntegration('streaming')} primary />
          )}
        />

        <IntegrationCard
          id="settings-ollama"
          icon={Bot}
          title="Ollama"
          accent="violet"
          status={statuses.ollama}
          fields={(
            <>
              <label className="dialog-field">
                <span>Ollama URL</span>
                <input value={forms.ollama.url || ''} onChange={(event) => updateField('ollama', 'url', event.target.value)} placeholder="http://localhost:11434" />
              </label>
              <label className="dialog-field">
                <span>Model</span>
                <input value={forms.ollama.model || ''} onChange={(event) => updateField('ollama', 'model', event.target.value)} placeholder="llama3" />
              </label>
              <label className="dialog-field">
                <span>AI candidate limit</span>
                <input
                  type="number"
                  min="1"
                  max="50"
                  step="1"
                  value={forms.ollama.candidateLimit || 15}
                  onChange={(event) => updateField('ollama', 'candidateLimit', event.target.value)}
                />
                <small>CP asks Ollama for this many candidates, then validates them with TMDB. Final results may be fewer after duplicates, TV entries, or unresolved titles are removed. Allowed range: 1-50.</small>
              </label>
            </>
          )}
          actions={(
            <>
              <ActionButton loading={saving['ollama-save']} icon={Save} label="Save Ollama" onClick={() => saveIntegration('ollama')} primary />
              <ActionButton loading={saving['ollama-test']} icon={PlugZap} label="Test URL" onClick={() => testIntegration('ollama')} />
            </>
          )}
        />
      </div>
      {trustedIndexerDialogOpen ? (
        <TrustedIndexerDialog
          prowlarr={forms.prowlarr}
          saving={Boolean(saving['prowlarr-save'])}
          onToggle={updateTrustedReleaseIndexer}
          onSave={() => saveIntegration('prowlarr')}
          onClose={() => setTrustedIndexerDialogOpen(false)}
        />
      ) : null}
      {aiControlIndexerDialogOpen ? (
        <AIControlIndexerDialog
          aiControl={forms.aiControl}
          saving={Boolean(saving['ai-control-save'])}
          onToggle={updateAiControlTrustedIndexer}
          onSave={() => saveAiControl({ includeTrusted: true })}
          onClose={() => setAiControlIndexerDialogOpen(false)}
        />
      ) : null}
    </section>
  );
}

function TrustedIndexerDialog({ prowlarr, saving, onToggle, onSave, onClose }) {
  const indexers = prowlarr.indexers || [];
  const trustedIds = prowlarr.trusted_release_indexers || [];

  async function saveAndClose() {
    const saved = await onSave();
    if (saved) onClose();
  }

  return (
    <div className="modal-backdrop trusted-indexer-backdrop" role="presentation" onClick={onClose}>
      <section className="small-dialog trusted-indexer-dialog" role="dialog" aria-modal="true" aria-label="Trusted release watchlist indexers" onClick={(event) => event.stopPropagation()}>
        <header className="dialog-header">
          <div>
            <p className="screen-kicker">Prowlarr</p>
            <h2>Trusted release watchlist indexers</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close trusted indexers">
            <X size={20} />
          </button>
        </header>
        <p className="trusted-indexer-detail">Only selected indexers can mark followed movies as Available. Normal Discover and torrent search still use Prowlarr normally.</p>
        <div className="settings-checkbox-group trusted-indexer-list">
          {indexers.length ? (
            indexers.map((indexer) => (
              <label className="settings-checkbox-field" key={indexer.id}>
                <input
                  type="checkbox"
                  checked={trustedIds.includes(String(indexer.id))}
                  onChange={(event) => onToggle(String(indexer.id), event.target.checked)}
                />
                <span>
                  <strong>{indexer.name || `Indexer ${indexer.id}`}</strong>
                  <small>{/yts|yify/i.test(indexer.name || '') ? 'Default trusted release source.' : 'Manual trust for followed-release availability.'}</small>
                </span>
              </label>
            ))
          ) : (
            <p className="settings-empty-note">Save and test Prowlarr to load enabled indexers. No trusted indexers selected.</p>
          )}
          {indexers.length && !trustedIds.length ? (
            <p className="settings-empty-note">No trusted indexers selected. Followed releases will stay Watching.</p>
          ) : null}
        </div>
        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-primary" onClick={saveAndClose} disabled={saving}>
            {saving ? <Loader2 size={15} className="spin" /> : <Save size={15} />} Save trusted indexers
          </button>
        </div>
      </section>
    </div>
  );
}

function AIControlIndexerDialog({ aiControl, saving, onToggle, onSave, onClose }) {
  const indexers = aiControl.indexers || [];
  const trustedIds = aiControl.trusted_indexers || [];

  async function saveAndClose() {
    const saved = await onSave();
    if (saved) onClose();
  }

  return (
    <div className="modal-backdrop trusted-indexer-backdrop" role="presentation" onClick={onClose}>
      <section className="small-dialog trusted-indexer-dialog" role="dialog" aria-modal="true" aria-label="AI Control trusted indexers" onClick={(event) => event.stopPropagation()}>
        <header className="dialog-header">
          <div>
            <p className="screen-kicker">AI Control download trust</p>
            <h2>AI Control trusted indexers</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close AI Control trusted indexers">
            <X size={20} />
          </button>
        </header>
        <p className="trusted-indexer-detail">Only selected indexers are used when AI Control plans downloads. YTS/YIFY is the default when no AI-specific selection is saved.</p>
        <div className="settings-checkbox-group trusted-indexer-list">
          {indexers.length ? (
            indexers.map((indexer) => (
              <label className="settings-checkbox-field" key={`ai-control-indexer-${indexer.id}`}>
                <input
                  type="checkbox"
                  checked={trustedIds.includes(String(indexer.id))}
                  onChange={(event) => onToggle(String(indexer.id), event.target.checked)}
                />
                <span>
                  <strong>{indexer.name || `Indexer ${indexer.id}`}</strong>
                  <small>{/yts|yify/i.test(indexer.name || '') ? 'Default AI Control download source.' : 'Manual trust for AI Control download planning.'}</small>
                </span>
              </label>
            ))
          ) : (
            <p className="settings-empty-note">Save and test Prowlarr to load enabled indexers. YTS/YIFY is used by default when available.</p>
          )}
          {indexers.length && !trustedIds.length && aiControl.trusted_indexers_configured ? (
            <p className="settings-empty-note">No AI Control trusted indexers selected. Download commands will be blocked.</p>
          ) : null}
        </div>
        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-primary" onClick={saveAndClose} disabled={saving}>
            {saving ? <Loader2 size={15} className="spin" /> : <Save size={15} />} Save AI Control indexers
          </button>
        </div>
      </section>
    </div>
  );
}

function serviceLabel(service) {
  return {
    plex: 'Plex',
    prowlarr: 'Prowlarr',
    tmdb: 'TMDB',
    streaming: 'Streaming',
    ollama: 'Ollama'
  }[service] || service;
}

function SettingsPanelHeader({ icon: Icon, title, label, text }) {
  return (
    <header className="settings-panel-header">
      <span className="settings-panel-icon"><Icon size={18} /></span>
      <div>
        <span>{label}</span>
        <h3>{title}</h3>
        <p>{text}</p>
      </div>
    </header>
  );
}

function SettingsInlineStatus({ status }) {
  if (!status) return null;
  const Icon = status.tone === 'error' ? AlertTriangle : CheckCircle2;
  return (
    <p className={cx('settings-inline-status', `settings-inline-${status.tone || 'neutral'}`)}>
      <Icon size={15} />
      <span>{status.message}</span>
      {status.detail && <small>{status.detail}</small>}
    </p>
  );
}

function IntegrationCard({ id, icon, title, accent, status, fields, actions }) {
  return (
    <section id={id} className={cx('settings-panel', 'integration-card', `integration-${accent}`)}>
      <SettingsPanelHeader icon={icon} title={title} label="Integration" text={integrationText(title)} />
      <div className="settings-field-stack">
        {fields}
      </div>
      <SettingsInlineStatus status={status} />
      <div className="settings-action-grid">
        {actions}
      </div>
    </section>
  );
}

function integrationText(title) {
  return {
    Plex: 'Read-only Plex cache and Plex server scan controls.',
    Prowlarr: 'Source search for upgrades and torrent lookup.',
    qBittorrent: 'Portable downloads powered by the original qBittorrent WebUI.',
    TMDB: 'Posters, plots, cast, discovery lists, and trailers.',
    'Streaming Link': 'Configurable embedded movie stream URL template.',
    Ollama: 'Local AI recommendations through your own model.'
  }[title] || '';
}

function SecretField({ label, value, revealed, onReveal, onChange }) {
  return (
    <label className="dialog-field secret-field">
      <span>{label}</span>
      <span className="secret-input-wrap">
        <input type={revealed ? 'text' : 'password'} value={value} onChange={(event) => onChange(event.target.value)} autoComplete="off" />
        <button type="button" className="secret-toggle" onClick={onReveal} aria-label={revealed ? `Hide ${label}` : `Reveal ${label}`}>
          {revealed ? <EyeOff size={15} /> : <Eye size={15} />}
        </button>
      </span>
    </label>
  );
}

function ActionButton({ loading, icon: Icon, label, onClick, primary }) {
  return (
    <button type="button" className={cx('btn', primary ? 'btn-primary' : 'btn-secondary')} onClick={onClick} disabled={loading}>
      {loading ? <Loader2 size={15} className="spin" /> : <Icon size={15} />} {label}
    </button>
  );
}

const paletteSwatches = [
  { label: 'BASE / BACKGROUND', value: '#0A0A0B' },
  { label: 'SURFACE / ELEVATED', value: '#121316' },
  { label: 'SURFACE / RAISED', value: '#1A1C20' },
  { label: 'BORDER / DIVIDER', value: '#26282D' },
  { label: 'TEXT / PRIMARY', value: '#E6E6E6', light: true },
  { label: 'TEXT / MUTED', value: '#A3A6AD' },
  { label: 'TEXT / DISABLED', value: '#6D7178' }
];

const functionalSwatches = [
  { label: 'OWNED / SUCCESS', value: '#22C55E' },
  { label: 'WARNING / QUALITY', value: '#F59E0B' },
  { label: 'AI / ASSISTANT', value: '#8B5CF6' },
  { label: 'LIBRARY / INFO', value: '#3B82F6' },
  { label: 'PLEX / CONNECTED', value: '#06B6D4' },
  { label: 'DANGER / DELETE', value: '#EF4444' }
];

const typographyRows = [
  { name: 'H1', sample: 'Cinema Paradiso.', spec: '32/40', weight: 'SemiBold' },
  { name: 'H2', sample: 'Panel Headline', spec: '20/28', weight: 'SemiBold' },
  { name: 'Body', sample: 'This is body text. Clean, readable and calm.', spec: '15/24', weight: 'Regular' },
  { name: 'Small', sample: 'Metadata and supporting information', spec: '12/16', weight: 'Medium' },
  { name: 'Caption', sample: 'Secondary text and hints', spec: '11/14', weight: 'Regular' }
];

const featureNotes = [
  { icon: Database, title: 'LOCAL FIRST', text: 'Your library, under your control' },
  { icon: Wand2, title: 'SMART TOOLS', text: 'Clean, fix and organize with precision' },
  { icon: Compass, title: 'DISCOVER MORE', text: 'Find, follow and get the best releases' },
  { icon: LinkIcon, title: 'SEAMLESS INTEGRATIONS', text: 'Plex, *arr stack, TMDB, Ollama & more' }
];

function StyleGuide() {
  return (
    <div className="styleguide-page">
      <section className="sg-hero">
        <img className="sg-hero-art" src={headerCropUrl} alt="" aria-hidden="true" />
        <div className="sg-brand-area">
          <img src={logoUrl} alt="" className="sg-logo-mark" />
          <div>
            <div className="sg-wordmark">
              <span>Cinema</span>
              <span>Paradiso</span>
            </div>
            <p className="sg-tagline">Movie Archive Command Console</p>
          </div>
          <p className="sg-hero-copy">Your movies. Your archive. Your way.</p>
        </div>

        <div className="sg-feature-grid">
          {featureNotes.map((item) => {
            const Icon = item.icon;
            return (
              <article className="sg-feature-note" key={item.title}>
                <Icon size={36} />
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <main className="sg-board">
        <section className="sg-panel sg-palette">
          <BoardTitle>Color Palette</BoardTitle>
          <div className="sg-swatch-grid">
            {paletteSwatches.map((swatch) => (
              <ColorSwatch key={swatch.label} {...swatch} />
            ))}
          </div>
          <div className="sg-accent-block">
            <span>ACCENT / FOCUS (GOLD)</span>
            <strong>#D4AF37</strong>
            <div />
          </div>
          <BoardTitle small>Functional Colors</BoardTitle>
          <div className="sg-functional-grid">
            {functionalSwatches.map((swatch) => (
              <ColorSwatch key={swatch.label} {...swatch} compact />
            ))}
          </div>
        </section>

        <section className="sg-panel sg-typography">
          <BoardTitle>Typography</BoardTitle>
          <div className="sg-type-hero">
            <strong>Aa</strong>
            <div>
              <span>Inter</span>
              <p>System Sans</p>
            </div>
          </div>
          <div className="sg-type-table">
            {typographyRows.map((row) => (
              <div className="sg-type-row" key={row.name}>
                <span>{row.name}</span>
                <strong>{row.sample}</strong>
                <small>{row.spec}</small>
                <small>{row.weight}</small>
              </div>
            ))}
          </div>
        </section>

        <section className="sg-panel sg-motif">
          <BoardTitle>Signature Motif</BoardTitle>
          <div className="sg-motif-art">
            <img src={motifCropUrl} alt="" />
          </div>
          <p>The projector light line. Precision. Focus. Direction.</p>
          <p>Guiding you through your archive.</p>
        </section>

        <section className="sg-panel sg-components">
          <BoardTitle>UI Components</BoardTitle>
          <ComponentSamples />
        </section>

        <section className="sg-panel sg-surfaces">
          <BoardTitle>Surfaces & Panels</BoardTitle>
          <SurfaceSample />
        </section>

        <section className="sg-panel sg-movie">
          <BoardTitle>Movie Card (Compact)</BoardTitle>
          <MovieCardSample />
        </section>

        <section className="sg-panel sg-footer-strip">
          <div className="sg-icon-sample">
            <div className="sg-footer-copy">
              <BoardTitle>Icon Style</BoardTitle>
              <span>Lucide Outline</span>
            </div>
            <div className="sg-footer-icons">
              {[Home, Folder, Clapperboard, Download, Search, Settings, Bot].map((Icon, index) => (
                <Icon key={index} size={26} />
              ))}
            </div>
          </div>
          <div className="sg-radius-sample">
            <div className="sg-footer-copy">
              <BoardTitle>Radius</BoardTitle>
              <span>8px</span>
            </div>
            <div />
          </div>
          <div className="sg-elevation-sample">
            <BoardTitle>Elevation</BoardTitle>
            {[0, 1, 2, 3].map((level) => (
              <div key={level} className={`sg-elevation-box sg-elevation-${level}`}>
                <span>{level}</span>
              </div>
            ))}
          </div>
          <div className="sg-focus-sample">
            <BoardTitle>Focus</BoardTitle>
            <div />
          </div>
          <div className="sg-loading-sample">
            <BoardTitle>Loading</BoardTitle>
            <span />
            <span />
            <span />
          </div>
        </section>
      </main>
    </div>
  );
}

function BoardTitle({ children, small }) {
  return <h2 className={cx('sg-board-title', small && 'sg-board-title-small')}>{children}</h2>;
}

function ColorSwatch({ label, value, light, compact }) {
  return (
    <div className={cx('sg-color-token', compact && 'sg-color-token-compact')}>
      <div
        className={cx(light && 'sg-light-swatch')}
        style={{ background: value }}
      />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ComponentSamples() {
  return (
    <div className="sg-component-stack">
      <div className="sg-button-row">
        <button className="sg-btn sg-btn-primary" type="button"><Play size={18} fill="currentColor" />Primary</button>
        <button className="sg-btn sg-btn-secondary" type="button"><Search size={18} />Secondary</button>
        <button className="sg-btn sg-btn-ghost" type="button"><MoreVertical size={18} />Ghost</button>
      </div>
      <div className="sg-button-row sg-button-row-small">
        <button type="button"><Sparkles size={15} />Action</button>
        <button type="button"><Clapperboard size={15} />Movie</button>
        <button type="button"><MonitorPlay size={15} />TV Show</button>
        <button type="button"><Folder size={15} />Collection</button>
      </div>
      <div className="sg-chip-row">
        <span className="sg-chip sg-owned">Owned</span>
        <span className="sg-chip sg-quality">Low Quality</span>
        <span className="sg-chip sg-info">Upgrade Available</span>
        <span className="sg-chip sg-ai">AI Pick</span>
        <span className="sg-chip sg-plex">Plex Match</span>
      </div>
      <div className="sg-toolbar">
        {[Play, Folder, Download, Search, CirclePlus, Settings, CheckCircle2, Trash2].map((Icon, index) => (
          <button key={index} className={index === 7 ? 'sg-danger-icon' : ''} type="button"><Icon size={21} /></button>
        ))}
      </div>
      <div className="sg-slider-card">
        <div>
          <span>Quality</span>
          <strong>1080p WEB-DL</strong>
        </div>
        <div className="sg-slider">
          <span />
        </div>
        <span className="sg-slider-label">1080p</span>
        <span className="sg-good-pill">Good</span>
      </div>
    </div>
  );
}

function SurfaceSample() {
  return (
    <div className="sg-surface-demo">
      <aside className="sg-sidebar-sample">
        {[
          { icon: Home, label: 'Home', active: true },
          { icon: Library, label: 'Library' },
          { icon: Clapperboard, label: 'Cleanup' },
          { icon: Compass, label: 'Discover' },
          { icon: Settings, label: 'Settings' }
        ].map((item) => {
          const Icon = item.icon;
          return (
            <div className={cx('sg-sidebar-item', item.active && 'sg-sidebar-item-active')} key={item.label}>
              <Icon size={18} />
              <span>{item.label}</span>
            </div>
          );
        })}
      </aside>
      <div className="sg-health-sample">
        <header>
          <h3>Library Health</h3>
          <button type="button">View All <ChevronRight size={16} /></button>
        </header>
        <div className="sg-metric-grid">
          {[
            ['Duplicates', '128', CheckCircle2],
            ['Low Quality', '42', Settings],
            ['Unmatched', '17', MonitorPlay],
            ['Plex Sync', 'OK', CirclePlus]
          ].map(([label, value, Icon]) => (
            <div className="sg-metric" key={label}>
              <Icon size={21} />
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
        <h4>Followed Releases</h4>
        <div className="sg-release-card">
          <div className="sg-dune-poster">Dune</div>
          <div>
            <strong>Dune: Part Two</strong>
            <span>New Quality Found</span>
            <p>2160p WEB-DL</p>
            <p>Today&nbsp;&nbsp;&bull;&nbsp;&nbsp;2.6 GB</p>
          </div>
          <button type="button"><ChevronRight size={18} /></button>
        </div>
      </div>
    </div>
  );
}

function MovieCardSample() {
  return (
    <article className="sg-movie-card">
      <InterstellarPoster />
      <div className="sg-movie-body">
        <span className="sg-status-owned">Owned</span>
        <h3>Interstellar</h3>
        <p className="sg-year">2014</p>
        <div className="sg-movie-meta">
          <span><Star size={17} fill="currentColor" />8.6</span>
          <span>&bull;</span>
          <span>Adventure, Drama, Sci-Fi</span>
          <span>&bull;</span>
          <span>169m</span>
        </div>
        <div className="sg-movie-chips">
          <span>1080p WEB-DL</span>
          <span>ENG</span>
          <span>USA / UK</span>
        </div>
        <div className="sg-movie-actions">
          <button className="sg-play-action" type="button"><Play size={19} fill="currentColor" />Play</button>
          <button type="button"><Download size={19} />Upgrade</button>
          <button type="button"><Info size={19} />Details</button>
          <button type="button" aria-label="More"><MoreVertical size={19} /></button>
        </div>
      </div>
    </article>
  );
}

function InterstellarPoster() {
  return (
    <div className="sg-interstellar-poster" aria-label="Interstellar poster sample">
      <div className="sg-poster-snow" />
      <div className="sg-astronaut">
        <span className="sg-helmet" />
        <span className="sg-torso" />
        <span className="sg-arm sg-arm-left" />
        <span className="sg-arm sg-arm-right" />
        <span className="sg-leg sg-leg-left" />
        <span className="sg-leg sg-leg-right" />
      </div>
      <strong>Interstellar</strong>
    </div>
  );
}

export default App;
