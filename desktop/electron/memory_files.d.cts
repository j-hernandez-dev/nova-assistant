import type {MemoryControlResult} from '../shared/application'
export function createMemoryFileControls(options:any):{
  transfer(kind:unknown,includeSensitive?:unknown):Promise<MemoryControlResult>
  projectAccess(projectPath:unknown,enabled:unknown):Promise<MemoryControlResult>
  isBusy():boolean
}
