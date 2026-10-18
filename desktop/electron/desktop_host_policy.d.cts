export const DESKTOP_UPDATES_ENABLED: boolean
export function disabledDesktopUpdate(version: string): {
  available: false; version: string; disabled: true; code: string; message: string
}
export function editingActionForInput(input: {
  type: string; key: string; alt: boolean; control: boolean; meta: boolean; shift: boolean
}, platform: string): 'copy' | 'cut' | 'paste' | 'selectAll' | 'undo' | 'redo' | null
