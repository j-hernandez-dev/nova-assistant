import {useCallback,useEffect,useMemo,useRef,useState} from 'react'
import type {DesktopSessionView} from '../shared/application'
import {projectPathKey} from './project_presentation'
import {MemoryProposalNotifications} from './memory_proposal_notifications'

/** Observe ordinary inspection while idle, without polling or retaining proposal content. */
export function useMemoryProposalNotifications(view:DesktopSessionView|null,windowVisible:boolean,locked:boolean){
  const workspace=view?.workspace?projectPathKey(view.workspace):''
  const model=useMemo(()=>new MemoryProposalNotifications(workspace?{
    load:()=>JSON.parse(window.localStorage.getItem('nova.memory-proposal-notifications.v1:'+workspace)||'null'),
    save:value=>window.localStorage.setItem('nova.memory-proposal-notifications.v1:'+workspace,JSON.stringify(value)),
  }:undefined),[workspace])
  const [revision,update]=useState(0),alive=useRef(true),flight=useRef(false)
  const checked=useRef<{model:MemoryProposalNotifications;session:string|null;revision:number}|null>(null)
  const current=useRef({model,view});current.current={model,view}
  const canRead=!!workspace&&!!view?.sessionId&&!!view.status.ready&&view.status.connected&&!view.recovering&&!view.gap&&!!view.memory
    &&!locked&&!view.activeTurnId&&!view.activeGenerationId&&!view.approvals.length&&!view.inputs.length&&!view.memory.maintenanceBusy
  const observe=useCallback((proposals:unknown)=>{if(model.observe(proposals))update(value=>value+1)},[model])
  const setTabVisible=useCallback((visible:boolean)=>{model.setTabVisible(visible);update(value=>value+1)},[model])
  useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[])
  useEffect(()=>{model.setWindowVisible(windowVisible);update(value=>value+1)},[model,windowVisible])
  useEffect(()=>{
    if(!canRead||flight.current||checked.current?.model===model&&checked.current.session===view!.sessionId&&checked.current.revision===view!.stateRevision)return
    // Wait for a burst of snapshots (and StrictMode's mount replay) to settle.
    const timer=setTimeout(()=>{
      const session=view!.sessionId
      flight.current=true
      void window.api.memoryCommand('memory_proposals',{}).then(receipt=>{
        if(!alive.current||current.current.model!==model||current.current.view?.sessionId!==session)return
        // The read itself advances the host revision. Do not turn its receipt
        // and follow-up snapshot into another inspection request.
        checked.current={model,session,revision:receipt.stateRevision??current.current.view!.stateRevision}
        if(receipt.completed&&!receipt.error)model.observe(receipt.data?.proposals)
      }).catch(()=>{
        if(current.current.model===model)checked.current={model,session,revision:current.current.view!.stateRevision}
      }).finally(()=>{flight.current=false;if(alive.current)update(value=>value+1)})
    },180)
    return()=>clearTimeout(timer)
  },[model,view?.sessionId,view?.stateRevision,canRead,revision])
  return{counts:model.counts,observe,setTabVisible}
}
