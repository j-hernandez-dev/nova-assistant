import { randomUUID } from 'node:crypto'
import type { StorageResult } from '../shared/storage'
import { ModelDownload } from './model_download.ts'
import type { Message } from '../src/types'
import { createHash } from 'node:crypto'
import type { DesktopSessionView, SessionSnapshot, EventEnvelope, CommandReceipt, ChatReadiness } from '../shared/application'
import type { MemoryControlResult, FetchStatus, SearchStatus, BrowserStatus, MemoryStatus, ContextStatus, EmbeddingStatus, KnowledgeSettingsStatus } from '../shared/application'
import { ConversationNotifications, type ConversationPreferences } from './conversation_notifications.ts'
import { activeActivity, attachActivities, toolActivity } from './activity_projection.ts'

const PRODUCT_COMMANDS = new Set([
  'SubmitUserInput', 'CancelTurn', 'CancelOperation', 'StopGeneration', 'ChangeModel', 'ChangeProvider',
  'ResolveApproval', 'ResolveUserInput', 'ExecuteCommand', 'SetRAGEnabled', 'QueryRAG',
  'ResetEmbeddingSettings', 'SetEmbeddingSettings', 'SetWebSettings', 'SetFetchEnabled', 'SetSearchEngine', 'SetBrowser', 'SetContextWindow',
  'SetKnowledgeSettings', 'ResetKnowledgeSettings',
])
const SETTINGS_COMMANDS = new Set(['SetKnowledgeSettings','ResetKnowledgeSettings','ResetEmbeddingSettings', 'SetEmbeddingSettings', 'SetWebSettings', 'SetFetchEnabled', 'SetSearchEngine', 'SetBrowser', 'SetContextWindow'])
const WORKSPACE_BOUND_COMMANDS = new Set(['SubmitUserInput', 'ExecuteCommand', 'ChangeProvider', 'ChangeModel', ...SETTINGS_COMMANDS])

function validSetting(kind: string, payload: Record<string, unknown>): boolean {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return false
  const keys = Object.keys(payload)
  if(kind==='ResetKnowledgeSettings')return keys.length===0
  if(kind==='SetKnowledgeSettings')return keys.length===4&&['lexicalRecall','semanticRecall','autoIndex','autoRebuild'].every(key=>typeof payload[key]==='boolean')
  if (kind === 'SetContextWindow') return keys.length === 1 && keys[0] === 'requestedTokens' && Number.isInteger(payload.requestedTokens) && [0,4096,8192,16384,32768,65536,131072,262144].includes(payload.requestedTokens as number)
  if (kind === 'ResetEmbeddingSettings') return keys.length===0
  if (kind === 'SetEmbeddingSettings') return keys.length===3 && keys.every(key=>['modelId','requestedTokens','enabledModels'].includes(key)) && typeof payload.modelId==='string' && payload.modelId.length<=512 && Number.isInteger(payload.requestedTokens) && [0,512,1024,2048,4096,8192,16384,32768].includes(payload.requestedTokens as number) && Array.isArray(payload.enabledModels) && payload.enabledModels.length<=1024 && payload.enabledModels.every(n=>typeof n==='string'&&n.trim()&&n.length<=512) && new Set(payload.enabledModels).size===payload.enabledModels.length
  if (kind === 'SetWebSettings') return keys.length===5 && ['fetchEnabled','searchEnabled','browserEnabled'].every(key=>typeof payload[key]==='boolean') && ['google','bing','duckduckgo'].includes(payload.engine as string) && ['webview2','chrome','edge'].includes(payload.browser as string)
  if (kind === 'SetFetchEnabled') return keys.length === 1 && keys[0] === 'enabled' && typeof payload.enabled === 'boolean'
  if (kind === 'SetSearchEngine') return keys.length === 1 && keys[0] === 'engine' && ['bing', 'google', 'duckduckgo'].includes(payload.engine as string)
  if (kind === 'SetBrowser') return keys.length === 1 && keys[0] === 'browser' && ['webview2', 'chrome', 'edge'].includes(payload.browser as string)
  return true
}
const identifier = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9_.-]{1,128}$/.test(value)
const nullableCode = (value: unknown): value is string | null => value === null || identifier(value)
const record = (value: any) => value && typeof value === 'object' && !Array.isArray(value)

function settingsProjection(services: SessionSnapshot['services']): {
  fetch?: FetchStatus; search?: SearchStatus; browser?: BrowserStatus; memory?: MemoryStatus; context?: ContextStatus; embedding?: EmbeddingStatus; knowledgeSettings?: KnowledgeSettingsStatus
} {
  const fetch = services.fetch, search = services.search, browser = services.browser, memory = services.memory
  const projected: ReturnType<typeof settingsProjection> = {}
  const ks=services.knowledgeSettings
  if(record(ks)&&['lexicalRecall','semanticRecall','autoIndex','autoRebuild','semanticAvailable','indexing'].every(key=>typeof (ks as any)[key]==='boolean')
    &&[ks!.indexedSources,ks!.totalSources].every(value=>Number.isSafeInteger(value)&&value>=0)&&nullableCode(ks!.errorCode))
    projected.knowledgeSettings={lexicalRecall:ks!.lexicalRecall,semanticRecall:ks!.semanticRecall,autoIndex:ks!.autoIndex,autoRebuild:ks!.autoRebuild,
      semanticAvailable:ks!.semanticAvailable,indexing:ks!.indexing,indexedSources:ks!.indexedSources,totalSources:ks!.totalSources,errorCode:ks!.errorCode}
  const em = services.embedding
  if(record(em) && typeof em!.modelId==='string' && typeof em!.selectedModel==='string'
    && [0,512,1024,2048,4096,8192,16384,32768].includes(em!.requestedTokens)
    && Array.isArray(em!.enabledModels) && em!.enabledModels.length<=1024 && em!.enabledModels.every(n=>typeof n==='string'&&n.length<=512)
    && typeof em!.connected==='boolean' && [em!.selectedTokens,em!.contextLimit].every(n=>n===null||Number.isSafeInteger(n)&&(n as number)>0)
    && nullableCode(em!.errorCode)) projected.embedding={modelId:em!.modelId,selectedModel:em!.selectedModel,requestedTokens:em!.requestedTokens,
      enabledModels:[...em!.enabledModels],connected:em!.connected,selectedTokens:em!.selectedTokens,contextLimit:em!.contextLimit,errorCode:em!.errorCode}
  const context = services.context
  if (record(context) && [0,4096,8192,16384,32768,65536,131072,262144].includes(context!.requestedTokens)
      && (context!.selectedTokens === null || [4096,8192,16384,32768,65536,131072,262144].includes(context!.selectedTokens))
      && nullableCode(context!.errorCode)
      && ((context!.selectedTokens === null) === (context!.errorCode !== null)))
    projected.context = { requestedTokens: context!.requestedTokens, selectedTokens: context!.selectedTokens, errorCode: context!.errorCode }
  if (record(fetch) && typeof fetch!.enabled === 'boolean' && typeof fetch!.available === 'boolean')
    projected.fetch = { enabled: fetch!.enabled, available: fetch!.available }
  if (record(search) && typeof search!.enabled === 'boolean' && search!.backend === 'browser' && ['bing', 'google', 'duckduckgo'].includes(search!.engine)
      && typeof search!.available === 'boolean' && identifier(search!.adapter) && typeof search!.runtimeCheckedOnUse === 'boolean'
      && nullableCode(search!.unavailableReason) && search!.serverRequired === false && search!.networkIsolation === 'NOT_PROVIDED')
    projected.search = { enabled: search!.enabled, backend: 'browser', engine: search!.engine, available: search!.available, adapter: search!.adapter,
      runtimeCheckedOnUse: search!.runtimeCheckedOnUse, unavailableReason: search!.unavailableReason,
      serverRequired: false, networkIsolation: 'NOT_PROVIDED' }
  if (record(browser) && typeof browser!.enabled === 'boolean' && ['webview2', 'chrome', 'edge'].includes(browser!.selected) && typeof browser!.available === 'boolean'
      && nullableCode(browser!.unavailableReason) && identifier(browser!.adapter) && typeof browser!.runtimeCheckedOnUse === 'boolean'
      && browser!.networkIsolation === 'NOT_PROVIDED' && browser!.controlClass === 'HOST_UNISOLATED'
      && Array.isArray(browser!.choices) && browser!.choices.every(choice => record(choice)
        && ['webview2', 'chrome', 'edge'].includes(choice.browser) && identifier(choice.adapter)
        && typeof choice.available === 'boolean' && nullableCode(choice.reason)
        && (choice.installed === undefined || typeof choice.installed === 'boolean'))) {
    projected.browser = { enabled: browser!.enabled, selected: browser!.selected, available: browser!.available, unavailableReason: browser!.unavailableReason,
      adapter: browser!.adapter, runtimeCheckedOnUse: browser!.runtimeCheckedOnUse, networkIsolation: 'NOT_PROVIDED', controlClass: 'HOST_UNISOLATED',
      choices: browser!.choices.map(choice => ({ browser: choice.browser, adapter: choice.adapter, available: choice.available,
        reason: choice.reason, ...(typeof choice.installed === 'boolean' ? { installed: choice.installed } : {}) })),
      ...(identifier(browser!.controlState) ? { controlState: browser!.controlState } : {}),
      ...(identifier(browser!.sessionState) ? { sessionState: browser!.sessionState } : {}),
      ...(typeof browser!.hasPage === 'boolean' ? { hasPage: browser!.hasPage } : {}),
      ...(nullableCode(browser!.lastErrorCode) ? { lastErrorCode: browser!.lastErrorCode } : {}) }
  }
  if (record(memory) && ['lexicalRecall', 'semantic', 'autoCapture'].every(key => typeof (memory as any)[key] === 'boolean'))
    projected.memory = { lexicalRecall: memory!.lexicalRecall, semantic: memory!.semantic, autoCapture: memory!.autoCapture,
      ...(typeof memory!.semanticAvailable==='boolean'?{semanticAvailable:memory!.semanticAvailable}:{}),
      ...(typeof memory!.maintenanceBusy==='boolean'?{maintenanceBusy:memory!.maintenanceBusy}:{}),
      ...(Array.isArray(memory!.sensitiveProjects)&&memory!.sensitiveProjects.every((p:unknown)=>typeof p==='string'&&p.length<=4096)?{sensitiveProjects:[...memory!.sensitiveProjects]}:{}),
      ...(['off', 'propose_only', 'low_risk'].includes(memory!.captureMode || '') ? { captureMode: memory!.captureMode } : {}) }
  return projected
}
const MEMORY_COMMANDS = new Set(['memory_status','memory_list','memory_search','memory_show',
  'memory_remember','memory_correct','memory_forget','memory_export','memory_configure','memory_reset_settings',
  'memory_project_access','memory_import','memory_export_all',
  'memory_proposals','memory_confirm','memory_reject','memory_edit','memory_delete'])
const KNOWLEDGE_COMMANDS = new Set(['source_import','source_promote','source_delete','source_list','source_status','source_cancel',
  'source_import_url','source_refresh_url','source_refresh','source_detail','source_remote','source_export'])
const MODEL_REQUEST_TERMINALS = new Map([
  ['catalog', 'catalog'], ['recommend', 'recommend'],
  ['library_search', 'library_search'], ['library_variants', 'library_variants'],
  ['pull_model', 'pull_done'], ['delete_model', 'delete_done'], ['update_catalog', 'catalog_updated'],
])

function uncheckedReadiness(reason = 'CHECKING'): ChatReadiness {
  return { schemaVersion: 1, sessionId: null, providerId: '', modelId: '', providerRevision: 0,
    ready: false, reason, observedAt: null, installedModels: [], requiredAction: null }
}
type RuntimeIdentity = { providerId: string; modelId: string; providerRevision: number }
type ReadinessRequest = { id: string; sessionId: string; runtime: RuntimeIdentity; epoch: number }

export function projectTranscript(transcript: Array<Record<string, any>>, prefix: string): Message[] {
  const messages: Message[] = []
  transcript.forEach((raw, index) => {
    if (raw.role === 'user' || raw.role === 'assistant') {
      const calls = (raw.tool_calls || []).map((call: any) => ({
        name: call.function?.name || '', args: call.function?.arguments || {},
      }))
      messages.push({ id: `${prefix}:${index}`, sourceIndex: index, role: raw.role, content: raw.content || '',
        ...(raw.role==='assistant' && raw.knowledgeCitations ? {knowledgeCitations:raw.knowledgeCitations} : {}),
        ...(raw.role === 'user' && Array.isArray(raw.attachmentRefs) ? {attachmentRefs:raw.attachmentRefs} : {}),
        ...(raw.role === 'user' && Array.isArray(raw.sourceContext) ? {sourceContext:raw.sourceContext.filter((row: any) =>
          record(row) && typeof row.sourceId === 'string' && typeof row.displayName === 'string'
          && ['complete','partial','unavailable'].includes(row.status))} : {}),
        ...(calls.length ? { toolCalls: calls, toolResults: [] } : {}) })
    } else if (raw.role === 'tool') {
      const last = messages[messages.length - 1]
      if (last?.role === 'assistant') {
        last.toolResults = [...(last.toolResults || []), { name: raw.tool_name || raw.name || '', output: raw.content || '' }]
      }
    }
  })
  return messages
}

/** Single renderer-independent client of the backend. Owns only a replaceable
 * display projection/cursor, never authority, Turn lifecycle or approvals. */
export class DesktopApplicationClient {
  view: DesktopSessionView = {
    sessionId: null, sequence: 0, stateRevision: 0, workspace: null,
    status: { model: '', provider: '', connected: false, ready: false, tools: [] },
    messages: [], activeTurnId: null, activeGenerationId: null, approvals: [], inputs: [], resumable: null,
    toolActivities: [],
    readiness: uncheckedReadiness(), modelPreferenceError: null, modelDownload: null,
    conversation: { hasConversation: false, unreadCount: 0, historyVisible: false, preferenceError: null },
    rag: { enabled: false, availability: 'UNKNOWN' }, ragProgress: '', ragResult: null,
    error: null, gap: false, recovering: false, fileRevision: 0,
  }
  private readonly download = new ModelDownload(frame => this.transmit(frame), state => {
    this.view = { ...this.view, modelDownload: state }; this.changed()
  }, models => { this.view = { ...this.view, readiness: { ...this.view.readiness, installedModels: models } } },
    () => this.refreshReadiness(true), () => { this.refresh(); if (this.download.state?.phase !== 'complete') this.refreshReadiness(true) })
  modelDownloadBusy() { return this.download.busy() }
  beginModelDownload(frame: Record<string, any>) {
    if (this.modelDownloadBusy() || this.workspaceBusy() || !this.view.status.ready || !this.view.status.connected ||
        !this.view.sessionId || this.view.recovering || this.pending.size > 0 || this.awaitingModelConfirmation || !Number.isSafeInteger(frame.id) || frame.id < 1 ||
        typeof frame.model !== 'string' || !frame.model || [...this.modelRequests.values()].some(kind => ['delete_done', 'catalog_updated'].includes(kind))) return false
    this.readinessEpoch++ // Old probes drain without turning a download into a connection warning.
    return this.download.start(frame.id, frame.model)
  }
  retryDownloadInventory() { return this.download.refreshInventory() }
  private serial = 0
  private conversationNotifications = new ConversationNotifications()
  private activityTurns: Array<Record<string, any>> = []
  private snapshotRequest: string | null = null
  private refreshAgain = false
  private subscription: string | null = null
  private reconnectCursor: { sessionId: string; sequence: number } | null = null
  private pending = new Map<string, { commandId: string; resolve: (receipt: CommandReceipt) => void;
    kind: string; modelId?: string; runtime?: RuntimeIdentity; settingsSessionId?: string }>()
  private runtimeIdentity: RuntimeIdentity | null = null
  private readinessRequest: ReadinessRequest | null = null
  private readinessEpoch = 0
  private readinessTimer: ReturnType<typeof setTimeout> | null = null
  private readinessLastAttempt = 0
  private retiredReadiness = new Set<string>()
  private confirmedModelObserver?: (runtime: { providerId: string; modelId: string }) => void
  private awaitingModelConfirmation: { sessionId: string; modelId: string; runtime: RuntimeIdentity } | null = null
  private modelConfirmationTimer: ReturnType<typeof setTimeout> | null = null
  private memoryPending = new Map<string, { commandId: string; resolve: (result: MemoryControlResult) => void }>()
  private knowledgePending = new Map<string, {commandId:string;resolve:(receipt:CommandReceipt)=>void}>()
  private storagePending = new Map<string, {resolve:(result:StorageResult<any>)=>void;timer:ReturnType<typeof setTimeout>}>()
  private retiredStorage = new Set<string>()
  private workspaceRequest: {id:string;path:string;sessionId:string;acknowledged:boolean;
    resolve:(value:{success:boolean;error?:{code:string}})=>void;timer:ReturnType<typeof setTimeout>} | null = null
  private serviceWorkActive = false
  private modelRequests = new Map<number, string>()
  private providerFailures = new Set<string>()
  constructor(private send: (frame: object) => boolean | void,
              private publish: (view: DesktopSessionView) => void,
              private approvalProof?: (command: Record<string, unknown>) => string) {}

  private id() { return `desktop-${++this.serial}` }
  private changed() { this.publish(this.view) }
  /** Main registers an actually submitted auxiliary model request. Its result
   * still reaches the renderer's model panel through the ordinary message relay;
   * it must not also become an unrelated chat/transport error. */
  trackModelRequest(frame: Record<string, any>): boolean {
    if (!frame || !Number.isSafeInteger(frame.id) || frame.id < 1 || !MODEL_REQUEST_TERMINALS.has(frame.type)) return false
    if (this.pending.has(frame.id) || this.memoryPending.has(frame.id) || this.knowledgePending.has(frame.id) ||
        frame.id === this.snapshotRequest || frame.id === this.subscription || frame.id === this.readinessRequest?.id ||
        frame.id === this.workspaceRequest?.id) return false
    if (this.modelRequests.has(frame.id)) {
      // A colliding request loses suppression; never attribute another error to
      // an old operation solely because the sender reused its number.
      this.modelRequests.delete(frame.id)
      return false
    }
    if (this.modelRequests.size >= 256) return false
    this.modelRequests.set(frame.id, MODEL_REQUEST_TERMINALS.get(frame.type)!)
    return true
  }
  workspaceBusy() {
    return this.modelDownloadBusy() || !!this.workspaceRequest || !!this.view.activeTurnId || !!this.view.activeGenerationId
      || this.view.approvals.length > 0 || this.view.inputs.length > 0 || this.serviceWorkActive
      || this.memoryPending.size > 0 || this.knowledgePending.size > 0 || this.storagePending.size > 0
      || [...this.pending.values()].some(item => WORKSPACE_BOUND_COMMANDS.has(item.kind))
  }
  /** Host-only folder selection. A receipt is followed by a matching Application snapshot. */
  changeWorkspace(path: string): Promise<{success:boolean;error?:{code:string}}> {
    if (this.workspaceBusy() || !this.view.status.ready || !this.view.sessionId || this.view.recovering)
      return Promise.resolve({success:false,error:{code:'PROJECT_BUSY'}})
    return new Promise(resolve => {
      const id = this.id(), sessionId = this.view.sessionId!
      const timer = setTimeout(() => this.finishWorkspace(false, 'PROJECT_CHANGE_UNKNOWN'), 15_000)
      timer.unref?.()
      this.workspaceRequest = {id,path,sessionId,acknowledged:false,resolve,timer}
      this.transmit({id,type:'set_cwd',path,projectChat:true})
    })
  }
  private finishWorkspace(success:boolean, code = 'PROJECT_CHANGE_NOT_CONFIRMED') {
    const request = this.workspaceRequest
    if (!request) return
    this.workspaceRequest = null; clearTimeout(request.timer)
    request.resolve(success ? {success:true} : {success:false,error:{code}})
  }
  private lostActivityObservation() {
    const toolActivities = this.view.toolActivities.map(activity => activeActivity(activity)
      ? { ...activity, observationLost: true } : activity)
    this.view = { ...this.view, toolActivities,
      messages: attachActivities(this.view.messages, toolActivities, this.activityTurns) }
  }
  setConversationPreferences(preferences: ConversationPreferences) {
    this.conversationNotifications.setPreferences(preferences)
  }
  setHistoryVisible(visible: boolean) {
    this.conversationNotifications.setVisible(visible)
    this.view = { ...this.view, conversation: { ...this.view.conversation,
      ...this.conversationNotifications.projection } }
    this.changed()
  }
  setConfirmedModelObserver(observer: (runtime: { providerId: string; modelId: string }) => void) {
    this.confirmedModelObserver = observer
  }
  setModelPreferenceError(code: string | null) {
    this.view = { ...this.view, modelPreferenceError: code }
    this.changed()
  }
  private retireReadiness(id: string) {
    this.retiredReadiness.add(id)
    if (this.retiredReadiness.size > 64) this.retiredReadiness.delete(this.retiredReadiness.values().next().value!)
  }
  private currentReadiness(request: ReadinessRequest) {
    const runtime = this.runtimeIdentity
    return request.epoch === this.readinessEpoch && request.sessionId === this.view.sessionId && !!runtime
      && request.runtime.providerId === runtime.providerId && request.runtime.modelId === runtime.modelId
      && request.runtime.providerRevision === runtime.providerRevision
  }
  private releaseReadiness(request: ReadinessRequest) {
    this.retireReadiness(request.id)
    if (this.readinessTimer) clearTimeout(this.readinessTimer)
    this.readinessTimer = null
    this.readinessRequest = null
  }
  private invalidateReadiness() {
    // Keep the physical probe in flight until it settles. Its backend slot is
    // still occupied even though its old runtime observation is now obsolete.
    this.readinessEpoch++
    this.readinessLastAttempt = 0
    const previous = this.view.readiness, runtime = this.runtimeIdentity
    this.view = { ...this.view, readiness: { ...uncheckedReadiness(),
      sessionId: this.view.sessionId, ...(runtime || {}),
      installedModels: previous.providerId === runtime?.providerId ? previous.installedModels : [] } }
  }
  private readinessFailed(request: ReadinessRequest) {
    const current = this.currentReadiness(request)
    this.releaseReadiness(request)
    if (!current) { this.refreshReadiness(true); this.changed(); return }
    if (this.modelDownloadBusy()) { this.download.confirmReadiness(false); this.changed(); return }
    // Retain the last catalog as an observation, never claim current readiness.
    this.view = { ...this.view, readiness: { ...this.view.readiness, ready: false,
      reason: 'READINESS_CHECK_FAILED', requiredAction: null } }
    this.changed()
  }
  private resetReadiness(reason = 'CHECKING') {
    this.readinessEpoch++
    if (this.readinessRequest) this.retireReadiness(this.readinessRequest.id)
    if (this.readinessTimer) clearTimeout(this.readinessTimer)
    this.readinessTimer = null
    this.readinessRequest = null
    this.readinessLastAttempt = 0
    this.view = { ...this.view, readiness: { ...uncheckedReadiness(reason),
      sessionId: this.view.sessionId, ...(this.runtimeIdentity || {}) } }
  }
  /** Read-only host observation, separate from protocol readiness and effects. */
  refreshReadiness(force = false) {
    if (this.modelDownloadBusy() && !this.download.inventoryReady) return
    if (!this.view.status.ready || !this.view.sessionId || !this.runtimeIdentity || this.readinessRequest || this.awaitingModelConfirmation) return
    if (!force && (this.view.activeTurnId || Date.now() - this.readinessLastAttempt < 5000)) return
    this.readinessLastAttempt = Date.now()
    const request = { id: this.id(), sessionId: this.view.sessionId, runtime: { ...this.runtimeIdentity }, epoch: this.readinessEpoch }
    this.readinessRequest = request
    if (force || !this.view.readiness.observedAt) {
      this.view = { ...this.view, readiness: { ...this.view.readiness, ready: false, reason: 'CHECKING', requiredAction: null } }
    }
    this.readinessTimer = setTimeout(() => {
      if (this.readinessRequest !== request) return
      this.readinessFailed(request)
    // Two sequential provider metadata calls each allow 30 seconds.
    }, 75000)
    this.readinessTimer.unref?.()
    this.transmit({ id: request.id, type: 'get_readiness', sessionId: request.sessionId })
    this.changed()
  }
  private confirmModelSelection() {
    const pending = this.awaitingModelConfirmation
    const current = this.runtimeIdentity
    if (!pending || !current || pending.sessionId !== this.view.sessionId) return
    if (current.providerRevision <= pending.runtime.providerRevision) return
    this.awaitingModelConfirmation = null
    if (this.modelConfirmationTimer) clearTimeout(this.modelConfirmationTimer)
    this.modelConfirmationTimer = null
    if (current.providerId === pending.runtime.providerId && current.modelId === pending.modelId) {
      this.confirmedModelObserver?.({ providerId: current.providerId, modelId: current.modelId })
    } else {
      this.modelSelectionUnconfirmed()
    }
  }
  private modelSelectionUnconfirmed() {
    this.awaitingModelConfirmation = null
    if (this.modelConfirmationTimer) clearTimeout(this.modelConfirmationTimer)
    this.modelConfirmationTimer = null
    this.view = { ...this.view, error: { code: 'MODEL_SELECTION_NOT_CONFIRMED',
      message: 'The model change could not be confirmed. The current host runtime remains authoritative; no automatic retry.' } }
    this.changed()
  }
  private transmit(frame: object) {
    if (this.send(frame) === false) this.disconnected()
  }
  refresh() {
    if (this.modelDownloadBusy()) { this.refreshAgain = true; return }
    if (!this.view.status.connected || !this.view.sessionId) return
    if (this.snapshotRequest) { this.refreshAgain = true; return }
    this.snapshotRequest = this.id()
    this.transmit({ id: this.snapshotRequest, type: 'get_snapshot', sessionId: this.view.sessionId })
  }
  private subscribe() {
    this.subscription = this.id()
    const cursor = this.reconnectCursor || { sessionId: this.view.sessionId, sequence: this.view.sequence }
    this.reconnectCursor = null
    this.transmit({ id: this.subscription, type: 'subscribe_events',
      sessionId: cursor.sessionId, afterSequence: cursor.sequence })
  }
  disconnected() {
    this.download.disconnected()
    this.modelRequests.clear()
    this.finishWorkspace(false, 'PROJECT_CHANGE_UNKNOWN')
    if (this.view.sessionId) this.reconnectCursor = { sessionId: this.view.sessionId, sequence: this.view.sequence }
    this.snapshotRequest = this.subscription = null
    this.refreshAgain = false
    this.runtimeIdentity = null
    this.awaitingModelConfirmation = null
    if (this.modelConfirmationTimer) clearTimeout(this.modelConfirmationTimer)
    this.modelConfirmationTimer = null
    this.resetReadiness('BACKEND_DISCONNECTED')
    this.view = { ...this.view, recovering: true, status: { ...this.view.status, ready: false, connected: false },
      fetch: undefined, search: undefined, browser: undefined, memory: undefined, context: undefined, embedding: undefined, knowledgeSettings:undefined,
      approvals: [], inputs: [], error: { code: 'BACKEND_DISCONNECTED', message: 'Backend disconnected. Restart to restore the saved transcript; active work is not resumed.' } }
    this.lostActivityObservation()
    for (const { commandId, resolve } of this.pending.values()) resolve({ schemaVersion: 1, commandId,
      accepted: false, createdIds: {}, error: { code: 'OUTCOME_UNKNOWN', message: 'Connection lost; command outcome is unknown. It will not be retried.' } })
    this.pending.clear()
    for (const {commandId,resolve} of this.knowledgePending.values()) resolve({schemaVersion:1,commandId,
      accepted:false,createdIds:{},error:{code:'OUTCOME_UNKNOWN',message:'Source outcome unknown. No retry.'}})
    this.knowledgePending.clear()
    for (const { commandId, resolve } of this.memoryPending.values()) resolve({ schemaVersion: 1,
      commandId, completed: false, error: { code: 'OUTCOME_UNKNOWN', message: 'Connection lost; memory outcome is unknown. No retry.',
        outcomeUnknown: true, retryable: false } })
    this.memoryPending.clear()
    for (const {resolve,timer} of this.storagePending.values()) {
      clearTimeout(timer);resolve({success:false,error:{code:'STORAGE_OUTCOME_UNKNOWN'}})
    }
    this.storagePending.clear()
    this.changed()
  }
  command(kind: string, payload: Record<string, unknown>, commandId = `cmd_${randomUUID()}`): Promise<CommandReceipt> {
    if (this.modelDownloadBusy()) return Promise.resolve({schemaVersion:1,commandId,accepted:false,createdIds:{},
      error:{code:'MODEL_DOWNLOAD_BUSY',message:'Wait for the model download and inventory update.'}})
    if (SETTINGS_COMMANDS.has(kind) && !validSetting(kind, payload)) {
      return Promise.resolve({schemaVersion:1,commandId,accepted:false,createdIds:{},
        error:{code:'INVALID_APPLICATION_COMMAND',message:'Invalid service settings.'}})
    }
    if (this.workspaceRequest && WORKSPACE_BOUND_COMMANDS.has(kind)) {
      return Promise.resolve({schemaVersion:1,commandId,accepted:false,createdIds:{},
        error:{code:'PROJECT_BUSY',message:'Wait for the selected project to be confirmed.'}})
    }
    if (!PRODUCT_COMMANDS.has(kind) || !this.view.status.ready || !this.view.sessionId) {
      return Promise.resolve({ schemaVersion: 1, commandId, accepted: false, createdIds: {},
        error: { code: 'APPLICATION_UNAVAILABLE', message: 'Application command is unavailable.' } })
    }
    // No optimistic transcript/provider/lifecycle mutation. A receipt is not a terminal.
    if (kind === 'ExecuteCommand' && payload.name === 'resume') this.conversationNotifications.beginHistoryImport()
    return new Promise(resolve => {
      const id = this.id()
      this.pending.set(id, { commandId, resolve, kind,
        ...(SETTINGS_COMMANDS.has(kind) ? { settingsSessionId: this.view.sessionId! } : {}),
        ...(kind === 'ChangeModel' ? { modelId: payload.modelId as string,
          runtime: this.runtimeIdentity ? { ...this.runtimeIdentity } : undefined } : {}) })
      const command = {
        schemaVersion: 1, commandId, sessionId: this.view.sessionId, kind, payload,
        expectedRevision: SETTINGS_COMMANDS.has(kind) ? this.view.stateRevision : null,
      }
      this.transmit({ id, type: 'application_command', command,
        ...(kind === 'ResolveApproval' && this.approvalProof
          ? { hostApprovalProof: this.approvalProof(command) } : {}) })
    })
  }
  memory(name: string, args: Record<string, unknown>, commandId = `cmd_${randomUUID()}`): Promise<MemoryControlResult> {
    if (this.modelDownloadBusy()) return Promise.resolve({schemaVersion:1,commandId,completed:false,error:{code:'MODEL_DOWNLOAD_BUSY',message:'Wait for the model download.'}})
    if (!MEMORY_COMMANDS.has(name) || !this.view.status.ready || !this.view.sessionId || !this.approvalProof) {
      return Promise.resolve({ schemaVersion: 1, commandId, completed: false,
        error: { code: 'MEMORY_UNAVAILABLE', message: 'Authenticated memory control is unavailable.' } })
    }
    return new Promise(resolve => {
      const id = this.id()
      this.memoryPending.set(id, { commandId, resolve })
      const command = { schemaVersion: 1, kind: 'MemoryControl', commandId,
        sessionId: this.view.sessionId, name, arguments: args, expectedRevision: this.view.stateRevision }
      this.transmit({ id, type: 'memory_command', command, hostMemoryProof: this.approvalProof!(command) })
    })
  }
  knowledge(name:string,args:Record<string,unknown>,commandId=`cmd_${randomUUID()}`): Promise<CommandReceipt> {
    if (this.modelDownloadBusy()) return Promise.resolve({schemaVersion:1,commandId,accepted:false,createdIds:{},error:{code:'MODEL_DOWNLOAD_BUSY',message:'Wait for the model download.'}})
    if (!KNOWLEDGE_COMMANDS.has(name) || !this.view.status.ready || !this.view.sessionId || !this.approvalProof) {
      return Promise.resolve({schemaVersion:1,commandId,accepted:false,createdIds:{},
        error:{code:'KNOWLEDGE_UNAVAILABLE',message:'Authenticated source control is unavailable.'}})
    }
    return new Promise(resolve => {
      const id=this.id()
      this.knowledgePending.set(id,{commandId,resolve})
      const command={schemaVersion:1,kind:'KnowledgeControl',commandId,sessionId:this.view.sessionId,
        name,arguments:args,expectedRevision:this.view.stateRevision}
      this.transmit({id,type:'knowledge_command',command,hostKnowledgeProof:this.approvalProof!(command)})
    })
  }
  storage(name:string,args:Record<string,unknown>):Promise<StorageResult<any>> {
    if (!['report','move','delete','detach_project','delete_project','delete_all','export','source_report','source_move','source_delete','source_export','source_preview'].includes(name) ||
        this.workspaceBusy() || !this.view.status.ready || !this.view.sessionId || !this.approvalProof || this.view.recovering)
      return Promise.resolve({success:false,error:{code:'PROJECT_BUSY'}})
    return new Promise(resolve=>{
      const id=this.id()
      const timer=setTimeout(()=>{
        if(!this.storagePending.delete(id))return
        this.retiredStorage.add(id)
        if(this.retiredStorage.size>128)this.retiredStorage.delete(this.retiredStorage.values().next().value!)
        resolve({success:false,error:{code:'STORAGE_OUTCOME_UNKNOWN'}})
        this.refresh()
      },30_000)
      timer.unref?.()
      this.storagePending.set(id,{resolve,timer})
      const command={schemaVersion:1,kind:'StorageControl',commandId:`cmd_${randomUUID()}`,
        sessionId:this.view.sessionId,name,arguments:args,expectedRevision:this.view.stateRevision}
      this.transmit({id,type:'storage_command',command,hostStorageProof:this.approvalProof!(command)})
    })
  }
  receive(frame: Record<string, any>) {
    if (this.retiredStorage.has(frame.id) && ['storage_result','error'].includes(frame.type)) return
    if (this.storagePending.has(frame.id) && ['storage_result','error'].includes(frame.type)) {
      const pending=this.storagePending.get(frame.id)!
      this.storagePending.delete(frame.id);clearTimeout(pending.timer)
      if(Number.isSafeInteger(frame.stateRevision) && frame.stateRevision>=this.view.stateRevision) {
        this.view={...this.view,stateRevision:frame.stateRevision,...(frame.data?.knowledge?{knowledge:frame.data.knowledge}:{})}
        this.changed()
      }
      pending.resolve(frame.type==='storage_result' && frame.success ? {success:true,data:frame.data} :
        {success:false,error:frame.error||{code:frame.code||'STORAGE_FAILED'}})
      if(frame.type==='storage_result')this.refresh()
      return
    }
    if (this.download.receive(frame)) return
    if (['error', 'readiness'].includes(frame.type) && this.retiredReadiness.has(frame.id)) return
    const modelTerminal = this.modelRequests.get(frame.id)
    if (modelTerminal && frame.type === 'error') {
      this.modelRequests.delete(frame.id)
      return
    }
    if (modelTerminal && frame.type === modelTerminal) this.modelRequests.delete(frame.id)
    if (frame.type === 'ready') {
      this.download.disconnected()
      // A backend/session replacement cannot confirm an earlier settings write.
      for (const [id, pending] of this.pending) {
        if (!pending.settingsSessionId) continue
        pending.resolve({schemaVersion:1,commandId:pending.commandId,accepted:false,createdIds:{},
          error:{code:'OUTCOME_UNKNOWN',message:'Service settings could not be confirmed. No automatic retry.'}})
        this.pending.delete(id)
      }
      if (this.view.sessionId !== frame.sessionId) {
        this.snapshotRequest = this.subscription = null
        this.refreshAgain = false
      }
      this.modelRequests.clear()
      this.runtimeIdentity = null
      this.awaitingModelConfirmation = null
      if (this.modelConfirmationTimer) clearTimeout(this.modelConfirmationTimer)
      this.modelConfirmationTimer = null
      this.resetReadiness()
      this.view = { ...this.view, sessionId: frame.sessionId, recovering: true,
        fetch: undefined, search: undefined, browser: undefined, memory: undefined, context: undefined, embedding: undefined,
        status: { ...this.view.status, connected: true, ready: false, tools: frame.tools || [] },
        resumable: frame.resumable || null, ragProgress: '', ragResult: null, error: null }
      this.refresh()
    } else if (frame.type === 'readiness' && frame.id === this.readinessRequest?.id) {
      const request = this.readinessRequest!
      const currentRequest = this.currentReadiness(request)
      this.releaseReadiness(request)
      if (!currentRequest) { this.refreshReadiness(true); this.changed(); return }
      const data = frame.data as ChatReadiness
      const current = this.runtimeIdentity
      if (data?.schemaVersion === 1 && data.sessionId === this.view.sessionId && current &&
          data.providerId === current.providerId && data.modelId === current.modelId &&
          data.providerRevision === current.providerRevision && typeof data.ready === 'boolean' &&
          typeof data.observedAt === 'string' && Number.isFinite(Date.parse(data.observedAt)) &&
          Array.isArray(data.installedModels) && (!data.ready || data.reason === null)) {
        this.view = { ...this.view, readiness: { ...data,
          installedModels: data.installedModels.filter(item => item && typeof item.name === 'string' && item.name).map(item=>({name:item.name,size:item.size,kind:['llm','embedding'].includes(item.kind||'')?item.kind:'unknown',contextLength:typeof item.contextLength==='number'&&Number.isSafeInteger(item.contextLength)&&item.contextLength>0?item.contextLength:null})),
          requiredAction: ['SELECT_MODEL', 'CONFIGURE_PROVIDER'].includes(data.requiredAction || '') ? data.requiredAction : null } }
        const downloaded = this.download.state?.model
        const downloadedTag = downloaded?.includes(':') ? downloaded : downloaded + ':latest'
        this.download.confirmReadiness(data.installedModels.some(item => item?.name === downloadedTag))
        this.refresh()
      } else {
        this.download.confirmReadiness(false)
        this.view = { ...this.view, readiness: { ...uncheckedReadiness('READINESS_CHECK_FAILED'),
          sessionId: request.sessionId, ...(current || request.runtime) } }
      }
    } else if (frame.type === 'snapshot' && frame.id === this.snapshotRequest) {
      this.snapshotRequest = null
      this.snapshot(frame.data)
      if (!this.subscription) this.subscribe()
      if (this.refreshAgain) { this.refreshAgain = false; this.refresh() }
    } else if (frame.type === 'event' && frame.id === this.subscription && frame.schemaVersion === 1) {
      this.event(frame.event)
    } else if (frame.type === 'subscription_out_of_sync' && frame.id === this.subscription) {
      this.reconnectCursor = { sessionId: this.view.sessionId!, sequence: this.view.sequence }
      this.subscription = null
      this.view = { ...this.view, gap: true, recovering: true }
      this.lostActivityObservation()
      this.refresh()
    } else if (frame.type === 'application_result' && this.pending.has(frame.id)) {
      const receipt = frame.data as CommandReceipt
      const pending = this.pending.get(frame.id)!
      if (receipt.accepted && pending.kind === 'ChangeModel' && pending.runtime && pending.modelId && this.view.sessionId) {
        this.awaitingModelConfirmation = { sessionId: this.view.sessionId, modelId: pending.modelId, runtime: pending.runtime }
        if (this.modelConfirmationTimer) clearTimeout(this.modelConfirmationTimer)
        this.modelConfirmationTimer = setTimeout(() => this.modelSelectionUnconfirmed(), 10_000)
        this.modelConfirmationTimer.unref?.()
      }
      if (receipt.accepted && ['ChangeModel', 'ChangeProvider'].includes(pending.kind)) this.invalidateReadiness()
      pending.resolve(receipt)
      this.pending.delete(frame.id)
      // Context errors belong to the settings form; they do not replace chat
      // errors or leave a conversation banner after a cancelled settings draft.
      if (pending.kind !== 'SetContextWindow')
        this.view = { ...this.view, error: receipt.accepted ? null : receipt.error || null }
      this.confirmModelSelection()
      this.refresh()
    } else if (frame.type === 'knowledge_result' && this.knowledgePending.has(frame.id)) {
      this.knowledgePending.get(frame.id)!.resolve(frame.data as CommandReceipt)
      this.knowledgePending.delete(frame.id)
      this.refresh()
    } else if (frame.type === 'memory_result' && this.memoryPending.has(frame.id)) {
      // The next inspection may be issued before the asynchronous snapshot arrives.
      // Advance only the authenticated receipt revision; never retain memory content.
      if(Number.isSafeInteger(frame.data?.stateRevision)&&frame.data.stateRevision>=this.view.stateRevision){
        this.view={...this.view,stateRevision:frame.data.stateRevision};this.changed()
      }
      this.memoryPending.get(frame.id)!.resolve(frame.data as MemoryControlResult)
      this.memoryPending.delete(frame.id)
      // No MEMORY payload stored in the chat view, transcript or recall cache.
      this.refresh()
    } else if (frame.type === 'error') {
      if (this.workspaceRequest && frame.id === this.workspaceRequest.id) {
        this.finishWorkspace(false, frame.code || 'PROJECT_CHANGE_FAILED')
        this.changed(); return
      }
      const error = { code: frame.code || 'TRANSPORT_ERROR', message: frame.message || 'Request failed' }
      if (this.readinessRequest && frame.id === this.readinessRequest.id) {
        this.readinessFailed(this.readinessRequest)
        return
      }
      const selectionSnapshotFailed = frame.id === this.snapshotRequest && !!this.awaitingModelConfirmation
      if (this.pending.has(frame.id)) {
        const pending = this.pending.get(frame.id)!
        pending.resolve({ schemaVersion: 1, commandId: pending.commandId, accepted: false, createdIds: {}, error })
        this.pending.delete(frame.id)
      }
      if (this.memoryPending.has(frame.id)) {
        const pending = this.memoryPending.get(frame.id)!
        pending.resolve({ schemaVersion: 1, commandId: pending.commandId, completed: false, error })
        this.memoryPending.delete(frame.id)
      }
      if (this.knowledgePending.has(frame.id)) {
        const p=this.knowledgePending.get(frame.id)!
        p.resolve({schemaVersion:1,commandId:p.commandId,accepted:false,createdIds:{},error})
        this.knowledgePending.delete(frame.id)
      }
      if (frame.id === this.snapshotRequest) {
        this.snapshotRequest = null
        if (this.awaitingModelConfirmation) this.modelSelectionUnconfirmed()
      }
      if (!selectionSnapshotFailed) this.view = { ...this.view, error }
    } else if (frame.type === 'cwd_changed') {
      const workspaceRequest = this.workspaceRequest
      if (workspaceRequest && frame.id === workspaceRequest.id) workspaceRequest.acknowledged = true
      this.view = { ...this.view, resumable: frame.resumable || null }
      this.refresh()
    }
    this.changed()
  }
  private snapshot(state: SessionSnapshot) {
    if (!state || state.sessionId !== this.view.sessionId || !Array.isArray(state.transcript)) return
    if (this.view.status.ready && (state.lastSequence < this.view.sequence || state.stateRevision < this.view.stateRevision)) {
      this.refreshAgain = true; return
    }
    const active = state.turns.find(t => !['completed', 'failed', 'cancelled'].includes(t.status))
    this.serviceWorkActive = (state.services.operations || []).some(op => ['requested','pending','running','cancelling'].includes(op.status))
    const lastTurn = state.turns[state.turns.length - 1]
    const lastRetrieval = [...(state.services.operations || [])].reverse().find(op => op.service === 'rag' && op.result)
    const chatIdentity = `${state.sessionId}-${createHash('sha256').update(state.workspace).digest('hex').slice(0,16)}`
    let messages = projectTranscript(state.transcript, chatIdentity)
    for (const item of state.services.conversationPresentation || []) {
      const row = messages.find(message => message.sourceIndex === item.sourceIndex)
      if (!row) continue
      for (const key of ['createdAt', 'completedAt', 'savedAt'] as const) {
        const value = item[key]
        if (typeof value === 'string' && Number.isFinite(Date.parse(value))) row[key] = value
      }
    }
    // Preserve existing harness chips after terminal/reload, using explicit
    // transcript ranges owned by Application rather than matching message text.
    for (const turn of state.turns) {
      // Metadata is an owner-facing Application sidecar, never provider input.
      const metadata = [turn.userMessage, ...(turn.displayMessages || [])]
      for (const item of metadata) {
        if (!item || typeof item.id !== 'string' || !Number.isInteger(item.sourceIndex)) continue
        const row = messages.find(m => m.sourceIndex === item.sourceIndex)
        if (row) Object.assign(row, { id: item.id, createdAt: item.createdAt,
          completedAt: item.completedAt, deliveryStatus: item.status })
      }
      const rules = (turn.displayMessages || []).flatMap((m: any) => m.harnessEvents || [])
      const rows = messages.filter(m => m.role === 'assistant' && m.sourceIndex !== undefined &&
        m.sourceIndex >= turn.transcriptStart && m.sourceIndex < turn.transcriptEnd)
      if (rules.length && rows.length) rows[rows.length - 1].harnessEvents = rules
      if (['completed', 'failed', 'cancelled'].includes(turn.status)) {
        // A stopped stream may have been observed but never appended to the
        // inference transcript. Keep that visible partial as interrupted,
        // preserving its exact identity without inventing a completed reply.
        const partials = (turn.displayMessages || []).filter((m: any) => !Number.isInteger(m.sourceIndex)
          && ['cancelled', 'failed'].includes(m.status) && (m.content?.trim() || m.toolCalls?.length))
          .map((m: any, i: number) => ({ ...m, id: m.id || `${turn.turnId}:partial:${i}`,
            deliveryStatus: m.status, streaming: false }))
        const next = messages.findIndex(m => m.sourceIndex !== undefined && m.sourceIndex >= turn.transcriptEnd)
        messages.splice(next < 0 ? messages.length : next, 0, ...partials)
      }
    }
    if (active) {
      const display = active.displayMessages?.length ? active.displayMessages : [{ role: 'assistant', content: '', thinking: true }]
      display.forEach((m: any, i: number) => messages.push({ ...m,
        id: m.id || `${active.turnId}:${i}`, deliveryStatus: m.status || 'streaming',
        streaming: !m.status || m.status === 'streaming' }))
    }
    this.activityTurns = state.turns
    const toolActivities = state.turns.flatMap(turn => (turn.toolActivities || [])
      .map((raw: any) => toolActivity(raw, turn.turnId)).filter(Boolean)) as import('../src/types').ToolActivity[]
    messages = attachActivities(messages, toolActivities, state.turns)
    const previousRuntime = this.runtimeIdentity
    this.runtimeIdentity = { providerId: state.modelRuntime.providerId, modelId: state.modelRuntime.modelId,
      providerRevision: state.modelRuntime.providerRevision }
    const runtimeChanged = !previousRuntime || ['modelId', 'providerId', 'providerRevision'].some(key =>
      previousRuntime[key as keyof RuntimeIdentity] !== this.runtimeIdentity![key as keyof RuntimeIdentity])
    if (runtimeChanged) this.invalidateReadiness()
    const settings = settingsProjection(state.services)
    const failureRuntimeMatches = lastTurn?.modelRuntime?.providerId === state.modelRuntime.providerId &&
      lastTurn.modelRuntime?.modelId === state.modelRuntime.modelId &&
      lastTurn.modelRuntime?.providerRevision === state.modelRuntime.providerRevision
    const obsoleteProviderFailure = !!lastTurn?.modelRuntime && !failureRuntimeMatches &&
      ['OLLAMA_CONNECTION_FAILED', 'OLLAMA_CONNECT_TIMEOUT', 'OLLAMA_RESPONSE_TIMEOUT', 'OLLAMA_MODEL_UNAVAILABLE'].includes(lastTurn.errorCode || '')
    this.view = { ...this.view, sequence: state.lastSequence, stateRevision: state.stateRevision, recovering: false,
      workspace: state.workspace, activeTurnId: active?.turnId || null, messages,
      toolActivities,
      conversation: { hasConversation: messages.some(m => m.role === 'user'),
        ...this.conversationNotifications.observe(chatIdentity, messages) },
      activeGenerationId: active?.activeGenerationId || null,
      status: { ...this.view.status, ready: true, connected: true,
        model: state.modelRuntime.modelId, provider: state.modelRuntime.providerId },
      approvals: state.services.interactions?.approvals || [], inputs: state.services.interactions?.inputs || [],
      rag: state.services.rag,
      fetch: undefined, search: undefined, browser: undefined, memory: undefined, context: undefined, embedding: undefined,
      ...settings,
      knowledge: state.services.knowledge,
      knowledgeOperations: (state.services.operations || []).filter(op => op.service === 'knowledge'),
      ragProgress: state.services.operations?.find(op => op.service === 'rag' &&
        ['running', 'requested'].includes(op.status))?.phase || '',
      ragResult: lastRetrieval?.result || this.view.ragResult,
      fileRevision: state.services.filesystem?.revision ?? this.view.fileRevision,
      error: obsoleteProviderFailure ? (this.view.error?.turnId === lastTurn?.turnId ? null : this.view.error)
        : lastTurn?.status === 'failed' ? { code: lastTurn.errorCode || 'TURN_FAILED', message: 'Turn failed.', turnId: lastTurn.turnId } : this.view.error,
      ...(messages.length ? { resumable: null } : {}),
    }
    if (lastTurn?.status === 'failed' && state.modelRuntime.providerId === 'ollama' &&
        ['OLLAMA_CONNECTION_FAILED', 'OLLAMA_CONNECT_TIMEOUT', 'OLLAMA_MODEL_UNAVAILABLE', 'OllamaRequestError', 'OllamaStreamError'].includes(lastTurn.errorCode || '') &&
        failureRuntimeMatches) {
      const failure = state.sessionId + ':' + lastTurn.turnId
      if (!this.providerFailures.has(failure)) {
        this.providerFailures.add(failure)
        if (this.providerFailures.size > 64) this.providerFailures.delete(this.providerFailures.values().next().value!)
        this.invalidateReadiness()
        const reason = lastTurn.errorCode === 'OLLAMA_CONNECTION_FAILED' ? 'OLLAMA_UNAVAILABLE'
          : lastTurn.errorCode === 'OLLAMA_CONNECT_TIMEOUT' ? 'OLLAMA_CONNECTION_TIMEOUT'
          : lastTurn.errorCode === 'OLLAMA_MODEL_UNAVAILABLE' ? 'MODEL_NOT_INSTALLED' : 'CHECKING'
        this.view = { ...this.view, readiness: { ...this.view.readiness, reason,
          requiredAction: reason === 'MODEL_NOT_INSTALLED' ? 'SELECT_MODEL' : null } }
        // Revalidate once after a terminal inference failure; never resend the Turn.
        // A real connection failure remains actionable while the periodic probe runs.
        if (reason === 'CHECKING') this.refreshReadiness(true)
      }
    }
    if (this.workspaceRequest?.acknowledged && state.sessionId === this.workspaceRequest.sessionId) {
      const normalize = (value:string) => process.platform === 'win32' ? value.replace(/\//g,'\\').toLowerCase() : value
      this.finishWorkspace(normalize(state.workspace) === normalize(this.workspaceRequest.path))
    }
    if ((state.services.securityAudit?.deliveryFailures || 0) > 0) {
      this.view = { ...this.view, error: { code: 'SECURITY_AUDIT_DELIVERY_FAILED',
        message: 'Audit gap. Observed result retained; no automatic retry or rollback.' } }
    }
    this.confirmModelSelection()
    if (runtimeChanged || this.view.readiness.reason === 'CHECKING') this.refreshReadiness(true)
  }
  private event(event: EventEnvelope) {
    if (!event || event.schemaVersion !== 1 || event.sessionId !== this.view.sessionId) return
    if (event.sequence <= this.view.sequence) return
    if (event.kind === 'EventGap') {
      this.view = { ...this.view, gap: true, recovering: true }
      this.lostActivityObservation()
    }
    this.view = { ...this.view, sequence: event.sequence, stateRevision: event.stateRevision }
    if (event.payload.securityAudit?.gap === true) {
      this.view = { ...this.view, error: { code: 'SECURITY_AUDIT_DELIVERY_FAILED',
        message: 'Audit gap. Observed result retained; no automatic retry or rollback.' } }
    }
    if (event.kind === 'SessionSnapshot') { this.snapshot(event.payload as SessionSnapshot); return }
    if (event.payload.activity && event.turnId) {
      const activity = toolActivity(event.payload.activity, event.turnId)
      if (!activity || activity.operationId !== event.operationId || activity.toolCallId !== event.toolCallId
          || !this.activityTurns.some(turn => turn.turnId === event.turnId)) { this.refresh(); return }
      const old = this.view.toolActivities.find(row => row.operationId === activity.operationId)
      if (old && (old.toolCallId !== activity.toolCallId || old.turnId !== activity.turnId
          || (!activeActivity(old) && activeActivity(activity)) || activity.outputSequence < old.outputSequence)) return
      const toolActivities = [...this.view.toolActivities.filter(row => row.operationId !== activity.operationId), activity]
      this.view = { ...this.view, toolActivities, messages: attachActivities(this.view.messages, toolActivities, this.activityTurns) }
      return
    }
    if (event.kind === 'OperationProgress' && event.payload.service === 'tool') {
      const activity = this.view.toolActivities.find(row => row.operationId === event.operationId && row.toolCallId === event.toolCallId && row.turnId === event.turnId)
      const sequence = event.payload.outputSequence
      if (!activity || !activeActivity(activity) || !Number.isInteger(sequence)) { this.refresh(); return }
      if (sequence <= activity.outputSequence) return
      if (sequence !== activity.outputSequence + 1 || !['stdout', 'stderr'].includes(event.payload.channel)
          || typeof event.payload.text !== 'string') { this.refresh(); return }
      const channel = event.payload.channel as 'stdout' | 'stderr'
      const text = (activity[channel] + event.payload.text).slice(0, 32768)
      const next = { ...activity, [channel]: text, outputSequence: sequence,
        outputTruncated: activity.outputTruncated || event.payload.outputTruncated === true || text.length < activity[channel].length + event.payload.text.length }
      const toolActivities = this.view.toolActivities.map(row => row.operationId === next.operationId ? next : row)
      this.view = { ...this.view, toolActivities, messages: attachActivities(this.view.messages, toolActivities, this.activityTurns) }
      return
    }
    if (event.kind === 'AssistantDelta' || event.kind === 'ThinkingDelta') {
      if (event.turnId !== this.view.activeTurnId || event.generationId !== this.view.activeGenerationId) { this.refresh(); return }
      if (this.view.recovering) { this.refresh(); return }
      const messages = [...this.view.messages]
      let index = messages.findIndex(message => message.role === 'assistant' && message.generationId === event.generationId)
      if (index < 0) {
        // Compatibility snapshots predating public generation metadata.
        for (let i = messages.length - 1; i >= 0; i--) {
          if (messages[i].role === 'assistant' && !messages[i].generationId && messages[i].streaming
              && !messages[i].id.startsWith('activity:')) { index = i; break }
        }
      }
      const last = messages[index]
      if (last) messages[index] = { ...last,
        content: event.kind === 'AssistantDelta' ? last.content + event.payload.text : last.content,
        thinking: event.kind === 'ThinkingDelta' && !last.content, streaming: true }
      this.view = { ...this.view, messages }
      return
    }
    if (event.kind === 'OperationProgress' && event.payload.service === 'rag') {
      this.view = { ...this.view, ragProgress: event.payload.phase || '' }
    }
    if (event.payload.service === 'rag' && event.kind.startsWith('Operation') && event.kind !== 'OperationProgress') {
      this.view = { ...this.view, ragProgress: '', ragResult: event.payload.result || null }
    }
    if (['ToolCompleted', 'ToolFailed'].includes(event.kind) && ['write', 'edit', 'bash'].includes(event.payload.name)) {
      this.view = { ...this.view, fileRevision: this.view.fileRevision + 1 }
    }
    // Rebuild non-delta state from authority, including multiple simultaneous
    // human requests. No reducer in React invents terminal or permission state.
    this.refresh()
  }
}
