export type LanguagePreference = 'system' | 'es' | 'en'
export type GeneralPreferences = { language: LanguagePreference; autoSwitchView: boolean; transitionsEnabled: boolean; showFiles: boolean; collapsibleSourceContext: boolean }
export const defaultGeneral: GeneralPreferences = { language: 'system', autoSwitchView: false, transitionsEnabled: true, showFiles: true, collapsibleSourceContext: false }
export function readGeneral(value: unknown): GeneralPreferences {
  const input = value && typeof value === 'object' ? value as Partial<GeneralPreferences> & {locale?: string} : {}
  return {
    language: ['system', 'es', 'en'].includes(input.language || '') ? input.language! :
      input.locale === 'es' || input.locale === 'en' ? input.locale : 'system',
    autoSwitchView: typeof input.autoSwitchView === 'boolean' ? input.autoSwitchView : false,
    transitionsEnabled: typeof input.transitionsEnabled === 'boolean' ? input.transitionsEnabled : true,
    showFiles: typeof input.showFiles === 'boolean' ? input.showFiles : true,
    collapsibleSourceContext: typeof input.collapsibleSourceContext === 'boolean' ? input.collapsibleSourceContext : false,
  }
}
export function applyGeneral(doc: Document, value: GeneralPreferences) {
  doc.documentElement?.setAttribute('data-nova-transitions', String(value.transitionsEnabled))
}
