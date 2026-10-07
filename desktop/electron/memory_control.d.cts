import type { MemoryControlResult } from '../shared/application'

export function memoryControl(client: {
  view: { sessionId: string | null; workspace: string | null; stateRevision: number; status: { ready: boolean } }
  memory(name: string, args: Record<string, unknown>, commandId?: string): Promise<MemoryControlResult>
}, name: string, args: Record<string, unknown>, commandId: string | undefined,
showDialog: (request: { name: string; workspace: string | null; write: boolean }) => Promise<{ response: number }>
): Promise<MemoryControlResult>
