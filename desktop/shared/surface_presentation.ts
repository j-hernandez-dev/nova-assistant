/** Only the fixed host dialog preloads consume this presentation payload. */
export function applySurfacePresentation(doc: Document, presentation: unknown) {
  if (!presentation || typeof presentation !== 'object') return
  const value = presentation as {variables?:Record<string,string>;attributes?:Record<string,string>}
  for (const [key, content] of Object.entries(value.variables || {})) {
    if ((key === 'color-scheme' || /^--[a-z0-9-]+$/.test(key)) && typeof content === 'string') doc.documentElement.style.setProperty(key, content)
  }
  doc.documentElement.style.setProperty('--nova-color-scheme', value.variables?.['color-scheme'] === 'light' ? 'light' : 'dark')
  for (const key of ['data-nova-theme','data-nova-scheme']) {
    if (typeof value.attributes?.[key] === 'string') doc.documentElement.setAttribute(key, value.attributes[key])
  }
}
