import { randomUUID } from 'node:crypto'
import type { ModelDownloadState } from '../shared/application'
type Inventory = Array<{ name: string; size: number }>
/** One host-owned download. Completion includes a fresh inventory and readiness observation. */
export class ModelDownload {
  state: ModelDownloadState | null = null
  inventoryReady = false
  private timer: ReturnType<typeof setTimeout> | null = null
  private inventoryId: string | null = null
  private retired = new Set<string>()
  constructor(private send: (frame: object) => unknown, private publish: (state: ModelDownloadState | null) => void,
    private installInventory: (models: Inventory) => void, private probe: () => void, private finished: () => void) {}
  busy() { return !!this.state && !['failed', 'complete'].includes(this.state.phase) }
  private emit() { this.publish(this.state) }
  private clearTimer() { if (this.timer) clearTimeout(this.timer); this.timer = null }
  private arm(ms: number, callback: () => void) { this.clearTimer(); this.timer = setTimeout(callback, ms); this.timer.unref?.() }
  private retireInventory() {
    if (this.inventoryId) this.retired.add(this.inventoryId)
    this.inventoryId = null
    if (this.retired.size > 64) this.retired.delete(this.retired.values().next().value!)
  }
  start(id: number, model: string) {
    if (this.busy()) return false
    this.inventoryReady = false
    this.state = { id, model, phase: 'downloading', percent: null, detail: '' }
    this.arm(120000, () => { if (this.state) { this.state = { ...this.state, phase: 'waiting' }; this.emit() } })
    this.emit(); return true
  }
  refreshInventory() {
    if (!this.state || !['refreshing', 'refresh-failed'].includes(this.state.phase)) return false
    this.inventoryReady = false; this.retireInventory()
    this.state = { ...this.state, phase: 'refreshing', percent: 100, detail: '' }; this.emit()
    this.inventoryId = 'desktop-download-inventory-' + randomUUID()
    this.arm(45000, () => this.refreshFailed())
    this.send({ id: this.inventoryId, type: 'catalog' }); return true
  }
  private refreshFailed() {
    this.clearTimer(); this.retireInventory(); this.inventoryReady = false
    if (this.state) { this.state = { ...this.state, phase: 'refresh-failed', detail: '' }; this.emit() }
  }
  confirmReadiness(valid: boolean) {
    if (!this.busy() || !this.inventoryReady) return
    if (!valid) { this.refreshFailed(); return }
    this.clearTimer(); this.state = { ...this.state!, phase: 'complete', detail: '' }; this.emit(); this.finished()
  }
  disconnected() {
    this.clearTimer(); this.retireInventory(); this.inventoryReady = false
    if (this.busy()) { this.state = { ...this.state!, phase: 'failed', detail: '' }; this.emit() }
  }
  receive(frame: Record<string, any>) {
    if (this.retired.has(frame.id)) return true
    if (this.inventoryId && frame.id === this.inventoryId) {
      if (!['catalog', 'error'].includes(frame.type)) return true
      const models = frame.data?.installedModels
      const target = this.state!.model.includes(':') ? this.state!.model : this.state!.model + ':latest'
      if (frame.type !== 'catalog' || !Array.isArray(models) ||
          !models.every(m => m && typeof m.name === 'string' && typeof m.size === 'number' && Number.isFinite(m.size) && m.size >= 0) ||
          !models.some(m => m.name === target)) { this.refreshFailed(); return true }
      this.clearTimer(); this.retireInventory(); this.inventoryReady = true
      this.installInventory(models.map(m => ({ name: m.name, size: m.size })))
      this.probe(); return true
    }
    const state = this.state
    if (!state || !this.busy() || frame.id !== state.id) return false
    if (frame.type === 'error' && !['downloading', 'waiting'].includes(state.phase)) return true
    if (frame.type === 'error') {
      this.clearTimer(); this.state = { ...state, phase: 'failed', detail: '' }; this.emit(); this.finished(); return false
    }
    if (frame.model !== state.model) return false
    if (['pull_start', 'pull_progress'].includes(frame.type) && ['downloading', 'waiting'].includes(state.phase)) {
      const numeric = Number.isFinite(frame.completed) && Number.isFinite(frame.total) && frame.completed >= 0 && frame.total > 0
      const percent = numeric ? Math.min(100, Math.round(frame.completed / frame.total * 100)) : state.percent
      const detail = typeof frame.status === 'string' ? frame.status.replace(/[\r\n\x00-\x1f]/g, ' ').slice(0, 160) : ''
      this.state = { ...state, phase: 'downloading', percent, detail }
      this.arm(120000, () => { if (this.state) { this.state = { ...this.state, phase: 'waiting' }; this.emit() } }); this.emit()
    } else if (frame.type === 'pull_done' && ['downloading', 'waiting'].includes(state.phase)) {
      this.state = { ...state, phase: 'refreshing', percent: 100, detail: '' }; this.refreshInventory()
    }
    return false
  }
}
