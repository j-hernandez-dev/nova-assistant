import type { DesktopApplicationClient } from './application_client'
import type { CommandReceipt } from '../shared/application'
export function pickKnowledge(client: DesktopApplicationClient,
  showPicker: () => Promise<{canceled:boolean;filePaths:string[]}>): Promise<CommandReceipt>
export function knowledgeControl(client: DesktopApplicationClient,name:string,
  args:Record<string,unknown>,commandId?:string): Promise<CommandReceipt>
export function hostSelection(client:DesktopApplicationClient,name:string,sourceId:string,
  select:()=>Promise<any>):Promise<CommandReceipt>
export function remoteKnowledge(client:DesktopApplicationClient,args:Record<string,unknown>,
  showConfirm:()=>Promise<{response:number}>,commandId?:string):Promise<CommandReceipt>
