import { resolveTheme, themeIds, SYSTEM_INTERFACE_FONT, SYSTEM_CODE_FONT, type ThemeId, type ColorScheme } from './desktop_theme'

/** Desktop presentation only; these values never enter runtime/model configuration. */
export type AppearancePreferences = {
  colorScheme: ColorScheme; lightTheme: ThemeId; darkTheme: ThemeId
  interfaceFont: string; codeFont: string
  showStartupScreen: boolean; startupMotion: boolean; mascotMotion: boolean
  mascotAppearance: '2d' | '3d'
}
export const defaultAppearance: AppearancePreferences = {
  colorScheme: 'system', lightTheme: 'nova', darkTheme: 'nova', interfaceFont: 'system', codeFont: 'system',
  showStartupScreen: true, startupMotion: true, mascotMotion: true, mascotAppearance: '2d',
}
export const appearanceKeys = Object.keys(defaultAppearance) as (keyof AppearancePreferences)[]
const fontValid = (value: unknown): value is string => typeof value === 'string' && value.trim() === value && value.length > 0 && value.length <= 128 && !/[\u0000-\u001f\u007f]/.test(value)
export function readAppearance(value: unknown): AppearancePreferences {
  const input = value && typeof value === 'object' ? value as Record<string, unknown> : {}
  return {
    colorScheme: ['system', 'light', 'dark'].includes(input.colorScheme as string) ? input.colorScheme as ColorScheme : 'system',
    lightTheme: themeIds.includes(input.lightTheme as ThemeId) ? input.lightTheme as ThemeId : 'nova',
    darkTheme: themeIds.includes(input.darkTheme as ThemeId) ? input.darkTheme as ThemeId : 'nova',
    interfaceFont: fontValid(input.interfaceFont) ? input.interfaceFont : 'system',
    codeFont: fontValid(input.codeFont) ? input.codeFont : 'system',
    showStartupScreen: typeof input.showStartupScreen === 'boolean' ? input.showStartupScreen : true,
    startupMotion: typeof input.startupMotion === 'boolean' ? input.startupMotion : input.reduceMotion !== true,
    mascotMotion: typeof input.mascotMotion === 'boolean' ? input.mascotMotion : input.reduceMotion !== true,
    mascotAppearance: input.mascotAppearance === '3d' ? '3d' : '2d',
  }
}
export function validAppearance(value: unknown): value is AppearancePreferences {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const input = value as Record<string, unknown>, parsed = readAppearance(value)
  return appearanceKeys.every(key => input[key] === parsed[key])
}
export function sameAppearance(left: AppearancePreferences, right: AppearancePreferences) {
  return appearanceKeys.every(key => left[key] === right[key])
}
function fontFamily(name: string, fallback: string) {
  return name === 'system' ? fallback : `${JSON.stringify(name)}, ${fallback}`
}
export function appearancePresentation(value: AppearancePreferences, systemDark: boolean) {
  const appearance = readAppearance(value), palette = resolveTheme(appearance, systemDark)
  return {
    attributes: { 'data-nova-theme': palette.id, 'data-nova-scheme': palette.mode,
      'data-nova-startup-motion': String(appearance.startupMotion),
      'data-nova-mascot-motion': String(appearance.mascotMotion),
      'data-nova-mascot-appearance': appearance.mascotAppearance,
      'data-nova-show-startup': String(appearance.showStartupScreen) },
    variables: { ...palette.colors, '--font': fontFamily(appearance.interfaceFont, SYSTEM_INTERFACE_FONT),
      '--font-code': fontFamily(appearance.codeFont, SYSTEM_CODE_FONT), 'color-scheme': palette.mode },
  }
}
export function applyAppearance(doc: Document, value: AppearancePreferences, systemDark = !!doc.defaultView?.matchMedia?.('(prefers-color-scheme: dark)').matches) {
  if (!doc.documentElement) return
  const { attributes, variables } = appearancePresentation(value, systemDark)
  for (const [key, content] of Object.entries(attributes)) doc.documentElement.setAttribute(key, content)
  for (const [key, content] of Object.entries(variables)) doc.documentElement.style.setProperty(key, content)
  doc.documentElement.removeAttribute('data-nova-reduce-motion')
}
