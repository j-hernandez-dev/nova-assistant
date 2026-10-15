import { useEffect, useState } from 'react'
import type { DesktopSessionView } from '../shared/application'

/** React only subscribes to the host's backend projection. Unmounting this
 * observer does not stop generation, unsubscribe the host or close a session. */
export function useSessionView() {
  const [view, setView] = useState<DesktopSessionView | null>(null)
  useEffect(() => window.api.onSessionView(setView), [])
  return view
}
