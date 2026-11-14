import { cloneElement, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

export default function Tooltip({ title, description, children }) {
  const id = useId();
  const anchor = useRef(null);
  const panel = useRef(null);
  const closeTimer = useRef(null);
  const hovered = useRef(false);
  const focused = useRef(false);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ left: 0, top: 0 });

  function cancelClose() { window.clearTimeout(closeTimer.current); }
  function hide() {
    cancelClose();
    hovered.current = false;
    setOpen(false);
  }
  function show(event) {
    cancelClose();
    anchor.current = event.currentTarget;
    setOpen(true);
  }
  function scheduleClose() {
    cancelClose();
    closeTimer.current = window.setTimeout(() => {
      if (!hovered.current && !focused.current) setOpen(false);
    }, 100);
  }

  function positionTooltip() {
    if (!anchor.current || !panel.current) return;
    const target = anchor.current.getBoundingClientRect();
    const tip = panel.current.getBoundingClientRect();
    const left = Math.max(16, Math.min(target.left + target.width / 2 - tip.width / 2, window.innerWidth - tip.width - 16));
    const top = target.top >= tip.height + 24 ? target.top - tip.height - 8 : Math.min(target.bottom + 8, window.innerHeight - tip.height - 16);
    setPosition({ left, top: Math.max(16, top) });
  }
  useLayoutEffect(() => {
    if (open) positionTooltip();
  }, [open, title, description]);

  useEffect(() => {
    if (!open) return;
    const scroll = () => { if (focused.current) positionTooltip(); else hide(); };
    const escape = (event) => { if (event.key === 'Escape') hide(); };
    window.addEventListener('scroll', scroll, true);
    window.addEventListener('resize', hide);
    document.addEventListener('keydown', escape);
    return () => {
      window.removeEventListener('scroll', scroll, true);
      window.removeEventListener('resize', hide);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);
  useEffect(() => () => window.clearTimeout(closeTimer.current), []);

  const handler = (name, callback) => (event) => {
    children.props[name]?.(event);
    callback(event);
  };
  return <>
    {cloneElement(children, {
      'aria-describedby': open ? [children.props['aria-describedby'], id].filter(Boolean).join(' ') : children.props['aria-describedby'],
      onMouseEnter: handler('onMouseEnter', event => { hovered.current = true; show(event); }),
      onMouseLeave: handler('onMouseLeave', () => { hovered.current = false; scheduleClose(); }),
      onFocus: handler('onFocus', event => { focused.current = true; show(event); }),
      onBlur: handler('onBlur', () => { focused.current = false; scheduleClose(); }),
      onClick: handler('onClick', hide)
    })}
    {open && createPortal(<div ref={panel} id={id} role="tooltip" className="app-tooltip" style={position}
      onMouseEnter={() => { hovered.current = true; cancelClose(); }}
      onMouseLeave={() => { hovered.current = false; scheduleClose(); }}>
      <strong>{title}</strong>
      {description && <span>{description}</span>}
    </div>, document.body)}
  </>;
}
