import type {SourceFile} from '../../shared/storage'
import {useI18n} from '../i18n'
import {sourceIcon} from '../source_presentation'
import {NovaIcon} from './NovaIcon'
import '../prompt_sources.css'
export function PromptSources({sources,disabled=false,onRemove}:{sources:SourceFile[];disabled?:boolean;onRemove:(id:string)=>void}){
  const {t}=useI18n()
  if(!sources.length)return null
  return <ul className="nova-prompt-sources" aria-label={t('promptSources')}>
    {sources.map(source=><li className="nova-prompt-source" key={source.id} data-source-id={source.id}>
      <NovaIcon name={sourceIcon(source)} size={17}/><span title={source.name}>{source.name}</span>
      <button type="button" className="nova-dismiss-button" disabled={disabled} aria-label={`${t('promptSourceRemove')}: ${source.name}`} title={t('promptSourceRemove')} onClick={()=>onRemove(source.id)}><NovaIcon name="close" size={16}/></button>
    </li>)}
  </ul>
}
