/** Resize after controlled value changes, including clearing a submitted multiline draft. */
export function resizePrompt(element: HTMLTextAreaElement): void {
  const style = getComputedStyle(element)
  const minimum = parseFloat(style.minHeight) || 0
  const maximum = parseFloat(style.maxHeight) || Infinity
  element.style.height = '0px'
  const desired = element.value ? element.scrollHeight : minimum
  element.style.height = `${Math.max(minimum, Math.min(desired, maximum))}px`
  element.style.overflowY = desired > maximum ? 'auto' : 'hidden'
}
