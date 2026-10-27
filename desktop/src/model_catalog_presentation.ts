import type { CatalogModel } from './components/ModelPicker'
import type { TranslationKey } from './i18n'

/** Display helpers never grant model availability or select a substitute tag. */
export function installedModelName(name: string, installed: readonly string[] | undefined): string | null {
  if (!installed) return null
  if (installed.includes(name)) return name
  if (name.includes(':')) return null
  const variants = installed.filter(value => value.split(':')[0] === name)
  return variants.length === 1 ? variants[0] : null
}
export function installedVariants(name: string, installed: readonly string[] | undefined): string[] {
  return installed?.filter(value => value === name || (!name.includes(':') && value.split(':')[0] === name)) || []
}
export function filterCatalog(models: CatalogModel[], filter: string, category: string | null): CatalogModel[] {
  const query = filter.trim().toLocaleLowerCase()
  return models.filter(model => (!category || model.category === category) && (!query ||
    [model.name, model.display, model.description, ...model.tags].some(value => value.toLocaleLowerCase().includes(query))))
}
export function modelCategoryKey(value: string): TranslationKey | null {
  const mapping: Record<string, TranslationKey> = { Installed: 'modelInstalledCategory', Code: 'code', General: 'modelGeneralCategory',
    Small: 'modelSmallCategory', Reasoning: 'reasoning',
    Multilingual: 'modelMultilingualCategory', Vision: 'vision', Embedding: 'modelEmbeddingCategory',
    'コード': 'code', '汎用': 'modelGeneralCategory', '小型': 'modelSmallCategory',
    '推論': 'reasoning',  '多言語': 'modelMultilingualCategory',
    '画像': 'vision', '埋め込み': 'modelEmbeddingCategory' }
  return Object.prototype.hasOwnProperty.call(mapping,value) ? mapping[value] : null
}
export function modelErrorKey(code?: string | null): TranslationKey {
  const mapping: Record<string, TranslationKey> = { MODEL_CATALOG_FAILED: 'modelCatalogFailed',
    MODEL_RECOMMEND_FAILED: 'modelRecommendFailed', MODEL_DOWNLOAD_FAILED: 'modelDownloadFailed',
    MODEL_DELETE_FAILED: 'modelDeleteFailed', MODEL_SYNC_FAILED: 'modelSyncFailed',
    MODEL_OPERATION_UNCONFIRMED: 'modelOperationUnconfirmed' }
  return code && Object.prototype.hasOwnProperty.call(mapping,code) ? mapping[code] : 'actionFailed'
}
export function pullPercent(progress: string): number | null {
  const match = progress.match(/(?:^|\s)(\d{1,3})%(?:\s|$)/)
  return match ? Math.min(100, Math.max(0, Number(match[1]))) : null
}
export function easeRating(value?: number): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value >= 1 && value <= 5 ? value : null
}
export function modelContext(value?: number): string {
  return typeof value === 'number' && Number.isFinite(value) && value > 0
    ? value >= 1024 ? `${Math.round(value / 1024)}K` : String(Math.round(value)) : ''
}

/** All is the primary library; recommendations use the same public inventory. */
export const catalogSections = [
  {id:'all',label:'all'}, {id:'installed',label:'modelInstalledCategory'}, {id:'recommend',label:'forYou'},
] as const satisfies ReadonlyArray<{id:string;label:TranslationKey}>
export type CatalogSection = typeof catalogSections[number]['id']
