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
    knowledge?: KnowledgeStatus
    memory?: { lexicalRecall: boolean; semantic: boolean; autoCapture: boolean; allowRemoteMemoryInjection: boolean }
    filesystem?: { revision: number }
    securityAudit?: { deliveryFailures: number; lastError: string | null; storageGapCodes: string[] }
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
  memoryNotice?: string | null
  knowledge?: KnowledgeStatus
  knowledgeOperations?: Array<{operationId:string;status:string;phase?:string;result?:any}>
}

export type AttachmentRef = {
  schemaVersion:1;attachmentId:string;sourceId:string;revisionId:string|null
  displayName:string;state:string
}
export type KnowledgeStatus = {
  hostAcquisition:boolean;extraction:boolean;lexicalRetrieval:boolean
  attachmentRefs:AttachmentRef[];closing:boolean
  capabilities?:{schemaVersion:number;capabilities:Array<{name:string;state:string;reason:string}>}
  sources?:Array<{schemaVersion:number;source:{sourceId:string;kind:string;scope:{kind:string};displayName:string;
    lifecycleState:string;remotePolicy:{remoteDocumentForwarding:boolean}};byteLength:number;chunkCount:number;errorCode:string|null}>
  capacity?:{schemaVersion:number;usage:Array<{scope:string;state:string;bytes:number;pendingBytes:number;byteLimit:number;sources:number;chunks:number}>;operationalOnly:boolean;automaticPurge:boolean}|null
}
export type KnowledgeCitations={schemaVersion:number;turnId:string;structuralOnly:boolean;
  valid:Array<{citationId:string;sourceId:string;revisionId:string;displayLabel:string;originDisplay:string;
    locator:{kind:string;coordinates:Record<string,string|number>}}>;invalid:string[]}

export type CommandReceipt = {
  schemaVersion: number; commandId: string; accepted: boolean
  createdIds: Record<string, string>; error?: { code: string; message: string } | null
}

// Explicit synchronous MEMORY controls, separate from asynchronous Core receipts.
export type MemoryControlResult = {
  schemaVersion: 1; commandId: string; completed: boolean; stateRevision?: number
  operationId?: string; data?: Record<string, any>
  error?: { code: string; message: string; outcomeUnknown?: boolean; retryable?: boolean }
  securityAudit?: { gap: boolean; errorCode: string; retryAllowed: false }
}
