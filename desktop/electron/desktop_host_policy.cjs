// Nova has no approved desktop update destination yet. Do not contact the
// inherited Local CLI updater, including from manual compatibility handlers.
const DESKTOP_UPDATES_ENABLED = false

function disabledDesktopUpdate(version) {
  return { available: false, version, disabled: true, code: 'NOVA_DESKTOP_UPDATES_DISABLED',
    message: 'Desktop updates are not configured for Nova.' }
}

/** Preserve ordinary editing shortcuts when the application menubar is absent. */
function editingActionForInput(input, platform) {
  if (input.type !== 'keyDown' || input.alt) return null
  const modifier = platform === 'darwin' ? input.meta && !input.control : input.control && !input.meta
  if (!modifier) return null
  const key = String(input.key || '').toLowerCase()
  if (input.shift) return key === 'z' ? 'redo' : null
  return ({ c: 'copy', x: 'cut', v: 'paste', a: 'selectAll', z: 'undo', y: 'redo' })[key] || null
}

module.exports = { DESKTOP_UPDATES_ENABLED, disabledDesktopUpdate, editingActionForInput }
