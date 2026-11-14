import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Bookmark, Bot, Compass, Download, Home, Info, Library, MonitorOff, PanelLeftClose, PanelLeftOpen, Power, RefreshCw, RotateCcw, Settings, ShieldCheck, Tv } from 'lucide-react';
import NotificationWindow from '../features/notifications/NotificationWindow.jsx';
import useDismissiblePopover from '../hooks/useDismissiblePopover.js';
import { cx } from '../utils/appUtils.js';
import logoUrl from '../assets/logo.svg';

export const navItems = [
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
    id: 'discover',
    label: 'Discover',
    icon: Compass,
    accent: 'violet'
  },
  {
    id: 'movie-lists',
    label: 'Lists',
    icon: Bookmark,
    accent: 'gold'
  },
  {
    id: 'iptv',
    label: 'IPTV',
    icon: Tv,
    accent: 'gold'
  },
  {
    id: 'downloads',
    label: 'Downloads',
    icon: Download,
    accent: 'gold',
    groupStart: true
  },
  {
    id: 'ai-control',
    label: 'AI Control',
    icon: Bot,
    accent: 'violet'
  },
  {
    id: 'cleanup',
    label: 'Maintenance',
    icon: ShieldCheck,
    accent: 'amber'
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: Settings,
    accent: 'cyan',
    utility: true
  },
  {
    id: 'help',
    label: 'Help',
    icon: Info,
    accent: 'gold',
    utility: true
  }
];

const APP_VERSION = `v${import.meta.env.VITE_APP_VERSION || '0.0.0'}`;

export default function Sidebar({
  activeSection,
  collapsed: preferredCollapsed,
  onSelect,
  onToggleCollapsed,
  powerStatus,
  onFrontendReset,
  onPowerAction,
  onPowerCancel,
  onPowerResume
}) {
  const collapsed = preferredCollapsed;
  const [navTooltip, setNavTooltip] = useState(null);
  const [openMenu, setOpenMenu] = useState(null);
  const powerMenuOpen = openMenu === 'power';
  const powerTriggerRef = useRef(null);
  const powerPanelRef = useRef(null);
  const dismissMenu = useCallback(() => setOpenMenu(null), []);
  const toggleNotifications = useCallback(() => {
    setOpenMenu((current) => current === 'notifications' ? null : 'notifications');
  }, []);
  useDismissiblePopover(powerMenuOpen, dismissMenu, powerTriggerRef, powerPanelRef);
  const [afterDownload, setAfterDownload] = useState(false);
  const [closeQbittorrent, setCloseQbittorrent] = useState(false);
  const plan = powerStatus?.plan || {};
  const planActive = ['armed', 'draining', 'paused', 'failed', 'dispatch_claimed', 'dispatch_failed', 'dispatch_unknown'].includes(plan.state);
  const cancellable = ['armed', 'paused', 'failed', 'dispatch_failed', 'dispatch_unknown'].includes(plan.state);
  const checkpointed = (plan.target_status || []).filter((target) => target.checkpointed).length;
  const canCloseQbittorrent = powerStatus?.torrent_client?.can_close === true;
  const planLabel = plan.action === 'device'
    ? 'SHUT DOWN DEVICE'
    : plan.action === 'restart' ? 'RESTART' : 'TURN OFF';

  useEffect(() => {
    if (!canCloseQbittorrent) setCloseQbittorrent(false);
  }, [canCloseQbittorrent]);

  const showNavTooltip = useCallback((label, event) => {
    if (!collapsed) return;
    const anchor = event.currentTarget.getBoundingClientRect();
    setNavTooltip({
      label,
      top: anchor.top + anchor.height / 2
    });
  }, [collapsed]);

  const hideNavTooltip = useCallback(() => {
    setNavTooltip((current) => (
      current ? { ...current, label: '' } : null
    ));
  }, []);

  const selectNavItem = useCallback((section) => {
    hideNavTooltip();
    setOpenMenu(null);
    onSelect(section);
  }, [hideNavTooltip, onSelect]);

  const toggleCollapsed = useCallback(() => {
    setNavTooltip(null);
    setOpenMenu(null);
    onToggleCollapsed();
  }, [onToggleCollapsed]);

  useEffect(() => {
    if (!collapsed) setNavTooltip(null);
  }, [collapsed]);

  const renderNavItem = (item) => {
    const Icon = item.icon;
    return (
      <div key={item.id} className={cx('nav-group', item.groupStart && 'nav-group-start')}>
        <button
          className={cx('nav-item', activeSection === item.id && 'nav-item-active', `accent-${item.accent}`)}
          onClick={() => selectNavItem(item.id)}
          onMouseEnter={(event) => showNavTooltip(item.label, event)}
          onMouseLeave={hideNavTooltip}
          onFocus={(event) => showNavTooltip(item.label, event)}
          onBlur={hideNavTooltip}
          type="button"
          aria-label={collapsed ? item.label : undefined}
        >
          <span className="nav-icon-wrap"><Icon size={22} /></span>
          <span className="nav-label">{item.label}</span>
        </button>
      </div>
    );
  };

  return (
    <>
      <aside id="primary-navigation" className={cx('sidebar', collapsed && 'sidebar-collapsed')} aria-label="Primary navigation">
      <div className="brand-lockup">
        <img src={logoUrl} alt="" className="brand-mark" />
        <div>
          <div className="brand-title">Cinema</div>
          <div className="brand-title brand-title-accent">Paradiso</div>
        </div>
        <button
          type="button"
          className="sidebar-toggle"
          onClick={toggleCollapsed}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!collapsed}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </button>
      </div>
      <nav className="nav-stack" onScroll={hideNavTooltip}>
        {navItems.filter((item) => !item.utility).map(renderNavItem)}
      </nav>
      <div className={cx('sidebar-power-zone', planActive && 'sidebar-power-zone-active')}>
        <NotificationWindow
          collapsed={collapsed}
          open={openMenu === 'notifications'}
          onToggle={toggleNotifications}
          onDismiss={dismissMenu}
          onMouseEnter={(event) => showNavTooltip('Notifications', event)}
          onMouseLeave={hideNavTooltip}
          onFocus={(event) => showNavTooltip('Notifications', event)}
          onBlur={hideNavTooltip}
        />
        <nav className="sidebar-utility-nav" aria-label="App utilities">
          {navItems.filter((item) => item.utility).map(renderNavItem)}
        </nav>
        <button
          ref={powerTriggerRef}
          type="button"
          className="nav-item sidebar-power-button"
          aria-label="Power options"
          aria-expanded={powerMenuOpen}
          aria-controls="sidebar-power-menu"
          onMouseEnter={(event) => showNavTooltip('Power', event)}
          onMouseLeave={hideNavTooltip}
          onFocus={(event) => showNavTooltip('Power', event)}
          onBlur={hideNavTooltip}
          onClick={() => setOpenMenu((current) => current === 'power' ? null : 'power')}
        >
          <span className="nav-icon-wrap"><Power size={21} /></span>
          <span className="nav-label">{planActive ? 'Power action active' : 'Power'}</span>
        </button>
        <div
          className="sidebar-footer"
          title={collapsed ? APP_VERSION : undefined}
        >
          <span className="sidebar-version">{APP_VERSION}</span>
        </div>
        {powerMenuOpen && createPortal(
          <div ref={powerPanelRef} id="sidebar-power-menu" className={cx('sidebar-power-menu', collapsed && 'sidebar-power-menu-collapsed')} role="menu" aria-label="Power options">
            <div className="sidebar-power-menu-heading">
              <strong>Power</strong>
              {planActive && <span>{plan.state.replace('_', ' ')}</span>}
            </div>
            {planActive ? (
              <div className="sidebar-power-plan">
                <strong>{planLabel}</strong>
                <span>{plan.detail}</span>
                {plan.action === 'cp' && plan.close_qbittorrent && <small>qBittorrent will also close</small>}
                {!!plan.target_status?.length && (
                  <small>{checkpointed} of {plan.target_status.length} downloads checkpointed</small>
                )}
                {plan.state === 'paused' && (
                  <button type="button" className="sidebar-power-action" onClick={onPowerResume}>Resume scheduled action</button>
                )}
                {cancellable && (
                  <button type="button" className="sidebar-power-action sidebar-power-cancel" onClick={onPowerCancel}>Cancel scheduled action</button>
                )}
              </div>
            ) : (
              <>
                <div className="sidebar-power-runtime-actions">
                  <button type="button" className="sidebar-power-action" role="menuitem" onClick={onFrontendReset}>
                    <RefreshCw size={18} /> <span>RESET</span>
                  </button>
                  <button type="button" className="sidebar-power-action" role="menuitem" onClick={() => onPowerAction('restart', false, false)}>
                    <RotateCcw size={18} /> <span>RESTART</span>
                  </button>
                </div>
                <label className="sidebar-power-after">
                  <input
                    type="checkbox"
                    checked={afterDownload}
                    disabled={!powerStatus?.active_downloads}
                    onChange={(event) => setAfterDownload(event.target.checked)}
                  />
                  <span>After current downloads finish</span>
                </label>
                {!powerStatus?.active_downloads && <small className="sidebar-power-note">No active CP downloads</small>}
                <label className="sidebar-power-after sidebar-power-torrent-option">
                  <input
                    type="checkbox"
                    checked={closeQbittorrent}
                    disabled={!canCloseQbittorrent}
                    onChange={(event) => setCloseQbittorrent(event.target.checked)}
                  />
                  <span>Close qBittorrent too</span>
                </label>
                {!canCloseQbittorrent && <small className="sidebar-power-note">System qBittorrent is not owned by CP</small>}
                <button type="button" className="sidebar-power-action" role="menuitem" onClick={() => onPowerAction('cp', afterDownload, closeQbittorrent)}>
                  <Power size={18} /> <span>TURN OFF</span>
                </button>
                <button type="button" className="sidebar-power-action" role="menuitem" onClick={() => onPowerAction('device', afterDownload, false)}>
                  <MonitorOff size={18} /> <span>SHUT DOWN DEVICE</span>
                </button>
              </>
            )}
          </div>, document.body
        )}
      </div>
      </aside>
      {collapsed && (
        <div
          className={cx('sidebar-tooltip', navTooltip?.label && 'sidebar-tooltip-visible')}
          role="tooltip"
          aria-hidden={!navTooltip?.label}
          style={{ top: `${navTooltip?.top ?? 0}px` }}
        >
          {navTooltip?.label || ''}
        </div>
      )}
    </>
  );
}
