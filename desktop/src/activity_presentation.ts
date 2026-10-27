import type { ToolActivity } from './types'
import type { TranslationKey } from './i18n'
import type { NovaIconName } from './components/NovaIcon'

export type ActivityPresentation = { key: TranslationKey; tone: 'neutral' | 'active' | 'confirmed' | 'warning'; running: boolean; exitCode?: number }

export function isTerminalActivity(activity: ToolActivity): boolean {
  return ['bash', 'shell', 'run_command', 'exec_command'].includes(activity.name)
}

export function activityStatusText(presentation: ActivityPresentation, t: (key: TranslationKey) => string): string {
  return t(presentation.key).replace('{code}', String(presentation.exitCode ?? ''))
}

/** A process exit describes execution only; arbitrary command effects stay unverified. */
function commandPresentation(activity: ToolActivity): ActivityPresentation | null {
  if (!isTerminalActivity(activity)) return null
  const result = (key: TranslationKey, tone: ActivityPresentation['tone'] = 'warning'): ActivityPresentation => ({ key, tone, running: false })
  if (activity.observationLost) return result('activityCommandUnconfirmed')
  if (['pending', 'running'].includes(activity.status)) return null
  if (activity.errorCode === 'PROCESS_CLEANUP_UNKNOWN') return result('activityCommandUnconfirmed')
  if (activity.errorCode === 'PROCESS_TIMEOUT') return result('activityCommandTimedOut')
  if (activity.errorCode === 'PROCESS_CANCELLED') return result('activityCommandStopped', 'neutral')
  if (activity.status === 'outcome_unknown' || activity.operationStatus === 'outcome_unknown') return result('activityCommandUnconfirmed')
  if (activity.status === 'cancelled' || activity.operationStatus === 'cancelled') return result('activityCommandStopped', 'neutral')
  if (activity.effectState !== 'partial' && activity.status === 'completed' && activity.operationStatus === 'completed'
      && activity.exitCode === 0 && !activity.errorCode) return result('activityCommandFinished', 'neutral')
  if (activity.status === 'failed' && activity.operationStatus === 'failed' && Number.isInteger(activity.exitCode)
      && activity.exitCode !== 0 && (!activity.errorCode || activity.errorCode === 'PROCESS_EXIT_NONZERO')) {
    return { ...result('activityCommandExitCode'), exitCode: activity.exitCode! }
  }
  if (activity.status === 'completed') return result('activityCommandUnconfirmed')
  return null
}

/** Only typed host receipts determine an outcome. Output is untrusted display text. */
export function activityPresentation(activity: ToolActivity, awaitingPermission = false): ActivityPresentation {
  const command = commandPresentation(activity)
  if (command) return command
  const state = activity.status
  const operation = activity.operationStatus
  const terminal = !['pending', 'running'].includes(state)
  if (activity.observationLost || state === 'outcome_unknown' || operation === 'outcome_unknown'
      || (terminal && ['unknown', 'partial'].includes(activity.effectState))) {
    return { key: 'activityUnknown', tone: 'warning', running: false }
  }
  if (awaitingPermission && !terminal) return { key: 'activityAwaitingPermission', tone: 'neutral', running: false }
  if (state === 'running' && operation === 'running') return { key: 'toolRunning', tone: 'active', running: true }
  if (state === 'pending') return { key: 'activityPending', tone: 'neutral', running: false }
  if (state === 'completed' && operation === 'completed' && ['none', 'applied'].includes(activity.effectState)) {
    return { key: 'activityCompleted', tone: 'confirmed', running: false }
  }
  if (activity.errorCode === 'PROCESS_TIMEOUT' && ['failed', 'cancelled'].includes(state)) return { key: 'activityTimedOut', tone: 'warning', running: false }
  if (unavailableCode(activity.errorCode)) return { key: 'activityUnavailable', tone: 'warning', running: false }
  if (state === 'denied') return { key: 'activityDenied', tone: 'warning', running: false }
  if (state === 'cancelled' || operation === 'cancelled') return { key: 'activityCancelled', tone: 'neutral', running: false }
  if (state === 'failed' || operation === 'failed') return { key: 'activityFailed', tone: 'warning', running: false }
  return { key: 'activityUnknown', tone: 'neutral', running: false }
}

function unavailableCode(code?: string | null): boolean {
  return !!code && ['CAPABILITY_UNAVAILABLE', 'TOOL_UNAVAILABLE', 'COMMAND_UNAVAILABLE', 'BROWSER_UNAVAILABLE',
    'SHELL_UNAVAILABLE', 'GIT_UNAVAILABLE', 'UNSUPPORTED_TOOL', 'EXECUTABLE_NOT_FOUND',
    'PROCESS_CONCURRENCY_LIMIT', 'WEB_SEARCH_NOT_CONFIGURED', 'REMOTE_SEARCH_DISABLED', 'FETCH_DISABLED'].includes(code)
}

export function activityExplanation(activity: ToolActivity, awaitingPermission = false): TranslationKey | null {
  const key = activityPresentation(activity, awaitingPermission).key
  if (['activityCommandUnconfirmed', 'activityCommandTimedOut', 'activityCommandStopped'].includes(key)) {
    if (activity.observationLost || ['unknown', 'partial'].includes(activity.effectState)) return 'activityCommandInterruptedExplanation'
    return key === 'activityCommandTimedOut' ? 'activityTimedOutExplanation'
      : key === 'activityCommandStopped' ? 'activityCancelledExplanation' : 'activityObservationLost'
  }
  if (key === 'activityUnknown') return activity.observationLost ? 'activityObservationLost' : 'activityUnknownExplanation'
  if (key === 'activityAwaitingPermission') return 'activityPermissionExplanation'
  if (key === 'activityDenied') return 'activityDeniedExplanation'
  if (key === 'activityUnavailable') return 'activityUnavailableExplanation'
  if (key === 'activityFailed') return 'activityFailedExplanation'
  if (key === 'activityCancelled') return 'activityCancelledExplanation'
  if (key === 'activityTimedOut') return 'activityTimedOutExplanation'
  return null
}

export function activityToolLabel(name: string, running = false): TranslationKey {
  if (name === 'source_read') return running ? 'readingSourceTool' : 'activitySourceReadTool'
  if (!running) {
    if (['read', 'read_file'].includes(name)) return 'activityReadTool'
    if (['write', 'write_file'].includes(name)) return 'activityWriteTool'
    if (['edit', 'apply_patch'].includes(name)) return 'activityEditTool'
    if (['grep', 'search_code'].includes(name)) return 'activityCodeSearchTool'
    if (['glob', 'list_files', 'list_dir'].includes(name)) return 'activityFileSearchTool'
    if (['bash', 'shell', 'run_command', 'exec_command'].includes(name)) return 'activityTerminalTool'
    if (name === 'ask_user') return 'activityQuestionTool'
    if (name === 'web_fetch') return 'activityFetchTool'
    if (name === 'web_search') return 'activityWebSearchTool'
    if (name.startsWith('browser_')) return activityToolVisual(name).heading
    if (name === 'agent') return 'delegatedTool'
    return activityToolVisual(name).heading
  }
  if (['read', 'read_file'].includes(name)) return 'readingTool'
  if (['write', 'write_file'].includes(name)) return 'writingTool'
  if (['edit', 'apply_patch'].includes(name)) return 'editingTool'
  if (['grep', 'search_code'].includes(name)) return 'searchingCodeTool'
  if (['glob', 'list_files', 'list_dir'].includes(name)) return 'searchingFilesTool'
  if (['bash', 'shell', 'run_command', 'exec_command'].includes(name)) return 'runningTool'
  if (name === 'ask_user') return 'askingTool'
  if (name === 'web_fetch') return 'fetchingTool'
  if (name === 'web_search') return 'searchingWebTool'
  if (name.startsWith('browser_')) return activityToolVisual(name).heading
  if (name === 'agent') return 'delegatedTool'
  return activityToolVisual(name).heading
}

export type ActivityError = { code: string; message?: string; operationId?: string | null; toolCallId?: string | null; turnId?: string | null }

/** Suppress only a correlated failure receipt, never matching model prose. */
export function representedActivityError(error: ActivityError | null | undefined, activities: ToolActivity[]): boolean {
  if (!error) return false
  return activities.some(activity => {
    const terminalCause = ['failed', 'denied', 'cancelled', 'outcome_unknown'].includes(activity.status)
      || ['failed', 'cancelled', 'outcome_unknown'].includes(activity.operationStatus)
      || (!['pending', 'running'].includes(activity.status) && ['unknown', 'partial'].includes(activity.effectState)
        && activityPresentation(activity).key !== 'activityCommandFinished')
    if (!terminalCause) return false
    if (error.operationId) return error.operationId === activity.operationId
    if (error.toolCallId) return error.toolCallId === activity.toolCallId
    return !!error.turnId && error.turnId === activity.turnId
      && (['TURN_FAILED', 'TURN_OUTCOME_UNKNOWN', 'OUTCOME_UNKNOWN'].includes(error.code) || activity.errorCode === error.code)
  })
}

export function applicationErrorKey(code: string): TranslationKey {
  if (code === 'CONFLICT_ACTIVE_TURN') return 'turnBusyAction'
  if (code === 'OllamaRequestError') return 'modelGenerationFailed'
  if (code === 'OLLAMA_RESPONSE_TIMEOUT') return 'modelResponseTimeout'
  if (code === 'OLLAMA_CONNECT_TIMEOUT') return 'modelConnectTimeout'
  if (code === 'OLLAMA_CONNECTION_FAILED') return 'modelConnectionFailed'
  if (code === 'OLLAMA_MODEL_UNAVAILABLE') return 'readinessModelMissing'
  if (['BACKEND_DISCONNECTED', 'BACKEND_UNAVAILABLE', 'CONNECTION_LOST'].includes(code)) return 'activityConnectionLost'
  if (code === 'OUTCOME_UNKNOWN' || code === 'TURN_OUTCOME_UNKNOWN') return 'activityUnknown'
  if (['PERMISSION_DENIED', 'POLICY_DENIED', 'APPROVAL_DENIED'].includes(code)) return 'activityDeniedExplanation'
  if (unavailableCode(code)) return 'activityUnavailableExplanation'
  if (['TURN_FAILED', 'GENERATION_FAILED', 'PROVIDER_ERROR'].includes(code)) return 'responseFailed'
  return 'actionFailed'
}

export function homeActivity(activities: ToolActivity[]): ToolActivity | null {
  return [...activities].reverse().find(activity => ['pending', 'running'].includes(activity.status))
    || activities[activities.length - 1] || null
}

/** A failed host surface must leave the pending request visible and actionable. */
export async function openApprovalReview(open: () => Promise<{ success: boolean }>): Promise<boolean> {
  try { return (await open())?.success === true } catch { return false }
}

/** Display metadata keyed only by tool identifiers; no routing or execution decisions. */
const toolVisuals: Array<[readonly string[], TranslationKey, NovaIconName]> = [
  [['read', 'read_file'], 'activityReadHeading', 'file-read'],
  [['write', 'write_file'], 'activityWriteHeading', 'file-write'],
  [['edit', 'edit_file', 'apply_patch'], 'activityEditHeading', 'file-edit'],
  [['glob', 'list_files', 'list_dir'], 'activityFileSearchTool', 'folder'],
  [['grep', 'search_code'], 'activityCodeSearchTool', 'search'],
  [['bash', 'shell', 'run_command', 'exec_command'], 'activityTerminalTool', 'terminal'],
  [['web_fetch', 'web_access'], 'activityFetchHeading', 'globe'],
  [['web_search'], 'activityWebSearchTool', 'search'],
  [['todo_write'], 'activityTasksHeading', 'checklist'],
  [['ask_user'], 'activityQuestionHeading', 'help'],
  [['agent'], 'activityDelegateHeading', 'agents'],
  [['memory_search', 'memory_recall'], 'activityMemoryReadHeading', 'brain'],
  [['memory_store', 'memory_remember'], 'activityMemoryWriteHeading', 'brain'],
  [['source_read', 'knowledge_read', 'document_read'], 'activityDocumentReadHeading', 'file-read'],
  [['knowledge_search', 'document_search'], 'activityDocumentSearchHeading', 'search'],
  [['browser_navigate'], 'activityNavigateHeading', 'browser'],
  [['browser_observe'], 'activityObserveHeading', 'eye'],
  [['browser_click'], 'activityClickHeading', 'pointer'],
  [['browser_type'], 'activityInputHeading', 'keyboard'],
  [['browser_press_key'], 'activityKeyHeading', 'keyboard'],
  [['browser_back'], 'activityBackHeading', 'back'],
  [['browser_forward'], 'activityForwardHeading', 'forward'],
  [['browser_reload'], 'activityReloadHeading', 'refresh'],
  [['browser_close'], 'activityCloseBrowserHeading', 'close'],
  [['browser_request_takeover'], 'activityTakeoverHeading', 'hand'],
  [['browser_upload'], 'activityUploadHeading', 'upload'],
  [['browser_download'], 'activityDownloadHeading', 'download'],
]
export function activityToolVisual(name: string): { heading: TranslationKey; icon: NovaIconName } {
  const row = toolVisuals.find(([names]) => names.includes(name))
  if (row) return { heading: row[1], icon: row[2] }
  if (name.startsWith('browser_')) return { heading: 'browserTool', icon: 'browser' }
  if (name.startsWith('memory_')) return { heading: 'activityMemoryHeading', icon: 'brain' }
  if (name.startsWith('knowledge_') || name.startsWith('document_')) return { heading: 'activityDocumentHeading', icon: 'files' }
  return { heading: 'activityTool', icon: 'tool' }
}
