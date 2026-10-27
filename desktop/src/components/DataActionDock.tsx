import {useLayoutEffect,useRef,type ReactNode} from 'react'

/** Floating controls never consume viewport height. Only the scroll content
 * gets a trailing inset, so its final row can move clear of wrapped controls. */
export function DataActionDock({visible,className='',children}:{visible:boolean;className?:string;children:ReactNode}){
  const element=useRef<HTMLDivElement>(null)
  useLayoutEffect(()=>{
    const dock=element.current,region=dock?.parentElement
    if(!dock||!region)return
    const measure=()=>region.style.setProperty('--nova-data-dock-height',`${dock.offsetHeight}px`)
    measure()
    const observer=new ResizeObserver(measure);observer.observe(dock)
    return()=>{observer.disconnect();region.style.removeProperty('--nova-data-dock-height')}
  },[])
  return <div ref={element} className={`nova-data-actions nova-data-dock ${className}`} data-visible={visible}
    aria-hidden={!visible} inert={!visible}>{children}</div>
}
