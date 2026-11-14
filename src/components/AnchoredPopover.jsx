import { useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import useDismissiblePopover from '../hooks/useDismissiblePopover.js';

// A viewport layer keeps interactive pickers clear of sticky, scrolling controls.
export default function AnchoredPopover({ open, anchorRef, triggerRef, onClose, children, maxWidth = 820, ...props }) {
  const panelRef = useRef(null);
  const focusedOnOpen = useRef(false);
  const [position, setPosition] = useState(null);
  useDismissiblePopover(open, onClose, triggerRef, panelRef, anchorRef);

  useLayoutEffect(() => {
    if (!open) focusedOnOpen.current = false;
    else if (position && !focusedOnOpen.current) {
      const initialControl = panelRef.current?.querySelector('select, input') || panelRef.current?.querySelector('button');
      initialControl?.focus({ preventScroll: true });
      focusedOnOpen.current = true;
    }
  }, [open, position]);

  useLayoutEffect(() => {
    if (!open) {
      setPosition(null);
      return undefined;
    }
    const anchor = anchorRef.current;
    const panel = panelRef.current;
    if (!anchor || !panel) return undefined;
    const update = () => {
      if (!anchor.getClientRects().length) {
        onClose();
        return;
      }
      const rect = anchor.getBoundingClientRect();
      const margin = 12;
      const viewportWidth = document.documentElement.clientWidth;
      const viewportHeight = window.innerHeight;
      const width = Math.min(maxWidth, viewportWidth - margin * 2);
      const height = Math.min(panel.scrollHeight, viewportHeight - margin * 2);
      const below = viewportHeight - rect.bottom - margin - 8;
      const above = rect.top - margin - 8;
      const top = height > below && above > below ? rect.top - height - 8 : rect.bottom + 8;
      const next = {
        width,
        left: Math.max(margin, Math.min(rect.left, viewportWidth - width - margin)),
        top: Math.max(margin, Math.min(top, viewportHeight - height - margin))
      };
      setPosition(previous => previous && Object.keys(next).every(key => previous[key] === next[key]) ? previous : next);
    };
    update();
    const resize = new ResizeObserver(update);
    resize.observe(anchor);
    resize.observe(panel);
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      resize.disconnect();
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  }, [open, anchorRef, onClose, maxWidth]);

  if (!open) return null;
  return createPortal(
    <div {...props} ref={panelRef} style={{ ...position, visibility: position ? undefined : 'hidden' }}>{children}</div>,
    document.body
  );
}
