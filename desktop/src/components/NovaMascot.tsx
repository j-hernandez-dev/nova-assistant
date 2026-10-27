import {useEffect,useRef,useState} from 'react'
import {useAppearance} from '../appearance'
import {useI18n} from '../i18n'
import {NovaOrbit} from './NovaOrbit'
import type {NovaThreeAvatar} from '../nova_three'
import '../nova_mascot.css'

/** The scene and settings preview share one confirmed appearance preference. */
export function NovaMascot({preview=false}:{preview?:boolean}){
  const {appearance}=useAppearance()
  return appearance.mascotAppearance==='3d'?<NovaThree motion={appearance.mascotMotion} preview={preview}/>:<NovaOrbit/>
}

function NovaThree({motion,preview}:{motion:boolean;preview:boolean}){
  const {t}=useI18n(),host=useRef<HTMLDivElement>(null),avatar=useRef<NovaThreeAvatar|null>(null)
  const motionRef=useRef(motion);motionRef.current=motion
  const [state,setState]=useState<'loading'|'ready'|'fallback'>('loading')
  useEffect(()=>{
    let current=true
    // Three.js stays out of the initial 2D path; all geometry is generated locally.
    void import('../nova_three').then(({createNovaThreeAvatar})=>{
      if(!current||!host.current)return
      try{
        avatar.current=createNovaThreeAvatar(host.current,motionRef.current,()=>{if(current)setState('fallback')})
        setState('ready')
      }catch{if(current)setState('fallback')}
    }).catch(()=>{if(current)setState('fallback')})
    return()=>{current=false;avatar.current?.dispose();avatar.current=null}
  },[])
  useEffect(()=>{avatar.current?.setMotion(motion)},[motion])
  useEffect(()=>{if(state==='fallback'){avatar.current?.dispose();avatar.current=null}},[state])
  return <div className="nova-mascot-3d" data-mascot-renderer={state}>
    <div ref={host} className="nova-mascot-3d-host" aria-hidden="true"/>
    {state!=='ready'&&<NovaOrbit/>}
    {preview&&state==='fallback'&&<p className="nova-mascot-fallback" role="status">{t('appearanceMascotUnavailable')}</p>}
  </div>
}
