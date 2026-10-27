import {useEffect,useRef,useState,type ReactNode,type DragEvent} from 'react'
import {useI18n} from '../i18n'
import {NovaIcon} from './NovaIcon'
import '../prompt_sources.css'
const fileDrag=(event:{dataTransfer:DataTransfer|null})=>Array.from(event.dataTransfer?.types||[]).includes('Files')
export function SourceDropTarget({children,disabled,onFiles,label}:{children:ReactNode;disabled:boolean;onFiles:(files:File[])=>void;label:string}){
  const {t}=useI18n(),depth=useRef(0),[dragging,setDragging]=useState(false)
  function reset(){depth.current=0;setDragging(false)}
  useEffect(()=>{if(disabled)reset()},[disabled])
  useEffect(()=>{
    // Unhandled OS file drops must never navigate the application away.
    const prevent=(event:globalThis.DragEvent)=>{if(fileDrag(event)){
      if(event.type==='dragover'&&event.dataTransfer){
        const target=event.target instanceof Element?event.target.closest('.nova-source-drop-target[data-source-drop-enabled],.sources-dropzone:not(:disabled)'):null
        event.dataTransfer.dropEffect=target?'copy':'none'
      }
      event.preventDefault()
    }}
    const escape=(event:KeyboardEvent)=>{if(event.key==='Escape')reset()}
    document.addEventListener('dragover',prevent);document.addEventListener('drop',prevent)
    window.addEventListener('dragend',reset);window.addEventListener('drop',reset);window.addEventListener('blur',reset);window.addEventListener('keydown',escape)
    return()=>{document.removeEventListener('dragover',prevent);document.removeEventListener('drop',prevent);window.removeEventListener('dragend',reset);window.removeEventListener('drop',reset);window.removeEventListener('blur',reset);window.removeEventListener('keydown',escape)}
  },[])
  const over=(event:DragEvent)=>{if(!fileDrag(event))return;event.preventDefault();event.dataTransfer.dropEffect=disabled?'none':'copy';if(!disabled)setDragging(true)}
  return <main className="chat-pane nova-source-drop-target" aria-label={label} data-source-drop-enabled={!disabled||undefined} data-source-drag={dragging&&!disabled||undefined}
    onDragEnter={event=>{if(!fileDrag(event))return;over(event);depth.current++}}
    onDragOver={over} onDragLeave={event=>{if(!fileDrag(event))return;depth.current=Math.max(0,depth.current-1);if(!depth.current)setDragging(false)}}
    onDrop={event=>{if(!fileDrag(event))return;event.preventDefault();event.stopPropagation();reset();if(!disabled&&event.dataTransfer.files.length)onFiles(Array.from(event.dataTransfer.files))}}>
    {children}
    {dragging&&!disabled&&<div className="nova-source-drop-overlay" role="status"><div><NovaIcon name="plus" size={34}/><strong>{t('promptSourcesDrop')}</strong><span>{t('promptSourcesCopy')}</span></div></div>}
  </main>
}
