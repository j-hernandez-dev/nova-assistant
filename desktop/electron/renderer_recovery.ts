import { randomUUID } from 'node:crypto'

export const RENDERER_PROBE_MS = 10_000
export const RENDERER_RELOAD_MS = 25_000
export const RENDERER_STABLE_MS = 60_000

type Timer = ReturnType<typeof setTimeout>
type RecoveryHost = {
  available: () => boolean
  visible: () => boolean
  repaint: () => void
  probe: (nonce: string) => void
  reload: (replaceProcess: boolean) => void
  refresh: () => void
  offerRetry: () => Promise<boolean>
  report: (event: string) => void
  schedule?: (callback: () => void, delay: number) => Timer
  cancel?: (timer: Timer) => void
}

/** Repairs presentation only. Never restarts the backend or replays a user command. */
export function createRendererRecovery(host: RecoveryHost) {
  const schedule = host.schedule || ((callback, delay) => {
    const timer = setTimeout(callback, delay); timer.unref?.(); return timer
  })
  const cancel = host.cancel || clearTimeout
  let disposed = false, suspended = false, mounted = false, needsCheck = false
  let reloading = false, automaticUsed = false, prompting = false, blocked = false, crashed = false
  let generation = 0, probeNonce: string | null = null
  let deadline: Timer | undefined, stable: Timer | undefined
  const live = () => !disposed && host.available()
  const clearDeadline = () => {
    if (deadline !== undefined) cancel(deadline)
    deadline = undefined; probeNonce = null
  }
  const clearStable = () => { if (stable !== undefined) cancel(stable); stable = undefined }
  const markStable = () => {
    clearStable()
    if (!suspended) stable = schedule(() => { stable = undefined; automaticUsed = false }, RENDERER_STABLE_MS)
  }
  const repaint = () => {
    try { host.repaint(); return true }
    catch { host.report('renderer-repaint-failed'); return false }
  }

  function offerRetry() {
    if (!live() || suspended || !host.visible()) { needsCheck = true; return }
    if (prompting || blocked) return
    clearDeadline(); clearStable(); reloading = false; blocked = true; prompting = true
    host.report('manual-recovery-offered')
    const current = generation
    void host.offerRetry().then(retry => {
      if (!live() || generation !== current) return
      prompting = false
      if (retry) { blocked = false; reload(true) }
    }).catch(() => { prompting = false })
  }
  function armReloadDeadline() {
    if (suspended || !host.visible()) return
    const current = generation
    deadline = schedule(() => {
      if (!live() || !reloading || generation !== current) return
      deadline = undefined; offerRetry()
    }, RENDERER_RELOAD_MS)
  }
  function reload(replaceProcess: boolean) {
    if (!live()) return
    clearDeadline(); clearStable()
    generation++; automaticUsed = true; reloading = true; needsCheck = false
    host.report('renderer-reload')
    armReloadDeadline()
    try { host.reload(replaceProcess) }
    catch { host.report('renderer-reload-failed'); offerRetry() }
  }
  function recover(replaceProcess: boolean) {
    clearDeadline(); clearStable(); needsCheck = true
    if (!live() || suspended || !host.visible() || blocked || prompting) return
    if (reloading || automaticUsed) { offerRetry(); return }
    reload(replaceProcess)
  }
  function check() {
    if (!live() || suspended || !needsCheck || !host.visible() || blocked || prompting) return
    if (reloading) { if (deadline === undefined) armReloadDeadline(); return }
    if (crashed) { recover(false); return }
    if (!mounted || probeNonce) return
    needsCheck = false
    const nonce = randomUUID(); probeNonce = nonce
    if (!repaint()) { recover(true); return }
    deadline = schedule(() => {
      if (probeNonce !== nonce) return
      host.report('renderer-probe-timeout'); recover(true)
    }, RENDERER_PROBE_MS)
    try { host.probe(nonce) }
    catch { host.report('renderer-probe-failed'); recover(true) }
  }
  return {
    suspend() {
      if (!live()) return
      suspended = true; needsCheck = true; clearDeadline(); clearStable()
      host.report('suspend')
    },
    resume() {
      if (!live()) return
      suspended = false; needsCheck = true; host.report('resume')
      try { host.refresh() } catch { host.report('resume-refresh-failed') }
      check()
    },
    visible: check,
    hidden() { if (probeNonce || reloading) needsCheck = true; clearDeadline() },
    suspect() { needsCheck = true; check() },
    gone() { if (live()) { crashed = true; host.report('renderer-gone'); recover(false) } },
    loading() { mounted = false; clearDeadline(); clearStable(); if (reloading) armReloadDeadline() },
    ready() {
      if (!live()) return
      mounted = true; generation++; reloading = false; blocked = false; prompting = false; crashed = false; needsCheck = false
      clearDeadline(); clearStable()
      if (!repaint()) { recover(true); return }
      markStable()
      check()
    },
    alive(nonce: unknown) {
      if (!live() || suspended || typeof nonce !== 'string' || nonce !== probeNonce) return
      clearDeadline(); needsCheck = false
      if (!repaint()) { recover(true); return }
      markStable(); host.report('renderer-responsive')
    },
    dispose() {
      disposed = true; generation++; clearDeadline(); clearStable()
    },
  }
}
