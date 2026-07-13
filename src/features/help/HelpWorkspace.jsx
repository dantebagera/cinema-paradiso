import { ExternalLink } from 'lucide-react';

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
          'Forgetting that qBittorrentâ€™s visible UI is intentionally the original qBittorrent interface.'
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

export default function HelpWorkspace() {
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
