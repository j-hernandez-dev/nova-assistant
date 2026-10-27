const labels={es:{menu:'Menú de Nova'},en:{menu:'Nova menu'}}
type Field=HTMLInputElement|HTMLTextAreaElement|HTMLElement
type Selection={field:Field;start?:number|null;end?:number|null;direction?:'forward'|'backward'|'none'|null;range?:Range}

function textField(element:Element|null):Field|null{
  if(element instanceof HTMLTextAreaElement)return element.disabled?null:element
  if(element instanceof HTMLInputElement)return !element.disabled&&['text','search','url','tel','email','password','number'].includes(element.type)?element:null
  return element instanceof HTMLElement&&element.isContentEditable?element:null
}

/** Preload-owned titlebar wiring. No renderer-supplied actions or command names. */
export function installWindowMenu(doc:Document,openMenu:(position:{x:number;y:number})=>Promise<unknown>,readyChanged:(ready:boolean)=>void){
  let button:HTMLButtonElement|null=null,root:HTMLElement|null=null,disposed=false,scoped=false,pending=false,lastReady:boolean|undefined
  let lastSelection:Selection|null=null
  const remember=(field:Field|null=textField(doc.activeElement))=>{
    if(!field)return
    if(field instanceof HTMLInputElement||field instanceof HTMLTextAreaElement){
      lastSelection={field,start:field.selectionStart,end:field.selectionEnd,direction:field.selectionDirection}
    }else{
      const selection=doc.getSelection()
      lastSelection={field,...(selection?.rangeCount?{range:selection.getRangeAt(0).cloneRange()}:{})}
    }
  }
  const restore=()=>{
    const current=textField(doc.activeElement)
    if(current){remember();return}
    const selection=doc.getSelection()
    if(selection&&!selection.isCollapsed&&selection.rangeCount&&doc.activeElement!==button)return
    const saved=lastSelection,field=saved?.field
    if(!saved||!field?.isConnected||!field.getClientRects().length||field.closest('[inert],[aria-hidden="true"]')||!textField(field))return
    if(field instanceof HTMLInputElement||field instanceof HTMLTextAreaElement){
      // Read before focus: Chromium may move the caret when an editor regains
      // focus, and a queued selectionchange need not have updated the cache.
      const start=field.selectionStart??saved.start,end=field.selectionEnd??saved.end,direction=field.selectionDirection??saved.direction
      field.focus({preventScroll:true})
      if(typeof start==='number'&&typeof end==='number'){
        try{field.setSelectionRange(start,end,direction||undefined)}catch{/* Numeric/email inputs retain native selection behavior. */}
      }
    }else if(saved.range){
      field.focus({preventScroll:true})
      const selection=doc.getSelection();selection?.removeAllRanges();selection?.addRange(saved.range)
    }else field.focus({preventScroll:true})
  }
  const show=async()=>{
    if(!button||button.disabled||pending||disposed)return
    restore();pending=true;button.setAttribute('aria-expanded','true')
    const box=button.getBoundingClientRect()
    try{await openMenu({x:Math.round(box.left),y:Math.round(box.bottom)})}catch{/* Loading, closing or disconnected hosts simply decline the menu. */}
    finally{pending=false;if(!disposed)button?.setAttribute('aria-expanded','false')}
  }
  const preventFocus=(event:Event)=>{if(button&&!button.disabled)event.preventDefault()}
  const key=(event:KeyboardEvent)=>{if(event.key==='ArrowDown'&&!button?.disabled){event.preventDefault();void show()}}
  const clicked=()=>{void show()}
  const refresh=()=>{
    if(disposed)return
    const next=doc.getElementById('nova-window-menu') as HTMLButtonElement|null
    if(next&&next!==button){
      button=next
      button.addEventListener('pointerdown',preventFocus);button.addEventListener('mousedown',preventFocus)
      button.addEventListener('click',clicked);button.addEventListener('keydown',key)
    }
    root=doc.getElementById('root')
    // ModalHost makes the application root inert while its editor lives in a
    // portal. That is an active workspace, not a new loading screen.
    const ready=!!root?.childElementCount&&!doc.getElementById('nova-startup')
    if(button){
      button.disabled=!ready
      const label=labels[doc.documentElement.lang==='en'?'en':'es'].menu
      button.setAttribute('aria-label',label);button.title=label
      if(!ready)button.setAttribute('aria-expanded','false')
    }
    if(ready!==lastReady){lastReady=ready;readyChanged(ready)}
    if(!scoped&&button&&root&&doc.body){
      scoped=true;observer.disconnect()
      observer.observe(doc.documentElement,{attributes:true,attributeFilter:['lang','data-nova-startup']})
      observer.observe(doc.body,{childList:true})
      observer.observe(root,{childList:true,attributes:true,attributeFilter:['inert']})
    }
  }
  const observer=new MutationObserver(refresh)
  const focusChanged=(event:FocusEvent)=>remember(textField(event.target instanceof Element?event.target:null))
  const selectionChanged=()=>remember()
  const pointerChanged=(event:PointerEvent)=>{
    if(event.target instanceof Element&&!button?.contains(event.target)&&!textField(event.target))lastSelection=null
  }
  doc.addEventListener('focusin',focusChanged,true);doc.addEventListener('focusout',focusChanged,true);doc.addEventListener('selectionchange',selectionChanged)
  doc.addEventListener('pointerdown',pointerChanged,true)
  observer.observe(doc,{childList:true,subtree:true})
  refresh()
  return()=>{
    disposed=true;observer.disconnect()
    button?.removeEventListener('pointerdown',preventFocus);button?.removeEventListener('mousedown',preventFocus)
    button?.removeEventListener('click',clicked);button?.removeEventListener('keydown',key)
    doc.removeEventListener('focusin',focusChanged,true);doc.removeEventListener('focusout',focusChanged,true);doc.removeEventListener('selectionchange',selectionChanged)
    doc.removeEventListener('pointerdown',pointerChanged,true)
    readyChanged(false)
  }
}
