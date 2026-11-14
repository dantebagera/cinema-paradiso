import SearchField from '../search/SearchField.jsx';
import DialogShell, { DialogHeader } from '../../components/ui/DialogShell.jsx';
import SectionTabs, { SectionTab } from '../../components/ui/SectionTabs.jsx';
import Pagination from '../../components/Pagination.jsx';
import WorkspaceEmptyState from '../../components/WorkspaceEmptyState.jsx';
import { Select, Input } from '../../components/ui/FormField.jsx';
import Button from '../../components/ui/Button.jsx';
import useIPTVPlaybackSession from './useIPTVPlaybackSession.js';
import IPTVSourceList from './IPTVSourceList.jsx';
import { ClassificationPreviewPanel, MatchProposalPanel } from './IPTVProposalPanels.jsx';
import IPTVBulkMetadataJob from './IPTVBulkMetadataJob.jsx';
import IPTVEnrichmentPanel from './IPTVEnrichmentPanel.jsx';
import useIPTVMovieStatus from './useIPTVMovieStatus.js';
import { useAIProvider } from '../ai/AIProviderContext.jsx';
import useAIJob from '../ai/useAIJob.js';
import AIJobStatus from '../ai/AIJobStatus.jsx';
import AIActionReview from '../ai/AIActionReview.jsx';
import { jobIsRunning } from '../ai/aiClient.js';
import { fetchJson } from '../../api/client.js';
import { IPTVPeopleNavigationContext, mediaTitle, movieGenreLabels, IPTVMovieCard, PosterTile, FavoriteButton, ListActionButton, ProviderImage } from './IPTVCards.jsx';
import {
  ChevronLeft,
  ChevronRight,
  CheckSquare,
  CircleAlert,
  Clapperboard,
  Clock3,
  Database,
  ExternalLink,
  Film,
  Heart,
  Home,
  Layers3,
  ListPlus,
  ListVideo,
  Loader2,
  Languages,
  Play,
  Radio,
  RefreshCcw,
  Search,
  ServerCog,
  Star,
  Tv,
  WandSparkles,
  X
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { iptvApi, iptvImage } from '../../api/iptv.js';
import { MovieExpandedFacts, MovieKeywordRow } from '../../components/SharedMovieCards.jsx';
import { UnifiedMovieCard } from '../../components/movie-card/MovieCard.jsx';
import { useMediaCardArtwork } from '../../components/movie-card/cardArtwork.js';
import useCardGridMetrics from '../../hooks/useCardGridMetrics.js';
import { formatCount, movieKey } from '../../utils/appUtils.js';
import { formatVoteCount } from '../../utils/moviePresentation.js';
import IPTVPlayer from './IPTVPlayer.jsx';
import IPTVListsWorkspace, { IPTVListPickerModal } from './IPTVListsWorkspace.jsx';
import {
  createIPTVMovieFilters,
  iptvMovieIdentity,
  iptvMovieQuery,
  iptvMovieQuerySignature,
  normalizeIPTVMovieSearchQuery,
  IPTV_MOVIE_CATEGORIES,
  IPTV_MOVIE_SORTS,
  IPTV_MOVIE_VIEWS
} from './iptvMovieFilters.js';
import { shouldAutoSyncIPTVCatalog } from './iptvSyncPolicy.js';
import './iptv.css';

const TABS = [
  { id: 'home', label: 'Home', icon: Home },
  { id: 'live', label: 'Live TV', icon: Radio },
  { id: 'movie', label: 'Movies', icon: Film },
  { id: 'metadata', label: 'Metadata', icon: Database },
  { id: 'series', label: 'Series', icon: Tv },
  { id: 'favorites', label: 'Favorites', icon: Heart },
  { id: 'lists', label: 'My Lists', icon: ListVideo }
];

const EMPTY_PAGE = { items: [], total: 0, page: 1, page_size: 30 };
const EMPTY_MOVIE_FACETS = { playlists: [], lists: [], categories: [], genres: [], languages: [], countries: [], qualities: [] };
const SAVED_REVIEW_LABELS = {
  'classification-review': 'Classification review', 'needs-review': 'Needs review', unmatched: 'Unmatched',
};
const EMPTY_METADATA_REVIEW = { items: [], total: 0, page: 1, page_size: 50 };

function movieWithDisplay(movie, display) {
  if (!display) return movie;
  return {
    ...movie,
    ...display,
    name: display.title || movie.name,
    image_url: display.poster_url || movie.image_url,
    backdrop_url: display.backdrop_url || movie.backdrop_url,
    directors: display.directors || movie.directors,
    writers: display.writers || movie.writers,
    cast: display.cast || movie.cast,
    genres: display.genres || movie.genres,
    collection: display.collection || movie.collection
  };
}

export default function IPTVWorkspace({ notify, followed = [], active = true, onOpenSettings, onOpenDiscoverPerson,
  reviewProvider, reviewStatus, reviewRevision, onReviewRefresh }) {
  const ai = useAIProvider();
  const [providers, setProviders] = useState([]);
  const [activeProviderId, setActiveProviderId] = useState(reviewProvider?.provider_id || '');
  const reviewActive = active && Boolean(reviewProvider);
  const aiClassification = useAIJob('F4', activeProviderId, { enabled: reviewActive });
  const aiMatching = useAIJob('F5', activeProviderId, { enabled: reviewActive });
  const bulkEndpoint = activeProviderId ? `/api/iptv/providers/${encodeURIComponent(activeProviderId)}/movies/ai/bulk-jobs` : '';
  const [aiFeatures, setAIFeatures] = useState([]);
  const [activeTab, setActiveTab] = useState(reviewProvider ? 'metadata' : 'home');
  const aiBulk = useAIJob('iptv-bulk', activeProviderId, {
    latestEndpoint: bulkEndpoint && `${bulkEndpoint}/latest`,
    recoverStatus: true, enabled: reviewActive,
  });
  const [favoriteKind, setFavoriteKind] = useState('all');
  const [status, setStatus] = useState(null);
  const [syncRequested, setSyncRequested] = useState('');
  const [categories, setCategories] = useState({ live: [], movie: [], series: [] });
  const [categoryId, setCategoryId] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [catalog, setCatalog] = useState(EMPTY_PAGE);
  const [recent, setRecent] = useState([]);
  const [loading, setLoading] = useState(true);
  const [movieLoading, setMovieLoading] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!reviewActive || !activeProviderId || ai.provider !== 'chatgpt') { setAIFeatures([]); return undefined; }
    let cancelled = false;
    fetchJson(`/api/ai/features?provider_id=${encodeURIComponent(activeProviderId)}`).then(data => {
      if (!cancelled) setAIFeatures(data.features || []);
    }).catch(failure => { if (!cancelled) setError(failure.message); });
    return () => { cancelled = true; };
  }, [reviewActive, activeProviderId, ai.provider, ai.config?.generation]);
  const [selectedId, setSelectedId] = useState('');
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedSeason, setSelectedSeason] = useState(1);
  const [selectedLive, setSelectedLive] = useState(null);
  const [epg, setEpg] = useState([]);
  const playbackSession = useIPTVPlaybackSession();
  const { playback, loading: playbackLoading } = playbackSession;
  const [lists, setLists] = useState([]);
  const [selectedListId, setSelectedListId] = useState('');
  const [listCatalog, setListCatalog] = useState(EMPTY_PAGE);
  const [listLoading, setListLoading] = useState(false);
  const [listQuery, setListQuery] = useState('');
  const [listKind, setListKind] = useState('all');
  const [listPage, setListPage] = useState(1);
  const [newListName, setNewListName] = useState('');
  const [renameListName, setRenameListName] = useState('');
  const [listRefresh, setListRefresh] = useState(0);
  const [listPickerItem, setListPickerItem] = useState(null);
  const [listPickerLists, setListPickerLists] = useState([]);
  const [listPickerBusy, setListPickerBusy] = useState(false);
  const [listPickerName, setListPickerName] = useState('');
  const peopleWorkspaceRef = useRef(null);
  const pendingPeopleRestore = useRef(null);
  const [peopleHistory, setPeopleHistory] = useState([]);
  const [personContext, setPersonContext] = useState(null);
  const [movieFilters, setMovieFilters] = useState(createIPTVMovieFilters);
  const [movieFacets, setMovieFacets] = useState(EMPTY_MOVIE_FACETS);
  const [movieRefresh, setMovieRefresh] = useState(0);
  const refreshMovieData = useCallback(() => {
    if (onReviewRefresh) onReviewRefresh();
    else setMovieRefresh(value => value + 1);
  }, [onReviewRefresh]);
  const automaticBulkJob = aiBulk.job?.bulk?.automatic ? aiBulk.job : null;
  const automaticBulkId = automaticBulkJob?.id;
  const automaticBulkApplied = automaticBulkJob?.bulk.automatic_counts?.applied || 0;
  const automaticBulkCompleted = automaticBulkJob?.state === 'completed';
  useEffect(() => {
    if (automaticBulkId && (automaticBulkApplied || automaticBulkCompleted)) refreshMovieData();
  }, [automaticBulkId, automaticBulkApplied, automaticBulkCompleted, refreshMovieData]);
  const firstPassStatus = useIPTVMovieStatus(activeProviderId, {
    enabled: !reviewProvider && active && Boolean(status?.configured) && ['movie', 'metadata'].includes(activeTab),
    generation: status?.generation, refresh: `${movieRefresh}:${activeTab}`, onSettled: refreshMovieData, notify,
  });
  const { worker: movieStatus, publish: publishMovieStatus, error: workerStatusError, current: movieStatusCurrent,
    control: enrichmentControl, controlError: enrichmentError, requestControl: requestEnrichment } = reviewStatus || firstPassStatus;
  const [metadataSettings, setMetadataSettings] = useState(null);
  const [readinessError, setReadinessError] = useState('');
  const [readinessRefresh, setReadinessRefresh] = useState(0);
  const [facetError, setFacetError] = useState('');
  const [facetRefresh, setFacetRefresh] = useState(0);
  const [metadataPane, setMetadataPane] = useState(null);
  const bulkInProgress = jobIsRunning(aiBulk.job) || ['paused', 'paused_budget', 'interrupted'].includes(aiBulk.job?.state) ||
    aiBulk.job?.bulk?.resume_after_sync ||
    ['running', 'stopping', 'interrupted'].includes(aiBulk.job?.bulk?.apply?.state);
  const metadataSurface = metadataPane || (bulkInProgress ? 'bulk' : 'catalog');
  const [metadataReview, setMetadataReview] = useState(EMPTY_METADATA_REVIEW);
  const [metadataReviewKey, setMetadataReviewKey] = useState('');
  const [metadataReviewError, setMetadataReviewError] = useState('');
  const [metadataReviewRetry, setMetadataReviewRetry] = useState(0);
  const [metadataPage, setMetadataPage] = useState(1);
  const [metadataFilters, setMetadataFilters] = useState({ q: '', category: '', playlist_id: '' });
  const [debouncedReviewQuery, setDebouncedReviewQuery] = useState('');
  const reviewKey = JSON.stringify([activeProviderId, reviewRevision, movieStatus?.projection?.source_generation,
    metadataPage, metadataFilters, metadataReviewRetry]);
  const metadataReviewLoading = metadataReviewKey !== reviewKey;
  const [metadataSelection, setMetadataSelection] = useState(() => new Set());
  const [metadataAllFiltered, setMetadataAllFiltered] = useState(false);
  const hasMetadataSelection = metadataAllFiltered || metadataSelection.size > 0;
  const [preparationFailure, setPreparationFailure] = useState(null);
  const clearBulkError = aiBulk.clearError;
  useEffect(() => {
    if (!preparationFailure) return;
    if (preparationFailure.providerId !== activeProviderId) {
      setPreparationFailure(null);
    } else if (movieStatusCurrent && movieStatus?.projection?.state === 'complete' &&
        !metadataReviewLoading && !metadataReviewError) {
      clearBulkError(preparationFailure.message);
      setPreparationFailure(null);
    }
  }, [preparationFailure, activeProviderId, movieStatusCurrent, movieStatus?.projection?.state,
    metadataReviewLoading, metadataReviewError, clearBulkError]);
  const [proposalJob, setProposalJob] = useState(null);
  const [lastProposalJob, setLastProposalJob] = useState(null);
  const [proposalBusy, setProposalBusy] = useState(false);
  const [classificationPreview, setClassificationPreview] = useState(null);
  const [movieLocale, setMovieLocale] = useState('default');
  const [sourceChooser, setSourceChooser] = useState(null);
  const [matchDialog, setMatchDialog] = useState(null);
  const [matchQuery, setMatchQuery] = useState('');
  const [matchYear, setMatchYear] = useState('');
  const [matchResults, setMatchResults] = useState([]);
  const [matchBusy, setMatchBusy] = useState(false);
  const activeProviderRef = useRef('');
  const detailRequestRef = useRef(0);
  const movieRequestRef = useRef({ sequence: 0, signature: '', controller: null });
  const categoryIdRef = useRef('');
  const autoSyncRequestedRef = useRef(new Set());
  const aiReviewRef = useRef(sessionStorage.getItem('cp-iptv-review-target') !== null);
  const [aiReviewTarget, setAIReviewTarget] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('cp-iptv-review-target') || 'null'); }
    catch { return null; }
  });
  const aiStartPending = useRef(false);

  const browseKind = activeTab === 'favorites' ? favoriteKind : activeTab;
  const isBrowseTab = ['live', 'movie', 'series', 'favorites'].includes(activeTab);
  const adaptiveCardGrid = ['movie', 'series'].includes(browseKind)
    && !(activeTab === 'favorites' && favoriteKind === 'all');
  const {
    gridRef: iptvCardGridRef,
    pageSize: adaptiveCardPageSize
  } = useCardGridMetrics({
    target: activeTab === 'favorites' ? 60 : 30,
    max: 100,
    bias: 'lower'
  });
  const browsePageSize = browseKind === 'live'
    ? 80
    : (adaptiveCardGrid ? adaptiveCardPageSize : (activeTab === 'favorites' ? 60 : 30));
  const activeCardGridRef = adaptiveCardGrid ? iptvCardGridRef : undefined;
  categoryIdRef.current = categoryId;
  activeProviderRef.current = activeProviderId;
  const activeProvider = providers.find((provider) => provider.provider_id === activeProviderId) || null;

  const refreshStatus = useCallback(async () => {
    if (!activeProviderId) return null;
    const data = await iptvApi.status(activeProviderId);
    if (activeProviderRef.current !== activeProviderId) return data;
    setStatus(data);
    setProviders((state) => state.map((provider) => provider.provider_id === activeProviderId ? { ...provider, ...data } : provider));
    return data;
  }, [activeProviderId]);

  useEffect(() => {
    if (reviewProvider) return undefined;
    let cancelled = false;
    iptvApi.providers()
      .then((data) => {
        if (cancelled) return;
        const nextProviders = data.providers || [];
        const requested = aiReviewTarget?.provider_id || data.last_selected_provider_id;
        const selected = nextProviders.some((provider) => provider.provider_id === requested)
    ? requested
    : (nextProviders[0]?.provider_id || '');
        setProviders(nextProviders);
        setActiveProviderId(selected);
      })
      .catch((requestError) => !cancelled && setError(requestError.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [reviewProvider]);

  useEffect(() => {
    if (reviewProvider) return undefined;
    if (!activeProviderId) {
      setStatus(null);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    refreshStatus()
      .then(async (data) => {
        if (cancelled || !data?.configured) return;
        if (!aiReviewRef.current && shouldAutoSyncIPTVCatalog(data) && !autoSyncRequestedRef.current.has(activeProviderId)) {
    autoSyncRequestedRef.current.add(activeProviderId);
    try {
      const result = await iptvApi.sync(activeProviderId);
      if (!cancelled && result.status) setStatus(result.status);
    } catch (requestError) {
      if (!cancelled) setError(requestError.message);
    }
        }
        if (!cancelled) {
    const result = await iptvApi.recent(activeProviderId);
    if (!cancelled) setRecent(result.items || []);
        }
      })
      .catch((requestError) => !cancelled && setError(requestError.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [activeProviderId, refreshStatus, reviewProvider]);

  useEffect(() => {
    if (reviewProvider) return undefined;
    function receive(event) {
      aiReviewRef.current = true;
      setAIReviewTarget(event.detail || {});
    }
    window.addEventListener('cp-iptv-review', receive);
    return () => window.removeEventListener('cp-iptv-review', receive);
  }, [reviewProvider]);

  useEffect(() => {
    if (reviewProvider || !aiReviewTarget || !providers.length) return;
    const target = aiReviewTarget;
    if (target.provider_id && target.provider_id !== activeProviderId) {
      if (providers.some(row => row.provider_id === target.provider_id)) setActiveProviderId(target.provider_id);
      else { setError('The reviewed IPTV provider is no longer available.'); setAIReviewTarget(null); }
      return;
    }
    if (!activeProviderId || !status?.configured) return;
    sessionStorage.removeItem('cp-iptv-review-target');
    setAIReviewTarget(null);
    const kind = target.kind || 'movie';
    setActiveTab(['movie', 'series', 'live'].includes(kind) ? kind : 'home');
    if (!target.item_id) return;
    if (kind === 'live') {
      // A review is navigation only. selectChannel also starts playback.
      iptvApi.detail(activeProviderId, kind, target.item_id).then(item => {
        if (activeProviderRef.current === activeProviderId) setSelectedId(item.item_id);
      }).catch(failure => setError(failure.message));
    } else {
      loadDetail(kind === 'movie' ? { movie_key: target.item_id, kind } : { item_id: target.item_id, kind });
    }
  }, [reviewProvider, aiReviewTarget, activeProviderId, providers, status?.configured]);

  useEffect(() => {
    if (status?.sync?.state !== 'running') return undefined;
    const timer = window.setInterval(() => {
      refreshStatus().catch(() => {});
    }, 1500);
    return () => window.clearInterval(timer);
  }, [status?.sync?.state, refreshStatus]);

  useEffect(() => {
    if (!status?.configured || !['live', 'series'].includes(activeTab)) return undefined;
    let cancelled = false;
    iptvApi.categories(activeProviderId, activeTab)
      .then((result) => {
        if (cancelled) return;
        const nextCategories = result.items || [];
        setCategories((state) => ({ ...state, [activeTab]: nextCategories }));
        const selectedCategory = categoryIdRef.current;
        if (selectedCategory && !nextCategories.some((category) => category.category_id === selectedCategory)) {
    setCategoryId('');
    setPage(1);
        }
      })
      .catch((requestError) => !cancelled && setError(requestError.message));
    return () => { cancelled = true; };
  }, [activeProviderId, activeTab, status?.configured, status?.generation]);

  const facetView = activeTab === 'movie' ? movieFilters.view : 'provider';
  const browseFacetRefresh = activeTab === 'movie' ? movieRefresh : 0;
  useEffect(() => {
    if (!active || (!reviewProvider && (!status?.configured || activeTab !== 'movie'))) return undefined;
    const controller = new AbortController();
    setFacetError('');
    iptvApi.movieFacets(activeProviderId, { view: facetView }, { signal: controller.signal }).then(facets => {
      if (!controller.signal.aborted) setMovieFacets({ ...EMPTY_MOVIE_FACETS, ...facets });
    }).catch(failure => {
      if (!controller.signal.aborted) {
        if (activeTab === 'movie') setError(failure.message);
        else setFacetError(failure.message);
      }
    });
    return () => controller.abort();
  }, [active, activeTab, activeProviderId, status?.configured, status?.generation,
    facetView, browseFacetRefresh, facetRefresh, reviewProvider]);

  useEffect(() => {
    if (!active || activeTab !== 'metadata') return undefined;
    const controller = new AbortController();
    setReadinessError('');
    iptvApi.metadataSettings({ signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) setMetadataSettings(data);
    }).catch(failure => { if (!controller.signal.aborted) setReadinessError(failure.message); });
    return () => controller.abort();
  }, [active, activeTab, readinessRefresh]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedReviewQuery(metadataFilters.q), 250);
    return () => window.clearTimeout(timer);
  }, [metadataFilters.q]);

  useEffect(() => {
    if (!reviewActive || (metadataSurface !== 'catalog' && !hasMetadataSelection) ||
        metadataFilters.q !== debouncedReviewQuery) return undefined;
    const controller = new AbortController();
    setMetadataReviewError('');
    setMetadataReviewKey('');
    iptvApi.movieMetadataReview(activeProviderId, {
      view: 'unmatched', review_scope: 'leftovers', ...metadataFilters, page: metadataPage, page_size: 50,
    }, { signal: controller.signal }).then(data => {
      if (controller.signal.aborted) return;
      setMetadataReview(data);
      setMetadataReviewKey(reviewKey);
    }).catch(failure => { if (!controller.signal.aborted) setMetadataReviewError(failure.message); });
    return () => controller.abort();
  }, [reviewActive, activeProviderId, metadataSurface, debouncedReviewQuery, reviewKey,
    metadataFilters, metadataPage, movieRefresh, hasMetadataSelection]);

  useEffect(() => {
    if (!status?.configured || activeTab !== 'movie') return undefined;
    const normalizedQuery = normalizeIPTVMovieSearchQuery(movieFilters.q);
    const signature = iptvMovieQuerySignature(
      activeProviderId,
      { ...movieFilters, q: normalizedQuery },
      page,
      browsePageSize,
      Number(status?.generation || 0)
    );
    const sequence = movieRequestRef.current.sequence + 1;
    movieRequestRef.current.controller?.abort();
    const controller = new AbortController();
    movieRequestRef.current = { sequence, signature, controller };
    setMovieLoading(true);
    setError('');
    setCatalog({ ...EMPTY_PAGE, page, page_size: browsePageSize, loading: true, query: normalizedQuery, view: movieFilters.view });
    const timer = window.setTimeout(async () => {
      try {
        const result = await iptvApi.movies(
    activeProviderId,
    iptvMovieQuery({ ...movieFilters, q: normalizedQuery }, page, browsePageSize),
    { signal: controller.signal }
        );
        const current = movieRequestRef.current;
        if (controller.signal.aborted || current.sequence !== sequence || current.signature !== signature || activeProviderRef.current !== activeProviderId) return;
        setCatalog({ ...result, loading: false, query: normalizedQuery, view: movieFilters.view });
      } catch (requestError) {
        if (controller.signal.aborted || requestError?.name === 'AbortError') return;
        const current = movieRequestRef.current;
        if (current.sequence !== sequence || current.signature !== signature || activeProviderRef.current !== activeProviderId) return;
        setCatalog({ ...EMPTY_PAGE, page, page_size: browsePageSize, loading: false, query: normalizedQuery, view: movieFilters.view, failed: true });
        setError(requestError.message);
      } finally {
        const current = movieRequestRef.current;
        if (current.sequence === sequence && current.signature === signature && activeProviderRef.current === activeProviderId) setMovieLoading(false);
      }
    }, normalizedQuery ? 220 : 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
      setMovieLoading(false);
    };
  }, [activeProviderId, activeTab, browsePageSize, page, status?.configured, status?.generation, movieFilters, movieRefresh]);

  useEffect(() => {
    if (!status?.configured || !isBrowseTab || activeTab === 'movie') return undefined;
    let cancelled = false;
    setLoading(true);
    setError('');
    const timer = window.setTimeout(async () => {
      try {
        if (activeTab === 'favorites') {
    const result = await iptvApi.favorites(activeProviderId, {
      kind: favoriteKind === 'all' ? '' : favoriteKind,
      q: query.trim(),
      page,
      page_size: browsePageSize
    });
    if (!cancelled) setCatalog(result);
    return;
        }
        const result = await iptvApi.items(activeProviderId, {
    kind: browseKind,
    category_id: categoryId,
    q: query.trim(),
    page,
    page_size: browsePageSize,
    favorites: activeTab === 'favorites'
        });
        if (!cancelled) setCatalog(result);
      } catch (requestError) {
        if (!cancelled) setError(requestError.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, query ? 220 : 0);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [activeProviderId, activeTab, browseKind, browsePageSize, categoryId, query, page, status?.configured, status?.generation]);

  useEffect(() => {
    setPage(1);
  }, [browsePageSize]);

  useEffect(() => {
    if (!status?.configured || activeTab !== 'lists') return undefined;
    let cancelled = false;
    iptvApi.lists(activeProviderId)
      .then((result) => {
        if (cancelled) return;
        const nextLists = result.items || [];
        setLists(nextLists);
        setSelectedListId((current) => nextLists.some((list) => list.list_id === current) ? current : (nextLists[0]?.list_id || ''));
      })
      .catch((requestError) => !cancelled && setError(requestError.message));
    return () => { cancelled = true; };
  }, [activeProviderId, activeTab, status?.configured, status?.generation, listRefresh]);

  useEffect(() => {
    const selected = lists.find((list) => list.list_id === selectedListId);
    setRenameListName(selected?.name || '');
  }, [lists, selectedListId]);

  useEffect(() => {
    if (!status?.configured || activeTab !== 'lists' || !selectedListId) {
      if (!selectedListId) setListCatalog(EMPTY_PAGE);
      return undefined;
    }
    let cancelled = false;
    setListLoading(true);
    const timer = window.setTimeout(() => {
      iptvApi.listItems(activeProviderId, selectedListId, {
        kind: listKind === 'all' ? '' : listKind,
        q: listQuery.trim(),
        page: listPage,
        page_size: 60
      })
        .then((result) => !cancelled && setListCatalog(result))
        .catch((requestError) => !cancelled && setError(requestError.message))
        .finally(() => !cancelled && setListLoading(false));
    }, listQuery ? 220 : 0);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [activeProviderId, activeTab, status?.configured, selectedListId, listKind, listQuery, listPage, listRefresh]);

  function browseIPTVPerson(role, person) {
    const workspace = peopleWorkspaceRef.current?.closest('.workspace') || peopleWorkspaceRef.current;
    setPeopleHistory(history => [...history, {
      activeTab, movieFilters, page, selectedId, detail, movieLocale, personContext,
      scrollTop: workspace?.scrollTop || 0,
    }]);
    setPersonContext({ name: person.name, role });
    setMovieFilters({ ...movieFilters,
      view: 'cp', category: 'film', person_id: String(person.id), person_role: role });
    setActiveTab('movie');
    setPage(1);
    setSelectedId('');
    setDetail(null);
  }

  function restoreIPTVPeopleView() {
    const saved = peopleHistory.at(-1);
    if (!saved) return;
    setPeopleHistory(history => history.slice(0, -1));
    setPersonContext(saved.personContext);
    setMovieFilters(saved.movieFilters);
    setActiveTab(saved.activeTab);
    setPage(saved.page);
    setMovieLocale(saved.movieLocale);
    setSelectedId('');
    pendingPeopleRestore.current = saved;
  }

  useEffect(() => {
    const saved = pendingPeopleRestore.current;
    if (!saved || movieLoading || catalog.loading) return;
    const frame = requestAnimationFrame(() => {
      const workspace = peopleWorkspaceRef.current?.closest('.workspace') || peopleWorkspaceRef.current;
      if (workspace) workspace.dataset.restoringCard = 'true';
      setSelectedId(saved.selectedId);
      setDetail(saved.detail);
      requestAnimationFrame(() => requestAnimationFrame(() => {
        if (workspace) { workspace.scrollTop = saved.scrollTop; delete workspace.dataset.restoringCard; }
      }));
      pendingPeopleRestore.current = null;
    });
    return () => cancelAnimationFrame(frame);
  }, [movieLoading, catalog]);

  function selectTab(tab) {
    setActiveTab(tab);
    setCategoryId('');
    setQuery('');
    setPage(1);
    setSelectedId('');
    setDetail(null);
  }

  function resetProviderState() {
    setPeopleHistory([]);
    setPersonContext(null);
    pendingPeopleRestore.current = null;
    movieRequestRef.current.controller?.abort();
    movieRequestRef.current = { sequence: movieRequestRef.current.sequence + 1, signature: '', controller: null };
    setStatus(null);
    setCategories({ live: [], movie: [], series: [] });
    setCategoryId('');
    setQuery('');
    setPage(1);
    setCatalog(EMPTY_PAGE);
    setMovieLoading(false);
    setRecent([]);
    setSelectedId('');
    setDetail(null);
    setDetailLoading(false);
    setSelectedSeason(1);
    setSelectedLive(null);
    setEpg([]);
    playbackSession.stop().catch(requestError => setError(requestError.message));
    setLists([]);
    setSelectedListId('');
    setListCatalog(EMPTY_PAGE);
    setListQuery('');
    setListKind('all');
    setListPage(1);
    setListPickerItem(null);
    setListPickerLists([]);
    setMovieFilters(createIPTVMovieFilters());
    setMovieFacets(EMPTY_MOVIE_FACETS);
    setMetadataPane(null);
    setMetadataPage(1);
    setMetadataFilters({ q: '', category: '', playlist_id: '' });
    setMetadataReview(EMPTY_METADATA_REVIEW);
    setMetadataReviewKey('');
    setMetadataReviewError('');
    setMetadataSelection(new Set());
    setMetadataAllFiltered(false);
    setProposalJob(null);
    setLastProposalJob(null);
    setClassificationPreview(null);
    setSourceChooser(null);
    setMatchDialog(null);
    setMatchResults([]);
    setError('');
  }

  async function switchProvider(providerId) {
    if (!providerId || providerId === activeProviderId) return;
    resetProviderState();
    setActiveProviderId(providerId);
    iptvApi.selectProvider(providerId).catch((requestError) => setError(requestError.message));
  }

  async function syncCatalog() {
    const providerId = activeProviderId;
    setSyncRequested(providerId);
    setError('');
    try {
      await iptvApi.sync(providerId);
      await refreshStatus();
      notify?.('IPTV catalog sync started');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSyncRequested(current => current === providerId ? '' : current);
    }
  }

  async function toggleFavorite(item) {
    const next = !item.favorite;
    try {
      if (item.movie_key) await iptvApi.movieFavorite(activeProviderId, item.movie_key, next);
      else await iptvApi.favorite(activeProviderId, item.kind, item.item_id, next);
      setCatalog((state) => {
        const matches = (row) => item.movie_key ? row.movie_key === item.movie_key : row.kind === item.kind && row.item_id === item.item_id;
        if (activeTab === 'favorites' && !next) {
    return { ...state, items: state.items.filter((row) => !matches(row)), total: Math.max(0, Number(state.total || 0) - 1) };
        }
        return { ...state, items: state.items.map((row) => matches(row) ? { ...row, favorite: next } : row) };
      });
      setDetail((state) => state && (item.movie_key ? state.movie_key === item.movie_key : state.kind === item.kind && state.item_id === item.item_id) ? { ...state, favorite: next } : state);
      setSelectedLive((state) => state && state.kind === item.kind && state.item_id === item.item_id ? { ...state, favorite: next } : state);
      setRecent((state) => state.map((row) => row.kind === item.kind && row.item_id === item.item_id ? { ...row, favorite: next } : row));
      notify?.(next ? 'Added to IPTV favorites' : 'Removed from IPTV favorites');
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function createIPTVList() {
    const name = newListName.trim();
    if (!name) return;
    try {
      const created = await iptvApi.createList(activeProviderId, name);
      setNewListName('');
      setSelectedListId(created.list_id);
      setListRefresh((value) => value + 1);
      notify?.(`IPTV list created: ${created.name}`);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function renameIPTVList() {
    const name = renameListName.trim();
    if (!selectedListId || !name) return;
    try {
      const renamed = await iptvApi.renameList(activeProviderId, selectedListId, name);
      setRenameListName(renamed.name);
      setListRefresh((value) => value + 1);
      notify?.(`IPTV list renamed: ${renamed.name}`);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function deleteIPTVList() {
    const selected = lists.find((list) => list.list_id === selectedListId);
    if (!selected || !window.confirm(`Delete IPTV list "${selected.name}"? Saved media will not be removed from the provider.`)) return;
    try {
      await iptvApi.deleteList(activeProviderId, selectedListId);
      setSelectedListId('');
      setListRefresh((value) => value + 1);
      notify?.('IPTV list deleted');
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function removeIPTVListItem(item) {
    try {
      await iptvApi.setListItem(activeProviderId, selectedListId, item.kind, item.item_id, false);
      setListRefresh((value) => value + 1);
      notify?.('Removed from IPTV list');
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function moveIPTVListItem(item, direction) {
    try {
      await iptvApi.moveListItem(activeProviderId, selectedListId, item.kind, item.item_id, direction);
      setListRefresh((value) => value + 1);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function openListPicker(item) {
    setListPickerItem(item);
    setListPickerLists([]);
    setListPickerName('');
    setListPickerBusy(true);
    try {
      const result = await iptvApi.lists(activeProviderId, { kind: item.kind, item_id: item.item_id });
      if (item.movie_key) {
        const movie = item.sources ? item : await iptvApi.movieDetail(activeProviderId, item.movie_key);
        const included = new Set(movie.list_ids || []);
        setListPickerLists((result.items || []).map((list) => ({ ...list, included: included.has(list.list_id) })));
      } else {
        setListPickerLists(result.items || []);
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setListPickerBusy(false);
    }
  }

  async function togglePickerList(list) {
    if (!listPickerItem) return;
    setListPickerBusy(true);
    try {
      const included = !list.included;
      if (listPickerItem.movie_key) await iptvApi.setMovieList(activeProviderId, listPickerItem.movie_key, list.list_id, included);
      else await iptvApi.setListItem(activeProviderId, list.list_id, listPickerItem.kind, listPickerItem.item_id, included);
      setListPickerLists((state) => state.map((row) => row.list_id === list.list_id ? { ...row, included, item_count: Math.max(0, row.item_count + (included ? 1 : -1)) } : row));
      setListRefresh((value) => value + 1);
      notify?.(included ? `Added to ${list.name}` : `Removed from ${list.name}`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setListPickerBusy(false);
    }
  }

  async function createPickerList() {
    const name = listPickerName.trim();
    if (!name || !listPickerItem) return;
    setListPickerBusy(true);
    try {
      const created = await iptvApi.createList(activeProviderId, name);
      if (listPickerItem.movie_key) await iptvApi.setMovieList(activeProviderId, listPickerItem.movie_key, created.list_id, true);
      else await iptvApi.setListItem(activeProviderId, created.list_id, listPickerItem.kind, listPickerItem.item_id, true);
      setListPickerLists((state) => [...state, { ...created, included: true, item_count: 1 }]);
      setListPickerName('');
      setListRefresh((value) => value + 1);
      notify?.(`Created ${created.name} and added media`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setListPickerBusy(false);
    }
  }

  async function loadDetail(item) {
    const requestedProviderId = activeProviderId;
    const requestedId = item.movie_key || item.item_id;
    const requestId = ++detailRequestRef.current;
    setSelectedId(requestedId);
    setMovieLocale('default');
    setDetailLoading(true);
    setError('');
    try {
      const result = item.movie_key
        ? await iptvApi.movieDetail(requestedProviderId, item.movie_key)
        : await iptvApi.detail(requestedProviderId, item.kind, item.item_id);
      if (activeProviderRef.current !== requestedProviderId || detailRequestRef.current !== requestId) return;
      let displayedResult = result;
      if (item.movie_key && result.matched && result.original_language === 'ar') {
        try {
    const localized = result.arabic_display
      || await iptvApi.movieLocalization(requestedProviderId, result.movie_key, 'ar-SA');
    if (activeProviderRef.current !== requestedProviderId || detailRequestRef.current !== requestId) return;
    displayedResult = movieWithDisplay({ ...result, arabic_display: localized }, localized);
        } catch (localizationError) {
    if (activeProviderRef.current === requestedProviderId && detailRequestRef.current === requestId) {
      setError(localizationError.message);
    }
        }
      }
      if (activeProviderRef.current !== requestedProviderId || detailRequestRef.current !== requestId) return;
      setDetail(displayedResult);
      const seasonNumbers = [...new Set((result.episodes || []).map((episode) => episode.season))].sort((a, b) => a - b);
      setSelectedSeason(seasonNumbers[0] || 1);
    } catch (requestError) {
      if (activeProviderRef.current === requestedProviderId) setError(requestError.message);
    } finally {
      if (activeProviderRef.current === requestedProviderId) setDetailLoading(false);
    }
  }

  async function openDetail(item) {
    const itemId = item.movie_key || item.item_id;
    if (selectedId === itemId) {
      detailRequestRef.current += 1;
      setSelectedId('');
      setDetail(null);
      setMovieLocale('default');
      return;
    }
    await loadDetail(item);
  }

  async function openListItem(item) {
    if (!item.available) return;
    if (item.kind === 'live') {
      selectTab('live');
      await selectChannel(item);
      return;
    }
    setActiveTab(item.kind);
    setCategoryId('');
    setQuery(mediaTitle(item));
    setPage(1);
    await loadDetail(item);
  }

  async function playListItem(item) {
    if (item.kind === 'live') {
      selectTab('live');
      await selectChannel(item);
      return;
    }
    await playItem(item);
  }

  async function playItem(item, options = {}) {
    if (item.movie_key && !options.itemId && Number(item.source_count || item.sources?.length || 1) > 1) {
      try {
        const sources = item.sources || (await iptvApi.movieSources(activeProviderId, item.movie_key)).items || [];
        setSourceChooser({ movie: item, sources });
      } catch (requestError) {
        setError(requestError.message);
      }
      return;
    }
    setError('');
    try {
      await playbackSession.start(activeProviderId, {
        kind: options.kind || item.kind,
        item_id: options.itemId || item.item_id,
        extension: options.extension || item.container_extension,
        title: options.title || item.name || item.title,
      }, { historyKind: options.historyKind, historyId: options.historyId });
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function chooseMovieSource(source) {
    const movie = sourceChooser?.movie;
    setSourceChooser(null);
    if (!movie) return;
    await playItem(movie, {
      kind: 'movie',
      itemId: source.item_id,
      extension: source.container_extension,
      title: source.name || movie.name || movie.title
    });
  }

  function updateMovieFilter(name, value) {
    if (name === 'view' && value === 'provider') {
      setPersonContext(null);
      setPeopleHistory([]);
    }
    setMovieFilters((state) => {
      if (name === 'view' && value === 'provider') {
        const defaults = createIPTVMovieFilters();
        return {
    ...defaults,
    view: 'provider',
    q: state.q,
    playlist_id: state.playlist_id,
    list_id: state.list_id,
    sort: state.sort
        };
      }
      return { ...state, [name]: value };
    });
    setPage(1);
    setSelectedId('');
    setDetail(null);
  }

  async function retryProjection() {
    const providerId = activeProviderId;
    try {
      const projection = await iptvApi.retryMovieProjection(providerId);
      publishMovieStatus({ projection }, (current, incoming) => ({ ...current, ...incoming }));
    } catch (requestError) {
      if (activeProviderRef.current === providerId) setError(requestError.message);
    }
  }

  async function switchMovieLocale(locale) {
    if (!detail?.movie_key) return;
    if (locale === 'en-US' && detail.base_display) {
      setDetail((state) => movieWithDisplay(state, state.base_display));
      setMovieLocale('en-US');
      return;
    }
    try {
      const localized = detail.arabic_display || await iptvApi.movieLocalization(activeProviderId, detail.movie_key, 'ar-SA');
      setDetail((state) => movieWithDisplay({ ...state, arabic_display: localized }, localized));
      setMovieLocale('ar-SA');
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  function openMatchMetadata(movie) {
    const identity = iptvMovieIdentity(
      movie.provider_title || movie.name || '',
      movie.provider_year || movie.year || ''
    );
    setMatchDialog({ ...movie, initialSearch: identity });
    setMatchQuery(identity.title);
    setMatchYear(identity.year);
    setMatchResults([]);
  }

  async function searchMatchMetadata() {
    if (!matchDialog) return;
    setMatchBusy(true);
    setError('');
    setMatchResults([]);
    try {
      const query = matchQuery.trim();
      const exact = matchDialog.category === 'plays' && /^tmdb:(\d+)$/i.exec(query);
      const result = await iptvApi.movieMatchSearch(activeProviderId, matchDialog.movie_key, {
        q: exact || query === matchDialog.initialSearch.title ? '' : query,
        year: matchYear.trim() === matchDialog.initialSearch.year ? '' : matchYear.trim(),
        ...(exact ? { tmdb_id: exact[1] } : {})
      });
      setMatchResults((result.items || []).map(item => ({ ...item, catalog_generation: result.catalog_generation })));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setMatchBusy(false);
    }
  }

  async function applyMovieMatch(candidate) {
    if (!matchDialog) return;
    setMatchBusy(true);
    try {
      await iptvApi.setMovieMatch(activeProviderId, matchDialog.movie_key, candidate.tmdb_id, matchDialog.category, candidate.catalog_generation);
      setMatchDialog(null);
      setMatchResults([]);
      setSelectedId('');
      setDetail(null);
      refreshMovieData();
      notify?.('IPTV movie metadata match saved');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setMatchBusy(false);
    }
  }

  async function removeMovieMatch(movie, reprocess = false) {
    try {
      await iptvApi.removeMovieMatch(activeProviderId, movie.movie_key, reprocess);
      setSelectedId('');
      setDetail(null);
      refreshMovieData();
      notify?.(reprocess ? 'IPTV movie queued for a new match' : 'IPTV metadata match removed');
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  const metadataSelectedCount = metadataAllFiltered ? metadataReview.total : metadataSelection.size;
  const matchingReady = Boolean(aiFeatures.find(row => row.id === 'F5')?.ready);
  const standardProposalRefs = [...new Map([
    movieStatus?.latest_jobs?.match, movieStatus?.latest_jobs?.match_tmdb, lastProposalJob,
  ].filter(job => job?.job_id).map(job => [job.method, job])).values()];

  function metadataSelectionPayload() {
    return {
      selection_mode: metadataAllFiltered ? 'all-filtered' : 'explicit',
      selected_keys: metadataAllFiltered ? [] : [...metadataSelection],
      filters: { review_view: 'unmatched', review_scope: 'leftovers', ...metadataFilters, view: 'provider' },
      page: metadataPage,
      page_size: metadataReview.page_size || 50
    };
  }

  function toggleMetadataSelection(sourceKey) {
    setMetadataAllFiltered(false);
    setMetadataSelection((current) => {
      const next = new Set(current);
      if (next.has(sourceKey)) next.delete(sourceKey); else next.add(sourceKey);
      return next;
    });
  }

  function selectMetadataPage() {
    setMetadataAllFiltered(false);
    setMetadataSelection((current) => new Set([
      ...current,
      ...(metadataReview.items || []).map((item) => item.source_key)
    ]));
  }

  async function previewBulkClassification(category) {
    setProposalBusy(true);
    setError('');
    try {
      const preview = await iptvApi.movieClassificationPreview(activeProviderId, {
        ...metadataSelectionPayload(), category
      });
      setClassificationPreview(preview);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProposalBusy(false);
    }
  }

  async function applyBulkClassification(proposalIds) {
    if (!classificationPreview) return;
    setProposalBusy(true);
    try {
      const selected = new Set(proposalIds || []);
      const result = await iptvApi.movieClassificationApply(activeProviderId, {
        catalog_generation: classificationPreview.catalog_generation,
        proposals: classificationPreview.proposals.map((proposal) => ({ ...proposal, selected: selected.has(proposal.proposal_id) }))
      });
      notify?.(`${formatCount(result.applied?.length || 0)} IPTV classifications applied`);
      setClassificationPreview(null);
      setMetadataSelection(new Set());
      setMetadataAllFiltered(false);
      refreshMovieData();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProposalBusy(false);
    }
  }

  async function startMetadataAI(operation, action) {
    if (aiStartPending.current) return;
    aiStartPending.current = true;
    setError('');
    try {
      await operation.start(`/api/iptv/providers/${activeProviderId}/movies/ai/${action}-jobs`, metadataSelectionPayload(), { followUp: false });
    } catch { /* The saved job control displays request errors beside the buttons. */ }
    finally { aiStartPending.current = false; }
  }

  async function createBulkMatchJob(method) {
    if (method === 'ai' && ai.provider === 'chatgpt') {
      return startMetadataAI(aiMatching, 'match');
    }
    setProposalBusy(true);
    setError('');
    try {
      const job = await iptvApi.createMovieMatchJob(activeProviderId, {
        ...metadataSelectionPayload(), method
      });
      setProposalJob(job);
      setLastProposalJob(job);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProposalBusy(false);
    }
  }

  const previewAIClassification = () => startMetadataAI(aiClassification, 'classification');
  async function startBulkMetadata(titlesPerRequest) {
    if (aiStartPending.current) return;
    aiStartPending.current = true;
    try {
      await aiBulk.start(bulkEndpoint, { ...metadataSelectionPayload(),
        titles_per_request: titlesPerRequest, expected_source_count: metadataSelectedCount }, { followUp: false });
    } catch (failure) {
      if (failure.code === 'bulk_selection_count_changed') {
        setMetadataPane('catalog');
        setMetadataAllFiltered(false);
        setMetadataSelection(new Set());
        refreshMovieData();
        setError(failure.message);
      } else if (failure.code === 'iptv_projection_in_progress') {
        setPreparationFailure({ providerId: activeProviderId, message: failure.message });
        refreshMovieData();
      }
    }
    finally { aiStartPending.current = false; }
  }
  async function aiProposalChanged() {
    await Promise.all([aiClassification.reload(), aiMatching.reload()]);
    setMetadataSelection(new Set()); setMetadataAllFiltered(false); refreshMovieData();
  }

  async function applyBulkMatchJob(proposalIds) {
    if (!proposalJob) return;
    setProposalBusy(true);
    try {
      const result = await iptvApi.applyMovieMatchJob(activeProviderId, proposalJob.job_id, { proposal_ids: proposalIds });
      setProposalJob(result.job);
      setLastProposalJob(result.job);
      notify?.(`${formatCount(result.applied?.length || 0)} IPTV metadata proposals applied`);
      setMetadataSelection(new Set());
      setMetadataAllFiltered(false);
      refreshMovieData();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProposalBusy(false);
    }
  }

  async function cancelBulkMatchJob() {
    if (!proposalJob) return;
    try {
      const cancelled = await iptvApi.cancelMovieMatchJob(activeProviderId, proposalJob.job_id);
      setProposalJob(cancelled);
      setLastProposalJob(cancelled);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function reopenLastMatchJob(reference) {
    if (lastProposalJob?.job_id === reference.job_id) { setProposalJob(lastProposalJob); return; }
    const providerId = activeProviderId;
    setProposalBusy(true);
    try {
      const job = await iptvApi.movieMatchJob(providerId, reference.job_id);
      if (activeProviderRef.current === providerId) { setLastProposalJob(job); setProposalJob(job); }
    } catch (failure) {
      if (activeProviderRef.current === providerId) setError(failure.message);
    } finally {
      if (activeProviderRef.current === providerId) setProposalBusy(false);
    }
  }

  async function closePlayback() {
    try { await playbackSession.stop(); }
    catch (requestError) { setError(requestError.message); }
  }

  async function selectChannel(channel) {
    setSelectedLive(channel);
    setEpg([]);
    const requestedProviderId = activeProviderId;
    iptvApi.epg(requestedProviderId, channel.item_id)
      .then((result) => {
        if (activeProviderRef.current === requestedProviderId) setEpg(result.items || []);
      })
      .catch(() => {
        if (activeProviderRef.current === requestedProviderId) setEpg([]);
      });
    await playItem(channel);
  }

  const tmdbReadiness = <>
    {readinessError && <div role="alert">{readinessError} <Button  type="button"
      onClick={() => setReadinessRefresh(value => value + 1)}>Retry readiness</Button></div>}
    {metadataSettings && !metadataSettings.tmdb_configured &&
      <a href="/settings#settings-iptv" onClick={event => { if (onOpenSettings) { event.preventDefault(); onOpenSettings(); } }}>
        Set up IPTV TMDB in Settings
      </a>}
  </>;
  const overlays = <>
      {playback && playback.kind !== 'live' ? (
        <div className="iptv-playback-backdrop" role="presentation" onClick={closePlayback}>
    <div className="iptv-playback-dialog" onClick={(event) => event.stopPropagation()}>
      <IPTVPlayer playback={playback} onClose={closePlayback} />
    </div>
        </div>
      ) : null}
      <IPTVListPickerModal
        item={listPickerItem}
        lists={listPickerLists}
        busy={listPickerBusy}
        newName={listPickerName}
        onNewName={setListPickerName}
        onCreate={createPickerList}
        onToggle={togglePickerList}
        onClose={() => { if (!listPickerBusy) setListPickerItem(null); }}
      />
      <SourceChooserModal chooser={sourceChooser} onChoose={chooseMovieSource} onClose={() => setSourceChooser(null)} />
      <MatchMetadataModal
        movie={matchDialog}
        query={matchQuery}
        year={matchYear}
        results={matchResults}
        busy={matchBusy}
        onQuery={setMatchQuery}
        onYear={setMatchYear}
        onSearch={searchMatchMetadata}
        onApply={applyMovieMatch}
        onClose={() => { if (!matchBusy) setMatchDialog(null); }}
      />
  </>;

  if (reviewProvider) return <div className="iptv-recovery-workspace">
    {error && <div role="alert" className="iptv-error"><span>{error}</span>
      <Button type="button" onClick={() => setError('')} aria-label="Dismiss error"><X size={16} /></Button></div>}
    <nav className="iptv-metadata-subtabs" aria-label="Recovery sections">
      <button type="button" className={metadataSurface === 'catalog' ? 'is-active' : ''}
        aria-pressed={metadataSurface === 'catalog'} onClick={() => setMetadataPane('catalog')}>Unmatched</button>
      <button type="button" className={metadataSurface === 'bulk' ? 'is-active' : ''}
        aria-pressed={metadataSurface === 'bulk'} onClick={() => setMetadataPane('bulk')}>ChatGPT matching</button>
    </nav>
    {tmdbReadiness}
    {metadataSurface === 'catalog' && ai.provider === 'ollama' && metadataSettings && !metadataSettings.ollama_enabled &&
      <a href="/settings#settings-iptv" onClick={event => { if (onOpenSettings) { event.preventDefault(); onOpenSettings(); } }}>
        Set up IPTV Ollama in Settings
      </a>}
    {metadataSurface === 'bulk' && <>
      {!matchingReady && <p className="settings-empty-note">To start a scan, select ChatGPT and enable IPTV title sharing in <a href="/settings">AI Settings</a>.</p>}
      <IPTVBulkMetadataJob key={`${activeProviderId}:${ai.config?.chatgpt?.active_account_id}`}
        operation={aiBulk} endpoint={bulkEndpoint}
        providerName={reviewProvider.name}
        canStart={movieStatusCurrent && movieStatus?.projection?.state === 'complete' &&
          !metadataReviewLoading && !metadataReviewError && !proposalBusy && metadataSelectedCount > 0 &&
          ai.provider === 'chatgpt' && matchingReady && Boolean(metadataSettings?.tmdb_configured)}
        projection={movieStatus?.projection} preparationCurrent={movieStatusCurrent} preparationError={workerStatusError}
        resumeReady={movieStatusCurrent && movieStatus?.projection?.state === 'complete' && matchingReady &&
          Boolean(metadataSettings?.tmdb_configured)}
        onResume={extraCalls => { setMetadataPane('bulk'); return aiBulk.continueJob(extraCalls); }}
        selectionLoading={metadataReviewLoading} selectionError={metadataReviewError}
        onRetryReadiness={refreshMovieData} onRetrySelection={() => setMetadataReviewRetry(value => value + 1)}
        selectedCount={metadataSelectedCount} onStart={startBulkMetadata} onManualMatch={openMatchMetadata}
        selectedQueue="Unmatched"
        savedQueue={SAVED_REVIEW_LABELS[aiBulk.job?.bulk?.selection_scope?.filters?.review_view]}
        onApplied={refreshMovieData} />
    </>}
    {metadataSurface === 'catalog' && <>
      <MetadataReviewWorkspace providerId={activeProviderId} review={metadataReview}
        loading={metadataReviewLoading} error={metadataReviewError} filters={metadataFilters} facets={movieFacets}
        facetError={facetError} onRetryFacets={() => setFacetRefresh(value => value + 1)}
        onRetry={() => setMetadataReviewRetry(value => value + 1)}
        onFilter={(name, value) => { setMetadataFilters(current => ({ ...current, [name]: value })); setMetadataPage(1); setMetadataSelection(new Set()); setMetadataAllFiltered(false); }}
        onSelect={toggleMetadataSelection} onSelectPage={selectMetadataPage}
        onSelectAllFiltered={() => { setMetadataSelection(new Set()); setMetadataAllFiltered(true); }}
        onClearSelection={() => { setMetadataSelection(new Set()); setMetadataAllFiltered(false); }}
        selection={metadataSelection} allFiltered={metadataAllFiltered}
        busy={proposalBusy || aiClassification.busy || aiMatching.busy || jobIsRunning(aiClassification.job) || jobIsRunning(aiMatching.job)}
        onUseSelection={() => setMetadataPane('bulk')} onClassify={previewBulkClassification}
        onAIClassify={previewAIClassification} onMatchSelected={createBulkMatchJob}
        tmdbConfigured={Boolean(metadataSettings?.tmdb_configured)}
        ollamaConfigured={ai.provider === 'chatgpt' ? matchingReady : Boolean(metadataSettings?.ollama_enabled)}
        chatgptSelected={ai.provider === 'chatgpt'} aiClassificationAvailable={Boolean(aiFeatures.find(row => row.id === 'F4')?.ready)}
        standardProposalRefs={standardProposalRefs}
        workerStatusError={workerStatusError} onRetryWorkerStatus={refreshMovieData} onReopenMatchJob={reopenLastMatchJob}
        selectedId={selectedId} detail={detail} detailLoading={detailLoading} locale={movieLocale}
        onToggle={openDetail} onPlay={playItem} onFavorite={toggleFavorite} onAddToList={openListPicker}
        onMatch={openMatchMetadata} onRemoveMatch={removeMovieMatch} onLocale={switchMovieLocale} />
      {!metadataReviewLoading && <Pagination page={metadataReview.page} totalPages={Math.max(1, Math.ceil(metadataReview.total / metadataReview.page_size))}
        onPageChange={setMetadataPage} ariaLabel="IPTV metadata pagination" previousAriaLabel="Previous IPTV page" nextAriaLabel="Next IPTV page" />}
      {classificationPreview && <ClassificationPreviewPanel preview={classificationPreview}
        busy={proposalBusy} onApply={applyBulkClassification} onCancel={() => setClassificationPreview(null)} />}
      {proposalJob && <MatchProposalPanel job={proposalJob} busy={proposalBusy} onApply={applyBulkMatchJob}
        onCancel={cancelBulkMatchJob} onClose={() => setProposalJob(null)} onManualMatch={openMatchMetadata} />}
      {[aiClassification, aiMatching].map((operation, index) => <div key={index}>
        <AIJobStatus operation={operation} title={index === 0 ? 'ChatGPT IPTV classification' : 'ChatGPT IPTV matching'} />
        {operation.job?.output?.prepared_review && <AIActionReview view={operation.job.output.prepared_review}
          onChanged={aiProposalChanged} notify={notify} disabled={operation.job.state === 'cancelled'} />}
      </div>)}
    </>}
    {overlays}
  </div>;

  if (loading && !status) return <div className="iptv-loading"><Loader2 className="spin" size={22} /> Loading IPTV...</div>;

  return (
    <IPTVPeopleNavigationContext.Provider value={{ onBrowse: browseIPTVPerson, onDiscover: onOpenDiscoverPerson }}>
    <section className="iptv-workspace" ref={peopleWorkspaceRef}>
      <SectionTabs as="nav"  aria-label="IPTV sections">
        {TABS.map(({ id, label, icon: Icon }) => (
          <SectionTab type="button" key={id} className={activeTab === id ? 'discover-tab-active' : ''} onClick={() => selectTab(id)}>
            <Icon size={17} /> {label}
          </SectionTab>
        ))}
      </SectionTabs>

      <div className="iptv-header-status iptv-provider-controls">
        {providers.length ? (
          <label className="iptv-provider-select">
            <ServerCog size={15} />
            <Select aria-label="Active IPTV provider" value={activeProviderId} onChange={(event) => switchProvider(event.target.value)}>
              {providers.map((provider) => <option key={provider.provider_id} value={provider.provider_id}>{provider.name}</option>)}
            </Select>
          </label>
        ) : <span><ServerCog size={15} /> No providers</span>}
        {status?.configured ? (
          <Button size="icon" type="button"  onClick={syncCatalog} disabled={status?.sync?.state === 'running'} aria-label="Sync IPTV catalog" title="Sync catalog">
            <RefreshCcw size={17} className={status?.sync?.state === 'running' ? 'spin' : ''} />
          </Button>
        ) : null}
      </div>

      {error ? <div className="iptv-error"><span>{error}</span><Button type="button" onClick={() => setError('')} aria-label="Dismiss error"><X size={16} /></Button></div> : null}
      {!activeProviderId ? <IPTVSetupRequired /> : null}
      {status?.configured && status?.sync?.state === 'running' ? <SyncBanner status={status.sync} /> : null}
      {status?.configured && status?.sync?.state === 'error' ? <div className="iptv-error"><span>{status.sync.error}</span></div> : null}

      {status?.configured && activeTab === 'home' ? (
        <IPTVHome providerId={activeProviderId} status={status} recent={recent} onBrowse={selectTab} onPlay={playItem} onFavorite={toggleFavorite} onAddToList={openListPicker} />
      ) : null}
      {personContext && activeTab === 'movie' && <div className="card-actions">
        <Button type="button"  onClick={restoreIPTVPeopleView}
          aria-label="Back to previous IPTV view">Back</Button>
        <strong>{personContext.name} · {providers.find(provider => provider.provider_id === activeProviderId)?.name}</strong>
      </div>}
      {status?.configured && isBrowseTab ? (
        <>
          {activeTab === 'movie' ? (
            <MovieToolbar
              filters={movieFilters}
              facets={movieFacets}
              total={catalog.total}
              onFilter={updateMovieFilter}
              onReset={() => {
                setMovieFilters({ ...createIPTVMovieFilters(), view: movieFilters.view,
                  ...(personContext ? { category: 'film', person_id: movieFilters.person_id, person_role: movieFilters.person_role } : {}) });
                setPage(1); setSelectedId(''); setDetail(null);
              }}
            />
          ) : (
            <BrowseToolbar
              kind={browseKind}
              categories={categories[browseKind] || []}
              categoryId={categoryId}
              onCategory={(value) => { setCategoryId(value); setPage(1); }}
              query={query}
              onQuery={(value) => { setQuery(value); setPage(1); }}
              activeTab={activeTab}
              favoriteKind={favoriteKind}
              onFavoriteKind={(value) => { setFavoriteKind(value); setCategoryId(''); setPage(1); setSelectedId(''); setDetail(null); }}
              total={catalog.total}
            />
          )}
          {activeTab === 'favorites' ? (
            <FavoritesView
              providerId={activeProviderId}
              catalog={catalog}
              followed={followed}
              selectedId={selectedId}
              detail={detail}
              detailLoading={detailLoading}
              selectedSeason={selectedSeason}
              onSeason={setSelectedSeason}
              onToggle={openDetail}
              onPlay={playItem}
              onFavorite={toggleFavorite}
              onAddToList={openListPicker}
              onOpenChannel={(channel) => { selectTab('live'); selectChannel(channel); }}
              loading={loading}
              gridRef={activeCardGridRef}
            />
          ) : browseKind === 'live' ? (
            <LiveView
              providerId={activeProviderId}
              categories={categories.live || []}
              categoryId={categoryId}
              onCategory={(value) => { setCategoryId(value); setPage(1); }}
              catalog={catalog}
              selected={selectedLive}
              epg={epg}
              playback={playback}
              loading={loading || playbackLoading}
              onSelect={selectChannel}
              onFavorite={toggleFavorite}
              onAddToList={openListPicker}
              onClosePlayback={closePlayback}
            />
          ) : browseKind === 'movie' ? (
            <MovieView
              providerId={activeProviderId}
              catalog={catalog}
              followed={followed}
              selectedId={selectedId}
              detail={detail}
              detailLoading={detailLoading}
              onToggle={openDetail}
              onPlay={playItem}
              onFavorite={toggleFavorite}
              onAddToList={openListPicker}
              onMatch={openMatchMetadata}
              onRemoveMatch={removeMovieMatch}
              personContext={personContext}
              providerName={providers.find(provider => provider.provider_id === activeProviderId)?.name}
              projection={catalog.projection || movieStatus?.projection}
              locale={movieLocale}
              onLocale={switchMovieLocale}
              onRetryProjection={retryProjection}
              loading={movieLoading}
              gridRef={activeCardGridRef}
            />
          ) : (
            <SeriesView providerId={activeProviderId} catalog={catalog} detail={detail} detailLoading={detailLoading} selectedId={selectedId} selectedSeason={selectedSeason} onSeason={setSelectedSeason} onToggle={openDetail} onPlay={playItem} onFavorite={toggleFavorite} onAddToList={openListPicker} gridRef={activeCardGridRef} />
          )}
          <Pagination page={catalog.page || page} totalPages={Math.max(1, Math.ceil((catalog.total || 0) / (catalog.page_size || browsePageSize)))} onPageChange={setPage} ariaLabel="IPTV pagination" previousAriaLabel="Previous IPTV page" nextAriaLabel="Next IPTV page" />
        </>
      ) : null}

      {status?.configured && activeTab === 'metadata' && (
        <section className="iptv-metadata-dashboard">
          <header className="iptv-metadata-header">
            <div><p className="screen-kicker">Provider-local Movies metadata</p>
              <h2>{activeProvider?.name || 'Selected provider'}</h2></div>
          </header>
          {tmdbReadiness}
          <IPTVEnrichmentPanel worker={movieStatus}
            current={movieStatusCurrent && Number(movieStatus?.projection?.source_generation) >= Number(status.generation || 0)}
            syncing={syncRequested === activeProviderId || status?.sync?.state === 'running'}
            settings={metadataSettings} control={enrichmentControl} controlError={enrichmentError}
            statusError={workerStatusError} onControl={requestEnrichment} onRetryProjection={retryProjection}
            onRefresh={refreshMovieData} />
        </section>
      )}

      {status?.configured && activeTab === 'lists' ? (
        <IPTVListsWorkspace
          providerId={activeProviderId}
          lists={lists}
          selectedListId={selectedListId}
          catalog={listCatalog}
          loading={listLoading}
          query={listQuery}
          kindFilter={listKind}
          newListName={newListName}
          renameName={renameListName}
          onSelectList={(value) => { setSelectedListId(value); setListPage(1); setListQuery(''); setListKind('all'); }}
          onQuery={(value) => { setListQuery(value); setListPage(1); }}
          onKindFilter={(value) => { setListKind(value); setListPage(1); }}
          onNewListName={setNewListName}
          onRenameName={setRenameListName}
          onCreate={createIPTVList}
          onRename={renameIPTVList}
          onDelete={deleteIPTVList}
          onRemove={removeIPTVListItem}
          onMove={moveIPTVListItem}
          onPlay={playListItem}
          onOpen={openListItem}
          onPage={setListPage}
        />
      ) : null}

      {overlays}
    </section>
    </IPTVPeopleNavigationContext.Provider>
  );
}

function IPTVSetupRequired() {
  return (
    <div className="iptv-setup">
      <ServerCog size={34} />
      <div><strong>Connect an Xtream provider first</strong><span>Enter the server, username, and password in Settings. Cinema Paradiso does not supply IPTV subscriptions.</span></div>
      <Button variant="primary" type="button"  onClick={() => window.location.assign('/settings#settings-iptv')}>Open Settings</Button>
    </div>
  );
}

function SyncBanner({ status }) {
  return <div className="iptv-sync"><Loader2 className="spin" size={16} /><strong>{status.phase || 'Syncing IPTV catalog'}</strong><span>The current catalog remains usable until the replacement is complete.</span></div>;
}

function IPTVHome({ providerId, status, recent, onBrowse, onPlay, onFavorite, onAddToList }) {
  const counts = status.counts || {};
  return (
    <div className="iptv-home">
      <div className="iptv-stat-grid">
        <HomeStat icon={Radio} label="Live channels" count={counts.live} onClick={() => onBrowse('live')} />
        <HomeStat icon={Film} label="Provider movies" count={counts.movie} onClick={() => onBrowse('movie')} />
        <HomeStat icon={Tv} label="Provider series" count={counts.series} onClick={() => onBrowse('series')} />
      </div>
      <section className="iptv-home-section">
        <header><div><p className="screen-kicker">Continue watching</p><h2>Recent IPTV</h2></div><Clock3 size={20} /></header>
        {recent.length ? (
          <div className="iptv-recent-row">
            {recent.map((item) => <PosterTile providerId={providerId} key={`${item.kind}-${item.item_id}`} item={item} onClick={() => item.kind === 'movie' ? onPlay(item) : onBrowse(item.kind)} onFavorite={onFavorite} onAddToList={onAddToList} />)}
          </div>
        ) : <WorkspaceEmptyState size="compact" ><ListVideo size={28} /><span>Played movies and series will appear here.</span></WorkspaceEmptyState>}
      </section>
    </div>
  );
}

function HomeStat({ icon: Icon, label, count = 0, onClick }) {
  return <button type="button" className="iptv-stat" onClick={onClick}><span><Icon size={21} /></span><strong>{formatCount(count)}</strong><small>{label}</small><ChevronRight size={18} /></button>;
}

function BrowseToolbar({ kind, categories, categoryId, onCategory, query, onQuery, activeTab, favoriteKind, onFavoriteKind, total }) {
  return (
    <div className={`iptv-browse-toolbar ${activeTab === 'favorites' ? 'is-favorites' : ''}`}>
      {activeTab === 'favorites' ? (
        <div className="iptv-segmented" aria-label="Favorite type">
          {[['all', 'All'], ['live', 'Channels'], ['movie', 'Movies'], ['series', 'Series']].map(([id, label]) => <button type="button" key={id} className={favoriteKind === id ? 'is-active' : ''} onClick={() => onFavoriteKind(id)}>{label}</button>)}
        </div>
      ) : <strong>{kind === 'live' ? 'Live channels' : kind === 'movie' ? 'Movies' : 'Series'}</strong>}
      {activeTab !== 'favorites' ? <label className="iptv-category-select">
        <Layers3 size={16} />
        <Select value={categoryId} onChange={(event) => onCategory(event.target.value)} aria-label="Provider category">
          <option value="">All provider categories</option>
          {categories.map((category) => <option value={category.category_id} key={category.category_id}>{category.name} ({formatCount(category.item_count)})</option>)}
        </Select>
      </label> : null}
      <SearchField className="iptv-search"><Search size={16} /><Input value={query} onChange={(event) => onQuery(event.target.value)} placeholder={activeTab === 'favorites' ? 'Search favorites...' : `Search ${kind === 'live' ? 'channels' : kind}...`} dir="auto" /></SearchField>
      <span>{formatCount(total)} results</span>
    </div>
  );
}

function MovieToolbar({ filters, facets, total, onFilter, onReset }) {
  const cpView = filters.view === 'cp';
  return (
    <div className="iptv-movie-toolbar">
      <div className="iptv-movie-view-switch" role="group" aria-label="IPTV Movies view">
        {IPTV_MOVIE_VIEWS.map(([id, label]) => <button type="button" key={id} className={filters.view === id ? 'is-active' : ''} aria-pressed={filters.view === id} onClick={() => onFilter('view', id)}>{label}</button>)}
      </div>
      <div className="iptv-movie-toolbar-primary">
        <strong>{cpView ? 'CP View' : 'Provider View'}</strong>
        <label><span>Provider playlist</span><Select value={filters.playlist_id} onChange={(event) => onFilter('playlist_id', event.target.value)} aria-label="Provider playlist"><option value="">All provider playlists</option>{facets.playlists.map((playlist) => <option key={playlist.id} value={playlist.id}>{playlist.name} ({formatCount(playlist.source_count)})</option>)}</Select></label>
        <label><span>My list</span><Select value={filters.list_id} onChange={(event) => onFilter('list_id', event.target.value)} aria-label="My list"><option value="">All movies</option>{facets.lists.map((list) => <option key={list.list_id} value={list.list_id}>{list.name} ({formatCount(list.movie_count)})</option>)}</Select></label>
        <SearchField className="iptv-search"><Search size={16} /><Input value={filters.q} onChange={(event) => onFilter('q', event.target.value)} placeholder="Search movie..." dir="auto" /></SearchField>
        <label><span>Sort</span><Select value={filters.sort} onChange={(event) => onFilter('sort', event.target.value)}>{IPTV_MOVIE_SORTS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</Select></label>
        <span>{formatCount(total)} results</span>
      </div>
      {cpView ? <div className="iptv-movie-category-row" role="group" aria-label="IPTV Movies category">
        <button type="button" className={!filters.category ? 'is-active' : ''} onClick={() => onFilter('category', '')}>All categories</button>
        {IPTV_MOVIE_CATEGORIES.map(([id, label]) => {
          const facet = facets.categories?.find((row) => row.id === id);
          return <button type="button" key={id} className={filters.category === id ? 'is-active' : ''} onClick={() => onFilter('category', id)}>{label} <small>{formatCount(facet?.source_count || 0)}</small></button>;
        })}
      </div> : <p className="iptv-provider-view-note">Every provider movie source remains visible here, whether classified, matched, or unresolved.</p>}
      {cpView ? <div className="iptv-movie-filter-row">
        <label><span>Genre</span><Select value={filters.genre_id} onChange={(event) => onFilter('genre_id', event.target.value)}><option value="">All genres</option>{facets.genres.map((genre) => <option key={genre.id} value={genre.id}>{genre.name}</option>)}</Select></label>
        <label title="Language remains the existing matched-metadata filter; its parked semantics are unchanged."><span>Language (matched metadata)</span><Select value={filters.language} onChange={(event) => onFilter('language', event.target.value)}><option value="">All languages</option>{facets.languages.map((language) => <option key={language.code} value={language.code}>{language.name || language.code}</option>)}</Select></label>
        <label><span>Country</span><Select value={filters.country} onChange={(event) => onFilter('country', event.target.value)}><option value="">All countries</option>{facets.countries.map((country) => <option key={country.code} value={country.code}>{country.name || country.code}</option>)}</Select></label>
        <label><span>From</span><Input type="number" min="1888" max="2200" value={filters.year_from} onChange={(event) => onFilter('year_from', event.target.value)} placeholder="Year" /></label>
        <label><span>To</span><Input type="number" min="1888" max="2200" value={filters.year_to} onChange={(event) => onFilter('year_to', event.target.value)} placeholder="Year" /></label>
        <label><span>Rating</span><Select value={filters.min_rating} onChange={(event) => onFilter('min_rating', event.target.value)}><option value="">Any rating</option>{[5, 6, 7, 8, 9].map((rating) => <option key={rating} value={rating}>{rating}+</option>)}</Select></label>
        <label><span>Metadata</span><Select value={filters.metadata_status} onChange={(event) => onFilter('metadata_status', event.target.value)}><option value="">All states</option><option value="matched">Matched</option><option value="unmatched">Unmatched</option><option value="ambiguous">Ambiguous</option><option value="failed">Failed</option><option value="unprocessed">Unprocessed</option></Select></label>
        <label><span>Claimed quality</span><Select value={filters.quality} onChange={(event) => onFilter('quality', event.target.value)}><option value="">Any quality</option>{facets.qualities.map((quality) => <option key={quality} value={quality}>{quality}</option>)}</Select></label>
        <label><span>Watched</span><Select value={filters.watched} onChange={(event) => onFilter('watched', event.target.value)}><option value="">Any state</option><option value="unwatched">Unwatched</option><option value="watched">Watched</option></Select></label>
        <label className="iptv-claim-check"><input type="checkbox" checked={filters.dubbed} onChange={(event) => onFilter('dubbed', event.target.checked)} /> Dubbed claim</label>
        <label className="iptv-claim-check"><input type="checkbox" checked={filters.subtitled} onChange={(event) => onFilter('subtitled', event.target.checked)} /> Subtitle claim</label>
        <Button type="button"  onClick={onReset}>Reset filters</Button>
      </div> : <div className="iptv-movie-filter-row iptv-provider-view-actions"><Button type="button"  onClick={onReset}>Reset filters</Button></div>}
    </div>
  );
}

function metadataReviewMovie(item) {
  return {
    ...item,
    movie_key: `source:${item.source_key}`,
    name: item.provider_title,
    title: item.provider_title,
    year: item.provider_year,
    kind: 'movie',
    item_id: item.source_id,
    source_count: 1,
    matched: Boolean(item.tmdb_id),
    metadata_status: item.state,
    unmatched_reason: item.state === 'ambiguous' ? 'Uncertain match' :
      item.state === 'unprocessed' ? 'Category unknown' : 'No verified match'
  };
}

function MetadataReviewWorkspace({ providerId, review, loading, error, filters, facets, facetError,
  workerStatusError, selection, allFiltered, busy, tmdbConfigured, ollamaConfigured,
  selectedId, detail, detailLoading, locale, onFilter, onRetry, onRetryFacets, onRetryWorkerStatus,
  onSelect, onSelectPage, onSelectAllFiltered, onClearSelection, onUseSelection, onClassify, onMatchSelected,
  onToggle, onPlay, onFavorite, onAddToList, onMatch, onRemoveMatch, onLocale, standardProposalRefs,
  onReopenMatchJob, chatgptSelected, aiClassificationAvailable, onAIClassify }) {
  const selectedCount = allFiltered ? Number(review.total || 0) : selection.size;
  const selectionLimit = Number(review.selection_limit || 5000);
  const overLimit = selectedCount > selectionLimit;
  const canSelect = selectedCount > 0 && !busy && !loading;
  const canAct = canSelect && !overLimit;
  return (
    <section className="iptv-review-workspace" aria-label="Unmatched listings">
      <div className="iptv-review-filters">
        <SearchField className="iptv-search"><Search size={16} /><Input value={filters.q} onChange={(event) => onFilter('q', event.target.value)} placeholder="Search unmatched listings..." dir="auto" /></SearchField>
        <Select aria-label="Filter by category" value={filters.category} onChange={(event) => onFilter('category', event.target.value)}><option value="">All categories</option>{IPTV_MOVIE_CATEGORIES.map(([id, label]) => <option value={id} key={id}>{label}</option>)}</Select>
        <Select aria-label="Review provider playlist" value={filters.playlist_id} onChange={(event) => onFilter('playlist_id', event.target.value)}><option value="">All provider playlists</option>{facets.playlists.map((playlist) => <option value={playlist.id} key={playlist.id}>{playlist.name}</option>)}</Select>
      </div>
      {facetError && <p role="alert">Playlists could not load. <Button type="button"
        onClick={onRetryFacets}>Retry playlists</Button></p>}
      {workerStatusError && <p role="alert">Provider worker status could not load. <Button type="button"
        onClick={onRetryWorkerStatus}>Retry worker status</Button></p>}
      {!loading && <p role="status">Unmatched · {formatCount(review.total)} listings</p>}
      <div className="iptv-selection-toolbar">
        <strong>{allFiltered && loading ? 'Checking filtered selection…' : allFiltered ?
          `${formatCount(review.total)} filtered sources selected` : `${formatCount(selection.size)} selected`}</strong>
        <Button type="button"  disabled={!review.items?.length || busy || loading} onClick={onSelectPage}><CheckSquare size={15} /> Add current page</Button>
        <Button type="button"  disabled={!review.total || busy || loading} onClick={onSelectAllFiltered}>Select all filtered</Button>
        <Button type="button"  disabled={!selectedCount || busy || loading} onClick={onClearSelection}>Clear selection</Button>
        <Button variant="primary" type="button"  disabled={!canSelect} onClick={onUseSelection}>Match with ChatGPT</Button>
      </div>
      <details className="iptv-rebuild-controls">
        <summary>Actions</summary>
        {overLimit && !loading && <p role="alert" className="library-status library-status-error"><CircleAlert size={16} /> Standard actions accept up to {formatCount(selectionLimit)} sources per job. Add the current page or narrow the filters for those actions.</p>}
        <div className="iptv-bulk-actions">
          <span>Classify selected</span>
          {IPTV_MOVIE_CATEGORIES.map(([id, label]) => <Button type="button"  key={id} disabled={!canAct} onClick={() => onClassify(id)}>{label}</Button>)}
          {chatgptSelected && <Button type="button"  disabled={!canAct || !aiClassificationAvailable}
            title={aiClassificationAvailable ? 'Prepare a classification review; nothing applies automatically' : 'Connect ChatGPT and enable IPTV title sharing in AI Settings'}
            onClick={onAIClassify}><WandSparkles size={15} /> Classify selected with ChatGPT</Button>}
          <Button type="button"  disabled={!canAct || !tmdbConfigured} onClick={() => onMatchSelected('tmdb')}><WandSparkles size={15} /> Match selected with TMDB</Button>
          <Button type="button"  disabled={!canAct || !tmdbConfigured || !ollamaConfigured} onClick={() => onMatchSelected('ai')}><WandSparkles size={15} /> {chatgptSelected ? 'Match selected with ChatGPT' : 'Match selected with AI'}</Button>
          {standardProposalRefs.map(job => <Button type="button"  key={job.job_id}
            disabled={busy} onClick={() => onReopenMatchJob(job)}>Reopen last {job.method === 'ai' ? 'AI-assisted' : 'TMDB'} proposal</Button>)}
        </div>
        {chatgptSelected && <p className="settings-empty-note">ChatGPT is selected for AI assistance. <a href="/settings">AI Settings</a></p>}
      </details>
      {error ? <div role="alert" className="iptv-error"><span>Unmatched listings could not load. {error}</span>
        <Button type="button"  onClick={onRetry}>Retry review</Button></div> :
        loading ? <WorkspaceEmptyState size="compact" role="status" className="iptv-grid-empty"><Loader2 className="spin" size={28} /><strong>Loading unmatched listings</strong></WorkspaceEmptyState> : null}
      {!loading && !review.items?.length && <WorkspaceEmptyState size="compact" ><Database size={28} /><span>No unmatched listings match these filters.</span></WorkspaceEmptyState>}
      {!loading && review.items?.length ? <div className="discover-grid iptv-movie-grid iptv-review-card-grid">{review.items.map((item) => {
        const movie = metadataReviewMovie(item);
        return <IPTVMovieCard key={item.source_key} providerId={providerId} movie={movie} selectedId={selectedId} detail={detail} detailLoading={detailLoading} onToggle={onToggle} onPlay={onPlay} onFavorite={onFavorite} onAddToList={onAddToList} onMatch={onMatch} onRemoveMatch={onRemoveMatch} locale={locale} onLocale={onLocale} selectable checked={allFiltered || selection.has(item.source_key)} onSelect={() => onSelect(item.source_key)} />;
      })}</div> : null}
    </section>
  );
}

function LiveView({ providerId, categories, categoryId, onCategory, catalog, selected, epg, playback, loading, onSelect, onFavorite, onAddToList, onClosePlayback }) {
  return (
    <div className="iptv-live-layout">
      <aside className="iptv-category-rail">
        <button type="button" className={!categoryId ? 'is-active' : ''} onClick={() => onCategory('')}><span>All channels</span><small>{formatCount(catalog.total)}</small></button>
        {categories.map((category) => <button type="button" key={category.category_id} className={categoryId === category.category_id ? 'is-active' : ''} onClick={() => onCategory(category.category_id)}><span dir="auto">{category.name}</span><small>{formatCount(category.item_count)}</small></button>)}
      </aside>
      <section className="iptv-channel-list" aria-label="Channels">
        {catalog.items.map((channel) => (
          <button type="button" key={channel.item_id} className={selected?.item_id === channel.item_id ? 'is-active' : ''} onClick={() => onSelect(channel)}>
            <span className="iptv-channel-number">{channel.channel_num || '–'}</span>
            <span className="iptv-channel-logo"><ProviderImage src={channel.image_url ? iptvImage(providerId, 'live', channel.item_id) : ''} alt="" fallback={Radio} /></span>
            <span className="iptv-channel-name" dir="auto">{channel.name}</span>
            <span className="iptv-live-mark">Live</span>
            <span className="iptv-row-favorite" role="button" tabIndex="0" onClick={(event) => { event.stopPropagation(); onFavorite(channel); }} aria-label={`${channel.favorite ? 'Remove' : 'Add'} favorite`}><Heart size={15} fill={channel.favorite ? 'currentColor' : 'none'} /></span>
            <span className="iptv-row-list" role="button" tabIndex="0" onClick={(event) => { event.stopPropagation(); onAddToList(channel); }} aria-label={`Add ${channel.name} to list`} title="Add to list"><ListPlus size={15} /></span>
          </button>
        ))}
        {!catalog.items.length && !loading ? <WorkspaceEmptyState size="compact" ><Radio size={28} /><span>No channels in this view.</span></WorkspaceEmptyState> : null}
      </section>
      <div className="iptv-live-player-column">
        <IPTVPlayer playback={playback?.kind === 'live' ? playback : null} compact onClose={playback?.kind === 'live' ? onClosePlayback : undefined} />
        {selected ? <div className="iptv-guide"><header><div><span>Selected channel</span><strong dir="auto">{selected.name}</strong></div><span className="iptv-guide-actions"><Button type="button" onClick={() => onAddToList(selected)} aria-label="Add channel to list" title="Add to list"><ListPlus size={17} /></Button><Button type="button" onClick={() => onFavorite(selected)} aria-label="Toggle channel favorite" title="Favorite"><Heart size={17} fill={selected.favorite ? 'currentColor' : 'none'} /></Button></span></header>{epg.length ? epg.map((entry, index) => <div className="iptv-guide-row" key={`${entry.start || index}-${entry.title || ''}`}><span>{index === 0 ? 'Now' : 'Next'}</span><div><strong dir="auto">{entry.title || 'Untitled program'}</strong>{entry.description ? <small dir="auto">{entry.description}</small> : null}</div></div>) : <p>Program guide is unavailable for this channel.</p>}</div> : null}
      </div>
    </div>
  );
}

function MovieView({ personContext, providerName, providerId, catalog, followed = [], selectedId, detail, detailLoading, onToggle, onPlay, onFavorite, onAddToList, onMatch, onRemoveMatch, projection, locale, onLocale, onRetryProjection, loading, gridRef }) {
  return (
    <div ref={gridRef} className="discover-grid iptv-movie-grid">
      {!loading ? catalog.items.map((movie) => <IPTVMovieCard key={movie.movie_key} providerId={providerId} movie={movie} followed={followed} selectedId={selectedId} detail={detail} detailLoading={detailLoading} onToggle={onToggle} onPlay={onPlay} onFavorite={onFavorite} onAddToList={onAddToList} onMatch={onMatch} onRemoveMatch={onRemoveMatch} locale={locale} onLocale={onLocale} />) : null}
      {loading ? <WorkspaceEmptyState size="compact" className="iptv-grid-empty"><Loader2 className="spin" size={30} /><strong>Searching provider movies</strong><span>{catalog.query ? `Filtering for “${catalog.query}”` : 'Loading this provider-scoped view.'}</span></WorkspaceEmptyState> : null}
      {!loading && !catalog.items.length && catalog.failed ? <WorkspaceEmptyState size="compact" className="iptv-grid-empty"><CircleAlert size={30} /><strong>Movies could not be loaded</strong><span>The previous grid was cleared because it does not represent the current search and filters.</span></WorkspaceEmptyState> : null}
      {!loading && !catalog.failed && !catalog.items.length && projection?.state === 'running' ? <WorkspaceEmptyState size="compact" className="iptv-grid-empty"><Loader2 className="spin" size={30} /><strong>Preparing provider movies</strong><span>{formatCount(projection.processed || 0)} of {formatCount(projection.total || 0)} sources projected. Browseable cards will appear in committed batches.</span></WorkspaceEmptyState> : null}
      {!loading && !catalog.failed && !catalog.items.length && ['failed', 'not-started'].includes(projection?.state) ? <WorkspaceEmptyState size="compact" className="iptv-grid-empty"><CircleAlert size={30} /><strong>Provider movie preparation needs attention</strong><span>{projection?.error || 'Projection has not completed.'}</span><Button type="button"  onClick={onRetryProjection}>Retry projection</Button></WorkspaceEmptyState> : null}
      {!loading && !catalog.failed && !catalog.items.length && !['running', 'failed', 'not-started'].includes(projection?.state) ? <WorkspaceEmptyState size="compact" className="iptv-grid-empty"><Film size={30} /><strong>{personContext ? `No matched films for ${personContext.name} in ${providerName}'s saved catalog.` : catalog.query ? `No movies match “${catalog.query}”` : 'No movies in this view'}</strong><span>{catalog.query ? 'Clear or change the search while keeping the selected provider and view.' : 'No provider-local cards match the current filters.'}</span></WorkspaceEmptyState> : null}
    </div>
  );
}

function SeriesView({ providerId, catalog, detail, detailLoading, selectedId, selectedSeason, onSeason, onToggle, onPlay, onFavorite, onAddToList, gridRef }) {
  const seasonNumbers = useMemo(() => [...new Set((detail?.episodes || []).map((episode) => episode.season))].sort((a, b) => a - b), [detail]);
  return (
    <>
      <div ref={gridRef} className="iptv-poster-grid">
        {catalog.items.map((series) => <PosterTile providerId={providerId} key={series.item_id} item={series} active={selectedId === series.item_id} onClick={() => onToggle(series)} onFavorite={onFavorite} onAddToList={onAddToList} />)}
      </div>
      {selectedId ? (
        <section className="iptv-series-detail">
          {detailLoading || !detail ? <div className="iptv-detail-loading"><Loader2 className="spin" size={18} /> Loading seasons...</div> : (
            <>
              <div className="iptv-series-summary">
                <div className="iptv-series-backdrop"><ProviderImage src={detail.backdrop_url ? iptvImage(providerId, 'series', detail.item_id, true) : iptvImage(providerId, 'series', detail.item_id)} fallbackSrc={iptvImage(providerId, 'series', detail.item_id)} alt={`${detail.name} artwork`} fallback={Tv} /></div>
                <div><p className="screen-kicker">Series details</p><h2 dir="auto">{detail.name}</h2><div className="iptv-series-meta">{detail.year ? <span>{String(detail.year).slice(0, 4)}</span> : null}{detail.rating ? <span><Star size={14} fill="currentColor" /> {detail.rating}</span> : null}{detail.genre ? <span dir="auto">{detail.genre}</span> : null}</div><p dir="auto">{detail.plot || 'No plot supplied by the provider.'}</p><div className="iptv-card-actions"><Button type="button"  onClick={() => onFavorite(detail)}><Heart size={15} fill={detail.favorite ? 'currentColor' : 'none'} /> {detail.favorite ? 'Favorited' : 'Favorite'}</Button><Button type="button"  onClick={() => onAddToList(detail)}><ListPlus size={15} /> Add to list</Button></div></div>
              </div>
              <div className="iptv-season-toolbar"><strong>Episodes</strong><div className="iptv-segmented">{seasonNumbers.map((season) => <button type="button" key={season} className={selectedSeason === season ? 'is-active' : ''} onClick={() => onSeason(season)}>Season {season}</button>)}</div></div>
              <div className="iptv-episode-list">{(detail.episodes || []).filter((episode) => episode.season === selectedSeason).map((episode) => <Button type="button" key={episode.id} onClick={() => onPlay(detail, { kind: 'episode', itemId: episode.id, extension: episode.container_extension, title: `${detail.name} · S${episode.season} E${episode.episode} · ${episode.title}`, historyKind: 'series', historyId: detail.item_id })}><span>{episode.episode}</span><div><strong dir="auto">{episode.title}</strong><small dir="auto">{episode.plot || episode.duration || 'Play episode'}</small></div><Play size={18} /></Button>)}</div>
            </>
          )}
        </section>
      ) : null}
      {!catalog.items.length ? <WorkspaceEmptyState size="compact" ><Tv size={30} /><span>No series in this view.</span></WorkspaceEmptyState> : null}
    </>
  );
}

function SourceChooserModal({ chooser, onChoose, onClose }) {
  if (!chooser) return null;
  return (
    <div className="iptv-modal-backdrop" role="presentation" onClick={onClose}>
      <DialogShell size="source" className="iptv-source-dialog" role="dialog" aria-modal="true" aria-label="Choose provider source" onClick={(event) => event.stopPropagation()}>
        <DialogHeader as="header"><div><p className="screen-kicker">Provider-local sources</p><h2 dir="auto">{chooser.movie.name || chooser.movie.title}</h2></div><Button type="button" onClick={onClose} aria-label="Close source chooser"><X size={18} /></Button></DialogHeader>
        <IPTVSourceList sources={chooser.sources} onChoose={onChoose} />
      </DialogShell>
    </div>
  );
}

function MatchMetadataModal({ movie, query, year, results, busy, onQuery, onYear, onSearch, onApply, onClose }) {
  if (!movie) return null;
  const orderedResults = [...results].sort((left, right) => {
    const rank = { validated: 0, plausible: 1, 'low-relevance': 2 };
    return (rank[left.result_class] ?? 1) - (rank[right.result_class] ?? 1) || Number(right.score || 0) - Number(left.score || 0);
  });
  return (
    <div className="iptv-modal-backdrop" role="presentation" onClick={onClose}>
      <DialogShell size="wide" className="iptv-match-dialog" role="dialog" aria-modal="true" aria-label="Match IPTV movie metadata" onClick={(event) => event.stopPropagation()}>
        <DialogHeader as="header"><div><p className="screen-kicker">Provider-local metadata</p><h2>Match metadata</h2><span dir="auto">{movie.provider_title || movie.name}</span></div><Button type="button" onClick={onClose} aria-label="Close metadata matching"><X size={18} /></Button></DialogHeader>
        <div className="iptv-match-search">
          <label><span>Title</span><Input value={query} onChange={(event) => onQuery(event.target.value)} dir="auto" /></label>
          <label><span>Year</span><Input type="number" value={year} onChange={(event) => onYear(event.target.value)} /></label>
          <Button variant="primary" type="button"  disabled={busy || !query.trim()} onClick={onSearch}>{busy ? <Loader2 className="spin" size={15} /> : <Search size={15} />} Search TMDB</Button>
        </div>
        <p className="iptv-match-warning">{movie.category === 'plays' ? 'This source stays in Plays. To look up a known record, enter its ID as tmdb:781869 in the title field.' : 'A selection is locked to this provider until you correct or remove it.'}</p>
        <div className="iptv-match-results">
          {orderedResults.map((candidate) => (
            <article key={candidate.tmdb_id} className={`is-${candidate.result_class || 'plausible'}`}>
              <div className="iptv-match-poster">{candidate.poster_url ? <img src={candidate.poster_url} alt="" /> : <Film size={24} />}</div>
              <div><strong dir="auto">{candidate.title}</strong><span>{candidate.year || 'Year unknown'} · TMDB {candidate.tmdb_id}</span><p dir="auto">{candidate.plot || 'No plot supplied by TMDB.'}</p></div>
              <Button type="button"  disabled={busy} onClick={() => onApply(candidate)}>{candidate.result_class === 'low-relevance' ? 'Review and use' : 'Use this match'}</Button>
            </article>
          ))}
          {!busy && !results.length ? <div className="iptv-match-empty"><WandSparkles size={22} /><span>Search for the correct TMDB movie. Nothing is matched automatically from this dialog.</span></div> : null}
        </div>
      </DialogShell>
    </div>
  );
}

function FavoritesView({ providerId, catalog, followed = [], selectedId, detail, detailLoading, selectedSeason, onSeason, onToggle, onPlay, onFavorite, onAddToList, onOpenChannel, loading, gridRef }) {
  const channels = catalog.items.filter((item) => item.kind === 'live');
  const movies = catalog.items.filter((item) => item.kind === 'movie');
  const series = catalog.items.filter((item) => item.kind === 'series');
  if (!catalog.items.length && !loading) {
    return <WorkspaceEmptyState size="compact" className="iptv-favorites-empty"><Heart size={34} /><strong>No favorites yet</strong><span>Saved channels, movies, and series will appear here.</span></WorkspaceEmptyState>;
  }
  return (
    <div className="iptv-favorites-view">
      {channels.length ? (
        <section className="iptv-favorite-section">
          <header><Radio size={18} /><h2>Channels</h2><span>{formatCount(channels.length)}</span></header>
          <div className="iptv-favorite-channels">
            {channels.map((channel) => (
              <article key={channel.item_id}>
                <button type="button" className="iptv-favorite-channel-main" onClick={() => onOpenChannel(channel)}>
                  <span className="iptv-channel-logo"><ProviderImage src={channel.image_url ? iptvImage(providerId, 'live', channel.item_id) : ''} alt="" fallback={Radio} /></span>
                  <strong dir="auto">{channel.name}</strong>
                  <Play size={17} fill="currentColor" />
                </button>
                <span className="iptv-favorite-channel-actions"><ListActionButton item={channel} onAddToList={onAddToList} /><FavoriteButton item={channel} onFavorite={onFavorite} /></span>
              </article>
            ))}
          </div>
        </section>
      ) : null}
      {movies.length ? (
        <section className="iptv-favorite-section">
          <header><Film size={18} /><h2>Movies</h2><span>{formatCount(movies.length)}</span></header>
          <MovieView providerId={providerId} catalog={{ ...catalog, items: movies }} followed={followed} selectedId={selectedId} detail={detail} detailLoading={detailLoading} onToggle={onToggle} onPlay={onPlay} onFavorite={onFavorite} onAddToList={onAddToList} gridRef={gridRef} />
        </section>
      ) : null}
      {series.length ? (
        <section className="iptv-favorite-section">
          <header><Tv size={18} /><h2>Series</h2><span>{formatCount(series.length)}</span></header>
          <SeriesView providerId={providerId} catalog={{ ...catalog, items: series }} detail={detail} detailLoading={detailLoading} selectedId={selectedId} selectedSeason={selectedSeason} onSeason={onSeason} onToggle={onToggle} onPlay={onPlay} onFavorite={onFavorite} onAddToList={onAddToList} gridRef={gridRef} />
        </section>
      ) : null}
    </div>
  );
}
