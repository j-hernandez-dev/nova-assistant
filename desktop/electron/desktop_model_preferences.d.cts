export type DesktopModelPreferences = { schemaVersion: 1; providerId: 'ollama'; modelId: string }
export type DesktopModelPreferencesResult =
  | { success: true; preferences: DesktopModelPreferences }
  | { success: false; error: { code: string; message: string } }
export function createDesktopModelPreferencesStore(directory: string): {
  get(): DesktopModelPreferences | null
  saveConfirmed(selection: { providerId: string; modelId: string }): DesktopModelPreferencesResult
  childEnvironment<T extends Record<string, string | undefined>>(environment: T): T & { LOCAL_CLI_MODEL?: string; LOCAL_CLI_PROVIDER?: string }
}
