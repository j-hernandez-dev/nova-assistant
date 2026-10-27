// Shared by the desktop preference boundary and renderer. No runtime/model settings.
const shortcutDefinitions = Object.freeze([
  { id: 'settings', group: 'general', label: 'shortcutSettings', hint: 'shortcutSettingsHint', default: 'Mod+,' },
  { id: 'sources', group: 'general', label: 'shortcutSources', hint: 'shortcutSourcesHint', default: 'Mod+Shift+F' },
  { id: 'memories', group: 'general', label: 'shortcutMemories', hint: 'shortcutMemoriesHint', default: 'Mod+Shift+N' },
  { id: 'models', group: 'general', label: 'shortcutModels', hint: 'shortcutModelsHint', default: 'Mod+Shift+M' },
  { id: 'focusPrompt', group: 'general', label: 'shortcutPrompt', hint: 'shortcutPromptHint', default: 'Mod+L' },
  { id: 'toggleHistory', group: 'chat', label: 'shortcutHistory', hint: 'shortcutHistoryHint', default: 'Mod+Shift+H' },
  { id: 'showHome', group: 'chat', label: 'shortcutHome', hint: 'shortcutHomeHint', default: null },
  { id: 'sendMessage', group: 'chat', label: 'shortcutSend', hint: 'shortcutSendHint', default: 'Enter' },
  { id: 'newLine', group: 'chat', label: 'shortcutNewLine', hint: 'shortcutNewLineHint', default: 'Shift+Enter' },
  { id: 'stopGeneration', group: 'chat', label: 'shortcutStop', hint: 'shortcutStopHint', default: 'Escape' },
  { id: 'attachFile', group: 'chat', label: 'shortcutAttach', hint: 'shortcutAttachHint', default: 'Mod+Shift+A' },
  { id: 'projects', group: 'projects', label: 'shortcutProjects', hint: 'shortcutProjectsHint', default: 'Mod+B' },
  { id: 'addProject', group: 'projects', label: 'shortcutAddProject', hint: 'shortcutAddProjectHint', default: 'Mod+Shift+O' },
  { id: 'closePreview', group: 'projects', label: 'shortcutClosePreview', hint: 'shortcutClosePreviewHint', default: 'Mod+Shift+W' },
].map(Object.freeze))
const ids = new Set(shortcutDefinitions.map(d => d.id))
const modifiers = ['Mod', 'Alt', 'Shift']
const namedKeys = new Set(['Enter', 'Space', 'Escape', 'Backspace', 'Delete', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Home', 'End', 'PageUp', 'PageDown', 'Insert', 'Plus', ',', '.', '/', ';', "'", '[', ']', '\\', '-', '=', '`'])
const reserved = new Set(['Mod+C', 'Mod+X', 'Mod+V', 'Mod+A', 'Mod+Z', 'Mod+Y', 'Mod+Shift+Z', 'Mod+R', 'Mod+Shift+R', 'Mod+W', 'Mod+Q', 'Mod+Space', 'Alt+F4', 'F5', 'F11', 'F12'])
function defaultShortcuts() { return Object.fromEntries(shortcutDefinitions.map(d => [d.id, d.default])) }
function bindingIssue(id, binding, bindings) {
  if (!ids.has(id)) return { kind: 'invalid' }
  if (binding === null) return null
  if (typeof binding !== 'string' || binding.length > 40) return { kind: 'invalid' }
  const parts = binding.split('+'), key = parts.pop()
  if (!key || !(/^[A-Z0-9]$/.test(key) || /^F([1-9]|1[0-2])$/.test(key) || namedKeys.has(key)) ||
      parts.some(p => !modifiers.includes(p)) || parts.join('+') !== modifiers.filter(m => parts.includes(m)).join('+')) return { kind: 'invalid' }
  if (reserved.has(binding)) return { kind: 'reserved' }
  if (key === 'Escape' && (id !== 'stopGeneration' || parts.length)) return { kind: 'reserved' }
  if (!parts.includes('Mod') && !parts.includes('Alt') && !/^F\d+$/.test(key) &&
      !(key === 'Escape' && id === 'stopGeneration') && !(key === 'Enter' && ['sendMessage', 'newLine'].includes(id))) return { kind: 'invalid' }
  const conflict = shortcutDefinitions.find(d => d.id !== id && bindings[d.id] === binding)
  return conflict ? { kind: 'conflict', action: conflict.id } : null
}
function validShortcuts(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === ids.size &&
    [...ids].every(id => Object.prototype.hasOwnProperty.call(value, id) && !bindingIssue(id, value[id], value))
}
/** Upgrade the previous complete map without replacing customized or removed bindings. */
function normalizeStoredShortcuts(value) {
  if (validShortcuts(value)) return { ...value }
  const added = ['sources', 'memories'], previous = [...ids].filter(id => !added.includes(id))
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).length !== previous.length ||
      !previous.every(id => Object.prototype.hasOwnProperty.call(value, id))) return null
  const next = { ...value, sources: null, memories: null }
  if (!validShortcuts(next)) return null
  for (const id of added) {
    const binding = shortcutDefinitions.find(d => d.id === id).default
    // Existing user assignments win when a new default combination is occupied.
    if (!bindingIssue(id, binding, next)) next[id] = binding
  }
  return next
}
function readShortcuts(value) { return normalizeStoredShortcuts(value) || defaultShortcuts() }
/** Logical keys preserve ordinary letters on localized keyboard layouts. */
function bindingFromEvent(event, mac = false) {
  if (event.isComposing || event.keyCode === 229 || event.getModifierState?.('AltGraph') ||
      (mac ? event.ctrlKey : event.metaKey)) return null
  let key = event.key
  if (!key || ['Control', 'Meta', 'Alt', 'Shift', 'Dead', 'Process', 'Unidentified', 'Tab'].includes(key)) return null
  if (key === ' ') key = 'Space'
  else if (key === '+') key = 'Plus'
  else if (/^[a-z]$/i.test(key)) key = key.toUpperCase()
  if (!(namedKeys.has(key) || /^[A-Z0-9]$/.test(key) || /^F([1-9]|1[0-2])$/.test(key))) return null
  return [(mac ? event.metaKey : event.ctrlKey) ? 'Mod' : '', event.altKey ? 'Alt' : '', event.shiftKey ? 'Shift' : '', key].filter(Boolean).join('+')
}
function formatShortcut(binding, locale = 'en', mac = false) {
  if (!binding) return ''
  const labels = { Mod: mac ? 'Cmd' : 'Ctrl', Shift: locale === 'es' ? 'Mayús' : 'Shift', Enter: locale === 'es' ? 'Intro' : 'Enter',
    Escape: 'Esc', Space: locale === 'es' ? 'Espacio' : 'Space', Backspace: locale === 'es' ? 'Retroceso' : 'Backspace', Delete: locale === 'es' ? 'Supr' : 'Delete',
    ArrowUp: '↑', ArrowDown: '↓', ArrowLeft: '←', ArrowRight: '→', Plus: '+' }
  return binding.split('+').map(p => labels[p] || p).join('+')
}
module.exports = { shortcutDefinitions, defaultShortcuts, readShortcuts, normalizeStoredShortcuts, validShortcuts, bindingIssue, bindingFromEvent, formatShortcut }
