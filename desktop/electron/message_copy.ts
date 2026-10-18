import type { Message } from '../src/types'

/** Copy only an exact public message in the current host projection; no clipboard reads. */
export function copyPublicMessage(messages: Message[], id: unknown, writeText: (text: string) => void): { success: boolean } {
  if (typeof id !== 'string' || !id || id.length > 1024) return { success: false }
  const message = messages.find(row => row.id === id)
  if (!message || !['user', 'assistant'].includes(message.role) || !message.content
      || message.streaming || message.deliveryStatus === 'streaming') return { success: false }
  try { writeText(message.content); return { success: true } } catch { return { success: false } }
}
