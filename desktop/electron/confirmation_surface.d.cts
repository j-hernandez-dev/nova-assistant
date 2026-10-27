export function createConfirmationSurface(options:any):{
  request(request:{kind:'remove-project'|'clear-chat'|'clear-all'|'memory-import'|'memory-export-sensitive'|'memory-sensitive-access'|'memory-reveal-sensitive'|'memory-write-sensitive'|'memory-classify-sensitive'|'memory-classify-normal'|'memory-delete-records'|'storage-delete-folder'|'storage-delete-files'|'sources-delete-files'|'storage-restart';projectName?:string;path?:string;folderId?:string;fileCount?:number;restartRequired?:boolean;validate:()=>boolean}):Promise<{confirmed:boolean;canceled:boolean;deleteAssociatedFiles?:boolean}>;
  isPending():boolean;sync():void;updateLocale():void;updateAppearance(preferences?:unknown,systemDark?:boolean):void;dispose():void
}
