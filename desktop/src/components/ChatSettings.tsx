import { useEffect, useRef, useState } from 'react'
import { useI18n } from '../i18n'

export type ProjectChat = {path:string;name:string;active:boolean;hasHistory:boolean;messageCount:number}
type Result = {success:boolean;canceled?:boolean}
export function ChatSettings({disabled,chats,loading,error,onClear,onOpen}: {
  disabled:boolean;chats:ProjectChat[];loading:boolean;error:boolean;
  onClear:(path?:string)=>Promise<Result>;onOpen:(path:string)=>void
}) {
  const {t}=useI18n()
  const [pending,setPending]=useState<string|null>(null)
  const [notice,setNotice]=useState<'chatDeleted'|'chatCleared'|'chatClearFailed'|null>(null)
  const locked=useRef(false),alive=useRef(true)
  useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[])
  const clear=async(path?:string)=>{
    if(disabled||locked.current)return
    locked.current=true;setPending(path||'*');setNotice(null)
    let result:Result={success:false}
    try{result=await onClear(path)}catch{/* A host failure remains in Chats. */}
    locked.current=false
    if(alive.current){setPending(null);if(!result.canceled)setNotice(result.success?(path?'chatDeleted':'chatCleared'):'chatClearFailed')}
  }
  const busy=disabled||pending!==null
  return <div className="nova-chat-settings" aria-busy={pending!==null}>
    <section className="nova-settings-card">
      <h3>{t('chatListTitle')}</h3>
      {loading&&<p className="settings-hint" role="status">{t('chatLoading')}</p>}
      {error&&<p className="nova-settings-error" role="alert">{t('chatLoadFailed')}</p>}
      <div className="nova-project-chats">{chats.map(chat=><div className="nova-project-chat" key={chat.path}>
        <button type="button" className="nova-chat-open" disabled={busy} onClick={()=>onOpen(chat.path)}
          aria-label={`${t('openProjectChat')}: ${chat.name}`} title={chat.path}>
          <strong>{chat.name}</strong><span>{chat.hasHistory?`${chat.messageCount} ${t('chatMessages')}`:t('chatEmpty')}</span>
        </button>
        <button type="button" className="nova-settings-danger" disabled={busy||loading||error||!chat.hasHistory}
          aria-label={`${t('chatDelete')}: ${chat.name}`} onClick={()=>void clear(chat.path)}>{t(pending===chat.path?'chatClearing':'chatDelete')}</button>
      </div>)}</div>
    </section>
    <section className="nova-settings-card"><h3>{t('chatClearHistory')}</h3><p className="settings-hint">{t('chatClearHint')}</p>
      <button type="button" className="nova-settings-danger" disabled={busy||loading||error}
        onClick={()=>void clear()}>{t(pending==='*'?'chatClearing':'chatClearHistory')}</button>
    </section>
    {disabled&&<p className="settings-hint">{t('chatClearBusy')}</p>}
    {notice&&<p className={notice==='chatClearFailed'?'nova-settings-error':'nova-settings-success'} role={notice==='chatClearFailed'?'alert':'status'}>{t(notice)}</p>}
  </div>
}
