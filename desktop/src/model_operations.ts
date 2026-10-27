import type { PythonMessage } from './types'
import type { CatalogModel, Recommendation, SystemInfo } from './components/ModelPicker'
import {PublicModelLibrary} from './public_model_library'

type Catalog = { categories: string[]; models: CatalogModel[] }
type RequestKind = 'catalog' | 'recommend' | 'sync' | 'pull' | 'delete'
type Pending = { id: number; kind: RequestKind; model?: string; timer: ReturnType<typeof setTimeout> }
export type ModelOperationNotice = { kind: 'downloaded' | 'deleted' | 'synced'; model?: string }
export type RecommendationStatus={phase:'catalog'|'variants'|'complete'|'memory_unknown';scanned:number;total:number;unavailable:number;
  offline:boolean;stale:boolean;syncedAt:number;budget_gb:number}
export type ModelOperationsState = {
  catalog: Catalog | null; catalogLoading: boolean; catalogError: string | null
  recommendations: Recommendation[] | null; systemInfo: SystemInfo | null
  recommending: boolean; recommendError: string | null
  recommendationStatus:RecommendationStatus|null
  pulling: string | null; pullProgress: string; deleting: string | null; updating: boolean
  operationError: string | null; operationNotice: ModelOperationNotice | null
  mutationUnconfirmed: boolean
}

const errors: Record<RequestKind, string> = {
  catalog: 'MODEL_CATALOG_FAILED', recommend: 'MODEL_RECOMMEND_FAILED',
  sync: 'MODEL_SYNC_FAILED', pull: 'MODEL_DOWNLOAD_FAILED', delete: 'MODEL_DELETE_FAILED',
}
const timeoutMs: Record<RequestKind, number> = {
  catalog: 30_000, recommend: 30_000, sync: 120_000, pull: 120_000, delete: 60_000,
}
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(v => typeof v === 'string')
const nonnegative = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && value >= 0
function validCatalog(value: unknown): value is Catalog {
  if (!value || typeof value !== 'object') return false
  const c = value as Catalog
  return strings(c.categories) && Array.isArray(c.models) && c.models.every(m => m &&
    ['name', 'display', 'category', 'params', 'description'].every(k => typeof (m as any)[k] === 'string') &&
    nonnegative(m.size_gb) && strings(m.tags) && typeof m.installed === 'boolean' &&
    (m.strengths === undefined || strings(m.strengths)) &&
    (m.context_length === undefined || nonnegative(m.context_length) && Number.isSafeInteger(m.context_length)) &&
    (m.release_date === undefined || typeof m.release_date === 'string') &&
    (m.ease_of_use === undefined || nonnegative(m.ease_of_use) && Number.isInteger(m.ease_of_use) && m.ease_of_use <= 5))
}
function validRecommendations(value: unknown): value is Recommendation[] {
  return Array.isArray(value) && value.every(m => m && typeof m.name === 'string' && typeof m.display === 'string' &&
    typeof m.reason === 'string' && nonnegative(m.size_gb) && nonnegative(m.rank) && Number.isSafeInteger(m.rank) &&
    typeof m.installed === 'boolean' && (m.reason!=='MEMORY_FIT'||
      typeof m.family==='string'&&m.name.startsWith(m.family+':')&&['llm','embedding'].includes(m.kind)&&
      typeof m.description==='string'&&strings(m.tags)&&typeof m.size_label==='string'&&
      nonnegative(m.estimated_memory_gb)&&nonnegative(m.context_length)&&typeof m.gpu_fit==='boolean'))
}
function validRecommendationStatus(value:any):value is RecommendationStatus{
  return value&&['catalog','variants','complete','memory_unknown'].includes(value.phase)&&
    ['scanned','total','unavailable'].every(key=>nonnegative(value[key])&&Number.isSafeInteger(value[key]))&&
    value.scanned<=value.total&&value.unavailable<=value.scanned&&nonnegative(value.budget_gb)&&
    nonnegative(value.syncedAt)&&value.syncedAt<=8_640_000_000_000&&typeof value.offline==='boolean'&&typeof value.stale==='boolean'
}
function validSystemInfo(value: unknown): value is SystemInfo {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const info = value as SystemInfo
  return (info.ram_gb === null || nonnegative(info.ram_gb)) &&
    ['chip', 'gpu', 'os', 'arch'].every(key => typeof (info as any)[key] === 'string')
}

/** Presentation lifecycle only. Requests still use the existing host/backend APIs;
 * this class never chooses a chat model or supplies execution permission. */
export class ModelOperations {
  readonly library:PublicModelLibrary
  state: ModelOperationsState = {
    catalog: null, catalogLoading: false, catalogError: null,
    recommendations: null, systemInfo: null, recommending: false, recommendError: null, recommendationStatus:null,
    pulling: null, pullProgress: '', deleting: null, updating: false,
    operationError: null, operationNotice: null, mutationUnconfirmed: false,
  }
  private requests = new Map<RequestKind, Pending>()
  private recommendAgain=false
  private listeners = new Set<(state: ModelOperationsState) => void>()
  constructor(private send: (message: object) => void, private nextId: () => number,
    private refreshInstalled: () => void = () => {},
    private schedule: typeof setTimeout = setTimeout.bind(globalThis),
    private cancel: typeof clearTimeout = clearTimeout.bind(globalThis)) {
    this.library=new PublicModelLibrary(send,nextId,schedule,cancel)
  }

  subscribe(listener: (state: ModelOperationsState) => void) {
    this.listeners.add(listener)
    listener(this.state)
    return () => { this.listeners.delete(listener) }
  }
  private patch(value: Partial<ModelOperationsState>) {
    this.state = { ...this.state, ...value }
    for (const listener of this.listeners) listener(this.state)
  }
  private remove(kind: RequestKind) {
    const pending = this.requests.get(kind)
    if (pending) this.cancel(pending.timer)
    this.requests.delete(kind)
  }
  private arm(pending: Pending) {
    this.cancel(pending.timer)
    pending.timer = this.schedule(() => {
      if (this.requests.get(pending.kind) !== pending) return
      // No receipt is not proof of failure/success. Retain the mutation identity
      // so a late terminal receipt can settle it, while preventing a second pull.
      const mutation = pending.kind === 'pull' || pending.kind === 'delete'
      this.fail(pending, 'MODEL_OPERATION_UNCONFIRMED', mutation)
    }, timeoutMs[pending.kind])
  }
  private start(kind: RequestKind, type: string, args: Record<string, unknown> = {}) {
    this.remove(kind)
    const pending: Pending = { id: this.nextId(), kind, model: typeof args.model === 'string' ? args.model : undefined, timer: 0 as any }
    this.requests.set(kind, pending)
    this.arm(pending)
    try { this.send({ id: pending.id, type, ...args }) }
    catch { this.fail(pending, errors[kind]) }
    return pending
  }
  refreshCatalog() {
    if (this.requests.has('catalog')) return
    this.patch({ catalogLoading: true, catalogError: null })
    this.start('catalog', 'catalog')
  }
  recommend() {
    if (this.requests.has('recommend')) return
    this.recommendAgain=false
    this.patch({ recommending: true, recommendError: null })
    this.start('recommend', 'recommend')
  }
  sync() {
    if (this.requests.has('sync')) return
    this.patch({ updating: true, operationError: null, operationNotice: null })
    this.start('sync', 'update_catalog')
  }
  pull(model: string) {
    if (!model || this.requests.has('pull') || this.requests.has('delete')) return false
    this.patch({ pulling: model, pullProgress: '', operationError: null, operationNotice: null, mutationUnconfirmed: false })
    this.start('pull', 'pull_model', { model })
    return true
  }
  delete(model: string) {
    if (!model || this.requests.has('pull') || this.requests.has('delete')) return false
    this.patch({ deleting: model, operationError: null, operationNotice: null, mutationUnconfirmed: false })
    this.start('delete', 'delete_model', { model })
    return true
  }
  private fail(pending: Pending, code: string, retain = false) {
    if (!retain) this.remove(pending.kind)
    else this.cancel(pending.timer)
    switch (pending.kind) {
      case 'catalog': this.patch({ catalogLoading: false, catalogError: code }); break
      case 'recommend': this.patch({ recommending: false, recommendError: code }); break
      case 'sync': this.patch({ updating: false, operationError: code, operationNotice: null }); break
      case 'pull': this.patch({ pulling: null, pullProgress: '', operationError: code, operationNotice: null, mutationUnconfirmed: retain }); break
      case 'delete': this.patch({ deleting: null, operationError: code, operationNotice: null, mutationUnconfirmed: retain }); break
    }
  }
  disconnected() {
    this.library.disconnected()
    for (const pending of [...this.requests.values()]) this.fail(pending, 'MODEL_OPERATION_UNCONFIRMED', pending.kind === 'pull' || pending.kind === 'delete')
  }
  backendReady() {
    this.recommendAgain=false
    this.library.disconnected()
    // A new ready frame is a new observation boundary. No automatic retry/select.
    for (const pending of [...this.requests.values()]) this.fail(pending, 'MODEL_OPERATION_UNCONFIRMED')
    this.patch({ mutationUnconfirmed: false })
    this.refreshCatalog()
  }
  dispose() {
    this.library.dispose()
    for (const pending of this.requests.values()) this.cancel(pending.timer)
    this.requests.clear()
    this.listeners.clear()
  }
  receive(message: PythonMessage): boolean {
    if(this.library.receive(message))return true
    const pending = [...this.requests.values()].find(p => p.id === message.id)
    if (!pending) return false
    const kind = pending.kind
    if (message.type === 'error') {
      const retryFresh=kind==='recommend'&&this.recommendAgain
      this.fail(pending, errors[kind]);if(retryFresh)this.recommend();return true
    }
    if (kind === 'catalog' && message.type === 'catalog') {
      if (!validCatalog(message.data)) { this.fail(pending, errors.catalog); return true }
      this.remove(kind)
      this.patch({ catalog: message.data, catalogLoading: false, catalogError: null })
    } else if (kind === 'recommend' && (message.type === 'recommend' || message.type === 'recommend_progress')) {
      const progress=message.type==='recommend_progress',metadata=(message as PythonMessage&{recommendation?:unknown}).recommendation
      if (!validRecommendations(message.models) || message.system != null && !validSystemInfo(message.system)||
        ((progress||metadata!==undefined)&&!validRecommendationStatus(metadata))) {
        this.fail(pending, errors.recommend); return true
      }
      const info = message.system as SystemInfo | undefined | null
      if(this.recommendAgain){
        if(progress)this.arm(pending)
        else{this.remove(kind);this.patch({recommending:false});this.recommend()}
        return true
      }
      if(progress)this.arm(pending);else this.remove(kind)
      this.patch({ recommendations: message.models, systemInfo: info ?? null, recommending: progress, recommendError: null,
        recommendationStatus:metadata as RecommendationStatus|undefined||null })
    } else if (kind === 'sync' && message.type === 'catalog_updating') {
      this.arm(pending)
    } else if (kind === 'sync' && message.type === 'catalog_updated') {
      this.remove(kind)
      this.patch({ updating: false, operationError: null, operationNotice: { kind: 'synced' } })
      const requested=this.state.recommendations!==null||this.requests.has('recommend')
      if(requested){
        this.patch({recommendations:null,recommendationStatus:null})
        if(this.requests.has('recommend'))this.recommendAgain=true
        else this.recommend()
      }
      this.library.search(this.library.state.filters,true)
      this.remove('catalog'); this.refreshCatalog()
    } else if (kind === 'pull' && message.model === pending.model && (message.type === 'pull_start' || message.type === 'pull_progress')) {
      this.arm(pending)
      const progress = message as PythonMessage & { completed?: number; total?: number; status?: string }
      const percent = Number.isFinite(progress.completed) && Number.isFinite(progress.total) && progress.total! > 0
        ? Math.max(0, Math.min(100, Math.round(progress.completed! / progress.total! * 100))) : null
      // Only a compact provider status, never raw exception content or HTML.
      const label = typeof progress.status === 'string' ? progress.status.replace(/[\r\n\x00-\x1f]/g, ' ').slice(0, 160) : ''
      this.patch({ pulling: pending.model!, pullProgress: percent === null ? label : `${label} ${percent}%`.trim(),
        mutationUnconfirmed: false, operationError: null })
    } else if ((kind === 'pull' && message.type === 'pull_done' || kind === 'delete' && message.type === 'delete_done') && message.model === pending.model) {
      this.remove(kind)
      this.patch({ pulling: null, pullProgress: '', deleting: null, operationError: null, mutationUnconfirmed: false,
        operationNotice: { kind: kind === 'pull' ? 'downloaded' : 'deleted', model: pending.model } })
      this.remove('catalog'); this.refreshCatalog()
      this.refreshInstalled()
    } else return false
    return true
  }
}
