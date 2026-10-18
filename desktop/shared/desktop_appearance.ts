/** Desktop presentation only; these values never enter runtime/model configuration. */
export type AppearancePreferences = { reduceMotion: boolean; showStartupScreen: boolean }
export const defaultAppearance: AppearancePreferences = { reduceMotion: false, showStartupScreen: true }
export function readAppearance(value: unknown): AppearancePreferences {
  const input = value && typeof value === 'object' ? value as Partial<AppearancePreferences> : {}
  return { reduceMotion: typeof input.reduceMotion === 'boolean' ? input.reduceMotion : false,
    showStartupScreen: typeof input.showStartupScreen === 'boolean' ? input.showStartupScreen : true }
}
export function applyAppearance(doc: Document, value: AppearancePreferences) {
  doc.documentElement?.setAttribute('data-nova-reduce-motion', String(value.reduceMotion))
  doc.documentElement?.setAttribute('data-nova-show-startup', String(value.showStartupScreen))
}
