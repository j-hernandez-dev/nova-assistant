export type DesktopPreferences = import('../shared/desktop_general').GeneralPreferences & import('../shared/desktop_appearance').AppearancePreferences & { schemaVersion: 1; locale: 'es' | 'en'; zoomPercent:number; shortcuts?: import('../shared/keyboard_shortcuts.cjs').ShortcutBindings }
export type DesktopPreferencesResult =
  | { success: true; preferences: DesktopPreferences }
  | { success: false; error: { code: string; message: string } }
export function createDesktopPreferencesStore(directory: string, systemLanguage?: () => string): {
  get(): DesktopPreferences
  setZoomPercent(value:unknown):DesktopPreferencesResult
  setLocale(locale: unknown): DesktopPreferencesResult
  setAppearance(value: unknown): DesktopPreferencesResult
  setShortcuts(value: unknown): DesktopPreferencesResult
  setGeneral(value: unknown): DesktopPreferencesResult
}
