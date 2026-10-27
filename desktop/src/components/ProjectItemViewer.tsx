import {useEffect,useState} from 'react'
import type {SourceFile,SourcePreview} from '../../shared/storage'
import {sourceIcon} from '../source_presentation'
import type {MemoryInspection} from './MemoryRecords'
import {useI18n,type TranslationKey} from '../i18n'
import {sameProjectPath,projectErrorKey} from '../project_presentation'
import {FileContent} from './FileViewer'
import {NovaIcon} from './NovaIcon'
const kindKeys={PREFERENCE:'memorySettingsPreference',SEMANTIC_FACT:'memorySettingsFact',WORKSPACE_FACT:'memorySettingsProjectFact',EPISODE:'memorySettingsEpisode',PROCEDURE:'memorySettingsProcedure'} as const
export function MemoryItemViewer({record,onClose}:{record:MemoryInspection;onClose:()=>void}){
  const {t}=useI18n()
  return <section className="file-viewer" aria-label={t('projectMemoryPreview')}><header className="file-viewer-header"><div className="file-viewer-path project-item-viewer-title"><NovaIcon name="memories" size={17}/><span className="file-viewer-name">{t('projectMemoryPreview')}</span></div><button className="file-viewer-close nova-dismiss-button" onClick={onClose} aria-label={t('closePreview')}><NovaIcon name="close" size={16}/></button></header>
    <div className="file-viewer-content"><div className="project-memory-preview"><dl>
      <div><dt>{t('memorySettingsKind')}</dt><dd>{t(kindKeys[record.kind as keyof typeof kindKeys])}</dd></div>
      <div><dt>{t('memorySettingsScope')}</dt><dd>{t(record.scopeKind==='WORKSPACE'?'memorySettingsWorkspace':'memorySettingsGlobal')}</dd></div>
      <div><dt>{t('memoriesSensitiveContent')}</dt><dd>{t(record.sensitivityClass==='SENSITIVE'?'projectSensitiveYes':'projectSensitiveNo')}</dd></div>
    </dl><h3>{t('projectMemoryPreview')}</h3><p>{record.hidden?t('memorySettingsHidden'):record.canonicalText}</p></div></div>
  </section>
}
export function SourceItemViewer({source,rootDir,onClose}:{source:SourceFile;rootDir:string;onClose:()=>void}){
  const {t}=useI18n(),[preview,setPreview]=useState<SourcePreview|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState<TranslationKey|null>(null)
  useEffect(()=>{
    let active=true
    setPreview(null);setLoading(true);setError(null)
    const timer=setTimeout(async()=>{
      try{
        for(let attempt=0;attempt<6;attempt++){
          const result=await window.api.sourcePreview(source.id)
          if(!active)return
          if(result.success){
            if(!sameProjectPath(result.data.root,rootDir)||result.data.sourceId!==source.id)setError('projectStaleRoot')
            else setPreview(result.data)
            return
          }
          const code=result.error?.code
          if(!['STORAGE_BUSY','PROJECT_BUSY','REVISION_CONFLICT','CONFLICT_ACTIVE_OPERATION'].includes(code||'')||attempt===5){setError(projectErrorKey(code));return}
          await new Promise(resolve=>setTimeout(resolve,Math.min(80*2**attempt,400)))
          if(!active)return
        }
      }catch{if(active)setError('projectActionFailed')}
      finally{if(active)setLoading(false)}
    },0)
    return()=>{active=false;clearTimeout(timer)}
  },[source.id,rootDir])
  const reason:TranslationKey=preview?.reason==='TOO_LARGE'?'projectFileTooLarge':preview?.reason==='BINARY'?'projectSourceBinary':'projectSourceNoContent'
  return <section className="file-viewer" aria-label={t('projectPreviewTitle')}><header className="file-viewer-header"><div className="file-viewer-path project-item-viewer-title" title={source.url||source.name}><NovaIcon name={sourceIcon(source)} size={17}/><span className="file-viewer-name">{source.name}</span></div><button className="file-viewer-close nova-dismiss-button" onClick={onClose} aria-label={t('closePreview')}><NovaIcon name="close" size={16}/></button></header>
    <div className="file-viewer-content">{loading?<div className="file-viewer-status" role="status">{t('projectPreviewLoading')}</div>:error?<div className="file-viewer-status" role="alert">{t(error)}</div>:preview?.content!==null&&preview?.content!==undefined?<FileContent content={preview.content}/>:<div className="file-viewer-status" role="status">{t(reason)}</div>}</div>
  </section>
}
