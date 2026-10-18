import type { ProjectState } from './types'
import type { TranslationKey } from './i18n'

/** Filesystem identity is host-owned. This normalization is display correlation only. */
export function projectPathKey(path: string): string {
  const normalized = path.replace(/\\/g, '/').replace(/\/+$/, '')
  return /^[A-Za-z]:/.test(normalized) ? normalized.toLowerCase() : normalized
}
export function sameProjectPath(left: string | null | undefined, right: string | null | undefined): boolean {
  return typeof left === 'string' && typeof right === 'string' && projectPathKey(left) === projectPathKey(right)
}
export function fileBasename(path: string): string { return path.replace(/\\/g, '/').split('/').pop() || path }
export function projectErrorKey(code?: string): TranslationKey {
  switch (code) {
    case 'PROJECT_BUSY': case 'WORKSPACE_BUSY': case 'CONFLICT_ACTIVE_OPERATION': return 'projectBusy'
    case 'PROJECT_OUTSIDE_ROOT': return 'projectOutsideRoot'
    case 'PROJECT_STALE_ROOT': return 'projectStaleRoot'
    case 'PROJECT_FILE_TOO_LARGE': return 'projectFileTooLarge'
    case 'PROJECT_BINARY_FILE': return 'projectBinaryFile'
    case 'PROJECT_NOT_DIRECTORY': case 'PROJECT_NOT_FOUND': case 'PROJECT_INVALID_PATH': case 'PROJECT_PATH_CHANGED': return 'projectMissingFolder'
    case 'PROJECT_NOT_FILE': return 'projectMissingFile'
    case 'PROJECT_UNAVAILABLE': case 'BACKEND_UNAVAILABLE': return 'projectUnavailable'
    case 'PROJECT_SAVE_FAILED': case 'PROJECT_PREFERENCES_SAVE_FAILED': case 'PREFERENCES_SAVE_FAILED': return 'projectSaveFailed'
    case 'PROJECT_OPEN_FAILED': return 'projectOpenFailed'
    case 'PROJECT_PREVIOUS_UNAVAILABLE': return 'projectPreviousUnavailable'
    case 'PROJECT_DEFAULT_UNAVAILABLE': case 'PROJECT_BOOTSTRAP_FAILED': return 'projectDefaultUnavailable'
    case 'PROJECT_CHANGE_NOT_CONFIRMED': case 'PROJECT_CHANGE_UNKNOWN': return 'projectChangeNotConfirmed'
    case 'PROJECT_DEFAULT_REQUIRED': return 'projectDefaultRequired'
    case 'PROJECT_LIMIT_REACHED': return 'projectLimitReached'
    default: return 'projectActionFailed'
  }
}
export function validProjectState(value: unknown): value is ProjectState {
  if (!value || typeof value !== 'object') return false
  const state = value as ProjectState
  return state.schemaVersion === 1 && typeof state.defaultPath === 'string'
    && (state.activePath === null || typeof state.activePath === 'string') && typeof state.busy === 'boolean'
    && Array.isArray(state.folders) && state.folders.every(folder => folder && typeof folder.path === 'string'
      && typeof folder.name === 'string' && typeof folder.isDefault === 'boolean')
}

/** Retain loaded child state when another bounded host page arrives. */
export function mergeProjectEntries<T extends { path: string; name: string; isDirectory: boolean }>(current: T[], incoming: T[]): T[] {
  const merged = new Map(current.map(entry => [projectPathKey(entry.path), entry]))
  for (const entry of incoming) if (!merged.has(projectPathKey(entry.path))) merged.set(projectPathKey(entry.path), entry)
  return [...merged.values()].sort((a, b) => a.isDirectory === b.isDirectory ? a.name.localeCompare(b.name) : a.isDirectory ? -1 : 1)
}

export function projectPreviewMatches(result: { root?: string; path?: string }, root: string, path: string): boolean {
  return sameProjectPath(result.root, root) && sameProjectPath(result.path, path)
}
