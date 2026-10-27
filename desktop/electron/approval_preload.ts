// This preload belongs only to the host-created fixed approval document. It
// exposes no API to its document or to the principal application renderer.
import { ipcRenderer } from 'electron'
import { applySurfacePresentation } from '../shared/surface_presentation'

if (process.isMainFrame) window.addEventListener('DOMContentLoaded', async () => {
  const element = (id: string) => document.getElementById(id)!
  const deny = element('deny') as HTMLButtonElement
  const allow = element('allow') as HTMLButtonElement
  const copy = {
    es: { heading: 'Confirmar esta acción', explanation: 'Revisa la solicitud exacta antes de decidir. Se ejecutará con los permisos de tu cuenta.',
      tool: 'Herramienta', cwd: 'Carpeta', deadline: 'Vence', scope: 'Esta decisión se aplica una sola vez a esta solicitud.', deny: 'No permitir', allow: 'Permitir' },
    en: { heading: 'Confirm this action', explanation: 'Review the exact request before deciding. It will run with your account permissions.',
      tool: 'Tool', cwd: 'Folder', deadline: 'Expires', scope: 'This decision applies once to this request.', deny: 'Do not allow', allow: 'Allow' },
  }
  const localize = (locale: unknown) => {
    const language = locale === 'en' ? 'en' : 'es'
    const text = copy[language]
    document.documentElement.lang = language
    element('heading').textContent = text.heading
    element('explanation').textContent = text.explanation
    element('tool-label').textContent = text.tool
    element('cwd-label').textContent = text.cwd
    element('deadline-label').textContent = text.deadline
    element('scope').textContent = text.scope
    deny.textContent = text.deny
    allow.textContent = text.allow
  }
  try {
    const binding = await ipcRenderer.invoke('approval-surface-ready')
    if (!binding?.accepted || typeof binding.nonce !== 'string') return
    applySurfacePresentation(document, binding.presentation)
    ipcRenderer.on('approval-surface-appearance', (_event, value) => applySurfacePresentation(document, value))
    localize(binding.locale)
    element('tool').textContent = String(binding.request.name)
    element('cwd').textContent = String(binding.request.cwd)
    element('deadline').textContent = String(binding.request.deadline)
    element('arguments').textContent = JSON.stringify(binding.request.arguments, null, 2)
    ipcRenderer.on('approval-surface-locale', (_event, locale: unknown) => localize(locale))
    let decided = false
    const decide = (decision: 'allow' | 'deny') => (event: MouseEvent) => {
      if (!event.isTrusted || decided) return
      decided = true
      allow.disabled = deny.disabled = true
      void ipcRenderer.invoke('approval-surface-decision', { nonce: binding.nonce, decision }).catch(() => {})
    }
    deny.addEventListener('click', decide('deny'))
    allow.addEventListener('click', decide('allow'))
    allow.disabled = deny.disabled = false
    deny.focus()
  } catch { /* Missing/stale host binding leaves both controls disabled. */ }
}, { once: true })
