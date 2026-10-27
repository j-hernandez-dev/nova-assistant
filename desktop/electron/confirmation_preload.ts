import { ipcRenderer } from 'electron'
import { applySurfacePresentation } from '../shared/surface_presentation'
const copy = {
  es: {cancel:'Cancelar',remove:'Quitar proyecto',clear:'Eliminar chat',all:'Eliminar todos los chats',
    removeMessage:(name:string)=>`Se eliminará el chat de «${name}» y se retirará el proyecto de Nova. Sus copias adjuntas pasarán a «No vinculado» en Almacenamiento. La carpeta original y sus archivos permanecerán en el equipo.`,
    clearMessage:(name:string)=>`Se eliminará el chat de «${name}». El proyecto seguirá disponible en Nova.\n\nEsta acción no se puede deshacer.`,
    allMessage:'Se eliminarán los chats de todos los proyectos de este perfil. Esta acción no se puede deshacer.'},
  en: {cancel:'Cancel',remove:'Remove project',clear:'Delete chat',all:'Delete all chats',
    removeMessage:(name:string)=>`The chat for “${name}” will be deleted and the project removed from Nova. Its stored attachments will move to “Unlinked” in Storage. The original folder and its files will remain on your computer.`,
    clearMessage:(name:string)=>`The chat for “${name}” will be deleted. The project will remain available in Nova.\n\nThis cannot be undone.`,
    allMessage:'The chats of all projects in this profile will be deleted. This cannot be undone.'},
}
const memoryCopy={
  es:{'memory-delete-records':{title:'Eliminar recuerdos',button:'Eliminar',message:'Se eliminarán definitivamente los recuerdos seleccionados y sus índices de recuperación. Nova dejará de utilizarlos como recuerdos. Las conversaciones y los archivos de copia de seguridad se conservarán.\n\nEsta acción no se puede deshacer. ¿Quieres continuar?'},
    'memory-classify-sensitive':{title:'Marcar contenido sensible',button:'Marcar',message:'El recuerdo se tratará como contenido sensible al guardar los cambios. Se ocultará de las consultas normales y su uso por el modelo dependerá del permiso del proyecto. Su exportación requerirá una elección explícita.\n\nEsto no concede acceso a ningún proyecto. ¿Quieres marcarlo?'},
    'memory-classify-normal':{title:'Retirar la marca de contenido sensible',button:'Retirar marca',message:'Al guardar, el recuerdo se tratará como contenido no sensible. Podrá aparecer en consultas y exportaciones normales y recuperarse para el modelo sin el permiso de contenido sensible. Si pertenece al perfil personal, podrá recuperarse desde cualquier proyecto.\n\nLos datos detectados como sensibles seguirán protegidos. ¿Quieres continuar?'},
    'memory-reveal-sensitive':{title:'Mostrar contenido sensible',button:'Mostrar',message:'Se mostrará el contenido sensible de los recuerdos solicitados en esta ventana.\n\nEsta confirmación sólo permite consultarlos. No cambia los permisos de los proyectos ni autoriza su uso por el modelo. ¿Quieres continuar?'},
    'memory-write-sensitive':{title:'Guardar contenido sensible',button:'Guardar',message:'Se guardará o actualizará el contenido sensible de este recuerdo en el ámbito seleccionado.\n\nSu uso por Nova dependerá de los permisos del proyecto en la configuración de Memoria. ¿Quieres continuar?'},
    'memory-import':{title:'Importar recuerdos',button:'Continuar',message:'Se reemplazarán los recuerdos de este perfil y de todos sus proyectos por los del archivo que selecciones, incluido el contenido sensible que contenga. Las propuestas pendientes actuales se descartarán. Los permisos de los proyectos se mantendrán.\n\nEsta acción no se puede deshacer. Exporta primero tus recuerdos si quieres conservar una copia.'},
    'memory-export-sensitive':{title:'Exportar contenido sensible',button:'Continuar',message:'El archivo incluirá el contenido sensible de los recuerdos de este perfil y de todos sus proyectos. Cualquier persona con acceso al archivo podrá leerlo.\n\n¿Quieres continuar con la exportación?'},
    'memory-sensitive-access':{title:'Permitir contenido sensible',button:'Permitir',message:'Nova podrá utilizar como contexto para el modelo local los recuerdos sensibles de este proyecto y del perfil personal, cuando sean pertinentes. La recuperación semántica también podrá procesarlos con el modelo de embeddings local.\n\nEl permiso no da acceso a recuerdos exclusivos de otros proyectos. Puedes desactivarlo desde Memoria.'}},
  en:{'memory-delete-records':{title:'Delete memories',button:'Delete',message:'The selected memories and their retrieval indexes will be permanently deleted. Nova will stop using them as memories. Conversations and backup files will be kept.\n\nThis cannot be undone. Do you want to continue?'},
    'memory-classify-sensitive':{title:'Mark sensitive content',button:'Mark',message:'When you save, this memory will be treated as sensitive. It will be hidden from normal queries, and model use will depend on the project permission. Exporting it will require an explicit choice.\n\nThis does not grant access to any project. Do you want to mark it?'},
    'memory-classify-normal':{title:'Remove sensitive content marking',button:'Remove marking',message:'When you save, this memory will be treated as non-sensitive. It may appear in normal queries and exports and be retrieved for the model without sensitive content permission. Personal profile memories may be retrieved from any project.\n\nContent detected as sensitive will remain protected. Do you want to continue?'},
    'memory-reveal-sensitive':{title:'Show sensitive content',button:'Show',message:'Sensitive content from the requested memories will be shown in this window.\n\nThis confirmation only allows viewing them. It does not change project permissions or authorize their use by the model. Do you want to continue?'},
    'memory-write-sensitive':{title:'Save sensitive content',button:'Save',message:'Sensitive content in this memory will be saved or updated in the selected scope.\n\nIts use by Nova will depend on the project permissions in Memory settings. Do you want to continue?'},
    'memory-import':{title:'Import memories',button:'Continue',message:'The memories in this profile and all its projects will be replaced by the selected file, including any sensitive content it contains. Current pending proposals will be discarded. Project permissions will be preserved.\n\nThis cannot be undone. Export your memories first if you want to keep a copy.'},
    'memory-export-sensitive':{title:'Export sensitive content',button:'Continue',message:'The file will include sensitive memory content from this profile and all its projects. Anyone with access to the file will be able to read it.\n\nDo you want to continue with the export?'},
    'memory-sensitive-access':{title:'Allow sensitive content',button:'Allow',message:'Nova will be able to use sensitive memories from this project and your personal profile as context for the local model when relevant. Semantic retrieval may also process them with the local embedding model.\n\nThis permission does not allow access to memories exclusive to other projects. You can turn it off in Memory.'}},
}
const storageNames:Record<string,Record<string,string>>={
  es:{chats:'Proyectos y chats',attachments:'Archivos adjuntos',memories:'Recuerdos',navigation:'Navegación',configuration:'Configuración',audit:'Auditoría',catalog:'Catálogo de modelos',caches:'Cachés'},
  en:{chats:'Projects and chats',attachments:'Attachments',memories:'Memories',navigation:'Browsing',configuration:'Configuration',audit:'Audit',catalog:'Model catalog',caches:'Caches'},
}
function storageText(language:'es'|'en',binding:any) {
  const es=language==='es',name=storageNames[language][binding.folderId]||''
  if(binding.kind==='storage-restart')return {title:es?'Reiniciar Nova':'Restart Nova',button:es?'Reiniciar':'Restart',message:es?'Nova se cerrará y volverá a abrir para completar la limpieza de almacenamiento. Las operaciones pendientes de eliminación se aplicarán antes de abrir las bases de datos.':'Nova will close and reopen to finish storage cleanup. Pending deletions will run before databases are opened.'}
  if(binding.kind==='sources-delete-files')return {title:es?'Eliminar fuentes':'Delete sources',button:es?'Eliminar':'Delete',message:es?`Se eliminarán definitivamente ${binding.fileCount} fuentes guardadas en Nova, incluidas sus copias, versiones y datos derivados. Los archivos originales y las páginas web se conservarán. Esta acción no se puede deshacer.`:`${binding.fileCount} sources stored in Nova, including their copies, versions and derived data, will be permanently deleted. Original files and web pages will be preserved. This cannot be undone.`}
  if(binding.kind==='storage-delete-files')return {title:es?'Eliminar archivos':'Delete files',button:es?'Eliminar':'Delete',message:es?`Se eliminarán definitivamente ${binding.fileCount} copias guardadas en Nova, sus versiones y los datos derivados correspondientes. Los archivos originales del equipo se conservarán. Esta acción no se puede deshacer.`:`${binding.fileCount} copies stored in Nova, their versions and associated derived data will be permanently deleted. Original files on your computer will be preserved. This cannot be undone.`}
  if(binding.kind!=='storage-delete-folder')return null
  const details:Record<string,string>=es?{
    chats:'Se eliminarán los chats guardados y sus registros de sesiones de todos los proyectos.',attachments:'Se eliminarán las copias adjuntas guardadas en Nova, incluidas las que no están vinculadas a un proyecto. Los originales del equipo se conservarán.',
    memories:'Se eliminarán todos los recuerdos, propuestas pendientes e índices de memoria de este perfil.',navigation:'Se eliminarán las descargas administradas por Nova y los perfiles temporales de navegación.',configuration:'Se restablecerán los ajustes y se eliminarán las estadísticas de uso. Se conservará la lista de proyectos.',audit:'Se eliminará el historial de auditoría de operaciones y permisos.',catalog:'Se eliminará el catálogo descargado. Nova podrá sincronizarlo de nuevo.',caches:'Se eliminarán los datos regenerables de caché. Nova volverá a crearlos cuando los necesite.',
  }:{chats:'Saved chats and session logs for all projects will be deleted.',attachments:'Attachments stored in Nova, including unlinked copies, will be deleted. Original files on your computer will be preserved.',memories:'All memories, pending proposals and memory indexes in this profile will be deleted.',navigation:'Nova-managed downloads and temporary browsing profiles will be deleted.',configuration:'Settings will be reset and usage statistics deleted. The list of projects will be retained.',audit:'Operation and permission audit history will be deleted.',catalog:'The downloaded catalog will be deleted. Nova can synchronize it again.',caches:'Regenerable cache data will be deleted. Nova will recreate it when needed.'}
  return {title:es?`Eliminar ${name.toLowerCase()}`:`Delete ${name.toLowerCase()}`,button:es?'Eliminar':'Delete',message:(details[binding.folderId]||'')+'\n\n'+(binding.restartRequired?(es?'La limpieza se completará al reiniciar Nova.':'Cleanup will finish when Nova restarts.'):(es?'Esta acción no se puede deshacer.':'This cannot be undone.'))}
}
window.addEventListener('DOMContentLoaded',async()=>{
  try{
    const binding=await ipcRenderer.invoke('confirmation-surface-ready')
    if(!binding?.accepted)return
    applySurfacePresentation(document,binding.presentation)
    ipcRenderer.on('confirmation-surface-appearance',(_event,value)=>applySurfacePresentation(document,value))
    const element=(id:string)=>document.getElementById(id)!
    const cancel=element('cancel') as HTMLButtonElement,confirm=element('confirm') as HTMLButtonElement
    const localize=(locale:unknown)=>{
      const language=locale==='en'?'en':'es',labels=copy[language]
      document.documentElement.lang=language
      const title=binding.kind==='remove-project'?labels.remove:binding.kind==='clear-chat'?labels.clear:labels.all
      const memory=memoryCopy[language][binding.kind as keyof typeof memoryCopy.es]
      const storage=storageText(language,binding)
      element('heading').textContent=storage?.title||memory?.title||title;confirm.textContent=storage?.button||memory?.button||title;cancel.textContent=labels.cancel
      element('message').textContent=storage?.message||memory?.message||(binding.kind==='remove-project'?labels.removeMessage(binding.projectName):binding.kind==='clear-chat'?labels.clearMessage(binding.projectName):labels.allMessage)
      element('path').textContent=binding.path
      const option=element('delete-files-option');option.hidden=binding.kind!=='remove-project';option.style.display=binding.kind==='remove-project'?'flex':'none'
      element('delete-files-label').textContent=language==='es'?'Eliminar también las copias adjuntas de Nova de forma permanente':'Also permanently delete the attachments stored in Nova'
    }
    localize(binding.locale);ipcRenderer.on('confirmation-surface-locale',(_event,locale)=>localize(locale))
    let decided=false
    const decide=(confirmed:boolean,event:Event)=>{
      if(!event.isTrusted||decided)return
      decided=true;cancel.disabled=confirm.disabled=true
      void ipcRenderer.invoke('confirmation-surface-decision',{nonce:binding.nonce,confirmed,...(binding.kind==='remove-project'?{deleteAssociatedFiles:(element('delete-files') as HTMLInputElement).checked}:{})}).catch(()=>{})
    }
    cancel.addEventListener('click',event=>decide(false,event));confirm.addEventListener('click',event=>decide(true,event))
    document.addEventListener('keydown',event=>{
      if(event.key==='Escape'){event.preventDefault();decide(false,event)}
      if(event.key==='Tab'){
        event.preventDefault()
        const controls:HTMLElement[]=binding.kind==='remove-project'?[element('delete-files'),cancel,confirm]:[cancel,confirm]
        const index=controls.indexOf(document.activeElement as HTMLElement),step=event.shiftKey?-1:1
        controls[(index+step+controls.length)%controls.length].focus()
      }
    })
    cancel.disabled=confirm.disabled=false;cancel.focus()
  }catch{/* An unavailable host keeps the confirmation disabled. */}
},{once:true})
