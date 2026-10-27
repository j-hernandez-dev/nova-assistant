export const CACHE_NAMES: readonly string[]
export function prepareChromiumCaches(directory: string): {
  rotated: string[]
  failures: Array<{ name: string; code: string }>
  backupDirectory: string
}
