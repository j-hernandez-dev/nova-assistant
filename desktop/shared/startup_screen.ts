import { applyAppearance, defaultAppearance, type AppearancePreferences } from './desktop_appearance'

/** Startup presentation only. No backend commands, provider checks or retries. */
export type StartupLocale = 'es' | 'en'
export type StartupPhase = 'loading' | 'mounted' | 'ready' | 'failed'
export const STARTUP_WAIT_MS = 15000
export const startupCopy = {
  es: { loading: 'Iniciando Nova…', hint: 'Preparando tu espacio de trabajo.',
    slow: 'El inicio está tardando más de lo habitual.',
    failed: 'No se pudo cargar la interfaz de Nova.', open: 'Abrir Nova', retry: 'Reintentar' },
  en: { loading: 'Starting Nova…', hint: 'Preparing your workspace.',
    slow: 'Startup is taking longer than usual.',
    failed: 'The Nova interface could not be loaded.', open: 'Open Nova', retry: 'Retry' },
} as const
export function startupLocale(args: readonly string[]): StartupLocale {
  return args.includes('--nova-desktop-locale=en') ? 'en' : 'es'
}

type Elements = { screen: HTMLElement; root: HTMLElement; message: HTMLElement; hint: HTMLElement; action: HTMLButtonElement }
type Clock = { schedule: (fn: () => void, ms: number) => unknown; cancel: (timer: unknown) => void; reload: () => void; reducedMotion?: () => boolean; showStartupScreen?: boolean }

/** Separate from React so a slow or broken renderer bundle still has a usable screen. */
export function createStartupScreen(elements: Elements, locale: StartupLocale, clock: Clock) {
  const { screen, root, message, hint, action } = elements, copy = startupCopy[locale]
  let mounted = false, finished = false, slow = false, failed = false
  let disposed = false, removed = false, exitTimer: unknown
  const removeScreen = () => {
    if (disposed || removed) return
    removed = true
    if (exitTimer !== undefined) clock.cancel(exitTimer)
    screen.removeEventListener('transitionend', transitionEnd)
    screen.remove()
  }
  const transitionEnd = (event: TransitionEvent) => {
    if (event.target === screen && event.propertyName === 'opacity') removeScreen()
  }
  const refresh = () => {
    message.textContent = failed ? copy.failed : slow ? copy.slow : copy.loading
    hint.textContent = copy.hint
    action.textContent = mounted ? copy.open : copy.retry
    action.hidden = !slow && !failed
    screen.setAttribute('aria-busy', slow || failed ? 'false' : 'true')
    if (slow || failed) screen.setAttribute('data-startup-recovery', 'true')
  }
  const timer = clock.schedule(() => { if (!finished) { slow = true; refresh() } }, STARTUP_WAIT_MS)
  const finish = () => {
    if (finished) return
    finished = true
    clock.cancel(timer)
    const restoreFocus = action === action.ownerDocument?.activeElement
    root.removeAttribute('inert'); root.removeAttribute('aria-hidden')
    screen.setAttribute('aria-busy', 'false')
    screen.setAttribute('aria-hidden', 'true')
    screen.setAttribute('inert', '')
    action.removeEventListener('click', proceed)
    if (restoreFocus) root.querySelector<HTMLElement>('textarea:not([disabled]), button:not([disabled])')?.focus({ preventScroll: true })
    if (clock.showStartupScreen === false || clock.reducedMotion?.()) { removeScreen(); return }
    screen.addEventListener('transitionend', transitionEnd)
    screen.setAttribute('data-leaving', 'true')
    // Keep cleanup bounded if Chromium skips transitionend (for example in a hidden window).
    exitTimer = clock.schedule(removeScreen, 400)
  }
  const proceed = () => { if (!finished) { if (mounted) finish(); else clock.reload() } }
  action.addEventListener('click', proceed)
  refresh()
  return {
    update(phase: StartupPhase) {
      if (finished) return
      if (phase === 'ready') { finish(); return }
      if (phase === 'mounted') {
        mounted = true
        if (clock.showStartupScreen === false) { finish(); return }
      }
      if (phase === 'failed') { failed = true; clock.cancel(timer) }
      refresh()
    },
    dispose() {
      disposed = true; finished = true; clock.cancel(timer)
      if (exitTimer !== undefined) clock.cancel(exitTimer)
      screen.removeEventListener('transitionend', transitionEnd)
      action.removeEventListener('click', proceed)
    },
  }
}

/** The preload observes parsing, rather than waiting for DOMContentLoaded (which waits for modules). */
export function installStartupScreen(doc: Document, locale: StartupLocale, appearance: AppearancePreferences = defaultAppearance): () => void {
  let controller: ReturnType<typeof createStartupScreen> | undefined
  const observer = new MutationObserver(() => {
    if (!controller) mount()
    else update()
  })
  const update = () => {
    const phase = doc.documentElement?.getAttribute('data-nova-startup')
    if (phase === 'mounted' || phase === 'ready' || phase === 'failed') controller?.update(phase)
    if (phase === 'ready') { observer.disconnect(); doc.removeEventListener('error', scriptError, true) }
  }
  const mount = () => {
    applyAppearance(doc, appearance)
    const screen = doc.getElementById('nova-startup'), root = doc.getElementById('root')
    const message = doc.getElementById('nova-startup-message'), hint = doc.getElementById('nova-startup-hint')
    const action = doc.getElementById('nova-startup-action') as HTMLButtonElement | null
    if (screen?.hasAttribute('data-startup-managed')) { observer.disconnect(); doc.removeEventListener('error', scriptError, true); return }
    if (!screen || !root || !message || !hint || !action) return
    screen.setAttribute('data-startup-managed', 'true')
    doc.documentElement.lang = locale
    controller = createStartupScreen({ screen, root, message, hint, action }, locale, {
      schedule: (fn, ms) => setTimeout(fn, ms), cancel: timer => clearTimeout(timer as ReturnType<typeof setTimeout>),
      reload: () => doc.defaultView?.location.reload(),
      reducedMotion: () => appearance.reduceMotion || !!doc.defaultView?.matchMedia('(prefers-reduced-motion: reduce)').matches,
      showStartupScreen: appearance.showStartupScreen,
    })
    // Stop observing the whole parsed document once the small startup island exists.
    observer.disconnect()
    observer.observe(doc.documentElement, { attributes: true, attributeFilter: ['data-nova-startup'] })
    update()
  }
  const scriptError = (event: Event) => {
    const target = event.target as HTMLScriptElement | null
    if (controller && target?.tagName === 'SCRIPT' && target.type === 'module') {
      doc.documentElement.setAttribute('data-nova-startup', 'failed')
    }
  }
  observer.observe(doc, { childList: true, subtree: true })
  doc.addEventListener('error', scriptError, true)
  mount()
  return () => { observer.disconnect(); controller?.dispose(); doc.removeEventListener('error', scriptError, true) }
}
