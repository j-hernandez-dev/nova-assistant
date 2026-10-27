import {useCallback,useEffect,useRef,useState} from 'react'
import {useI18n} from './i18n'
import {settingErrorKey} from './settings_services_locale'

type Receipt={accepted?:boolean;completed?:boolean;success?:boolean;canceled?:boolean;error?:{code?:string;outcomeUnknown?:boolean}|null}
export type SettingsActionState={busy:boolean;unconfirmed:boolean;errorCode:string|null;result:Receipt|null}

/** UI request observation only; authority and operation outcomes remain in the host. */
export function useSettingsAction(scope:string) {
  const [state,setState]=useState<SettingsActionState>({busy:false,unconfirmed:false,errorCode:null,result:null})
  const active=useRef(false), alive=useRef(true), epoch=useRef(0)
  const timer=useRef<ReturnType<typeof setTimeout>|null>(null)
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;epoch.current++;if(timer.current)clearTimeout(timer.current)}},[])
  useEffect(()=>{epoch.current++;active.current=false;if(timer.current)clearTimeout(timer.current)
    setState({busy:false,unconfirmed:false,errorCode:null,result:null})},[scope])
  const run=useCallback(async<T extends Receipt,>(action:()=>Promise<T>):Promise<T|null>=>{
    if(active.current)return null
    active.current=true;const request=epoch.current
    setState({busy:true,unconfirmed:false,errorCode:null,result:null})
    timer.current=setTimeout(()=>{if(alive.current&&request===epoch.current)
      setState({busy:true,unconfirmed:true,errorCode:null,result:null})},30_000)
    let retain=false
    try {
      const result=await action()
      if(!alive.current||request!==epoch.current)return null
      if(result?.canceled){setState({busy:false,unconfirmed:false,errorCode:null,result:null});return null}
      if(result?.error && (result.error.outcomeUnknown===true||['OUTCOME_UNKNOWN','COMMAND_OUTCOME_UNKNOWN','TIMEOUT','CONNECTION_LOST'].includes(result.error.code||''))){
        retain=true
        setState({busy:true,unconfirmed:true,errorCode:null,result:null});return null
      }
      const success=result && !result.error && (result.accepted===true||result.completed===true||result.success===true)
      setState({busy:false,unconfirmed:false,errorCode:success?null:result?.error?.code||'SETTINGS_OPERATION_FAILED',result:success?result:null})
      return success?result:null
    }catch{
      retain=true
      if(alive.current&&request===epoch.current)setState({busy:true,unconfirmed:true,errorCode:null,result:null})
      return null
    }finally{
      if(request===epoch.current){active.current=retain;if(timer.current)clearTimeout(timer.current);timer.current=null}
    }
  },[])
  return {...state,run}
}

export function SettingsActionFeedback({action}:{action:SettingsActionState}) {
  const {t}=useI18n()
  if(action.unconfirmed)return <p className="settings-feedback" role="status">{t('settingsServiceUnknown')}</p>
  if(action.errorCode)return <div className="settings-feedback error" role="alert"><p>{t(settingErrorKey(action.errorCode))}</p>
    <details><summary>{t('diagnosticDetails')}</summary><code>{action.errorCode}</code></details></div>
  if(action.busy)return <p className="settings-feedback" role="status">{t('settingsServiceSaving')}</p>
  if(action.result)return <p className="settings-feedback" role="status">{t(action.result.completed||action.result.success?'settingsOperationComplete':'settingsOperationAccepted')}</p>
  return null
}
