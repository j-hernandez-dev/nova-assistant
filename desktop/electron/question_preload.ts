import { ipcRenderer } from 'electron'
import { applySurfacePresentation } from '../shared/surface_presentation'
// Only the host-created question document receives this preload. No bridge is exposed.
if (process.isMainFrame) window.addEventListener('DOMContentLoaded', async () => {
  const element = (id: string) => document.getElementById(id)!
  const answer = element('answer') as HTMLTextAreaElement
  const send = element('send') as HTMLButtonElement, stop = element('stop') as HTMLButtonElement
  const status = element('status')
  const copy = {
    es: { heading: 'Nova tiene una pregunta', answer: 'Responder a Nova', placeholder: 'Escribe tu respuesta…',
      hint: 'Intro para enviar · Mayús+Intro para una nueva línea', send: 'Enviar', stop: 'Detener',
      sending: 'Enviando…', stopping: 'Deteniendo…', sent: 'Respuesta enviada. Esperando a que Nova continúe…',
      failed: 'No se pudo completar la acción. Inténtalo de nuevo; tu respuesta se conserva.' },
    en: { heading: 'Nova has a question', answer: 'Answer Nova', placeholder: 'Write your answer…',
      hint: 'Enter to send · Shift+Enter for a new line', send: 'Send', stop: 'Stop',
      sending: 'Sending…', stopping: 'Stopping…', sent: 'Answer sent. Waiting for Nova to continue…',
      failed: 'The action could not be completed. Try again; your answer is preserved.' },
  }
  let language: 'es' | 'en' = 'es', sending = false, stopping = false, completed = false
  let statusKey: 'sent' | 'failed' | null = null
  const refresh = () => {
    const labels = copy[language]
    send.disabled = completed || sending || stopping || !answer.value.trim()
    stop.disabled = completed || stopping
    answer.disabled = completed || sending || stopping
    send.textContent = sending ? labels.sending : labels.send
    stop.textContent = stopping ? labels.stopping : labels.stop
    status.textContent = statusKey ? labels[statusKey] : ''
    status.setAttribute('role', statusKey === 'failed' ? 'alert' : 'status')
  }
  const localize = (locale: unknown) => {
    language = locale === 'en' ? 'en' : 'es'
    const labels = copy[language]
    document.documentElement.lang = language
    element('heading').textContent = labels.heading; element('answer-label').textContent = labels.answer
    element('hint').textContent = labels.hint; answer.placeholder = labels.placeholder; refresh()
  }
  try {
    const binding = await ipcRenderer.invoke('question-surface-ready')
    if (!binding?.accepted || typeof binding.nonce !== 'string' || typeof binding.question !== 'string') return
    applySurfacePresentation(document, binding.presentation)
    ipcRenderer.on('question-surface-appearance', (_event, value) => applySurfacePresentation(document, value))
    element('question').textContent = binding.question
    localize(binding.locale)
    ipcRenderer.on('question-surface-locale', (_event, locale) => localize(locale))
    const decide = async (action: 'answer' | 'stop', event: Event) => {
      if (!event.isTrusted || completed || stopping || (action === 'answer' && (sending || !answer.value.trim()))) return
      if (action === 'answer') sending = true; else stopping = true
      statusKey = null; refresh()
      try {
        const result = await ipcRenderer.invoke('question-surface-decision', { nonce: binding.nonce, action,
          ...(action === 'answer' ? { response: answer.value } : {}) })
        if (result?.accepted) { completed = true; statusKey = 'sent' } else statusKey = 'failed'
      } catch { statusKey = 'failed' }
      finally { if (action === 'answer') sending = false; else stopping = false; refresh() }
      if (!completed && !stopping && !sending) answer.focus()
    }
    send.addEventListener('click', event => { void decide('answer', event) })
    stop.addEventListener('click', event => { void decide('stop', event) })
    answer.addEventListener('input', () => { statusKey = null; refresh() })
    document.addEventListener('keydown', event => {
      if (event.key === 'Enter' && event.target === answer && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
        event.preventDefault(); void decide('answer', event)
      }
      if (event.key === 'Escape') event.preventDefault()
      if (event.key === 'Tab') {
        const controls = [answer, stop, send].filter(control => !control.disabled)
        const next = controls.indexOf(document.activeElement as typeof answer)
        event.preventDefault()
        controls[(next + (event.shiftKey ? controls.length - 1 : 1)) % controls.length]?.focus()
      }
    })
    refresh(); answer.focus()
  } catch { /* A missing host binding keeps all controls disabled. */ }
}, { once: true })
