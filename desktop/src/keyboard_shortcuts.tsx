import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { defaultShortcuts, readShortcuts, validShortcuts, formatShortcut, type ShortcutBindings, type ShortcutAction } from '@nova/keyboard-shortcuts'
import { useI18n } from './i18n'

type SaveState = 'idle' | 'saving' | 'unconfirmed' | 'saved' | 'reset' | 'failed'
const ShortcutsContext = createContext({ bindings: defaultShortcuts(), loaded: false, loadFailed: false, state: 'idle' as SaveState,
  save: async (_next: ShortcutBindings, _reset = false): Promise<boolean> => false })

/** Effective shortcuts change only after the desktop store confirms the atomic save. */
export function ShortcutsProvider({ children }: { children: ReactNode }) {
  const [bindings, setBindings] = useState(() => readShortcuts(typeof window === 'undefined' ? null : window.api?.initialDesktopShortcuts))
  const [loaded, setLoaded] = useState(() => typeof window !== 'undefined' && window.api?.initialDesktopShortcuts !== undefined)
  const [loadFailed, setLoadFailed] = useState(false)
  const [state, setState] = useState<SaveState>('idle')
  const pending = useRef(false)
  useEffect(() => {
    if (loaded) return
    let current = true
    const timer = setTimeout(() => { if (current) { current = false; setLoadFailed(true) } }, 15000)
    void window.api?.getDesktopPreferences?.().then(value => {
      if (!current) return
      if (value.schemaVersion !== 1) { setLoadFailed(true); return }
      setBindings(readShortcuts(value.shortcuts)); setLoaded(true)
    }).catch(() => { if (current) setLoadFailed(true) }).finally(() => clearTimeout(timer))
    return () => { current = false; clearTimeout(timer) }
  }, [loaded])
  const save = useCallback(async (next: ShortcutBindings, reset = false) => {
    if (!loaded || pending.current || !validShortcuts(next)) return false
    pending.current = true; setState('saving')
    const timer = setTimeout(() => setState('unconfirmed'), 15000)
    try {
      const result = await window.api.setDesktopShortcuts(next)
      if (!result.success || !validShortcuts(result.preferences.shortcuts) ||
          Object.keys(next).some(key => next[key as ShortcutAction] !== result.preferences.shortcuts![key as ShortcutAction])) {
        setState('failed'); return false
      }
      setBindings({ ...result.preferences.shortcuts }); setState(reset ? 'reset' : 'saved'); return true
    } catch { setState('failed'); return false }
    finally { pending.current = false; clearTimeout(timer) }
  }, [loaded])
  return <ShortcutsContext.Provider value={{ bindings, loaded, loadFailed, state, save }}>{children}</ShortcutsContext.Provider>
}

export function useShortcuts() {
  const context = useContext(ShortcutsContext)
  const { locale } = useI18n()
  const mac = typeof document !== 'undefined' && (document.documentElement.dataset.novaPlatform === 'darwin' || /Mac/.test(navigator.platform))
  return { ...context, mac, busy: context.state === 'saving' || context.state === 'unconfirmed',
    label: (action: ShortcutAction) => formatShortcut(context.bindings[action], locale, mac) }
}
