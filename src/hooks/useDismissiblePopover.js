import { useEffect } from 'react';

// Include both the trigger and panel so toggling or using a popup never dismisses it early.
export default function useDismissiblePopover(open, onDismiss, triggerRef, panelRef, boundaryRef, { dismissOutside = true, dismissEscape = true, workspaceOnly = false } = {}) {
  useEffect(() => {
    if (!open) return;
    const outside = (event) => {
      if (triggerRef.current?.contains(event.target) || panelRef.current?.contains(event.target) || boundaryRef?.current?.contains(event.target)) return;
      onDismiss();
    };
    const escape = (event) => {
      if (event.key !== 'Escape') return;
      onDismiss();
      if (triggerRef.current?.getClientRects().length) triggerRef.current.focus();
    };
    const trigger = triggerRef.current || boundaryRef?.current;
    const owner = workspaceOnly
      ? trigger?.closest('.media-workspace-panel, [role="tabpanel"], .workspace-panel') || trigger
      : trigger;
    const visibility = new MutationObserver(() => {
      if (owner && (!owner.getClientRects().length || getComputedStyle(owner).visibility === 'hidden')) onDismiss();
    });
    for (let node = owner; node && node !== document.body; node = node.parentElement) {
      visibility.observe(node, { attributes: true, attributeFilter: ['hidden', 'class', 'style'] });
    }
    if (dismissOutside) document.addEventListener('pointerdown', outside, true);
    if (dismissEscape) document.addEventListener('keydown', escape);
    return () => {
      visibility.disconnect();
      document.removeEventListener('pointerdown', outside, true);
      document.removeEventListener('keydown', escape);
    };
  }, [open, onDismiss, triggerRef, panelRef, boundaryRef, dismissOutside, dismissEscape, workspaceOnly]);
}
