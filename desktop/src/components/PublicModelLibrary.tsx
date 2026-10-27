import {useEffect,useRef,useState} from 'react'
import {useI18n} from '../i18n'
import {PublicModelLibrary,type LibraryFilters,type VariantResult} from '../public_model_library'
import {ModelActions,ModelRow,type CatalogModel} from './ModelPicker'
import {SettingsSelect} from './SettingsSelect'
import {installedModelName,installedVariants,modelContext} from '../model_catalog_presentation'

type Props={library:PublicModelLibrary;query:string;current:string;embeddingCurrent?:string;installed?:string[];
  locked:boolean;mutationLocked:boolean;pulling:string|null;deleting:string|null;
  onPull:(name:string)=>void;onSelect:(name:string)=>void;onSelectEmbedding?:(name:string)=>void;onDelete:(name:string)=>void}
export function PublicLibraryView({library,query,...props}:Props){
  const {t,locale}=useI18n(),[state,setState]=useState(library.state),[expanded,setExpanded]=useState<string|null>(null)
  const list=useRef<HTMLDivElement>(null),sentinel=useRef<HTMLDivElement>(null)
  useEffect(()=>library.subscribe(setState),[library])
  useEffect(()=>{const timer=setTimeout(()=>{library.search({...library.state.filters,query})},300);return()=>clearTimeout(timer)},[library,query])
  useEffect(()=>{
    const observer=new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting))library.more()},
      {root:list.current,rootMargin:'100px'})
    if(sentinel.current)observer.observe(sentinel.current)
    return()=>observer.disconnect()
  },[library,state.nextPage,state.loading,state.error])
  const change=(patch:Partial<LibraryFilters>)=>{setExpanded(null);library.search({...state.filters,query,...patch});if(list.current)list.current.scrollTop=0}
  const date=state.syncedAt?new Intl.DateTimeFormat(locale,{dateStyle:'medium',timeStyle:'short'}).format(state.syncedAt*1000):''
  return <>
    <div className="picker-library-filters">
      <SettingsSelect aria-label={t('libraryType')} value={state.filters.kind} onChange={kind=>change({kind:kind as LibraryFilters['kind']})}
        options={[{value:'all',label:t('libraryAnyType')},{value:'llm',label:t('libraryLLM')},{value:'embedding',label:t('libraryEmbedding')}]}/>
      <SettingsSelect aria-label={t('libraryCapability')} value={state.filters.capability} onChange={capability=>change({capability:capability as LibraryFilters['capability']})}
        options={[{value:'',label:t('libraryAnyCapability')},{value:'tools',label:t('libraryTools')},{value:'vision',label:t('libraryVision')},{value:'thinking',label:t('libraryThinking')}]}/>
      <label><input type="checkbox" checked={state.filters.local} onChange={event=>change({local:event.target.checked})}/>{t('libraryLocal')}</label>
    </div>
    <div className="picker-library-state" aria-live="polite">
      <span>{state.offline?t('libraryOffline'):date?`${t('librarySynced')}: ${date}`:t('libraryUnknownDate')}</span>
      {state.offline&&date&&<span>{date}</span>}{state.stale&&<span>{t('libraryStale')}</span>}
    </div>
    <div ref={list} className="picker-list picker-public-library" aria-busy={state.loading}>
      {state.error&&<div className="picker-load-error" role="alert"><p>{t('libraryError')}</p>
        <button className="picker-action use" onClick={()=>library.retry()}>{t('libraryRetry')}</button></div>}
      {state.models.map(model=><div className="picker-family" key={model.name}>
        <ModelRow name={model.name} display={model.display} description={model.description} selected={installedVariants(model.name,props.installed).includes(model.kind==='embedding'?props.embeddingCurrent||'':props.current)}
          metadata={<><span className="picker-model-params">{t(model.kind==='embedding'?'libraryEmbedding':'libraryLLM')}</span>
            {model.cloud_only&&<span className="picker-model-params">{t('modelCloudOnly')}</span>}</>}
          extras={<>{model.tags.filter(tag=>['tools','vision','thinking'].includes(tag)).map(tag=><span className="picker-model-strength" key={tag}>
            {t(tag==='tools'?'libraryTools':tag==='vision'?'libraryVision':'libraryThinking')}</span>)}</>}
          actions={<button className="picker-action use" aria-expanded={expanded===model.name} onClick={()=>{
            setExpanded(expanded===model.name?null:model.name);if(expanded!==model.name)library.variants(model.name)
          }}>{t(expanded===model.name?'libraryHideVariants':'libraryVariants')}</button>}/>
        {expanded===model.name&&<FamilyVariants model={model} result={state.variants.get(model.name)}
          retry={()=>library.variants(model.name,true)} local={state.filters.local} {...props}/>}
      </div>)}
      {!state.loading&&!state.error&&state.page>0&&state.models.length===0&&<div className="picker-empty" role="status">{t('noModelMatches')}</div>}
      <div className="picker-library-more" ref={sentinel}>
        {state.loading||state.page===0&&!state.error?<span role="status">{t('libraryLoading')}</span>
          :state.nextPage&&!state.error?<button className="picker-action use" onClick={()=>library.more()}>{t('libraryMore')}</button>
          :state.models.length>0&&!state.error?<span>{t('libraryComplete')}</span>:null}
      </div>
    </div>
    <footer className="picker-footer"><span>{state.models.length} {t('modelFilterCount')}</span><span>{t('libraryNotice')}</span></footer>
  </>
}
function FamilyVariants({model,result,retry,local,...props}:Omit<Props,'library'|'query'> & {model:CatalogModel;result?:VariantResult;retry:()=>void;local:boolean}){
  const {t}=useI18n(),[chosen,setChosen]=useState('')
  const variants=result?.variants.filter(v=>!local||!v.cloud_only)||[]
  const selected=variants.find(v=>v.name===chosen)||variants.find(v=>v.name===model.name+':latest')||variants[0]
  const embedding=model.kind==='embedding'
  return <div className="picker-family-variants">
    {result?.loading&&<p role="status">{t('libraryVariantLoading')}</p>}
    {result?.error&&<div className="picker-load-error" role="alert"><p>{t('libraryVariantError')}</p><button className="picker-action use" onClick={retry}>{t('libraryRetry')}</button></div>}
    {selected&&<>
      <div className="picker-variant-choice"><label>{t('libraryVariant')}
        <SettingsSelect aria-label={`${t('libraryVariant')} ${model.name}`} value={selected.name} onChange={setChosen}
          options={variants.map(v=>({value:v.name,label:v.name.slice(model.name.length+1),description:v.size_label||(v.cloud_only?t('modelCloudOnly'):undefined)}))}/></label>
        <div className="picker-variant-metadata">
          {selected.size_label&&<span title={t('libraryExactSize')}>{selected.size_label}</span>}
          {selected.context_length>0&&<span>{modelContext(selected.context_length)} ctx</span>}
        </div>
        <ModelActions name={selected.name} current={embedding?props.embeddingCurrent||'':props.current} exact={installedModelName(selected.name,props.installed)}
          ambiguous={false} cloudOnly={model.cloud_only===true||selected.cloud_only} disabled={props.locked||embedding&&!props.onSelectEmbedding}
          mutationLocked={props.mutationLocked} pulling={props.pulling===selected.name} deleting={props.deleting===selected.name} canDelete
          onSelect={embedding?props.onSelectEmbedding||(()=>{}):props.onSelect} onDelete={props.onDelete} onPull={props.onPull} onViewInstalled={()=>{}}/>
      </div>
      {result?.offline&&<p className="picker-variant-cache">{t('libraryOffline')}{result.stale?' · '+t('libraryStale'):''}</p>}
    </>}
  </div>
}
