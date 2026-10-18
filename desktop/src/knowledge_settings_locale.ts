export const knowledgeSettingsEnglish = {
  knowledgeScopeSession: 'Current session', knowledgeScopeOther: 'Source scope',
  knowledgeNoAttachments: 'No document attachments are available in this session.',
  knowledgeOperations: 'Document operations', knowledgeIndexing: 'Project indexing is in progress.',
} as const
export const knowledgeSettingsSpanish: Record<keyof typeof knowledgeSettingsEnglish, string> = {
  knowledgeScopeSession: 'Sesión actual', knowledgeScopeOther: 'Ámbito de la fuente',
  knowledgeNoAttachments: 'No hay archivos adjuntos disponibles en esta sesión.',
  knowledgeOperations: 'Operaciones de documentos', knowledgeIndexing: 'La indexación del proyecto está en curso.',
}
