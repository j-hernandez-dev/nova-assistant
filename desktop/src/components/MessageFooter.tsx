import { useEffect, useRef, useState } from 'react'
import type { Message } from '../types'
import { messageDate, messageTime } from '../message_presentation'
import { useI18n } from '../i18n'
import { NovaIcon } from './NovaIcon'

export function MessageFooter({ message }: { message: Message }) {
  const { t, locale } = useI18n()
  const [state, setState] = useState<'idle' | 'copying' | 'copied' | 'failed'>('idle')
  const request = useRef(0), pending = useRef(false), timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  useEffect(() => {
    request.current++; pending.current = false; setState('idle')
    return () => { request.current++; clearTimeout(timer.current) }
  }, [message.id, message.content])
  if (!['user', 'assistant'].includes(message.role) || !message.content) return null
  const date = messageDate(message)
  const streaming = message.streaming || message.deliveryStatus === 'streaming'
  const label = t(state === 'copied' ? 'messageCopied' : state === 'failed' ? 'messageCopyFailed'
    : state === 'copying' ? 'messageCopying' : 'copyMessage')
  async function copy() {
    if (pending.current || streaming) return
    pending.current = true; const id = ++request.current
    clearTimeout(timer.current); setState('copying')
    let success = false
    try { success = typeof window.api?.copyMessage === 'function' && (await window.api.copyMessage(message.id)).success === true } catch { /* Localized failure below. */ }
    if (request.current !== id) return
    pending.current = false; setState(success ? 'copied' : 'failed')
    timer.current = setTimeout(() => { if (request.current === id) setState('idle') }, success ? 2200 : 3500)
  }
  const time = date && <time className="nova-message-time" dateTime={date.toISOString()}
    title={date.toLocaleString(locale === 'es' ? 'es-MX' : 'en-US')}>{messageTime(date, locale)}</time>
  const control = !streaming && <button className="nova-message-copy" type="button" onClick={() => void copy()}
    title={label} aria-label={label} disabled={state === 'copying'}>
    <NovaIcon name={state === 'copied' ? 'check' : 'copy'} size={15} />
    <span className="nova-copy-feedback" role="status" aria-live="polite">{state === 'copied' || state === 'failed' ? label : ''}</span>
  </button>
  return <footer className="nova-message-footer" data-copy-state={state}>
    {message.role === 'user' ? <>{time}{control}</> : <>{control}{time}</>}
  </footer>
}
