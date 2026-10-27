import {useLayoutEffect,useRef,useState,type CSSProperties,type ReactNode,type RefObject} from 'react'
import {useI18n} from '../i18n'
import {projectPaneBounds,projectPaneWidth,readProjectPaneWidth,saveProjectPaneWidth} from '../project_pane_layout'

type Props={open:boolean;onCollapse:()=>void;toggleRef:RefObject<HTMLButtonElement|null>;children:ReactNode}
type Drag={id:number;target:HTMLDivElement;lastWidth:number;offset:number}

/** The existing drawer keeps its own content and motion; only its width changes. */
export function ProjectPane({open,onCollapse,toggleRef,children}:Props){
  const {t}=useI18n(),pane=useRef<HTMLElement>(null),drag=useRef<Drag|null>(null)
  const [preferred,setPreferred]=useState(readProjectPaneWidth)
  const [draft,setDraft]=useState<number|null>(null)
  const [sized,setSized]=useState(false),[dragging,setDragging]=useState(false)
  const [bounds,setBounds]=useState(()=>projectPaneBounds(Math.max(0,window.innerWidth-64),window.innerWidth))
  const width=projectPaneWidth(draft??preferred??(window.innerWidth<=900?260:312),bounds.minimum,bounds.maximum)
  const latest=useRef({open,onCollapse,toggleRef,bounds,width})
  latest.current={open,onCollapse,toggleRef,bounds,width}

  function release(){
    const session=drag.current
    drag.current=null
    document.documentElement.removeAttribute('data-nova-resizing-projects')
    if(session?.target.hasPointerCapture(session.id))session.target.releasePointerCapture(session.id)
  }
  function finish(commit:boolean,keepDraft=false){
    const session=drag.current
    if(!session)return
    release();setDragging(false)
    if(commit){
      const {minimum,maximum}=latest.current.bounds
      const value=projectPaneWidth(session.lastWidth,minimum,maximum)
      setPreferred(value);saveProjectPaneWidth(value)
    }
    if(!keepDraft)setDraft(null)
  }
  const finishRef=useRef(finish)
  finishRef.current=finish
  function collapse(){
    // Keep the displayed draft during the outgoing animation, while preserving
    // the last committed width for reopening with the folder button.
    finish(false,true)
    latest.current.onCollapse()
    latest.current.toggleRef.current?.focus({preventScroll:true})
  }
  function commit(value:number){
    const {minimum,maximum}=latest.current.bounds
    const next=projectPaneWidth(value,minimum,maximum)
    setSized(true);setPreferred(next);setDraft(null);saveProjectPaneWidth(next)
  }
  useLayoutEffect(()=>{
    const container=pane.current?.parentElement
    if(!container)return
    let viewer:Element|null=null
    const measure=()=>{
      const panel=container.querySelector('.viewer-pane')
      const reserve=panel&&getComputedStyle(panel).position!=='absolute'?panel.getBoundingClientRect().width:0
      const next=projectPaneBounds(container.clientWidth,window.innerWidth,reserve)
      latest.current.bounds=next
      setBounds(old=>old.maximum===next.maximum&&old.minimum===next.minimum?old:next)
    }
    const observer=new ResizeObserver(measure)
    const observe=()=>{
      if(viewer)observer.unobserve(viewer)
      viewer=container.querySelector('.viewer-pane')
      if(viewer)observer.observe(viewer)
      measure()
    }
    observer.observe(container)
    const mutations=new MutationObserver(observe)
    mutations.observe(container,{childList:true})
    observe()
    const cancel=()=>finishRef.current(false)
    const escape=(event:KeyboardEvent)=>{
      if(event.key==='Escape'&&drag.current){event.preventDefault();event.stopPropagation();cancel()}
    }
    window.addEventListener('resize',measure)
    window.addEventListener('blur',cancel)
    window.addEventListener('keydown',escape,true)
    return()=>{
      observer.disconnect();mutations.disconnect();release()
      window.removeEventListener('resize',measure);window.removeEventListener('blur',cancel);window.removeEventListener('keydown',escape,true)
    }
  },[])
  useLayoutEffect(()=>{
    if(!open)finishRef.current(false,true)
    else setDraft(null)
  },[open])

  return <aside ref={pane} id="nova-project-pane" className="explorer-pane nova-project-pane" data-resizable
    data-user-sized={sized||undefined} data-resizing={dragging||undefined} data-exiting={!open||undefined}
    inert={!open} aria-hidden={!open||undefined} aria-label={t('projects')}
    style={{'--nova-project-width':width+'px'} as CSSProperties}>
    {children}
    <div className="nova-project-resize" role="separator" aria-orientation="vertical" aria-controls="nova-project-pane"
      aria-label={t('projectPaneResize')} aria-valuemin={bounds.minimum} aria-valuemax={bounds.maximum} aria-valuenow={width}
      aria-valuetext={`${width} px`} tabIndex={open?0:-1} title={t('projectPaneResizeHint')}
      onPointerDown={event=>{
        if(!open||event.button!==0||!event.isPrimary||drag.current)return
        event.preventDefault()
        const target=event.currentTarget
        target.focus({preventScroll:true});target.setPointerCapture(event.pointerId)
        drag.current={id:event.pointerId,target,lastWidth:latest.current.width,
          offset:latest.current.width-event.clientX+(pane.current?.getBoundingClientRect().left||0)}
        setSized(true);setDragging(true)
        document.documentElement.setAttribute('data-nova-resizing-projects','true')
      }}
      onPointerMove={event=>{
        if(!drag.current||drag.current.id!==event.pointerId)return
        const edge=pane.current?.getBoundingClientRect().left
        if(edge===undefined)return
        const candidate=event.clientX-edge+drag.current.offset
        if(candidate<latest.current.bounds.collapseAt){collapse();return}
        const {minimum,maximum}=latest.current.bounds
        const value=projectPaneWidth(candidate,minimum,maximum)
        drag.current.lastWidth=value;setDraft(value)
      }}
      onPointerUp={event=>{if(drag.current?.id===event.pointerId)finish(true)}}
      onPointerCancel={event=>{if(drag.current?.id===event.pointerId)finish(false)}}
      onLostPointerCapture={event=>{if(drag.current?.id===event.pointerId)finish(false)}}
      onDoubleClick={()=>{if(!open)return;finish(false);setSized(true);setPreferred(null);setDraft(null);saveProjectPaneWidth(null)}}
      onKeyDown={event=>{
        if(!open||drag.current||event.altKey||event.ctrlKey||event.metaKey)return
        const {minimum,maximum}=latest.current.bounds
        const step=event.shiftKey?32:16
        if(!['ArrowLeft','ArrowRight','Home','End','Enter'].includes(event.key))return
        event.preventDefault();event.stopPropagation()
        if(event.key==='Enter'||event.key==='ArrowLeft'&&width<=minimum)collapse()
        else commit(event.key==='Home'?minimum:event.key==='End'?maximum:width+(event.key==='ArrowLeft'?-step:step))
      }}/>
  </aside>
}
