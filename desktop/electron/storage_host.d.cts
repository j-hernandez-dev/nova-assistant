import type {StorageOverview,StorageFiles,StorageMutation,StorageResult,SourceInventory,SourcePreview} from '../shared/storage'
export type StorageLocations = {profileDir:string;stateDir?:string;auditDir?:string;catalogDir?:string;tempDir?:string;controlDir?:string;homeDir?:string;configFile?:string;env?:Record<string,string|undefined>}
export type ResolvedStorageLocations = {profileDir:string;stateDir:string;auditDir:string;catalogDir:string;controlDir:string;knowledge:string;browserProfiles:string;usageDir:string;usageFiles:string[];hostConfigFile:string;manifest:string;rootFingerprint:string;warnings:string[];groups:Record<string,string[]>}
export function storageLocations(options:StorageLocations):ResolvedStorageLocations
export {storageLocations as resolveStorageLocations}
export function applyPendingStorageDeletions(options:StorageLocations):{completed:string[];failed:Array<{id:string;code:string}>;warnings:string[]}
export function createStorageHost(options:StorageLocations & {
  client:any;getProjects:()=>Array<{path:string;name:string}>|{folders:Array<{path:string;name:string}>}
  confirm:(request:{kind:'storage-delete-folder'|'storage-delete-files'|'sources-delete-files'|'storage-restart';folderId?:string;fileCount?:number;path?:string;restartRequired?:boolean;validate:()=>boolean})=>Promise<boolean|{confirmed:boolean}>
  openPath:(path:string)=>Promise<string>;restart:()=>void|Promise<void>;publish?:()=>void;isBlocked?:()=>boolean;externalBusy?:()=>boolean
  pickSave?:(request:{name:string})=>Promise<{canceled:boolean;filePath?:string}>
}): {
  overview(args?:{refresh?:boolean}):Promise<StorageResult<StorageOverview>>
  files(projectPath:string|null):Promise<StorageResult<StorageFiles>>
  sources():Promise<StorageResult<SourceInventory>>
  sourcePreview(id:string):Promise<StorageResult<SourcePreview>>
  move(ids:string[],projectPath:string|null,sources?:boolean):Promise<StorageResult<StorageMutation>>
  deleteFiles(ids:string[],sources?:boolean):Promise<StorageResult<StorageMutation>>
  download(ids:string[],sources?:boolean):Promise<StorageResult<{downloaded:number}>>
  openFolder(id:string):Promise<StorageResult<{path:string}>>
  deleteFolder(id:string):Promise<StorageResult<{restartRequired:boolean;queued:boolean}>>
  restart():Promise<StorageResult<{restartRequired:boolean}>>
  detachProject(projectPath:string,deleteFiles?:boolean):Promise<StorageResult<StorageMutation>>
  invalidate():void
  isBusy():boolean
}
