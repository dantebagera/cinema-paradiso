// Small CP vector depictions. Bundled locally; no image requests or emoji fonts.
export function RottenTomatoesIcon({kind}) {
  return <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" data-rt-icon={kind}>
    {kind==='fresh' ? <><path fill="#ed4136" d="M12 6C2 3 0 18 9 21c3 1 5 0 7-1C25 15 22 3 12 6Z"/><path fill="#4d9b48" d="m12 8-5-4 5 1 2-5 1 5 5-1-4 4-3-1Z"/><path stroke="#ff9886" fill="none" strokeLinecap="round" d="M6 10q-3 4 0 7"/></> : null}
    {kind==='rotten' ? <><path fill="#73a847" d="m11 5 3-4 2 6 6-1-3 5 5 4-7 1-1 7-5-5-5 4 1-7-7-2 7-3-3-6Z"/><ellipse cx="12" cy="12" rx="5" ry="4" fill="#426e35"/><circle cx="3" cy="20" r="2" fill="#73a847"/></> : null}
    {kind==='upright' ? <><path fill="#fff1c3" d="M4 10C-1 6 4 1 8 4 8-1 16-1 16 4c5-3 10 3 5 7Z"/><path fill="#f2e9d2" d="m4 9 3 14h11l3-14Z"/><path fill="#e9453b" d="m5 10 3 12h3L9 10Zm10 0-1 12h3l2-12Z"/></> : null}
    {kind==='spilled' ? <><path fill="#f2e9d2" d="m4 7 15 6-7 10L1 14Z"/><path fill="#e9453b" d="m5 8 12 7-2 3-12-7Zm-3 5 11 7-2 2-10-7Z"/><ellipse cx="17" cy="13" rx="3" ry="6" transform="rotate(36 17 13)" fill="#807966"/><path fill="#eee7c8" d="M17 7c-4-3 0-7 3-4 4-2 5 4 1 5Zm-7-2c-3-3 1-6 3-3 3 2 0 5-3 3Zm10 17c-3-3 1-6 3-3 3 2 0 5-3 3Z"/></> : null}
  </svg>;
}
