// Versioned wire DTOs. These are projections, not domain state machines.
import type { Message, AppStatus, ResumableInfo } from '../src/types'

export type Approval = {
  approvalId: string; toolCallId: string; turnId: string; operationId: string
  arguments: Record<string, unknown>; cwd: string; policyRevision: number
  requestDigest: string; deadline: string | null; name: string
}
export type UserInputRequest = {
  inputRequestId: string; turnId: string; question: string; deadline: string | null
}
export type RAGStatus = {
  enabled: boolean; availability: string; topK?: number
  error?: { code: string; message?: string } | null
}
export type EventEnvelope = {
  schemaVersion: number; eventId: string; sequence: number; sessionId: string
  kind: string; payload: Record<string, any>; stateRevision: number
  turnId?: string; generationId?: string; operationId?: string
  approvalId?: string; toolCallId?: string; agentId?: string
}
export type SessionSnapshot = {
  sessionId: string; workspace: string; stateRevision: number; lastSequence: number
  transcript: Array<Record<string, any>>; turns: Array<Record<string, any>>
  modelRuntime: { modelId: string; providerId: string; providerRevision: number }
  services: {
    rag: RAGStatus
    filesystem?: { revision: number }
    interactions?: { approvals: Approval[]; inputs: UserInputRequest[] }
    operations?: Array<{ operationId: string; status: string; service?: string; phase?: string; result?: any }>
  }
}
export type DesktopSessionView = {
  sessionId: string | null; sequence: number; stateRevision: number
  status: AppStatus; messages: Message[]; activeTurnId: string | null
  activeGenerationId: string | null
  approvals: Approval[]; inputs: UserInputRequest[]; workspace: string | null
  resumable: ResumableInfo | null; rag: RAGStatus; ragProgress: string
  ragResult: { matches?: Array<Record<string, any>> } | null
  error: { code: string; message: string } | null; gap: boolean
  fileRevision: number
}

export type CommandReceipt = {
  schemaVersion: number; commandId: string; accepted: boolean
  createdIds: Record<string, string>; error?: { code: string; message: string } | null
}
