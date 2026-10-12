import type { DesktopApplicationClient } from './application_client'
import type { BrowserControlResult } from '../shared/application'
export const RISK_ACKNOWLEDGEMENT_VERSION: 'IB_V12_RISK_1'
export const RISK_MESSAGE: string
export const RISK_DETAIL: string
export function configureWebV12(client:DesktopApplicationClient,
  request:{controlledFetchEnabled:boolean;interactiveBrowserEnabled:boolean},
  showRiskDialog:(request:{message:string;detail:string})=>Promise<{response:number}>,
  commandId?:string):Promise<BrowserControlResult>
export function finishWebV12Takeover(client:DesktopApplicationClient,takeoverRef:string,
  showConfirm:(request:{reason:string})=>Promise<{response:number}>,
  commandId?:string):Promise<BrowserControlResult>
export function selectWebV12Upload(client:DesktopApplicationClient,operationId:string,
  showPicker:(request:{origin:string;label:string})=>Promise<{canceled:boolean;filePaths:string[]}>,
  commandId?:string):Promise<BrowserControlResult>
