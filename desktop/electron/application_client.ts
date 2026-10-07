import { randomUUID } from 'node:crypto'
import type { Message } from '../src/types'
import type { DesktopSessionView, SessionSnapshot, EventEnvelope, CommandReceipt } from '../shared/application'
import type { MemoryControlResult } from '../shared/application'

const PRODUCT_COMMANDS = new Set([
  'SubmitUserInput', 'CancelTurn', 'StopGeneration', 'ChangeModel', 'ChangeProvider',
  'ResolveApproval', 'ResolveUserInput', 'ExecuteCommand', 'SetRAGEnabled', 'QueryRAG',
])
const MEMORY_COMMANDS = new Set(['memory_status','memory_list','memory_search','memory_show',
  'memory_remember','memory_correct','memory_forget','memory_export',
  'memory_proposals','memory_confirm','memory_reject'])

export function projectTranscript(transcript: Array<Record<string, any>>, prefix: string): Message[] {
  const messages: Message[] = []
  transcript.forEach((raw, index) => {
    if (raw.role === 'user' || raw.role === 'assistant') {
      const calls = (raw.tool_calls || []).map((call: any) => ({
        name: call.function?.name || '', args: call.function?.arguments || {},
      }))
      messages.push({ id: `${prefix}:${index}`, sourceIndex: index, role: raw.role, content: raw.content || '',
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
    rag: { enabled: false, availability: 'UNKNOWN' }, ragProgress: '', ragResult: null,
    error: null, gap: false, fileRevision: 0,
  }
  private serial = 0
  private snapshotRequest: string | null = null
  private refreshAgain = false
  private subscription: string | null = null
  private reconnectCursor: { sessionId: string; sequence: number } | null = null
  private pending = new Map<string, { commandId: string; resolve: (receipt: CommandReceipt) => void }>()
  private memoryPending = new Map<string, { commandId: string; resolve: (result: MemoryControlResult) => void }>()
  constructor(private send: (frame: object) => boolean | void,
              private publish: (view: DesktopSessionView) => void,
              private approvalProof?: (command: Record<string, unknown>) => string) {}

  private id() { return `desktop-${++this.serial}` }
  private changed() { this.publish(this.view) }
  private transmit(frame: object) {
    if (this.send(frame) === false) this.disconnected()
  }
  refresh() {
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
    if (this.view.sessionId) this.reconnectCursor = { sessionId: this.view.sessionId, sequence: this.view.sequence }
    this.snapshotRequest = this.subscription = null
    this.refreshAgain = false
    this.view = { ...this.view, status: { ...this.view.status, ready: false, connected: false },
      approvals: [], inputs: [], error: { code: 'BACKEND_DISCONNECTED', message: 'Backend disconnected. Restart to restore the saved transcript; active work is not resumed.' } }
    for (const { commandId, resolve } of this.pending.values()) resolve({ schemaVersion: 1, commandId,
      accepted: false, createdIds: {}, error: { code: 'OUTCOME_UNKNOWN', message: 'Connection lost; command outcome is unknown. It will not be retried.' } })
    this.pending.clear()
    for (const { commandId, resolve } of this.memoryPending.values()) resolve({ schemaVersion: 1,
      commandId, completed: false, error: { code: 'OUTCOME_UNKNOWN', message: 'Connection lost; memory outcome is unknown. No retry.',
        outcomeUnknown: true, retryable: false } })
    this.memoryPending.clear()
    this.changed()
  }
  command(kind: string, payload: Record<string, unknown>, commandId = `cmd_${randomUUID()}`): Promise<CommandReceipt> {
    if (!PRODUCT_COMMANDS.has(kind) || !this.view.status.ready || !this.view.sessionId) {
      return Promise.resolve({ schemaVersion: 1, commandId, accepted: false, createdIds: {},
        error: { code: 'APPLICATION_UNAVAILABLE', message: 'Application command is unavailable.' } })
    }
    // No optimistic transcript/provider/lifecycle mutation. A receipt is not a terminal.
    return new Promise(resolve => {
      const id = this.id()
      this.pending.set(id, { commandId, resolve })
      const command = {
        schemaVersion: 1, commandId, sessionId: this.view.sessionId, kind, payload,
        expectedRevision: null,
      }
      this.transmit({ id, type: 'application_command', command,
        ...(kind === 'ResolveApproval' && this.approvalProof
          ? { hostApprovalProof: this.approvalProof(command) } : {}) })
    })
  }
  memory(name: string, args: Record<string, unknown>, commandId = `cmd_${randomUUID()}`): Promise<MemoryControlResult> {
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
  receive(frame: Record<string, any>) {
    if (frame.type === 'ready') {
      this.view = { ...this.view, sessionId: frame.sessionId,
        status: { ...this.view.status, connected: true, ready: false, tools: frame.tools || [] },
        resumable: frame.resumable || null, ragProgress: '', ragResult: null, error: null }
      this.refresh()
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
      this.view = { ...this.view, gap: true }
      this.refresh()
    } else if (frame.type === 'application_result' && this.pending.has(frame.id)) {
      const receipt = frame.data as CommandReceipt
      this.pending.get(frame.id)!.resolve(receipt)
      this.pending.delete(frame.id)
      this.view = { ...this.view, error: receipt.accepted ? null : receipt.error || null }
      this.refresh()
    } else if (frame.type === 'memory_result' && this.memoryPending.has(frame.id)) {
      this.memoryPending.get(frame.id)!.resolve(frame.data as MemoryControlResult)
      this.memoryPending.delete(frame.id)
      // No MEMORY payload stored in the chat view, transcript or recall cache.
      this.refresh()
    } else if (frame.type === 'error') {
      const error = { code: frame.code || 'TRANSPORT_ERROR', message: frame.message || 'Request failed' }
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
      if (frame.id === this.snapshotRequest) this.snapshotRequest = null
      this.view = { ...this.view, error }
    } else if (frame.type === 'cwd_changed') {
      this.view = { ...this.view, resumable: frame.resumable || null }
      this.refresh()
    }
    this.changed()
  }
  private snapshot(state: SessionSnapshot) {
    if (!state || state.sessionId !== this.view.sessionId || !Array.isArray(state.transcript)) return
    if (this.view.status.ready && state.lastSequence < this.view.sequence) { this.refreshAgain = true; return }
    const active = state.turns.find(t => !['completed', 'failed', 'cancelled'].includes(t.status))
    const lastTurn = state.turns[state.turns.length - 1]
    const lastRetrieval = [...(state.services.operations || [])].reverse().find(op => op.service === 'rag' && op.result)
    const messages = projectTranscript(state.transcript, state.sessionId)
    // Preserve existing harness chips after terminal/reload, using explicit
    // transcript ranges owned by Application rather than matching message text.
    for (const turn of state.turns) {
      const rules = (turn.displayMessages || []).flatMap((m: any) => m.harnessEvents || [])
      const rows = messages.filter(m => m.role === 'assistant' && m.sourceIndex !== undefined &&
        m.sourceIndex >= turn.transcriptStart && m.sourceIndex < turn.transcriptEnd)
      if (rules.length && rows.length) rows[rows.length - 1].harnessEvents = rules
    }
    if (active) {
      const display = active.displayMessages?.length ? active.displayMessages : [{ role: 'assistant', content: '', thinking: true }]
      display.forEach((m: any, i: number) => messages.push({ ...m,
        id: `${active.turnId}:${i}`, streaming: true }))
    }
    this.view = { ...this.view, sequence: state.lastSequence, stateRevision: state.stateRevision,
      workspace: state.workspace, activeTurnId: active?.turnId || null, messages,
      activeGenerationId: active?.activeGenerationId || null,
      status: { ...this.view.status, ready: true, connected: true,
        model: state.modelRuntime.modelId, provider: state.modelRuntime.providerId },
      approvals: state.services.interactions?.approvals || [], inputs: state.services.interactions?.inputs || [],
      rag: state.services.rag,
      memoryNotice: state.services.memory?.allowRemoteMemoryInjection
        ? 'Remote memory injection is enabled by host configuration. Selected memories may leave this host.' : null,
      ragProgress: state.services.operations?.find(op => op.service === 'rag' &&
        ['running', 'requested'].includes(op.status))?.phase || '',
      ragResult: lastRetrieval?.result || this.view.ragResult,
      fileRevision: state.services.filesystem?.revision ?? this.view.fileRevision,
      error: lastTurn?.status === 'failed' ? { code: lastTurn.errorCode || 'TURN_FAILED', message: 'Turn failed.' } : this.view.error,
      ...(messages.length ? { resumable: null } : {}),
    }
    if ((state.services.securityAudit?.deliveryFailures || 0) > 0) {
      this.view = { ...this.view, error: { code: 'SECURITY_AUDIT_DELIVERY_FAILED',
        message: 'Audit gap. Observed result retained; no automatic retry or rollback.' } }
    }
  }
  private event(event: EventEnvelope) {
    if (!event || event.schemaVersion !== 1 || event.sessionId !== this.view.sessionId) return
    if (event.kind === 'EventGap') this.view = { ...this.view, gap: true }
    if (event.sequence <= this.view.sequence) return
    this.view = { ...this.view, sequence: event.sequence, stateRevision: event.stateRevision }
    if (event.payload.securityAudit?.gap === true) {
      this.view = { ...this.view, error: { code: 'SECURITY_AUDIT_DELIVERY_FAILED',
        message: 'Audit gap. Observed result retained; no automatic retry or rollback.' } }
    }
    if (event.kind === 'SessionSnapshot') { this.snapshot(event.payload as SessionSnapshot); return }
    if (event.kind === 'AssistantDelta' || event.kind === 'ThinkingDelta') {
      if (event.turnId !== this.view.activeTurnId || event.generationId !== this.view.activeGenerationId) { this.refresh(); return }
      const messages = [...this.view.messages]
      const last = messages[messages.length - 1]
      if (last?.role === 'assistant') messages[messages.length - 1] = { ...last,
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
