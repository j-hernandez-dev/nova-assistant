type Locale = 'es' | 'en'
type ConfirmationOptions = { type: 'warning'; title: string; message: string; detail: string;
  buttons: string[]; defaultId: 0; cancelId: 0; noLink: true }
export function desktopHostMessages(locale: unknown): Record<string, string>
export function memoryDialogOptions(locale: Locale, request: { name: string; workspace: string | null; write: boolean }): ConfirmationOptions
export function forwardingDialogOptions(locale: Locale): ConfirmationOptions
export function pickerDialogOptions(locale: Locale, kind: 'export'): { title: string; buttonLabel: string; defaultPath: string }
export function pickerDialogOptions(locale: Locale, kind: 'document' | 'refresh' | 'project'): { title: string; buttonLabel: string; properties: Array<'openDirectory' | 'openFile'> }
export function oauthPage(locale: Locale, status: 'success' | 'failed' | 'invalid'): string
