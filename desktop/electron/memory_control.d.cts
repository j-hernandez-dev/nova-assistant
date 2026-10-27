import type { MemoryControlResult } from '../shared/application'

export function memoryControl(client: {
  view: { sessionId: string | null; workspace: string | null; stateRevision: number; status: { ready: boolean } }
  memory(name: string, args: Record<string, unknown>, commandId?: string): Promise<MemoryControlResult>
}, name: string, args: Record<string, unknown>, commandId: string | undefined,
showDialog: (request: { name: string; workspace: string | null; write: boolean; validate:()=>boolean }) => Promise<{ response: number }>
): Promise<MemoryControlResult>

export function createMemoryEditControls(client: Parameters<typeof memoryControl>[0],
  showDialog:(request:{kind:'memory-classify-sensitive'|'memory-classify-normal'|'memory-write-sensitive'|'memory-delete-records';fileCount?:number;workspace:string|null;validate:()=>boolean})=>Promise<{confirmed:boolean}>):{
    confirm(choice:unknown):Promise<MemoryControlResult>;
    edit(args:Record<string,unknown>,commandId?:string):Promise<MemoryControlResult>;
    remove(args:Record<string,unknown>,commandId?:string):Promise<MemoryControlResult>;
    isBusy():boolean;
  }
