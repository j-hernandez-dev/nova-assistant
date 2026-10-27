export function resolvePythonRuntime(projectRoot: string, options?: {
  platform?: NodeJS.Platform
  packaged?: boolean
  env?: NodeJS.ProcessEnv
  exists?: (path: string) => boolean
  probe?: (command: string) => boolean
}): { executable: string; args?: string[]; env: Record<string, string> }
export function resolveDefaultWorkspace(projectRoot:string, documentsDirectory:string, packaged:boolean, platform?:NodeJS.Platform):string
