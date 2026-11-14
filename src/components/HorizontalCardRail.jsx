import Button from './ui/Button.jsx';
import { useEffect, useId, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import './horizontalCardRail.css';

export default function HorizontalCardRail({ label, header, children, className = '', trackClassName = '', trackRole = 'group', trackLabel, visibleCount = 8, minCardWidth = 164, cardWidth, resetKey, arrowPlacement = 'header', nativeScrollbar = false }) {
  const id = useId();
  const track = useRef(null);
  const [edges, setEdges] = useState({ start: true, end: true });

  useEffect(() => {
    const element = track.current;
    function update() {
      const start = element.scrollLeft <= 1;
      const end = element.scrollLeft + element.clientWidth >= element.scrollWidth - 1;
      setEdges(previous => previous.start === start && previous.end === end ? previous : { start, end });
    }
    const observer = new ResizeObserver(update);
    observer.observe(element);
    const observed = new Set();
    function reconcile() {
      const children = new Set(element.children);
      observed.forEach(child => {
        if (!children.has(child)) { observer.unobserve(child); observed.delete(child); }
      });
      children.forEach(child => {
        if (!observed.has(child)) { observer.observe(child); observed.add(child); }
      });
      update();
    }
    const membership = new MutationObserver(reconcile);
    membership.observe(element, { childList: true });
    element.addEventListener('scroll', update, { passive: true });
    reconcile();
    return () => { membership.disconnect(); observer.disconnect(); element.removeEventListener('scroll', update); };
  }, []);

  useEffect(() => { track.current.scrollLeft = 0; }, [resetKey]);

  function scroll(direction) {
    const element = track.current;
    const gap = parseFloat(getComputedStyle(element).columnGap || 0);
    const step = element.firstElementChild?.getBoundingClientRect().width + gap;
    const distance = Number.isFinite(step) && step > 0 ? Math.max(1, Math.floor((element.clientWidth + gap) / step)) * step : element.clientWidth;
    element.scrollBy({ left: direction * distance, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  }

  const edgeArrows = arrowPlacement === 'edges';
  const arrows = <div className={`horizontal-card-rail-arrows${edgeArrows ? ' horizontal-card-rail-edge-arrows' : ''}`} role="group" aria-label={`${label} scrolling`}
    data-can-scroll-left={!edges.start} data-can-scroll-right={!edges.end}>
    <Button size="compact" type="button" className="rail-arrow" aria-label={`Scroll ${label} left`} aria-controls={id} disabled={edges.start} onClick={() => scroll(-1)}><ChevronLeft size={16} /></Button>
    <Button size="compact" type="button" className="rail-arrow" aria-label={`Scroll ${label} right`} aria-controls={id} disabled={edges.end} onClick={() => scroll(1)}><ChevronRight size={16} /></Button>
  </div>;

  return <div className={`horizontal-card-rail ${className}`}>
    <header className="horizontal-card-rail-header">
      {header}
      {!edgeArrows && arrows}
    </header>
    <div className={`horizontal-card-rail-body${edgeArrows ? ' horizontal-card-rail-body-edges' : ''}`}>
      <div ref={track} id={id} role={trackRole} aria-label={trackLabel || `${label} cards`} className={`horizontal-card-rail-track${nativeScrollbar ? ' horizontal-card-rail-track-native-scrollbar' : ''} ${trackClassName}`}
        style={{ '--rail-visible-count': visibleCount, '--rail-min-card-width': `${minCardWidth}px`, '--rail-card-width': cardWidth }}>
        {children}
      </div>
      {edgeArrows && arrows}
    </div>
  </div>;
}
