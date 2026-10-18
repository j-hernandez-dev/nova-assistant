import type { Message, ToolActivity } from '../src/types'

const statuses = new Set(['pending', 'running', 'completed', 'failed', 'denied', 'cancelled', 'outcome_unknown'])
export const activeActivity = (activity: ToolActivity) => ['pending', 'running'].includes(activity.status)

export function toolActivity(raw: any, turnId: string): ToolActivity | null {
  if (!raw || typeof raw.operationId !== 'string' || !raw.operationId || typeof raw.toolCallId !== 'string'
      || !raw.toolCallId || !statuses.has(raw.status) || (raw.turnId && raw.turnId !== turnId)) return null
  const text = (value: unknown) => typeof value === 'string' ? value.slice(0, 32768) : ''
  return { operationId: raw.operationId, toolCallId: raw.toolCallId, turnId,
    messageId: typeof raw.messageId === 'string' ? raw.messageId : null,
    name: text(raw.name), arguments: raw.arguments && typeof raw.arguments === 'object' && !Array.isArray(raw.arguments) ? raw.arguments : {},
    cwd: text(raw.cwd), status: raw.status, operationStatus: text(raw.operationStatus),
    effectState: ['none', 'applied', 'partial', 'unknown'].includes(raw.effectState) ? raw.effectState : 'unknown',
    errorCode: typeof raw.errorCode === 'string' ? text(raw.errorCode) : null,
    exitCode: Number.isInteger(raw.exitCode) ? raw.exitCode : null,
    output: text(raw.output), stdout: text(raw.stdout), stderr: text(raw.stderr),
    outputSequence: Number.isInteger(raw.outputSequence) && raw.outputSequence >= 0 ? raw.outputSequence : 0,
    outputTruncated: raw.outputTruncated === true,
    ...(typeof raw.startedAt === 'string' ? { startedAt: raw.startedAt } : {}),
    ...(typeof raw.completedAt === 'string' ? { completedAt: raw.completedAt } : {}),
  }
}

/** Attach only through host-issued messageId, never names, argument text or position.
 * Unassociated operations stay in the flat collection for the activity section;
 * they never become a synthetic public assistant message. */
export function attachActivities(messages: Message[], activities: ToolActivity[], turns: Array<Record<string, any>>): Message[] {
  const rows = messages.filter(message => !message.id.startsWith('activity:')).map(message => ({ ...message, toolActivities: [] as ToolActivity[], turn: undefined as Message['turn'] }))
  for (const turn of turns) {
    const owned = activities.filter(activity => activity.turnId === turn.turnId)
    const metadata = [turn.userMessage, ...(turn.displayMessages || [])].filter(Boolean)
    const ids = new Set(metadata.map(item => item.id).filter(id => typeof id === 'string'))
    const validDate = (value: unknown): value is string => typeof value === 'string' && Number.isFinite(Date.parse(value))
    const starts = metadata.map(item => item.createdAt).filter(validDate).sort((a, b) => Date.parse(a) - Date.parse(b))
    const ends = [...metadata.map(item => item.completedAt), ...owned.map(item => item.completedAt)]
      .filter(validDate).sort((a, b) => Date.parse(b) - Date.parse(a))
    const terminal = ['completed', 'failed', 'cancelled'].includes(turn.status)
    const observation = { id: turn.turnId, status: turn.status,
      ...(starts.length ? { startedAt: starts[0] } : {}),
      ...(terminal && ends.length ? { completedAt: ends[0] } : {}) }
    for (const row of rows) {
      if (ids.has(row.id) || (row.sourceIndex !== undefined && Number.isInteger(turn.transcriptStart)
          && row.sourceIndex >= turn.transcriptStart && row.sourceIndex < turn.transcriptEnd)) row.turn = observation
    }
    for (const activity of owned) {
      const message = rows.find(row => row.id === activity.messageId && row.role === 'assistant')
      if (message) message.toolActivities.push(activity)
    }
  }
  return rows
}
