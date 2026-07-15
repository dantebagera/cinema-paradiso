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


export default function StyleGuide() {
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

import {
  Bot,
  CheckCircle2,
  ChevronRight,
  CirclePlus,
  Clapperboard,
  Compass,
  Database,
  Download,
  Folder,
  Home,
  Info,
  Library,
  Link as LinkIcon,
  MonitorPlay,
  MoreVertical,
  Play,
  Search,
  Settings,
  Sparkles,
  Star,
  Trash2,
  Wand2,
} from 'lucide-react'
import headerCropUrl from '../../assets/header.png'
import logoUrl from '../../assets/logo.svg'
import motifCropUrl from '../../assets/styleguide-motif-crop.png'
import { cx } from '../../utils/appUtils.js'
