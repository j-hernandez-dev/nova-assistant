import type {StorageFile, StorageOverview} from '../shared/storage'
import type {TranslationKey} from './i18n'

export const storageCategoryKeys = {
  chats: 'storageChats', attachments: 'storageAttachments', memories: 'storageMemories', navigation: 'storageNavigation',
  configuration: 'storageConfiguration', audit: 'storageAudit', catalog: 'storageCatalog', caches: 'storageCaches',
} as const satisfies Record<string,TranslationKey>
export type StorageCategoryId = keyof typeof storageCategoryKeys
export function storageCategoryKey(id:string):TranslationKey {
  return Object.prototype.hasOwnProperty.call(storageCategoryKeys,id)?storageCategoryKeys[id as StorageCategoryId]:'settingsStorage'
}
export function storageCategoryHint(id:string):TranslationKey {
  return (storageCategoryKey(id)+'Hint') as TranslationKey
}
export function storageBytes(bytes:number,locale:'es'|'en'):string {
  const amount=Number.isFinite(bytes)&&bytes>0?bytes:0
  const index=Math.max(0,Math.min(4,amount?Math.floor(Math.log(amount)/Math.log(1024)):0))
  return new Intl.NumberFormat(locale,{maximumFractionDigits:index===0?0:1}).format(amount/1024**index)+' '+['B','KB','MB','GB','TB'][index]
}
/** Unlinked is always visible and first, even with no files. Host project order is retained. */
export function storageGroups(projects:StorageOverview['projects']):StorageOverview['projects'] {
  return [projects.find(project=>project.path===null)||{path:null,name:'',bytes:0,fileCount:0},...projects.filter(project=>project.path!==null)]
}
export function storageSelectionTarget(files:StorageFile[],selected:readonly string[]):string {
  const values=new Set(files.filter(file=>selected.includes(file.id)).map(file=>file.projectPath||''))
  return values.size===1?[...values][0]:'__mixed__'
}
export function storageSelectedFiles(files:StorageFile[],selected:readonly string[]):string[] {
  const wanted=new Set(selected)
  return files.filter(file=>wanted.has(file.id)).map(file=>file.id)
}
