export function resolvePythonRuntime(projectRoot: string, options?: {
  platform?: NodeJS.Platform
  env?: NodeJS.ProcessEnv
  exists?: (path: string) => boolean
  probe?: (command: string) => boolean
}): { executable: string; env: Record<string, string> }
