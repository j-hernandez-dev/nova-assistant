import {useEffect,useId,useLayoutEffect,useRef,useState,type CSSProperties,type KeyboardEvent} from 'react'
import {createPortal} from 'react-dom'
import type {ProjectAction,ProjectFolder} from '../types'
import {useI18n} from '../i18n'

/** Registered folder actions only. The host owns pickers, confirmation and the effective root. */
export function ProjectFolderMenu({folder,disabled,onAction}:{folder:ProjectFolder;disabled:boolean;onAction:(action:ProjectAction,path?:string)=>Promise<void>}){
  const {t}=useI18n(),id=useId(),trigger=useRef<HTMLButtonElement>(null),menu=useRef<HTMLDivElement>(null)
  const [open,setOpen]=useState(false),[position,setPosition]=useState<CSSProperties>({visibility:'hidden'})
  const container=typeof document==='undefined'?null:trigger.current?.closest<HTMLElement>('[role="dialog"]')||document.body
  const actions=folder.isDefault?['change','open'] as const:['change','remove','open'] as const
  const close=(restore=false)=>{setOpen(false);if(restore)trigger.current?.focus()}
  useEffect(()=>{setOpen(false)},[disabled,folder.path])
  useLayoutEffect(()=>{
    if(!open||!container)return
    const place=()=>{
      const box=trigger.current?.getBoundingClientRect();if(!box)return
      const modal=container!==document.body,bounds=modal?container.getBoundingClientRect():null
      const originX=(bounds?.left||0)+(modal?container.clientLeft:0),originY=(bounds?.top||0)+(modal?container.clientTop:0)
      const right=originX+(modal?container.clientWidth:innerWidth)-8,bottom=originY+(modal?container.clientHeight:innerHeight)-8
      const left=originX+8,top=originY+8,width=Math.min(220,right-left),above=box.top-top-8,below=bottom-box.bottom-8
      if(box.bottom<top||box.top>bottom){setOpen(false);return}
      const up=below<actions.length*40+12&&above>below
      setPosition({position:modal?'absolute':'fixed',width,left:Math.max(left,Math.min(box.right-width,right-width))-originX,
        maxHeight:Math.min(320,up?above:below),...(up?{bottom:bottom+8-box.top+8}:{top:box.bottom+8-originY})})
    }
    const outside=(event:PointerEvent)=>{if(!trigger.current?.contains(event.target as Node)&&!menu.current?.contains(event.target as Node))setOpen(false)}
    const scroll=(event:Event)=>{if(!menu.current?.contains(event.target as Node))place()}
    place();const observer=new ResizeObserver(place);if(trigger.current)observer.observe(trigger.current)
    document.addEventListener('pointerdown',outside,true);window.addEventListener('resize',place);window.addEventListener('scroll',scroll,true)
    menu.current?.querySelector<HTMLButtonElement>('button')?.focus()
    return()=>{observer.disconnect();document.removeEventListener('pointerdown',outside,true);window.removeEventListener('resize',place);window.removeEventListener('scroll',scroll,true)}
  },[open,container,actions.length])
  useEffect(()=>{if(open&&position.visibility!=='hidden')menu.current?.querySelector<HTMLButtonElement>('button')?.focus()},[open,position.visibility])
  function key(event:KeyboardEvent){
    if(event.key==='Escape'&&open){event.preventDefault();event.stopPropagation();close(true)}
    else if(event.key==='Tab')close()
    else if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
      event.preventDefault();if(!open){setOpen(true);return}
      const items=Array.from(menu.current?.querySelectorAll<HTMLButtonElement>('button')||[]),at=items.indexOf(document.activeElement as HTMLButtonElement)
      items[event.key==='Home'?0:event.key==='End'?items.length-1:(at+(event.key==='ArrowDown'?1:items.length-1))%items.length]?.focus()
    }
  }
  return <><button type="button" ref={trigger} className="project-options-button nova-dismiss-button" data-project-menu={folder.path}
    aria-haspopup="menu" aria-expanded={open} aria-controls={open?id:undefined} aria-label={`${t('projectOptions')}: ${folder.name}`} disabled={disabled}
    onClick={()=>setOpen(value=>!value)} onKeyDown={key}>
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/></svg>
  </button>{open&&container&&createPortal(<div id={id} ref={menu} className="project-context-menu nova-project-folder-menu nova-floating-panel" role="menu" aria-label={`${t('projectOptions')}: ${folder.name}`} style={position} onKeyDown={key}
    onBlur={event=>{if(!menu.current?.contains(event.relatedTarget as Node)&&event.relatedTarget!==trigger.current)close()}}>
    {actions.map(action=><button type="button" role="menuitem" key={action} data-project-action={action}
      onClick={()=>{close(true);void onAction(action,folder.path)}}>{t(action==='change'?'projectChange':action==='remove'?'projectRemove':'projectOpen')}</button>)}
  </div>,container)}</>
}
