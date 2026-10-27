import type {DesktopApplicationClient} from './application_client'
import type {SourceImportResult} from '../shared/storage'
export function createSourceImporter(client:DesktopApplicationClient,options:{
  pick:()=>Promise<{canceled:boolean;filePaths:string[]}>;isBlocked?:()=>boolean;onBusy?:(busy:boolean)=>void
}):{pick:()=>Promise<SourceImportResult>;drop:(paths:unknown)=>Promise<SourceImportResult>;isBusy:()=>boolean}
