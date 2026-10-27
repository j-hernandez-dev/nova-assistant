export type StorageCategory = 'chats'|'attachments'|'memories'|'navigation'|'configuration'|'audit'|'catalog'|'caches'
export type StorageFile = {id:string;name:string;modifiedAt:string;bytes:number;projectPath:string|null}
export type SourceFile = StorageFile & {kind:'file'|'url';url:string|null;state:string;downloadable:boolean}
export type SourceInventory = {files:SourceFile[];projects:Array<{path:string;name:string}>}
export type SourceImportResult = {completed:boolean;imported:number;sourceIds?:string[];canceled?:boolean;error?:{code:string}}
export type SourcePreview = {sourceId:string;root:string;name:string;content:string|null;reason:'NO_CONTENT'|'TOO_LARGE'|'BINARY'|null}
/** Folder bytes cover the explicit managed cleanup targets, which may be a
 * subset of the category total (for example, shared metadata is preserved). */
export type StorageFolder = {id:StorageCategory;category:StorageCategory;path:string;paths?:string[];bytes:number;exists:boolean;restartRequired:boolean;complete?:boolean}
export type StorageProject = {path:string|null;name:string;bytes:number;fileCount:number}
export type StorageOverview = {
  totalBytes:number;categories:Array<{id:StorageCategory;bytes:number;complete?:boolean}>
  folders:StorageFolder[];projects:StorageProject[];warnings?:string[];restartRequired:boolean
}
export type StorageResult<T=unknown> = {success:true;data:T;canceled?:false}|{success:false;canceled?:boolean;error?:{code:string}}
export type StorageFiles = {files:StorageFile[];projectPath:string|null}
export type StorageMutation = {restartRequired?:boolean;queued?:boolean;files?:StorageFile[]}
