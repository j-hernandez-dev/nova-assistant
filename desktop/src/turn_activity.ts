import type { Message, ToolActivity, TurnObservation } from './types'
import type { TranslationKey } from './i18n'
import type { NovaIconName } from './components/NovaIcon'
import { activityPresentation, activityToolLabel } from './activity_presentation'

export type TurnAction = {
  key: string; name: string; args: Record<string, unknown>; output: string; receipt?: ToolActivity
}
export type ConversationGroup = { id: string; user?: Message; messages: Message[]; activities: ToolActivity[]; turn?: TurnObservation }

/** Group by host identity; restored transcripts without sidecars use visible user boundaries only. */
export function conversationGroups(messages: Message[], activities: ToolActivity[]): ConversationGroup[] {
  const groups: ConversationGroup[] = [], byTurn = new Map<string, ConversationGroup>()
  let current: ConversationGroup | undefined
  for (const message of messages) {
    let group = message.turn ? byTurn.get(message.turn.id) : undefined
    if (!group && (message.role === 'user' || !current || (message.turn && current.turn?.id !== message.turn.id))) {
      group = { id: message.turn?.id || `transcript:${message.id}`, messages: [], activities: [], turn: message.turn }
      groups.push(group)
      if (message.turn) byTurn.set(message.turn.id, group)
    }
    group ||= current!
    if (message.role === 'user') group.user = message
    else group.messages.push(message)
    current = group
  }
  for (const group of groups) {
    const attached = group.messages.flatMap(message => message.toolActivities || [])
    group.activities = [...new Map([...attached, ...activities.filter(row => row.turnId === group.turn?.id)]
      .map(row => [row.operationId, row])).values()]
  }
  return groups
}

/** A legacy tool request remains unverified, even if its output claims success. */
export function collectActions(messages: Message[], activities: ToolActivity[]): TurnAction[] {
  const result: TurnAction[] = [], seen = new Set<string>()
  const append = (receipt: ToolActivity) => {
    if (seen.has(receipt.operationId)) return
    seen.add(receipt.operationId)
    result.push({ key: receipt.operationId, name: receipt.name, args: receipt.arguments, output: receipt.output, receipt })
  }
  for (const message of messages) {
    const owned = activities.filter(row => row.messageId === message.id)
    if (owned.length || message.toolActivities?.length) {
      ;[...owned, ...(message.toolActivities || [])].forEach(append)
    } else if (!activities.length) {
      const calls = message.toolCalls || [], outputs = message.toolResults || []
      for (let index = 0; index < Math.max(calls.length, outputs.length); index++) {
        const call = calls[index], output = outputs[index]
        result.push({ key: `legacy:${message.id}:${index}`, name: call?.name || output?.name || '',
          args: call?.args || {}, output: output?.output || '' })
      }
    }
  }
  activities.forEach(append)
  return result
}

export function elapsedSeconds(turn: TurnObservation | undefined, active: boolean, now: number): number | null {
  if (!turn?.startedAt) return null
  const start = Date.parse(turn.startedAt), end = active ? now : Date.parse(turn.completedAt || '')
  return Number.isFinite(start) && Number.isFinite(end) ? Math.max(0, Math.floor((end - start) / 1000)) : null
}
/** Reloaded chats retain exact message dates even after ephemeral Turn sidecars end. */
export function groupElapsedSeconds(group: ConversationGroup, active: boolean, now: number): number | null {
  const observed = elapsedSeconds(group.turn, active, now)
  if (observed !== null) return observed
  const valid = (value: unknown): value is string => typeof value === 'string' && Number.isFinite(Date.parse(value))
  const startedAt = valid(group.turn?.startedAt) ? group.turn.startedAt : group.user?.createdAt
  const final = [...group.messages].reverse().find(message => message.role === 'assistant'
    && !message.toolCalls?.length && valid(message.completedAt))
  const completedAt = valid(group.turn?.completedAt) ? group.turn.completedAt : final?.completedAt
  return elapsedSeconds({ id: group.id, status: active ? 'running' : 'completed', startedAt, completedAt }, active, now)
}
export function formatDuration(seconds: number): string {
  const value = Math.max(0, Math.floor(seconds))
  if (value < 60) return `${value} s`
  const minutes = Math.floor(value / 60), rest = value % 60
  return minutes < 60 ? `${minutes} min ${rest} s` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`
}

/** Display only explicit tool arguments. They are never parsed as status or authority. */
export function actionTarget(name: string, args: Record<string, unknown>): string {
  const keys = ['bash', 'shell', 'run_command', 'exec_command'].includes(name) ? ['command']
    : ['web_search'].includes(name) ? ['query'] : ['url', 'path', 'file_path', 'pattern', 'query', 'command']
  return keys.map(key => args[key]).find(value => typeof value === 'string') as string || ''
}
export function actionTitle(action: TurnAction, t: (key: TranslationKey) => string, awaiting = false): string {
  const state = action.receipt && activityPresentation(action.receipt, awaiting)
  const key = state?.running && ['bash', 'shell', 'run_command', 'exec_command'].includes(action.name)
    ? 'runningTool' : activityToolLabel(action.name, !!state?.running)
  const target = actionTarget(action.name, action.args)
  return `${t(key)}${target ? ` ${target}` : ''}`
}

export function activeAction(actions: TurnAction[]): TurnAction | undefined {
  return [...actions].reverse().find(row => row.receipt && ['pending', 'running'].includes(row.receipt.status))
}
export function chainLabel(actions: TurnAction[]): TranslationKey {
  const names = actions.map(action => action.name)
  const shell = names.some(name => ['bash', 'shell', 'run_command', 'exec_command'].includes(name))
  const files = names.some(name => ['read', 'read_file', 'write', 'write_file', 'edit', 'apply_patch', 'glob', 'grep', 'list_files', 'list_dir'].includes(name))
  const web = names.length > 0 && names.every(name => name.startsWith('web_') || name.startsWith('browser_'))
  return shell && files ? 'activityFilesAndCommands' : shell ? 'activityCommands' : files ? 'activityFiles' : web ? 'activityWeb' : 'activityActions'
}

export function chainIcon(actions: TurnAction[]): NovaIconName {
  const label = chainLabel(actions)
  if (label === 'activityFilesAndCommands') return 'workflow'
  if (label === 'activityCommands') return 'terminal'
  if (label === 'activityFiles') return 'files'
  if (label === 'activityWeb') return 'globe'
  if (actions.length && actions.every(action => action.name.startsWith('memory_'))) return 'brain'
  return 'tool'
}
