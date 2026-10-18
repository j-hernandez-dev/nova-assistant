import type { Message } from './types'
import type { ConversationGroup } from './turn_activity'

export function validMessageDate(value: unknown): Date | null {
  if (typeof value !== 'string' || !Number.isFinite(Date.parse(value))) return null
  return new Date(value)
}
export function messageDate(message: Message): Date | null {
  return validMessageDate(message.role === 'assistant' ? message.completedAt : message.createdAt)
    || validMessageDate(message.createdAt)
}
export function localDay(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}
export function numericDate(date: Date): string {
  return `${String(date.getDate()).padStart(2, '0')}/${String(date.getMonth() + 1).padStart(2, '0')}/${date.getFullYear()}`
}
export function messageTime(date: Date, locale: 'es' | 'en'): string {
  return date.toLocaleTimeString(locale === 'es' ? 'es-MX' : 'en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
}
export function historySections(groups: ConversationGroup[], now: Date) {
  let previous: string | null = null
  return groups.map(group => {
    const exactDate = validMessageDate(group.user?.createdAt) || validMessageDate(group.turn?.startedAt)
      || group.messages.map(messageDate).find(Boolean) || null
    const date = exactDate || validMessageDate(group.user?.savedAt)
      || group.messages.map(message => validMessageDate(message.savedAt)).find(Boolean) || null
    const day = date ? localDay(date) : null
    const separator = date && day !== previous ? { date, today: day === localDay(now), archived: !exactDate } : null
    previous = day
    return { group, separator }
  })
}
