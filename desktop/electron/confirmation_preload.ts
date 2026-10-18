import { ipcRenderer } from 'electron'
const copy = {
  es: {cancel:'Cancelar',remove:'Quitar proyecto',clear:'Borrar chat',all:'Borrar todos los chats',
    removeMessage:(name:string)=>`Se eliminará el chat de «${name}». La carpeta se retirará de los accesos de Nova y sus archivos permanecerán en el equipo.\n\nEsta acción no se puede deshacer.`,
    clearMessage:(name:string)=>`Se eliminará el chat de «${name}». El proyecto seguirá disponible en Nova.\n\nEsta acción no se puede deshacer.`,
    allMessage:'Se eliminarán los chats de todos los proyectos de este perfil. Esta acción no se puede deshacer.'},
  en: {cancel:'Cancel',remove:'Remove project',clear:'Delete chat',all:'Delete all chats',
    removeMessage:(name:string)=>`The chat for “${name}” will be deleted. The folder will be removed from Nova’s shortcuts and its files will remain on your computer.\n\nThis cannot be undone.`,
    clearMessage:(name:string)=>`The chat for “${name}” will be deleted. The project will remain available in Nova.\n\nThis cannot be undone.`,
    allMessage:'The chats of all projects in this profile will be deleted. This cannot be undone.'},
}
window.addEventListener('DOMContentLoaded',async()=>{
  try{
    const binding=await ipcRenderer.invoke('confirmation-surface-ready')
    if(!binding?.accepted)return
    const element=(id:string)=>document.getElementById(id)!
    const cancel=element('cancel') as HTMLButtonElement,confirm=element('confirm') as HTMLButtonElement
    const localize=(locale:unknown)=>{
      const language=locale==='en'?'en':'es',labels=copy[language]
      document.documentElement.lang=language
      const title=binding.kind==='remove-project'?labels.remove:binding.kind==='clear-chat'?labels.clear:labels.all
      element('heading').textContent=title;confirm.textContent=title;cancel.textContent=labels.cancel
      element('message').textContent=binding.kind==='remove-project'?labels.removeMessage(binding.projectName):binding.kind==='clear-chat'?labels.clearMessage(binding.projectName):labels.allMessage
      element('path').textContent=binding.path
    }
    localize(binding.locale);ipcRenderer.on('confirmation-surface-locale',(_event,locale)=>localize(locale))
    let decided=false
    const decide=(confirmed:boolean,event:Event)=>{
      if(!event.isTrusted||decided)return
      decided=true;cancel.disabled=confirm.disabled=true
      void ipcRenderer.invoke('confirmation-surface-decision',{nonce:binding.nonce,confirmed}).catch(()=>{})
    }
    cancel.addEventListener('click',event=>decide(false,event));confirm.addEventListener('click',event=>decide(true,event))
    document.addEventListener('keydown',event=>{
      if(event.key==='Escape'){event.preventDefault();decide(false,event)}
      if(event.key==='Tab'){event.preventDefault();(document.activeElement===cancel?confirm:cancel).focus()}
    })
    cancel.disabled=confirm.disabled=false;cancel.focus()
  }catch{/* An unavailable host keeps the confirmation disabled. */}
},{once:true})
