import {
  AlertTriangle,
  Bell,
  Bot,
  CheckCircle2,
  Clapperboard,
  CirclePlus,
  Compass,
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
  Play,
  PlugZap,
  Radio,
  RefreshCcw,
  Save,
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
import { useCallback, useEffect, useMemo, useState } from 'react';
import headerCropUrl from './assets/header.png';
import logoUrl from './assets/logo.svg';
import motifCropUrl from './assets/styleguide-motif-crop.png';
import {
  buildOwnershipMap,
  discoverMoviePayload,
  filterEnrichedIndexerResults,
  listsForDiscoverMovie,
  ownedMovieFor,
  sortTorrentVariants
} from './discoverUtils.js';

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
    id: 'settings',
    label: 'Settings',
    icon: Settings,
    accent: 'cyan'
  }
];

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

function cx(...classes) {
  return classes.filter(Boolean).join(' ');
}

function formatCount(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '0';
  return Number(value).toLocaleString();
}

function movieKey(movie) {
  return `${String(movie.title || '').toLowerCase()}|${String(movie.year || '')}`;
}

function sortFollowedReleases(items) {
  const rank = { available: 0, watching: 1, owned: 2 };
  return [...(items || [])].sort((a, b) => (
    (rank[a.status] ?? 3) - (rank[b.status] ?? 3)
    || Number(b.updated_at || b.followed_at || 0) - Number(a.updated_at || a.followed_at || 0)
  ));
}

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

function splitLibraryTitle(title) {
  const raw = String(title || '');
  const match = raw.match(/\s+\((\d{4})\)$/);
  return {
    title: match ? raw.slice(0, match.index) : raw,
    year: match ? match[1] : ''
  };
}

function resolutionRank(resolution) {
  const value = String(resolution || '').toLowerCase();
  if (value.includes('2160') || value.includes('4k')) return 4;
  if (value.includes('1080')) return 3;
  if (value.includes('720')) return 2;
  if (value.includes('480')) return 1;
  return 0;
}

function isLowQuality(resolution) {
  return resolutionRank(resolution) < 3;
}

function matchesLibraryResolutionFilter(resolution, filter) {
  const rank = resolutionRank(resolution);
  if (filter === 'all') return true;
  if (filter === '4k') return rank === 4;
  if (filter === '1080p') return rank === 3;
  if (filter === '720p') return rank === 2;
  if (filter === 'below-720p') return rank < 2;
  return true;
}

function getMovieIdentity(item) {
  const canonical = item?.canonical_metadata || {};
  if (canonical.accepted && canonical.title) {
    return {
      title: canonical.title,
      year: String(canonical.year || '').trim()
    };
  }
  const parsed = splitLibraryTitle(item?.title);
  const plexTitle = String(item?.plex_title || '').trim();
  const title = plexTitle || parsed.title || String(item?.filename || '').replace(/\.[^.]+$/, '');
  const year = String(item?.plex_year || parsed.year || '').trim();
  return { title, year };
}

function getTmdbCacheKey(item) {
  const identity = getMovieIdentity(item);
  const canonical = item?.canonical_metadata || {};
  return canonical?.tmdb_id ? `tmdb:${canonical.tmdb_id}` : item?.tmdb_id ? `tmdb:${item.tmdb_id}` : `${identity.title}|${identity.year}`;
}

function normalizePersonName(name) {
  return String(name || '').trim().toLowerCase();
}

function normalizeCollectionTitle(title) {
  return String(title || '')
    .toLowerCase()
    .replace(/[³ł]/g, ' 3 ')
    .replace(/[²]/g, ' 2 ')
    .replace(/\b(directors?|special|extended|theatrical|ultimate|final|anniversary|edition|cut|dc)\b/g, ' ')
    .replace(/[^\w\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function peopleMatch(person, filter) {
  if (!person || !filter) return false;
  const personId = String(person.id || '');
  const filterId = String(filter.id || '');
  if (personId && filterId) return personId === filterId;
  return normalizePersonName(person.name) === normalizePersonName(filter.name);
}

function mergePeople(primary, fallback) {
  if (!primary.length) return fallback;
  if (!fallback.length) return primary;
  const merged = primary.map((person) => {
    const richMatch = fallback.find((candidate) => normalizePersonName(candidate.name) === normalizePersonName(person.name));
    if (!richMatch) return person;
    return {
      ...richMatch,
      ...person,
      id: person.id || richMatch.id,
      profile_url: person.profile_url || richMatch.profile_url,
      character: person.character || richMatch.character
    };
  });
  const existing = new Set(merged.map((person) => normalizePersonName(person.name)));
  fallback.forEach((person) => {
    const key = normalizePersonName(person.name);
    if (key && !existing.has(key)) {
      merged.push(person);
      existing.add(key);
    }
  });
  return merged;
}

function getRolePeople(item, details, role) {
  const canonical = item?.canonical_metadata || {};
  if (role === 'director') {
    const plexDirectors = canonical.directors?.length ? canonical.directors : item?.plex_directors || [];
    const tmdbDirectors = details?.directors?.length ? details.directors : details?.director?.name ? [details.director] : [];
    return mergePeople(plexDirectors, tmdbDirectors);
  }
  const plexCast = canonical.cast?.length ? canonical.cast : item?.plex_cast || [];
  return mergePeople(plexCast, details?.cast || []);
}

function itemMatchesRoleFilter(item, details, filter) {
  if (!filter) return true;
  return getRolePeople(item, details, filter.role).some((person) => peopleMatch(person, filter));
}

function itemMatchesCollectionFilter(item, details, filter) {
  if (!filter) return true;
  if (details?.collection?.id && String(details.collection.id) === String(filter.id)) return true;
  const identity = getMovieIdentity(item);
  const itemTitle = normalizeCollectionTitle(identity.title);
  const itemYear = String(identity.year || '');
  return (filter.parts || []).some((part) => {
    if (item?.tmdb_id && part.tmdb_id && String(item.tmdb_id) === String(part.tmdb_id)) return true;
    const partTitle = normalizeCollectionTitle(part.title);
    const partYear = String(part.year || '');
    return itemTitle === partTitle && (!partYear || !itemYear || partYear === itemYear);
  });
}

function moviePayload(item) {
  const identity = getMovieIdentity(item);
  const canonical = item?.canonical_metadata || {};
  return {
    tmdb_id: String(canonical.tmdb_id || item?.tmdb_id || ''),
    imdb_id: String(canonical.imdb_id || item?.imdb_id || ''),
    title: identity.title || item?.title || '',
    year: identity.year || String(item?.year || '').trim(),
    path: item?.path || '',
    poster_url: canonical.poster_url || item?.plex_poster || item?.poster_url || ''
  };
}

function movieIdentityKey(movie) {
  if (movie?.tmdb_id) return `tmdb:${movie.tmdb_id}`;
  if (movie?.path) return `path:${String(movie.path).toLowerCase()}`;
  return `title:${normalizeCollectionTitle(movie?.title)}|${String(movie?.year || '')}`;
}

function listsForItem(item, lists) {
  const key = movieIdentityKey(moviePayload(item));
  return (lists || []).filter((list) => (
    (list.movies || []).some((movie) => movieIdentityKey(movie) === key)
  ));
}

function getLocaleTag(item) {
  const canonical = item?.canonical_metadata || {};
  const countryMap = {
    'United States of America': 'US',
    'United States': 'US',
    'United Kingdom': 'UK',
    'Republic of Korea': 'KR',
    'South Korea': 'KR',
    France: 'FR',
    Germany: 'DE',
    Italy: 'IT',
    Spain: 'ES',
    Japan: 'JP',
    China: 'CN',
    Canada: 'CA',
    Australia: 'AU',
    Netherlands: 'NL',
    India: 'IN',
    Egypt: 'EG'
  };
  const languageMap = {
    English: 'EN',
    Korean: 'KO',
    French: 'FR',
    German: 'DE',
    Italian: 'IT',
    Spanish: 'ES',
    Japanese: 'JA',
    Chinese: 'ZH',
    Hindi: 'HI',
    Arabic: 'AR',
    Dutch: 'NL'
  };
  const rawCountry = String(canonical.country_flag || canonical.country || item?.plex_country_flag || item?.plex_country || '').trim();
  const rawLanguage = String(canonical.language || item?.plex_language || '').trim();
  const country = countryMap[rawCountry] || (rawCountry.length <= 3 ? rawCountry.toUpperCase() : rawCountry.slice(0, 2).toUpperCase());
  const language = languageMap[rawLanguage] || (rawLanguage.length <= 3 ? rawLanguage.toUpperCase() : rawLanguage.slice(0, 2).toUpperCase());
  if (country && language) return `${country} / ${language}`;
  return country || language || '';
}

function getQualityLabel(item) {
  return [item?.resolution, item?.rip_source].filter((part) => part && part !== 'Unknown').join(' ') || 'Unknown quality';
}

function rootLabel(path) {
  const value = String(path || '').replace(/[\\/]+$/, '');
  const parts = value.split(/[\\/]+/).filter(Boolean);
  return parts.length ? `Root: ${parts[parts.length - 1]}` : 'Library root';
}

function getUniqueOptions(items, getter) {
  return [...new Set(items.flatMap((item) => {
    const value = getter(item);
    if (Array.isArray(value)) return value.filter(Boolean);
    return value ? [value] : [];
  }))].sort((a, b) => String(a).localeCompare(String(b)));
}

function torrentSizeBytes(item) {
  return Number(item?.size_bytes || item?.size || 0);
}

function sectionFromPath(pathname) {
  const section = String(pathname || '').replace(/^\/+/, '').split('/')[0];
  return navItems.some((item) => item.id === section) ? section : 'home';
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok || data.error) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

function App() {
  if (typeof window !== 'undefined' && window.location.pathname === '/styleguide') {
    return <StyleGuide />;
  }

  return <ArchiveApp />;
}

function ArchiveApp() {
  const [activeSection, setActiveSection] = useState(() => (
    typeof window === 'undefined' ? 'home' : sectionFromPath(window.location.pathname)
  ));
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
  const [libraryQuery, setLibraryQuery] = useState('');
  const [discoverQuery, setDiscoverQuery] = useState('');
  const [browseQuery, setBrowseQuery] = useState('');
  const [discoverActiveTab, setDiscoverActiveTab] = useState('explore');
  const [discoverSearchRequest, setDiscoverSearchRequest] = useState(0);
  const [cleanupInitialTab, setCleanupInitialTab] = useState('duplicates');

  const notify = useCallback((message, tone = 'success') => {
    setToast({ message, tone });
    window.clearTimeout(window.__cpToastTimer);
    window.__cpToastTimer = window.setTimeout(() => setToast(null), 3200);
  }, []);

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

  const selectedOwnership = selectedMovie ? ownedMovieFor(selectedMovie, ownership) : null;
  const selectedDetails = selectedMovie?.tmdb_id ? details[selectedMovie.tmdb_id] : null;

  useEffect(() => {
    function handlePopState() {
      setActiveSection(sectionFromPath(window.location.pathname));
    }
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  function selectSection(id) {
    setActiveSection(id);
    if (typeof window === 'undefined') return;
    const path = id === 'home' ? '/' : `/${id}`;
    if (window.location.pathname !== path) {
      window.history.pushState({}, '', path);
    }
  }

  function reviewUnmatchedMetadata() {
    setCleanupInitialTab('unmatched');
    selectSection('cleanup');
  }

  async function toggleFollow(movie) {
    const key = movieKey(movie);
    const existing = followed.find((item) => movieKey(item) === key);
    const payload = { title: movie.title, year: movie.year, tmdb_id: movie.tmdb_id, poster_url: movie.poster_url };
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
    if (!movie.tmdb_id) return;
    try {
      const data = await fetchJson(`/api/tmdb/imdb_id?tmdb_id=${encodeURIComponent(movie.tmdb_id)}`);
      if (data.imdb_id) window.open(`https://www.playimdb.com/title/${data.imdb_id}`, '_blank', 'noopener,noreferrer');
      else notify('No IMDB stream id found for this movie', 'error');
    } catch (error) {
      notify(`Stream lookup failed: ${error.message}`, 'error');
    }
  }

  async function findTorrent(movie, upgrade = false) {
    const title = movie?.title || '';
    const year = movie?.year || '';
    if (!title) return;
    setTorrentModal({ title, year, upgrade, loading: true, error: '', variants: [] });
    try {
      const params = new URLSearchParams({ title });
      if (year) params.set('year', year);
      const data = await fetchJson(`/api/explore/search?${params.toString()}`);
      setTorrentModal({ title, year, upgrade, loading: false, error: '', variants: data.variants || [] });
    } catch (error) {
      setTorrentModal({ title, year, upgrade, loading: false, error: error.message, variants: [] });
    }
  }

  async function searchTorrents(query) {
    const q = String(query || '').trim();
    if (!q) return;
    setTorrentModal({ title: q, year: '', upgrade: false, loading: true, error: '', variants: [] });
    try {
      const data = await fetchJson(`/api/prowlarr/search?q=${encodeURIComponent(q)}`);
      setTorrentModal({ title: q, year: '', upgrade: false, loading: false, error: '', variants: data.results || [] });
    } catch (error) {
      setTorrentModal({ title: q, year: '', upgrade: false, loading: false, error: error.message, variants: [] });
    }
  }

  return (
    <div className="app-shell">
      <Sidebar
        activeSection={activeSection}
        onSelect={selectSection}
      />
      <main className="workspace">
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
        {activeSection === 'home' ? (
          <HomeWorkspace
            stats={stats}
            loading={loading}
            movies={movies}
            ownership={ownership}
            followed={followed}
            followedChecking={followedChecking}
            selectedMovie={selectedMovie}
            selectedOwnership={selectedOwnership}
            selectedDetails={selectedDetails}
            onSelectSection={selectSection}
            onSelectMovie={setSelectedMovie}
            onPlay={playLocal}
            onStream={streamMovie}
            onFindTorrent={findTorrent}
            onFollow={toggleFollow}
          />
        ) : activeSection === 'library' ? (
          <LibraryWorkspace
            onPlay={playLocal}
            onFindTorrent={findTorrent}
            notify={notify}
            query={libraryQuery}
            setQuery={setLibraryQuery}
            onReviewUnmatched={reviewUnmatchedMetadata}
          />
        ) : activeSection === 'discover' ? (
          <DiscoverWorkspace
            followed={followed}
            notify={notify}
            onPlay={playLocal}
            onStream={streamMovie}
            onFindTorrent={findTorrent}
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
        ) : (
          <MigrationWorkspace section={activeSection} notify={notify} onFindTorrent={findTorrent} cleanupInitialTab={cleanupInitialTab} />
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
          onClose={() => setTorrentModal(null)}
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
                <span className="nav-label">{item.label}</span>
              </button>
            </div>
          );
        })}
      </nav>
      <div className="sidebar-footer">
        <span className="status-dot" />
        <span>Local-first archive</span>
      </div>
    </aside>
  );
}

function TorrentModal({ state, onClose }) {
  const initialQuery = `${state.title || ''} ${state.year || ''}`.trim();
  const [manualQuery, setManualQuery] = useState(initialQuery);
  const [titleFilter, setTitleFilter] = useState('');
  const [resolutionFilter, setResolutionFilter] = useState('all');
  const [indexerFilter, setIndexerFilter] = useState('all');
  const [sortMode, setSortMode] = useState('size-desc');
  const [variants, setVariants] = useState(state.variants || []);
  const [loading, setLoading] = useState(state.loading);
  const [error, setError] = useState(state.error || '');

  useEffect(() => {
    setManualQuery(`${state.title || ''} ${state.year || ''}`.trim());
    setVariants(state.variants || []);
    setLoading(state.loading);
    setError(state.error || '');
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

  async function runManualSearch(event) {
    event.preventDefault();
    const q = manualQuery.trim();
    if (!q) return;
    setLoading(true);
    setError('');
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

        {loading ? (
          <div className="dialog-loading">
            <Loader2 size={20} className="spin" />
            <span>Searching Prowlarr indexers...</span>
          </div>
        ) : error ? (
          <div className="dialog-error">{error}</div>
        ) : filteredVariants.length ? (
          <div className="torrent-result-list">
            {filteredVariants.map((variant, index) => {
              const actionUrl = variant.magnet_url || variant.download_url || variant.info_url;
              const actionLabel = variant.magnet_url ? 'Magnet' : variant.download_url ? '.torrent' : 'Page';
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
                  {actionUrl ? (
                    <a className="btn btn-secondary" href={actionUrl} target="_blank" rel="noreferrer">
                      {variant.magnet_url ? <ExternalLink size={15} /> : <Download size={15} />}
                      {actionLabel}
                    </a>
                  ) : (
                    <span className="torrent-no-link">No link</span>
                  )}
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
  const isBrowseSearch = isDiscover && discoverActiveTab === 'browse';
  const isExploreSearch = isDiscover && discoverActiveTab === 'explore';
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
        <h1>
          {section?.label || 'Home'}
          {isLibrary && <span className="offline-badge">Offline</span>}
        </h1>
      </div>
      <form
        className="command-search"
        onSubmit={(event) => {
          event.preventDefault();
          if (isExploreSearch || isBrowseSearch) onDiscoverSearch();
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
          readOnly={!isLibrary && !isExploreSearch && !isBrowseSearch}
        />
        <kbd>{isExploreSearch || isBrowseSearch ? 'Enter' : 'Ctrl K'}</kbd>
      </form>
      <div className="topbar-stat">
        <Database size={16} />
        <span>{formatCount(stats?.total_files)} files</span>
      </div>
    </header>
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
    onSelectMovie,
    onPlay,
    onStream,
    onFindTorrent,
    onFollow
  } = props;
  const [releaseDrawerOpen, setReleaseDrawerOpen] = useState(false);

  return (
    <div className="home-grid">
      <section className="hero-panel">
        <img className="home-hero-art" src={headerCropUrl} alt="" aria-hidden="true" />
        <div className="hero-copy">
          <p className="screen-kicker">Cinematic archive console</p>
          <h2>Your movie archive, under command.</h2>
          <p>
            Cinema Paradiso brings local files, Plex metadata, cleanup tools, torrent sources, TMDB discovery,
            live streaming, and AI recommendations into one private console built for collectors who manage real libraries.
          </p>
        </div>
      </section>

      <HealthPanel stats={stats} loading={loading.stats} />
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
                  details={movieKey(movie) === movieKey(selectedMovie || {}) ? selectedDetails : null}
                  onSelect={() => onSelectMovie(movie)}
                  onPlay={onPlay}
                  onStream={onStream}
                  onFindTorrent={onFindTorrent}
                  onFollow={onFollow}
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
        onClose={() => onSelectMovie(null)}
        onPlay={onPlay}
        onStream={onStream}
        onFindTorrent={onFindTorrent}
        onFollow={onFollow}
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

function HealthPanel({ stats, loading }) {
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
      tone: 'amber'
    },
    {
      label: 'Duplicates',
      value: stats?.dup_groups,
      detail: `${formatCount(stats?.extra_copies)} extra copies`,
      icon: Trash2,
      tone: 'red'
    },
    {
      label: 'Plex matched',
      value: stats?.plex_matched,
      detail: `${formatCount(stats?.plex_unmatched)} need attention`,
      icon: LinkIcon,
      tone: 'cyan'
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
          return (
            <article key={card.label} className={cx('health-card', `tone-${card.tone}`)}>
              <Icon size={18} />
              <strong>{loading ? '...' : formatCount(card.value)}</strong>
              <span>{card.label}</span>
              <small>{card.detail}</small>
            </article>
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
  const { movie, owned, selected, followed, details, onSelect, onPlay, onStream, onFindTorrent, onFollow } = props;
  const lowQuality = owned && isLowQuality(owned.resolution);
  const genres = (movie.genres || []).slice(0, 3);

  return (
    <article className={cx('movie-card', selected && 'movie-card-selected')} onClick={onSelect}>
      <Poster movie={movie} />
      <div className="movie-card-body">
        <div className="movie-title-row">
          <div>
            <h4>{movie.title}</h4>
            <span>{movie.year || 'Unknown year'}</span>
          </div>
          <Rating value={movie.tmdb_rating} votes={movie.tmdb_vote_count} />
        </div>
        <div className="chip-row">
          {genres.map((genre) => <span className="chip" key={genre}>{genre}</span>)}
          {movie.language && <span className="chip chip-muted">{movie.language}</span>}
          {(movie.country_flag || movie.country) && <span className="chip chip-muted">{movie.country_flag || movie.country}</span>}
        </div>
        <div className="ownership-row">
          {owned ? (
            <span
              className={cx('status-badge', lowQuality ? 'status-warning' : 'status-owned')}
              data-label={`Owned - ${owned.resolution || 'Unknown'} - ${owned.size_human || 'local file'}`}
            >
              <CheckCircle2 size={14} />
              Owned - {owned.resolution || 'Unknown'} - {owned.size_human || 'local file'}
            </span>
          ) : (
            <span className="status-badge status-missing">
              <Radio size={14} />
              Not in library
            </span>
          )}
          <button type="button" className="expand-button" onClick={(event) => { event.stopPropagation(); onSelect(); }}>
            Details
          </button>
        </div>
        <p className="movie-card-plot">{movie.plot || 'No plot summary is available yet.'}</p>
        {selected && details?.trailer_url && (
          <a
            className="inline-trailer"
            href={details.trailer_url}
            target="_blank"
            rel="noreferrer"
            onClick={(event) => event.stopPropagation()}
          >
            <Film size={14} /> Play trailer
          </a>
        )}
        <div className="card-actions" onClick={(event) => event.stopPropagation()}>
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
              <button type="button" className="btn btn-primary" onClick={() => onFindTorrent(movie)}>
                <Search size={15} /> Find torrent
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => onStream(movie)}>
                <MonitorPlay size={15} /> Stream
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => onFollow(movie)}>
                <Bell size={15} /> {followed ? 'Following' : 'Follow'}
              </button>
            </>
          )}
        </div>
      </div>
    </article>
  );
}

function MovieInspector({ movie, owned, details, followed, onClose, onPlay, onStream, onFindTorrent, onFollow }) {
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
  const cast = details?.cast || [];
  const trailerUrl = details?.trailer_url || '';

  return (
    <aside className="inspector">
      <button className="inspector-close" type="button" onClick={onClose} aria-label="Close movie details">
        <X size={17} />
      </button>
      <div className="inspector-hero">
        <Poster movie={movie} large />
        <div>
          <p className="screen-kicker">Selected movie</p>
          <h3>{movie.title}</h3>
          <div className="inspector-meta">
            <span>{movie.year || 'Unknown year'}</span>
            <Rating value={movie.tmdb_rating} votes={movie.tmdb_vote_count} />
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
            <button type="button" className="btn btn-primary" onClick={() => onFindTorrent(movie)}>
              <Search size={15} /> Find torrent
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => onFollow(movie)}>
              <Bell size={15} /> {followed ? 'Following' : 'Follow release'}
            </button>
          </>
        )}
        <button type="button" className="btn btn-secondary" onClick={() => onStream(movie)}>
          <MonitorPlay size={15} /> Stream
        </button>
        {trailerUrl && (
          <a className="btn btn-secondary" href={trailerUrl} target="_blank" rel="noreferrer">
            <Film size={15} /> Play trailer
          </a>
        )}
      </div>
    </aside>
  );
}

function Poster({ movie, large }) {
  return (
    <div className={cx('poster', large && 'poster-large')}>
      {movie.poster_url ? (
        <img src={movie.poster_url} alt={`${movie.title} poster`} loading="lazy" />
      ) : (
        <Film size={large ? 42 : 28} />
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
  onFindTorrent,
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
    setDiscoverLoading(true);
    setDiscoverError('');
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
      const nextResults = data.results || [];
      setDiscoverResults((state) => (append ? [...state, ...nextResults] : nextResults));
      setDiscoverPage(data.page || nextPage);
      setDiscoverTotalPages(data.total_pages || 1);
      setDiscoverTotalResults(data.total_results || nextResults.length);
      setDiscoverMode(query ? 'search' : 'discover');
      if (!append) {
        setDiscoverContext(null);
        setDiscoverHistory([]);
      }
      checkOwnership(nextResults);
    } catch (error) {
      setDiscoverError(error.message);
      if (!append) setDiscoverResults([]);
    } finally {
      setDiscoverLoading(false);
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
    const fallbackUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(`${movie.title || ''} ${movie.year || ''} trailer`)}`;
    if (!movie?.tmdb_id) {
      window.open(fallbackUrl, '_blank', 'noopener,noreferrer');
      return;
    }
    try {
      let details = detailsCache[movie.tmdb_id];
      if (!details) {
        details = await fetchJson(`/api/tmdb/details?tmdb_id=${encodeURIComponent(movie.tmdb_id)}`);
        setDetailsCache((state) => ({ ...state, [movie.tmdb_id]: details }));
      }
      window.open(details.trailer_url || fallbackUrl, '_blank', 'noopener,noreferrer');
    } catch {
      window.open(fallbackUrl, '_blank', 'noopener,noreferrer');
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
    notify('Movie added to list');
  }

  async function removeDiscoverMovieFromList(listId, movie) {
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie })
    });
    await loadUserLists();
    notify('Movie removed from list');
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

          <DiscoverResultGrid
            error={discoverError}
            loading={discoverLoading && !discoverResults.length}
            emptyText={discoverContext?.emptyText || 'No TMDB movies match this view.'}
          >
            {discoverResults.map((movie) => {
              const owned = ownedMovieFor(movie, ownership);
              return (
                <DiscoverMovieCard
                  key={`${movie.tmdb_id || movie.title}-${movie.year}`}
                  movie={movie}
                  owned={owned}
                  followed={followed.some((item) => movieKey(item) === movieKey(movie))}
                  expanded={expandedMovieKey === movieKey(movie)}
                  details={movie.tmdb_id ? detailsCache[String(movie.tmdb_id)] : null}
                  collection={movie.tmdb_id && detailsCache[String(movie.tmdb_id)]?.collection?.id ? collectionCache[detailsCache[String(movie.tmdb_id)].collection.id] || detailsCache[String(movie.tmdb_id)].collection : {}}
                  itemLists={listsForDiscoverMovie(movie, userLists, owned)}
                  onPlay={onPlay}
                  onStream={onStream}
                  onFindTorrent={onFindTorrent}
                  onFollow={onFollow}
                  onTrailer={openTrailer}
                  onToggleDetails={() => toggleMovieDetails(movie)}
                  onPersonBrowse={(role, person) => browsePerson('explore', movie, role, person)}
                  onCollectionBrowse={(collectionItem) => browseCollection('explore', movie, collectionItem)}
                  onListBrowse={(list) => browseList('explore', movie, list)}
                  onEditLists={() => setListEditorTarget(discoverMoviePayload(movie, owned))}
                  onRemoveFromList={(listId) => removeDiscoverMovieFromList(listId, discoverMoviePayload(movie, owned))}
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
                    onVariantSelect={(index) => setSelectedVariants((state) => ({ ...state, [movie.parsed_title]: index }))}
                    onPlay={onPlay}
                    onStream={onStream}
                    onFindTorrent={onFindTorrent}
                    onTrailer={openTrailer}
                    onToggleDetails={() => toggleMovieDetails(movie)}
                    onEditLists={() => setListEditorTarget(discoverMoviePayload(movie, owned))}
                    onRemoveFromList={(listId) => removeDiscoverMovieFromList(listId, discoverMoviePayload(movie, owned))}
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
                  onPlay={onPlay}
                  onStream={onStream}
                  onFindTorrent={onFindTorrent}
                  onFollow={onFollow}
                  onTrailer={openTrailer}
                  onToggleDetails={() => toggleMovieDetails(movie)}
                  onPersonBrowse={(role, person) => browsePerson('pick', movie, role, person)}
                  onCollectionBrowse={(collectionItem) => browseCollection('pick', movie, collectionItem)}
                  onListBrowse={(list) => browseList('pick', movie, list)}
                  onEditLists={() => setListEditorTarget(discoverMoviePayload(movie, owned))}
                  onRemoveFromList={(listId) => removeDiscoverMovieFromList(listId, discoverMoviePayload(movie, owned))}
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
          item={listEditorTarget}
          items={[]}
          lists={userLists}
          onClose={() => setListEditorTarget(null)}
          onCreate={createDiscoverList}
          onAdd={addDiscoverMovieToList}
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
  onFindTorrent,
  onFollow,
  onTrailer,
  onToggleDetails,
  onPersonBrowse,
  onCollectionBrowse,
  onListBrowse,
  onEditLists,
  onRemoveFromList
}) {
  const lowQuality = owned && isLowQuality(owned.resolution);
  return (
    <article className={cx('movie-card discover-movie-card', expanded && 'discover-card-expanded')}>
      <Poster movie={movie} />
      <div className="movie-card-body">
        <div className="movie-title-row">
          <div>
            <h4>{movie.title}</h4>
            <span>{movie.year || 'Unknown year'}</span>
          </div>
          <Rating value={movie.tmdb_rating} votes={movie.tmdb_vote_count} />
        </div>
        <MovieFactChips movie={movie} owned={owned} lowQuality={lowQuality} />
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
              <button type="button" className="btn btn-primary" onClick={() => onFindTorrent(movie)}>
                <Search size={15} /> Find sources
              </button>
              <button type="button" className="btn btn-secondary btn-green-outline" onClick={() => onStream(movie)}>
                <MonitorPlay size={15} /> Stream
              </button>
            </>
          )}
          <button type="button" className="btn btn-secondary" onClick={() => onTrailer(movie)}>
            <Film size={15} /> Trailer
          </button>
          <button type="button" className="btn btn-secondary" onClick={onToggleDetails}>
            <Info size={15} /> {expanded ? 'Less' : 'Details'}
          </button>
          {!owned && (
            <button type="button" className="btn btn-secondary" onClick={() => onFollow(movie)}>
              <Bell size={15} /> {followed ? 'Following' : 'Follow'}
            </button>
          )}
        </div>
        {expanded && (
          <DiscoverExpandedDetails
            movie={movie}
            details={details}
            collection={collection}
            itemLists={itemLists}
            onPersonBrowse={onPersonBrowse}
            onCollectionBrowse={onCollectionBrowse}
            onListBrowse={onListBrowse}
            onEditLists={onEditLists}
            onRemoveFromList={onRemoveFromList}
          />
        )}
      </div>
    </article>
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
  onVariantSelect,
  onPlay,
  onStream,
  onFindTorrent,
  onTrailer,
  onToggleDetails,
  onEditLists,
  onRemoveFromList
}) {
  const lowQuality = owned && isLowQuality(owned.resolution);
  const variants = sortTorrentVariants(movie.variants || []);
  const selected = variants[selectedIndex] || variants[0] || {};
  const actionUrl = selected.magnet_url || selected.download_url || selected.info_url;
  const actionLabel = selected.magnet_url ? 'Magnet' : selected.download_url ? '.torrent' : 'Source page';

  return (
    <article className="indexer-card">
      <div className="indexer-poster-wrap">
        <Poster movie={movie} />
        <span className="indexer-resolution-badge">{selected.resolution || movie.best_resolution || 'Unknown'}</span>
      </div>
      <div className="indexer-card-body">
        <div className="movie-title-row">
          <div>
            <h4>{movie.title}</h4>
            <span>{movie.year || 'Unknown year'}</span>
          </div>
          <Rating value={movie.tmdb_rating} votes={movie.tmdb_vote_count} />
        </div>
        <MovieFactChips movie={movie} owned={owned} lowQuality={lowQuality} />

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
        {expanded && (
          <DiscoverExpandedDetails
            movie={movie}
            details={details}
            collection={collection}
            itemLists={itemLists}
            onEditLists={onEditLists}
            onRemoveFromList={onRemoveFromList}
          />
        )}
      </div>
      <div className="indexer-action-rail">
        <div className="indexer-selected-meta">
          <strong>{formatCount(selected.seeders)} seeders</strong>
          <span>{selected.indexer || 'Unknown tracker'}</span>
          <small>{selected.size_human || '?'}</small>
        </div>
        {actionUrl ? (
          <a className="btn btn-primary" href={actionUrl} target="_blank" rel="noreferrer">
            {selected.magnet_url ? <ExternalLink size={15} /> : <Download size={15} />} {actionLabel}
          </a>
        ) : (
          <span className="torrent-no-link">No link</span>
        )}
        {owned ? (
          <button type="button" className="btn btn-primary btn-green" onClick={() => onPlay(owned.path)}>
            <Play size={15} /> Play
          </button>
        ) : (
          <button type="button" className="btn btn-secondary btn-green-outline" onClick={() => onStream(movie)}>
            <MonitorPlay size={15} /> Stream
          </button>
        )}
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
        <button type="button" className="btn btn-secondary" onClick={onToggleDetails}>
          <Info size={15} /> {expanded ? 'Less' : 'Details'}
        </button>
      </div>
    </article>
  );
}

function DiscoverExpandedDetails({
  movie,
  details,
  collection,
  itemLists = [],
  onPersonBrowse,
  onCollectionBrowse,
  onListBrowse,
  onEditLists,
  onRemoveFromList
}) {
  const loading = details?.loading;
  const directors = details?.directors?.length ? details.directors : details?.director?.name ? [details.director] : [];
  const cast = (details?.cast || []).slice(0, 6);
  const activeCollection = collection?.id ? collection : details?.collection || {};
  const canBrowsePeople = Boolean(onPersonBrowse);
  const canBrowseCollection = Boolean(onCollectionBrowse);
  const canBrowseLists = Boolean(onListBrowse);

  return (
    <div className="discover-expanded-details">
      {loading ? (
        <div className="people-loading"><Loader2 size={15} className="spin" /> Loading TMDB details...</div>
      ) : details?.error ? (
        <p className="discover-detail-error"><AlertTriangle size={15} /> {details.error}</p>
      ) : (
        <>
          {(details?.tagline || details?.runtime) && (
            <div className="movie-expanded-meta discover-expanded-meta">
              {details?.tagline && <div><span>Tagline</span><strong>{details.tagline}</strong></div>}
              {details?.runtime && <div><span>Runtime</span><strong>{details.runtime} min</strong></div>}
            </div>
          )}
          <div className="people-panel discover-people-panel">
            <div className="director-panel">
              <span className="mini-label">Director</span>
              {directors.length ? (
                directors.slice(0, 2).map((person) => (
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
              {cast.length ? (
                <div className="person-grid">
                  {cast.map((person) => (
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
                      <small>{formatCount((activeCollection.parts || []).length)} movies, {activeCollection.source || 'TMDB'} collection</small>
                    </span>
                  </button>
                ) : (
                  <div className="collection-main-action discover-collection-static">
                    <Clapperboard size={17} />
                    <span>
                      <strong>{activeCollection.name}</strong>
                      <small>{formatCount((activeCollection.parts || []).length)} movies, {activeCollection.source || 'TMDB'} collection</small>
                    </span>
                  </div>
                )}
              </div>
            )}
            <div className="lists-panel">
              <div className="lists-panel-header">
                <span className="mini-label">Lists</span>
                <button type="button" className="mini-action" onClick={onEditLists}>Add to list</button>
              </div>
              {itemLists.length ? (
                <div className="list-chip-row">
                  {itemLists.map((list) => (
                    <span className="list-chip" key={list.id}>
                      <button type="button" onClick={canBrowseLists ? () => onListBrowse(list) : undefined}>{list.name}</button>
                      <button type="button" aria-label={`Remove ${movie.title} from ${list.name}`} onClick={() => onRemoveFromList(list.id)}>
                        <Trash2 size={13} />
                      </button>
                    </span>
                  ))}
                </div>
              ) : (
                <small>Not in any user list yet.</small>
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

function LibraryWorkspace({ onPlay, onFindTorrent, notify, query, setQuery, onReviewUnmatched }) {
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
  const [showAdultMovies, setShowAdultMovies] = useState(true);

  const loadLibrary = useCallback(async (forcePlex = false) => {
    setLoading(true);
    setError('');
    setStatus(forcePlex ? 'Syncing Plex and scanning library...' : 'Scanning library...');
    try {
      const data = await fetchJson(`/api/library${forcePlex ? '?force_plex=1' : ''}`);
      setItems(data.items || []);
      setCurrentPage(1);
      setStatus(data.cached ? 'Loaded from cache' : '');
      notify(`${formatCount(data.count)} library files loaded`, 'success');
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

  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const result = items.filter((item) => {
      const canonical = item.canonical_metadata || {};
      if (mode === 'movie' && !canonical.accepted) return false;
      if (mode === 'movie' && !showAdultMovies && canonical.adult) return false;
      const identity = getMovieIdentity(item);
      const rating = Number(canonical.rating || item.plex_rating || 0);
      const year = Number(identity.year || 0);
      if (normalizedQuery) {
        const haystack = [
          identity.title,
          identity.year,
          item.filename,
          item.path,
          canonical.summary || canonical.plot || item.plex_summary,
          (canonical.genres?.length ? canonical.genres : item.plex_genres || []).join(' ')
        ].filter(Boolean).join(' ').toLowerCase();
        if (!haystack.includes(normalizedQuery)) return false;
      }
      if (qualityFilter === 'upgrade' && !isLowQuality(item.resolution)) return false;
      if (qualityFilter === 'good' && resolutionRank(item.resolution) < 3) return false;
      if (qualityFilter === '4k' && resolutionRank(item.resolution) !== 4) return false;
      if (!matchesLibraryResolutionFilter(item.resolution, resolutionFilter)) return false;
      if (sourceFilter !== 'all' && item.rip_source !== sourceFilter) return false;
      if (genreFilter !== 'all' && !(canonical.genres?.length ? canonical.genres : item.plex_genres || []).includes(genreFilter)) return false;
      if (languageFilter !== 'all' && (canonical.language || item.plex_language) !== languageFilter) return false;
      if (countryFilter !== 'all' && (canonical.country_flag || canonical.country || item.plex_country_flag || item.plex_country) !== countryFilter) return false;
      if (mode === 'file' && plexFilter === 'matched' && !item.plex_matched) return false;
      if (mode === 'file' && plexFilter === 'unmatched' && item.plex_matched) return false;
      if (mode === 'movie' && minRating !== 'all' && rating < Number(minRating)) return false;
      if (mode === 'movie' && yearFrom && (!year || year < Number(yearFrom))) return false;
      if (mode === 'movie' && yearTo && (!year || year > Number(yearTo))) return false;
      if (mode === 'file' && sizeFilter === 'small' && Number(item.size || 0) > 1.5 * 1024 * 1024 * 1024) return false;
      if (mode === 'file' && sizeFilter === 'large' && Number(item.size || 0) < 6 * 1024 * 1024 * 1024) return false;
      const details = tmdbCache[getTmdbCacheKey(item)];
      if (mode === 'movie' && roleFilter && !itemMatchesRoleFilter(item, details, roleFilter)) return false;
      if (mode === 'movie' && collectionFilter && !itemMatchesCollectionFilter(item, details, collectionFilter)) return false;
      if (mode === 'movie' && listFilter && !listsForItem(item, [listFilter]).length) return false;
      return true;
    });

    const sorted = [...result];
    sorted.sort((a, b) => {
      const aIdentity = getMovieIdentity(a);
      const bIdentity = getMovieIdentity(b);
      if (sortMode === 'rating') return Number(b.plex_rating || 0) - Number(a.plex_rating || 0) || aIdentity.title.localeCompare(bIdentity.title);
      if (sortMode === 'added') return Number(b.added_time || b.modified_time || 0) - Number(a.added_time || a.modified_time || 0) || aIdentity.title.localeCompare(bIdentity.title);
      if (sortMode === 'year-desc') return Number(bIdentity.year || 0) - Number(aIdentity.year || 0) || aIdentity.title.localeCompare(bIdentity.title);
      if (sortMode === 'year-asc') return Number(aIdentity.year || 0) - Number(bIdentity.year || 0) || aIdentity.title.localeCompare(bIdentity.title);
      if (sortMode === 'quality') return resolutionRank(b.resolution) - resolutionRank(a.resolution) || aIdentity.title.localeCompare(bIdentity.title);
      if (sortMode === 'size') return Number(b.size || 0) - Number(a.size || 0) || a.filename.localeCompare(b.filename);
      if (sortMode === 'plex') return Number(Boolean(b.plex_matched)) - Number(Boolean(a.plex_matched)) || a.filename.localeCompare(b.filename);
      if (sortMode === 'source') return String(a.rip_source || '').localeCompare(String(b.rip_source || '')) || a.filename.localeCompare(b.filename);
      if (sortMode === 'filename') return a.filename.localeCompare(b.filename);
      return aIdentity.title.localeCompare(bIdentity.title);
    });
    return sorted;
  }, [items, query, qualityFilter, plexFilter, sortMode, genreFilter, resolutionFilter, sourceFilter, languageFilter, countryFilter, yearFrom, yearTo, minRating, sizeFilter, mode, roleFilter, collectionFilter, listFilter, tmdbCache, userLists, showAdultMovies]);

  const totalPages = Math.max(1, Math.ceil(filteredItems.length / pageSize));
  const safePage = Math.min(currentPage, totalPages);
  const pageStart = filteredItems.length ? (safePage - 1) * pageSize : 0;
  const pageEnd = Math.min(pageStart + pageSize, filteredItems.length);
  const visibleItems = filteredItems.slice(pageStart, pageEnd);
  const stats = useMemo(() => ({
    total: items.length,
    low: items.filter((item) => isLowQuality(item.resolution)).length,
    matched: items.filter((item) => item.canonical_metadata?.accepted).length,
    pending: items.filter((item) => item.metadata_status === 'pending').length,
    unmatched: items.filter((item) => !item.canonical_metadata?.accepted && item.metadata_status !== 'pending').length
  }), [items]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
      setExpandedPath('');
    }
  }, [currentPage, totalPages]);

  function resetLibraryPage() {
    setCurrentPage(1);
    setExpandedPath('');
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
          fetchJson(`/api/tmdb/collection?collection_id=${encodeURIComponent(details.collection.id)}`)
            .then((collectionData) => setCollectionCache((cache) => ({ ...cache, [details.collection.id]: collectionData })))
            .catch(() => {});
        }
      } catch (detailsError) {
        details = { cast: [], trailer_url: '', error: detailsError.message };
        setTmdbCache((cache) => ({ ...cache, [cacheKey]: details }));
      }
    }
    if (openTrailer) {
      if (details.trailer_url) window.open(details.trailer_url, '_blank', 'noopener,noreferrer');
      else window.open(`https://www.youtube.com/results?search_query=${encodeURIComponent(`${identity.title} ${identity.year} trailer`)}`, '_blank', 'noopener,noreferrer');
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
      const data = await fetchJson(`/api/tmdb/collection?collection_id=${encodeURIComponent(collection.id)}`);
      setCollectionCache((cache) => ({ ...cache, [data.id || collection.id]: data }));
      setCollectionFilter({
        id: data.id || collection.id,
        name: data.name || collection.name,
        parts: data.parts || [],
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
    const data = await fetchJson('/api/user/collection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        collection_id: collection.id,
        original: collection,
        parts
      })
    });
    setCollectionCache((cache) => ({ ...cache, [collection.id]: data }));
    setCollectionEditor(null);
    notify(`Collection saved as user edited`);
  }

  async function resetCollection(collection) {
    await fetchJson(`/api/user/collection/${encodeURIComponent(collection.id)}/reset`, { method: 'POST' });
    const data = await fetchJson(`/api/tmdb/collection?collection_id=${encodeURIComponent(collection.id)}&refresh=1`);
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
    notify('Movie added to list');
  }

  async function renameList(listId, name) {
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    await loadUserLists();
    notify('List renamed');
  }

  async function deleteList(listId) {
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}`, { method: 'DELETE' });
    if (listFilter?.id === listId) setListFilter(null);
    await loadUserLists();
    notify('List deleted');
  }

  async function removeMovieFromList(listId, item) {
    await fetchJson(`/api/user/lists/${encodeURIComponent(listId)}/movies`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ movie: moviePayload(item) })
    });
    await loadUserLists();
    notify('Movie removed from list');
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
            <button type="button" className="btn btn-secondary" onClick={() => loadLibrary(false)} disabled={loading}>
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
        </div>
      </div>

      <div className="library-stat-strip">
        <LibraryStat icon={HardDrive} label="Files" value={formatCount(stats.total)} tone="blue" />
        <LibraryStat icon={AlertTriangle} label="Upgrade candidates" value={formatCount(stats.low)} tone="amber" />
        <LibraryStat icon={LinkIcon} label="Metadata matched" value={formatCount(stats.matched)} tone="cyan" />
        {stats.pending > 0 && <LibraryStat icon={Loader2} label="Metadata pending" value={formatCount(stats.pending)} tone="amber" />}
        <LibraryStat icon={Radio} label="Unmatched metadata" value={formatCount(stats.unmatched)} tone="violet" onClick={stats.unmatched > 0 ? onReviewUnmatched : undefined} />
      </div>

      <div className="library-toolbar library-filter-toolbar">
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
              <X size={14} />
            </button>
          )}
          {listFilter && (
            <button type="button" className="metadata-filter-chip" onClick={clearMetadataFilters}>
              List: {listFilter.name}
              <X size={14} />
            </button>
          )}
        </div>
      )}

      {!loading && !error && (
        <>
          <div className="library-results-meta">
            <span>{formatCount(filteredItems.length)} matching {mode === 'movie' ? 'movies' : 'files'}</span>
            {filteredItems.length > 0 && <span>Showing {formatCount(pageStart + 1)}-{formatCount(pageEnd)} of {formatCount(filteredItems.length)}</span>}
          </div>
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
          items={items}
          lists={userLists}
          onClose={() => setListEditor(null)}
          onCreate={createList}
          onAdd={addMovieToList}
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
  onRemoveFromList
}) {
  const identity = getMovieIdentity(item);
  const canonical = item.canonical_metadata || {};
  const lowQuality = isLowQuality(item.resolution);
  const genres = (canonical.genres?.length ? canonical.genres : item.plex_genres || []).slice(0, expanded ? 10 : 3);
  const directors = getRolePeople(item, details, 'director');
  const director = directors[0];
  const cast = getRolePeople(item, details, 'actor').slice(0, 6);
  const activeCollection = collection?.id ? collection : details?.collection || {};
  const locale = getLocaleTag(item);
  const movieForSearch = { title: identity.title, year: identity.year };

  return (
    <article className={cx('library-movie-card', expanded && 'library-movie-card-expanded')}>
      <div className="library-poster movie-view-poster">
        {(canonical.poster_url || item.plex_poster) ? <img src={canonical.poster_url || item.plex_poster} alt={`${identity.title} poster`} loading="lazy" /> : <Film size={28} />}
      </div>
      <div className="library-item-body">
        <div className="library-item-title-row">
          <div>
            <h3>{identity.title}</h3>
            <span>{identity.year || 'Unknown year'}</span>
          </div>
          {(canonical.rating || item.plex_rating) && <Rating value={canonical.rating || item.plex_rating} votes={canonical.tmdb_vote_count} />}
        </div>
        <div className="chip-row">
          {genres.map((genre) => <span className="chip" key={genre}>{genre}</span>)}
          {locale && <span className="chip chip-muted">{locale}</span>}
          <span className={cx('chip', lowQuality && 'chip-warning')}>{getQualityLabel(item)}</span>
        </div>
        <p className={cx('library-summary movie-summary', expanded && 'movie-summary-expanded')}>
          {canonical.summary || canonical.plot || item.plex_summary || 'No plot summary is available yet.'}
        </p>
        {expanded && (
          <>
            <div className="movie-expanded-meta">
              <div><span>Country</span><strong>{canonical.country || canonical.country_flag || item.plex_country || item.plex_country_flag || 'Unknown'}</strong></div>
              <div><span>Language</span><strong>{canonical.language || item.plex_language || 'Unknown'}</strong></div>
              <div><span>Resolution</span><strong>{item.resolution || 'Unknown'}</strong></div>
              <div><span>Source</span><strong>{item.rip_source || 'Unknown'}</strong></div>
            </div>
            <div className="people-panel">
              <div className="director-panel">
                <span className="mini-label">Director</span>
                {details?.loading ? (
                  <div className="people-loading"><Loader2 size={15} className="spin" /> Loading director...</div>
                ) : director?.name ? (
                  <button type="button" className="director-person" onClick={() => onPersonFilter('director', director)}>
                    <PersonAvatar person={director} />
                    <span>
                      <strong>{director.name}</strong>
                      <small>Show directed movies</small>
                    </span>
                  </button>
                ) : (
                  <small>No director data found.</small>
                )}
              </div>
              <div className="cast-panel">
                <span className="mini-label">Top cast</span>
                {details?.loading ? (
                  <div className="people-loading"><Loader2 size={15} className="spin" /> Loading cast...</div>
                ) : cast.length ? (
                  <div className="person-grid">
                    {cast.map((person) => (
                      <button type="button" className="person-card" key={`${person.id || person.name}-${person.character || ''}`} onClick={() => onPersonFilter('actor', person)}>
                        <PersonAvatar person={person} />
                        <strong>{person.name}</strong>
                        <small>{person.character || 'Cast'}</small>
                      </button>
                    ))}
                  </div>
                ) : (
                  <small>No cast data found.</small>
                )}
              </div>
              {activeCollection?.id && (
                <div className="collection-panel">
                  <button type="button" className="collection-main-action" onClick={() => onCollectionFilter(activeCollection)}>
                    <Clapperboard size={17} />
                    <span>
                      <strong>{activeCollection.name}</strong>
                      <small>Collection made by {activeCollection.source || 'TMDB'}</small>
                    </span>
                  </button>
                  <div className="collection-actions">
                    <button type="button" className="mini-action" onClick={() => onEditCollection(activeCollection)}>Edit</button>
                    {activeCollection.is_edited && (
                      <button type="button" className="mini-action mini-action-danger" onClick={() => onResetCollection(activeCollection)}>
                        <RefreshCcw size={13} /> Reset
                      </button>
                    )}
                  </div>
                </div>
              )}
              <div className="lists-panel">
                <div className="lists-panel-header">
                  <span className="mini-label">Lists</span>
                  <button type="button" className="mini-action" onClick={onEditLists}>Add to list</button>
                </div>
                {itemLists.length ? (
                  <div className="list-chip-row">
                    {itemLists.map((list) => (
                      <span className="list-chip" key={list.id}>
                        <button type="button" onClick={() => onListFilter(list)}>{list.name}</button>
                        <button type="button" aria-label={`Remove from ${list.name}`} onClick={() => onRemoveFromList(list.id)}>
                          <Trash2 size={13} />
                        </button>
                      </span>
                    ))}
                  </div>
                ) : (
                  <small>No user lists yet.</small>
                )}
              </div>
            </div>
          </>
        )}
        <div className="library-card-actions">
          <button type="button" className="btn btn-primary btn-green" onClick={() => onPlay(item.path)}>
            <Play size={15} /> Play
          </button>
          <button type="button" className="btn btn-secondary" onClick={onTrailer}>
            <Film size={15} /> Trailer
          </button>
          <button type="button" className="btn btn-secondary" onClick={onToggle}>
            <Info size={15} /> {expanded ? 'Less' : 'Details'}
          </button>
          {lowQuality && (
            <button type="button" className="btn btn-upgrade" onClick={() => onFindTorrent(movieForSearch, true)}>
              <Wand2 size={15} /> Find upgrade
            </button>
          )}
        </div>
      </div>
    </article>
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

function ListEditorModal({ item, items, lists, onClose, onCreate, onAdd }) {
  const [name, setName] = useState('');
  const [selected, setSelected] = useState(() => (item ? [item] : []));
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const selectedKeys = useMemo(() => new Set(selected.map((movie) => movieIdentityKey(moviePayload(movie)))), [selected]);
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
    try {
      const created = await onCreate(cleanName);
      for (const movie of selected) {
        await onAdd(created.id, movie);
      }
      setName('');
      onClose();
    } finally {
      setBusy(false);
    }
  }

  async function addExisting(listId) {
    if (!item) return;
    setBusy(true);
    try {
      await onAdd(listId, item);
      onClose();
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
            <h2>{item ? 'Add movie to list' : 'Create list'}</h2>
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
          {!item && (
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
          <div className="dialog-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={busy || !name.trim() || (!item && selected.length === 0)}>
              {busy ? <Loader2 size={15} className="spin" /> : <CirclePlus size={15} />} Create
            </button>
          </div>
        </form>
        {item && lists.length > 0 && (
          <div className="existing-list-picker">
            <span className="mini-label">Existing lists</span>
            {lists.map((list) => (
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

function MyListsManagerModal({ lists, items, onClose, onCreate, onRename, onDelete, onAdd, onRemove, onFilter }) {
  const [selectedId, setSelectedId] = useState(lists[0]?.id || '');
  const [newName, setNewName] = useState('');
  const [renameValue, setRenameValue] = useState('');
  const [search, setSearch] = useState('');
  const selectedList = lists.find((list) => list.id === selectedId) || lists[0] || null;
  const listMovieKeys = useMemo(() => new Set((selectedList?.movies || []).map((movie) => movieIdentityKey(movie))), [selectedList]);
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
                  <input value={renameValue} onChange={(event) => setRenameValue(event.target.value)} />
                  <button type="submit" className="mini-action">Rename</button>
                  <button type="button" className="mini-action" onClick={() => onFilter(selectedList)}>Filter</button>
                  <button type="button" className="mini-action mini-action-danger" onClick={deleteSelected}>
                    <Trash2 size={13} /> Delete
                  </button>
                </form>
                <label className="library-search curation-search">
                  <Search size={17} />
                  <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search local movies to add..." />
                </label>
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
                <div className="curation-list">
                  {(selectedList.movies || []).map((movie) => (
                    <div className="curation-row" key={movieIdentityKey(movie)}>
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
      </section>
    </div>
  );
}

function LibraryFileRow({ item, expanded, onToggle, onPlay, onFindTorrent, onRename, onDelete }) {
  const identity = getMovieIdentity(item);
  const lowQuality = isLowQuality(item.resolution);
  const movieForSearch = { title: identity.title, year: identity.year };
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

function MigrationWorkspace({ section, notify, onFindTorrent, cleanupInitialTab }) {
  if (section === 'cleanup') return <CleanupWorkspace notify={notify} onFindTorrent={onFindTorrent} initialTab={cleanupInitialTab} />;
  if (section === 'settings') return <SettingsWorkspace notify={notify} />;
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
  { id: 'unmatched', label: 'Unmatched Metadata', icon: LinkIcon }
];

function CleanupWorkspace({ notify, onFindTorrent, initialTab = 'duplicates' }) {
  const [activeTab, setActiveTab] = useState(initialTab);
  const [loading, setLoading] = useState({});
  const [errors, setErrors] = useState({});
  const [data, setData] = useState({ duplicates: [], smart: [], low: [], unmatched: [] });
  const [selected, setSelected] = useState({ duplicates: new Set(), smart: new Set(), low: new Set(), unmatched: new Set() });
  const [filters, setFilters] = useState({ query: '', resolution: 'all', source: 'all', plex: 'all' });
  const [confirmAction, setConfirmAction] = useState(null);
  const [renameTarget, setRenameTarget] = useState(null);
  const [matchModal, setMatchModal] = useState(null);
  const [rowStatus, setRowStatus] = useState({});

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  const loadCleanup = useCallback(async (forcePlex = false) => {
    const suffix = forcePlex ? '?force_plex=1' : '';
    setLoading({ duplicates: true, smart: true, low: true, unmatched: true });
    setErrors({});
    const requests = await Promise.allSettled([
      fetchJson(`/api/duplicates${suffix}`),
      fetchJson('/api/smart-scan'),
      fetchJson(`/api/low-quality${suffix}`),
      fetchJson(`/api/fix-unmatched${suffix}`)
    ]);
    const [duplicates, smart, low, unmatched] = requests;
    setData({
      duplicates: duplicates.status === 'fulfilled' ? duplicates.value.duplicates || [] : [],
      smart: smart.status === 'fulfilled' ? smart.value.recommendations || [] : [],
      low: low.status === 'fulfilled' ? low.value.items || [] : [],
      unmatched: unmatched.status === 'fulfilled' ? unmatched.value.items || [] : []
    });
    setSelected({ duplicates: new Set(), smart: new Set(), low: new Set(), unmatched: new Set() });
    setErrors({
      duplicates: duplicates.status === 'rejected' ? duplicates.reason.message : '',
      smart: smart.status === 'rejected' ? smart.reason.message : '',
      low: low.status === 'rejected' ? low.reason.message : '',
      unmatched: unmatched.status === 'rejected' ? unmatched.reason.message : ''
    });
    setLoading({ duplicates: false, smart: false, low: false, unmatched: false });
  }, []);

  useEffect(() => {
    loadCleanup(false);
  }, [loadCleanup]);

  const duplicateFiles = useMemo(() => data.duplicates.flatMap((group) => group.files || []), [data.duplicates]);
  const selectableDuplicatePaths = useMemo(() => data.duplicates.flatMap((group) => (group.files || []).slice(1).map((file) => file.path)), [data.duplicates]);
  const smartSelectablePaths = useMemo(() => data.smart.filter((item) => item.delete_path && !item.skipped).map((item) => item.delete_path), [data.smart]);

  const optionSets = useMemo(() => ({
    lowResolutions: getUniqueOptions(data.low, (item) => item.resolution),
    lowSources: getUniqueOptions(data.low, (item) => item.rip_source)
  }), [data.low]);

  const filteredLow = useMemo(() => filterCleanupItems(data.low, filters), [data.low, filters]);
  const filteredUnmatched = useMemo(() => filterUnmatchedItems(data.unmatched, filters), [data.unmatched, filters]);
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

  function openPlexMatch(item) {
    if (!item.rating_key) {
      notify('No Plex rating key for this file. Try Scan Plex Library first.', 'error');
      return;
    }
    setMatchModal({
      provider: 'plex',
      item,
      title: item.suggested_title || '',
      year: item.suggested_year || '',
      loading: false,
      applying: '',
      error: '',
      results: []
    });
  }

  function openTmdbMatch(item) {
    setMatchModal({
      provider: 'tmdb',
      item,
      title: item.suggested_title || item.tmdb_title || '',
      year: item.suggested_year || item.tmdb_year || '',
      loading: false,
      applying: '',
      error: '',
      results: []
    });
  }

  async function searchPlexMatch(event) {
    event.preventDefault();
    if (!matchModal?.item?.rating_key) return;
    setMatchModal((state) => ({ ...state, loading: true, error: '', results: [] }));
    try {
      const params = new URLSearchParams({
        rating_key: matchModal.item.rating_key,
        title: matchModal.title,
        year: matchModal.year
      });
      const result = await fetchJson(`/api/plex/match-search?${params.toString()}`);
      setMatchModal((state) => ({ ...state, loading: false, results: result.results || [] }));
    } catch (error) {
      setMatchModal((state) => ({ ...state, loading: false, error: error.message }));
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
    if (!matchModal?.item?.rating_key || !match?.guid) return;
    setMatchModal((state) => ({ ...state, applying: match.guid, error: '' }));
    try {
      await fetchJson('/api/plex/match-apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: matchModal.item.path, rating_key: matchModal.item.rating_key, guid: match.guid, name: match.name })
      });
      setRowStatus((state) => ({ ...state, [matchModal.item.path]: { tone: 'success', text: `Plex match applied: ${match.name}` } }));
      setData((state) => ({
        ...state,
        unmatched: state.unmatched.filter((item) => item.path !== matchModal.item.path)
      }));
      setMatchModal(null);
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
      setData((state) => ({
        ...state,
        unmatched: state.unmatched.filter((item) => item.path !== matchModal.item.path)
      }));
      setRowStatus((state) => ({ ...state, [matchModal.item.path]: { tone: 'success', text: `TMDB match applied: ${match.title}` } }));
      setMatchModal(null);
      notify('TMDB match applied');
    } catch (error) {
      setMatchModal((state) => ({ ...state, applying: '', error: error.message }));
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
        {(activeTab === 'low' || activeTab === 'unmatched') && (
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
            <UnmatchedCleanupTab items={filteredUnmatched} selected={selected.unmatched} rowStatus={rowStatus} onToggle={toggleSelected} onDelete={requestDelete} onRename={setRenameTarget} onFixPath={requestFixPath} onPlexMatch={openPlexMatch} onTmdbMatch={openTmdbMatch} />
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
            onApply={applyPlexMatch}
          />
        )
      )}
    </section>
  );
}

function filterCleanupItems(items, filters) {
  const q = filters.query.trim().toLowerCase();
  return items.filter((item) => {
    if (q) {
      const haystack = [item.title, item.filename, item.path, item.plex_title, item.plex_year, item.rip_source, item.resolution].filter(Boolean).join(' ').toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    if (filters.resolution !== 'all' && item.resolution !== filters.resolution) return false;
    if (filters.source !== 'all' && item.rip_source !== filters.source) return false;
    if (filters.plex === 'matched' && !item.plex_matched) return false;
    if (filters.plex === 'unmatched' && item.plex_matched) return false;
    return true;
  });
}

function filterUnmatchedItems(items, filters) {
  const q = filters.query.trim().toLowerCase();
  return items.filter((item) => {
    if (q) {
      const haystack = [item.filename, item.path, item.suggested_title, item.suggested_year, item.plex_title, item.tmdb_title, item.metadata_hint, item.plex_hint, item.folder].filter(Boolean).join(' ').toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    if (filters.plex === 'plex-unmatched' && item.plex_matched) return false;
    if (filters.plex === 'tmdb-unmatched' && item.tmdb_id) return false;
    if (filters.plex === 'pending' && item.metadata_status !== 'pending') return false;
    if (filters.plex === 'conflict' && item.metadata_status !== 'conflict') return false;
    if (filters.plex === 'needs_review' && item.metadata_status !== 'needs_review') return false;
    return true;
  });
}

function renameModalItem(item) {
  const title = item.suggested_title || getMovieIdentity(item).title;
  const year = item.suggested_year || getMovieIdentity(item).year;
  return { ...item, title: `${title}${year ? ` (${year})` : ''}` };
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
                  <button type="button" className="btn btn-upgrade" onClick={() => onFindTorrent({ title: identity.title, year: identity.year }, true)}>
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

function UnmatchedCleanupTab({ items, selected, rowStatus, onToggle, onDelete, onRename, onFixPath, onPlexMatch, onTmdbMatch }) {
  return (
    <div className="cleanup-panel">
      <CleanupSelectionBar
        label={`${formatCount(items.length)} unmatched files`}
        selectedCount={selected.size}
        selectableCount={items.length}
        onSelectAll={() => items.forEach((item) => onToggle('unmatched', item.path, true))}
        onClear={() => items.forEach((item) => onToggle('unmatched', item.path, false))}
      />
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
                <button type="button" className="btn btn-primary btn-violet" onClick={() => onTmdbMatch(item)}>
                  <Search size={15} /> Search TMDB
                </button>
                {item.in_plex ? (
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

function metadataStatusLabel(item) {
  if (item.metadata_status === 'pending') return 'Pending metadata';
  if (item.metadata_status === 'conflict') return 'Conflict';
  if (item.metadata_status === 'needs_review') return 'Needs review';
  if (item.in_plex && !item.plex_matched) return 'Plex unmatched';
  if (!item.tmdb_id) return 'TMDB unmatched';
  return 'Unmatched metadata';
}

function metadataStatusChipClass(item) {
  if (item.metadata_status === 'pending') return 'chip-warning';
  if (item.metadata_status === 'conflict') return 'chip-warning';
  return 'status-missing';
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

function PlexMatchModal({ state, onClose, onChange, onSearch, onApply }) {
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
        <div className="match-result-list">
          {state.results.length ? state.results.map((match) => (
            <article className="match-result-row" key={match.guid}>
              <div>
                <strong>{match.name}</strong>
                <span>{match.year || 'Unknown year'} | Score {match.score}</span>
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
  prowlarr: { url: '', key: '' },
  tmdb: { key: '', includeAdult: false },
  ollama: { url: '', model: '' }
};

function SettingsWorkspace({ notify }) {
  const [forms, setForms] = useState(emptySettingsState);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState({});
  const [statuses, setStatuses] = useState({});
  const [revealed, setRevealed] = useState({});

  useEffect(() => {
    let cancelled = false;
    async function loadSettings() {
      setLoading(true);
      const requests = await Promise.allSettled([
        fetchJson('/api/config'),
        fetchJson('/api/app-data/config'),
        fetchJson('/api/plex/config'),
        fetchJson('/api/prowlarr/config'),
        fetchJson('/api/tmdb/config'),
        fetchJson('/api/ollama/config')
      ]);
      if (cancelled) return;
      const [library, appData, plex, prowlarr, tmdb, ollama] = requests;
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
        prowlarr: prowlarr.status === 'fulfilled' ? { url: prowlarr.value.url || '', key: prowlarr.value.key || '' } : { url: '', key: '' },
        tmdb: tmdb.status === 'fulfilled' ? { key: tmdb.value.key || '', includeAdult: Boolean(tmdb.value.include_adult) } : { key: '', includeAdult: false },
        ollama: ollama.status === 'fulfilled' ? { url: ollama.value.url || '', model: ollama.value.model || '' } : { url: '', model: '' }
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
      ollama: '/api/ollama/config'
    };
    const payloads = {
      plex: { url: forms.plex.url, token: forms.plex.token },
      prowlarr: { url: forms.prowlarr.url, key: forms.prowlarr.key },
      tmdb: { key: forms.tmdb.key, include_adult: Boolean(forms.tmdb.includeAdult) },
      ollama: { url: forms.ollama.url, model: forms.ollama.model }
    };
    setActionState(`${service}-save`, true);
    try {
      await fetchJson(endpoints[service], {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payloads[service])
      });
      setCardStatus(service, 'success', `${serviceLabel(service)} settings saved.`, 'Run Test to verify the saved connection.');
      notify(`${serviceLabel(service)} settings saved`);
    } catch (error) {
      setCardStatus(service, 'error', `${serviceLabel(service)} settings not saved.`, error.message);
    } finally {
      setActionState(`${service}-save`, false);
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

  const summary = [
    { key: 'library', label: 'Library roots', ready: (forms.library.directories || []).some((path) => path.trim()), tone: 'blue' },
    { key: 'plex', label: 'Plex', ready: Boolean(forms.plex.url && forms.plex.token), tone: 'cyan' },
    { key: 'prowlarr', label: 'Prowlarr', ready: Boolean(forms.prowlarr.url && forms.prowlarr.key), tone: 'gold' },
    { key: 'tmdb', label: 'TMDB', ready: Boolean(forms.tmdb.key), tone: 'green' },
    { key: 'ollama', label: 'Ollama', ready: Boolean(forms.ollama.url && forms.ollama.model), tone: 'violet' }
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
            </>
          )}
          actions={(
            <>
              <ActionButton loading={saving['prowlarr-save']} icon={Save} label="Save Prowlarr" onClick={() => saveIntegration('prowlarr')} primary />
              <ActionButton loading={saving['prowlarr-test']} icon={PlugZap} label="Test saved" onClick={() => testIntegration('prowlarr')} />
            </>
          )}
        />

        <IntegrationCard
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
    </section>
  );
}

function serviceLabel(service) {
  return {
    plex: 'Plex',
    prowlarr: 'Prowlarr',
    tmdb: 'TMDB',
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

function IntegrationCard({ icon, title, accent, status, fields, actions }) {
  return (
    <section className={cx('settings-panel', 'integration-card', `integration-${accent}`)}>
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
    TMDB: 'Posters, plots, cast, discovery lists, and trailers.',
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
