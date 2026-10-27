export type ShortcutAction = 'settings' | 'sources' | 'memories' | 'models' | 'focusPrompt' | 'toggleHistory' | 'showHome' | 'sendMessage' | 'newLine' | 'stopGeneration' | 'attachFile' | 'projects' | 'addProject' | 'closePreview'
export type ShortcutBindings = Record<ShortcutAction, string | null>
export type ShortcutKeyEvent = { key: string; ctrlKey: boolean; metaKey: boolean; altKey: boolean; shiftKey: boolean; isComposing?: boolean; keyCode?: number; getModifierState?: (key: string) => boolean }
export const shortcutDefinitions: ReadonlyArray<Readonly<{ id: ShortcutAction; group: 'general' | 'chat' | 'projects'; label: string; hint: string; default: string | null }>>
export function defaultShortcuts(): ShortcutBindings
export function readShortcuts(value: unknown): ShortcutBindings
export function normalizeStoredShortcuts(value: unknown): ShortcutBindings | null
export function validShortcuts(value: unknown): value is ShortcutBindings
export function bindingIssue(id: ShortcutAction, binding: unknown, bindings: ShortcutBindings): { kind: 'invalid' | 'reserved' | 'conflict'; action?: ShortcutAction } | null
export function bindingFromEvent(event: ShortcutKeyEvent, mac?: boolean): string | null
export function formatShortcut(binding: string | null, locale?: 'es' | 'en', mac?: boolean): string
