import {useEffect,useId,useLayoutEffect,useRef,useState,type CSSProperties,type KeyboardEvent} from 'react'
import {createPortal} from 'react-dom'
import {NovaIcon} from './NovaIcon'

type Option = {value:string;label:string;disabled?:boolean;description?:string}
type Props = {id?:string;value:string;options:Option[];disabled?:boolean;onChange:(value:string)=>void;'aria-label'?:string;'aria-describedby'?:string;'data-settings-select'?:string}
/** Keeps focus on the trigger; the list lives inside the modal's active backdrop. */
export function SettingsSelect({id:givenId,value,options,disabled=false,onChange,...aria}:Props){
  const generated=useId(),id=givenId||generated,listId=id+'-options'
  const trigger=useRef<HTMLButtonElement>(null),menu=useRef<HTMLDivElement>(null),typed=useRef({text:'',at:0})
  const [open,setOpen]=useState(false),[active,setActive]=useState(0),[position,setPosition]=useState<CSSProperties>({visibility:'hidden'})
  const locked=disabled||!options.some(o=>!o.disabled)
  const optionsKey=options.map(o=>o.value+':'+!!o.disabled).join('|')
  const container=typeof document==='undefined'?null:trigger.current?.closest('.nova-modal-backdrop')||document.body
  useEffect(()=>{setOpen(false)},[locked,value,optionsKey])
  useLayoutEffect(()=>{
    if(!open)return
    const place=()=>{
      const box=trigger.current?.getBoundingClientRect();if(!box)return
      const bounds=container?.getBoundingClientRect(),gap=8,top=(bounds?.top||0)+gap,bottom=(bounds?.bottom||innerHeight)-gap
      const left=(bounds?.left||0)+gap,right=(bounds?.right||innerWidth)-gap
      if(box.bottom<top||box.top>bottom){setOpen(false);return}
      const above=Math.max(0,box.top-top-gap),below=Math.max(0,bottom-box.bottom-gap)
      const up=below<Math.min(280,options.length*40+12)&&above>below
      const width=Math.min(Math.max(200,box.width),Math.max(0,right-left))
      // The backdrop is the containing block (its blur also contains fixed children).
      // Use its local coordinates so the popup stays anchored below the titlebar.
      setPosition({position:'absolute',left:Math.max(left,Math.min(box.right-width,right-width))-(bounds?.left||0),width,maxHeight:Math.min(320,up?above:below),
        ...(up?{bottom:(bounds?.bottom||innerHeight)-box.top+gap}:{top:box.bottom-(bounds?.top||0)+gap})})
    }
    const dismiss=(event:PointerEvent)=>{if(!trigger.current?.contains(event.target as Node)&&!menu.current?.contains(event.target as Node))setOpen(false)}
    const scroll=(event:Event)=>{if(!menu.current?.contains(event.target as Node))place()}
    const blur=()=>setOpen(false)
    place();const observer=new ResizeObserver(place);if(trigger.current)observer.observe(trigger.current)
    document.addEventListener('pointerdown',dismiss,true);window.addEventListener('resize',place);window.addEventListener('scroll',scroll,true);window.addEventListener('blur',blur)
    return()=>{observer.disconnect();document.removeEventListener('pointerdown',dismiss,true);window.removeEventListener('resize',place);window.removeEventListener('scroll',scroll,true);window.removeEventListener('blur',blur)}
  },[open,container,options.length])
  useEffect(()=>{if(open)menu.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({block:'nearest'})},[open,active])
  function show(){if(locked)return;typed.current={text:'',at:0};setActive(Math.max(0,options.findIndex(o=>o.value===value&&!o.disabled)));setOpen(true)}
  function choose(index:number){const option=options[index];if(locked||!option||option.disabled)return;setOpen(false);trigger.current?.focus();if(option.value!==value)onChange(option.value)}
  function key(event:KeyboardEvent<HTMLButtonElement>){
    if(locked)return
    if(event.key==='Escape'&&open){event.preventDefault();event.stopPropagation();setOpen(false);return}
    if(event.key==='Tab'){setOpen(false);return}
    if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
      event.preventDefault()
      if(!open){show();return}
      const available=options.map((o,index)=>o.disabled?-1:index).filter(index=>index>=0),at=available.indexOf(active)
      setActive(event.key==='Home'?available[0]:event.key==='End'?available[available.length-1]:available[(at+(event.key==='ArrowDown'?1:available.length-1))%available.length])
    }else if(event.key==='Enter'||event.key===' '){event.preventDefault();if(open)choose(active);else show()}
    else if(event.key.length===1&&!event.ctrlKey&&!event.metaKey&&!event.altKey){
      event.preventDefault();const now=Date.now(),text=(now-typed.current.at<700?typed.current.text:'')+event.key.toLocaleLowerCase()
      typed.current={text,at:now};const index=options.findIndex(o=>!o.disabled&&o.label.toLocaleLowerCase().startsWith(text))
      if(!open)show();typed.current={text,at:now};if(index>=0)setActive(index)
    }
  }
  return <span className="nova-settings-select">
    <button {...aria} id={id} ref={trigger} type="button" role="combobox" value={value} disabled={locked}
      aria-haspopup="listbox" aria-expanded={open} aria-controls={open?listId:undefined} aria-activedescendant={open?`${listId}-${active}`:undefined}
      onKeyDown={key} onBlur={()=>setOpen(false)} onClick={()=>open?setOpen(false):show()}>
      <span>{options.find(o=>o.value===value)?.label||value}</span><NovaIcon name="chevron" size={16}/>
    </button>
    {open&&container&&createPortal(<div id={listId} ref={menu} role="listbox" aria-label={aria['aria-label']}
      className="nova-model-listbox nova-settings-listbox nova-floating-panel" style={position} onMouseDown={event=>event.preventDefault()}>
      {options.map((option,index)=><div id={`${listId}-${index}`} key={option.value} role="option" aria-selected={option.value===value}
        aria-disabled={option.disabled||undefined} data-index={index} data-value={option.value}
        className={`nova-model-option${index===active?' active':''}${option.value===value?' selected':''}`}
        onPointerMove={()=>{if(!option.disabled)setActive(index)}} onClick={()=>choose(index)}>
        <span>{option.label}{option.description&&<small>{option.description}</small>}</span>{option.value===value&&<NovaIcon name="check" size={15}/>}</div>)}
    </div>,container)}
  </span>
}
