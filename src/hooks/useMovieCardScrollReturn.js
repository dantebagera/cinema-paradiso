import { useLayoutEffect, useRef } from 'react';
import { restoreWorkspaceScroll } from '../components/movie-card/expandedCardViewport.js';

// Capture before React expands the card or temporarily collapses its controls.
// Keeping this on the shared card also covers its nested expand buttons.
export default function useMovieCardScrollReturn(cardRef, expanded) {
  const origin = useRef(null);
  const wasExpanded = useRef(expanded);

  function captureOrigin(event) {
    if (expanded || !event.currentTarget.contains(event.target)) return;
    if (event.type === 'keydown' && !['Enter', ' '].includes(event.key)) return;
    const workspace = cardRef.current?.closest('.workspace');
    if (workspace && !workspace.dataset.restoringCard) {
      origin.current = { workspace, top: workspace.scrollTop };
    }
  }

  useLayoutEffect(() => {
    const collapsed = wasExpanded.current && !expanded;
    wasExpanded.current = expanded;
    if (!collapsed) return;
    const saved = origin.current;
    origin.current = null;
    if (!saved || saved.workspace.dataset.restoringCard || !cardRef.current?.getClientRects().length) return;
    // A different card opening or a restored navigation snapshot owns scrolling.
    const anotherExpanded = [...saved.workspace.querySelectorAll('.unified-movie-card-expanded')]
      .some(card => card.getClientRects().length);
    if (anotherExpanded) return;
    return restoreWorkspaceScroll(saved.top, saved.workspace);
  }, [expanded, cardRef]);

  return captureOrigin;
}
