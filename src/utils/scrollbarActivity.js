/** Reveal native scrollbars during scrolling, including late-mounted dialogs.
 * No scroll positions, focus, wheel events or component state are changed.
 */
export function installScrollbarActivity(doc) {
  const timers = new Map();
  const view = doc.defaultView;

  function onScroll(event) {
    const element = event.target === doc ? doc.scrollingElement : event.target;
    if (!element?.setAttribute) return;

    element.setAttribute('data-cp-scrolling', '');
    view.clearTimeout(timers.get(element));
    timers.set(element, view.setTimeout(() => {
      element.removeAttribute('data-cp-scrolling');
      timers.delete(element);
    }, 900));
  }

  doc.addEventListener('scroll', onScroll, { capture: true, passive: true });
  return () => {
    doc.removeEventListener('scroll', onScroll, true);
    for (const [element, timer] of timers) {
      view.clearTimeout(timer);
      element.removeAttribute('data-cp-scrolling');
    }
    timers.clear();
  };
}
