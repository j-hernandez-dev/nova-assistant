import { useEffect, useState } from 'react'

export function reducedMotion() {
  return typeof document !== 'undefined' && (document.documentElement.dataset.novaReduceMotion === 'true' ||
    !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)
}
/** Keep outgoing presentation briefly; commands and focus follow the requested state immediately. */
export function usePresence(open: boolean, duration = 220) {
  const [present, setPresent] = useState(open)
  useEffect(() => {
    if (open) { setPresent(true); return }
    if (reducedMotion()) { setPresent(false); return }
    const timer = setTimeout(() => setPresent(false), duration + 30)
    return () => clearTimeout(timer)
  }, [open, duration])
  return open || present
}
