import { useEffect, useRef } from 'react';

export default function usePlayerDialog(onClose) {
  const dialogRef = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    dialogRef.current?.querySelector('button')?.focus();
    const handleKey = (event) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); return; }
      if (event.key !== 'Tab') return;
      const controls = [...(dialogRef.current?.querySelectorAll('button, iframe, a[href], [tabindex="0"]') || [])]
        .filter(control => !control.disabled && control.getClientRects().length > 0);
      if (!controls.length) return;
      if (event.shiftKey && document.activeElement === controls[0]) { event.preventDefault(); controls.at(-1).focus(); }
      else if (!event.shiftKey && document.activeElement === controls.at(-1)) { event.preventDefault(); controls[0].focus(); }
    };
    document.addEventListener('keydown', handleKey);
    return () => { document.removeEventListener('keydown', handleKey); previous?.focus(); };
  }, []);
  return dialogRef;
}
