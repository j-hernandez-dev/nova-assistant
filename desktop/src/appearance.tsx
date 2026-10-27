import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { applyAppearance, defaultAppearance, readAppearance, validAppearance, sameAppearance, type AppearancePreferences } from '../shared/desktop_appearance'

type SaveState = 'idle' | 'saving' | 'unconfirmed' | 'saved' | 'reset' | 'failed'
const AppearanceContext = createContext({ appearance: defaultAppearance, ready: false, saveState: 'idle' as SaveState,
  effectiveScheme: 'dark' as 'light' | 'dark', saveAppearance: async (_next: AppearancePreferences, _reset = false): Promise<boolean> => false })

/** Every surface uses confirmed preferences; a failed save retains the current presentation. */
export function AppearanceProvider({ children }: { children: ReactNode }) {
  const [appearance, setAppearance] = useState(() => readAppearance(window.api?.initialDesktopAppearance))
  const [ready, setReady] = useState(() => window.api?.initialDesktopAppearance !== undefined)
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [systemDark, setSystemDark] = useState(() => window.api?.initialDesktopSystemDark ?? window.matchMedia('(prefers-color-scheme: dark)').matches)
  const pending = useRef(false)
  useEffect(() => { applyAppearance(document, appearance, systemDark) }, [appearance, systemDark])
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const changed = () => setSystemDark(media.matches)
    media.addEventListener('change', changed)
    const unsubscribe = window.api?.onDesktopAppearanceChanged?.(event => {
      if (!event || event.preferences?.schemaVersion !== 1 || !validAppearance(event.preferences)) return
      setAppearance(readAppearance(event.preferences)); setSystemDark(event.systemDark === true); setReady(true)
    })
    return () => { media.removeEventListener('change', changed); unsubscribe?.() }
  }, [])
  useEffect(() => {
    if (ready) return
    let current = true
    const timer = setTimeout(() => { if (current) { current = false; setSaveState('failed') } }, 15000)
    void window.api?.getDesktopPreferences?.().then(value => {
      if (!current) return
      if (value?.schemaVersion !== 1) { setSaveState('failed'); return }
      setAppearance(readAppearance(value)); setReady(true)
    }).catch(() => { if (current) setSaveState('failed') }).finally(() => clearTimeout(timer))
    return () => { current = false; clearTimeout(timer) }
  }, [ready])
  const saveAppearance = useCallback(async (next: AppearancePreferences, reset = false) => {
    if (!ready || pending.current || !validAppearance(next)) return false
    pending.current = true; setSaveState('saving')
    const timer = setTimeout(() => setSaveState('unconfirmed'), 15000)
    try {
      const result = await window.api.setDesktopAppearance(next)
      if (!result.success || !validAppearance(result.preferences) || !sameAppearance(next, result.preferences)) {
        setSaveState('failed'); return false
      }
      setAppearance(readAppearance(result.preferences)); setSaveState(reset ? 'reset' : 'saved'); return true
    } catch { setSaveState('failed'); return false }
    finally { pending.current = false; clearTimeout(timer) }
  }, [ready])
  const effectiveScheme = appearance.colorScheme === 'system' ? (systemDark ? 'dark' : 'light') : appearance.colorScheme
  return <AppearanceContext.Provider value={{ appearance, ready, saveState, saveAppearance, effectiveScheme }}>{children}</AppearanceContext.Provider>
}
export function useAppearance() { return useContext(AppearanceContext) }
