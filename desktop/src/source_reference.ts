import type {KnowledgeCitations} from '../shared/application'
import type {TranslationKey} from './i18n'

type Citation = KnowledgeCitations['valid'][number]
type Translate = (key: TranslationKey) => string

/** Presentation only. Coordinates never resolve a path or open a URL. */
export function sourceReferenceLocation(locator: Citation['locator'], t: Translate): string {
  const c = locator?.coordinates || {}
  const number = (value: unknown) => typeof value === 'number' && Number.isSafeInteger(value) && value > 0
  const label = (key: TranslationKey, value: string | number) => t(key).replace('{value}', String(value))
  switch (locator?.kind) {
    case 'TEXT_LINES':
      if (number(c.lineStart) && number(c.lineEnd) && Number(c.lineEnd) >= Number(c.lineStart))
        return Number(c.lineStart) === Number(c.lineEnd) ? label('referenceLine', c.lineStart)
          : t('referenceLines').replace('{start}', String(c.lineStart)).replace('{end}', String(c.lineEnd))
      break
    case 'PDF_PAGE':
      if (number(c.page)) return label('referencePage', c.page)
      break
    case 'DOCX_PARAGRAPH':
      if (number(c.paragraph)) return label('referenceParagraph', c.paragraph)
      break
    case 'JSON_POINTER':
      if (typeof c.pointer === 'string') return c.pointer ? label('referenceField', c.pointer) : t('referenceDocumentRoot')
      break
    case 'WEB_BLOCK':
      if (typeof c.block === 'string' && c.block) return label('referenceBlock', c.block)
      break
    case 'SEARCH_RESULT':
      if (number(c.rank)) return label('referenceResult', c.rank)
  }
  return t('referenceLocation')
}

export function sourceReferenceIcon(citation: Citation): 'globe' | 'file-read' {
  return /^https?:\/\//i.test(citation.originDisplay || '') || citation.locator?.kind === 'SEARCH_RESULT' ? 'globe' : 'file-read'
}
