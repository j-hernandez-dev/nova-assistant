export type DesktopPreferences = { schemaVersion: 1; locale: 'es' | 'en'; reduceMotion: boolean; showStartupScreen: boolean }
export type DesktopPreferencesResult =
  | { success: true; preferences: DesktopPreferences }
  | { success: false; error: { code: string; message: string } }
export function createDesktopPreferencesStore(directory: string): {
  get(): DesktopPreferences
  setLocale(locale: unknown): DesktopPreferencesResult
  setAppearance(value: unknown): DesktopPreferencesResult
}
