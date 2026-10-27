import { useState, useRef, useEffect, useId, type ReactNode } from 'react'
import { ModalHost } from './ModalHost'
import { NovaIcon } from './NovaIcon'
import { useI18n } from '../i18n'
import type {PublicModelLibrary} from '../public_model_library'
import type {RecommendationStatus} from '../model_operations'
import {PublicLibraryView} from './PublicModelLibrary'
import { modelLibraryText } from '../model_catalog_locale'
import { catalogSections, type CatalogSection, easeRating, filterCatalog, installedModelName, installedVariants,
  modelCategoryKey, modelContext, modelErrorKey, pullPercent } from '../model_catalog_presentation'

export type CatalogModel = {
  name: string; display: string; category: string; params: string; size_gb: number
  description: string; tags: string[]; installed: boolean; context_length?: number
  release_date?: string; strengths?: string[]; ease_of_use?: number
  kind?: 'llm'|'embedding'; cloud_only?:boolean; family?:boolean; sizes?:string[]
}
export type Recommendation = {
  name: string; display: string; size_gb: number; reason: string; rank: number; installed: boolean
  family?:string;kind?:'llm'|'embedding';description?:string;tags?:string[];size_label?:string;
  context_length?:number;estimated_memory_gb?:number;gpu_fit?:boolean
}
export type SystemInfo = { ram_gb: number | null; chip: string; gpu: string; os: string; arch: string }
type Props = {
  library?:PublicModelLibrary;embeddingCurrent?:string;embeddingModels?:string[];onSelectEmbedding?:(name:string)=>void
  open?: boolean
  catalog: { categories: string[]; models: CatalogModel[] } | null; current: string
  onSelect: (model: string) => void; onPull: (model: string) => void; onDelete: (model: string) => void
  onUpdate: () => void; onClose: () => void
  pulling: string | null; pullProgress: string; updating: boolean
  recommendations: Recommendation[] | null; systemInfo: SystemInfo | null; onRequestRecommend: () => void
  selectionError?: boolean; selectionPending?: boolean; actionsDisabled?: boolean; installedModels?: string[]
  catalogLoading?: boolean; recommending?: boolean; catalogError?: string | null
  recommendError?: string | null; operationError?: string | null; operationUnconfirmed?: boolean
  recommendationStatus?:RecommendationStatus|null
  operationNotice?: {kind: 'downloaded' | 'deleted' | 'synced'; model?: string} | null
  deleting?: string | null; onRefreshCatalog?: () => void
}

export function ModelPicker({catalog, current, onSelect, onPull, onDelete, onUpdate,
  onClose, open = true, pulling, pullProgress, updating, recommendations, systemInfo, onRequestRecommend,
  selectionError = false, selectionPending = false, actionsDisabled = false, installedModels,
  catalogLoading = false, recommending = false, catalogError, recommendError,
  operationError, operationUnconfirmed = false, operationNotice, deleting = null, onRefreshCatalog,
  library,embeddingCurrent,embeddingModels,onSelectEmbedding,recommendationStatus}: Props) {
  const {t,locale} = useI18n()
  const numberFormat=new Intl.NumberFormat(locale,{maximumFractionDigits:2})
  const titleId = useId()
  const [filter, setFilter] = useState('')
  const [section, setSection] = useState<CatalogSection>('all')
  const input = useRef<HTMLInputElement>(null)
  const locked = selectionPending || actionsDisabled
  const mutationLocked = locked || !!pulling || !!deleting || operationUnconfirmed
  const installed = installedModels ? [...new Set(installedModels)] : undefined
  const percent = pullPercent(pullProgress)
  const recommended = section === 'recommend'
  const publicView = section === 'all' && !!library
  const filtered = filterCatalog(catalog?.models || [], filter, null)
    .filter(model => section !== 'installed' || !!installedModelName(model.name, installed))
  const shownCategories = [...new Set(filtered.map(model => model.category))]
  const query = filter.trim().toLocaleLowerCase()
  const suggestions = recommendations?.filter(model => !query || [model.name,model.display,model.description||'',...(model.tags||[]),modelLibraryText(model.reason,locale)]
    .some(value => value.toLocaleLowerCase().includes(query)))
  const categoryLabel = (value: string) => {const key = modelCategoryKey(value); return key ? t(key) : value}
  function selectSection(next: CatalogSection) {
    setSection(next)
    if (next === 'recommend' && recommendations === null && !recommending && !actionsDisabled) onRequestRecommend()
  }
  function showInstalled(name: string) {setSection('installed');setFilter(name);input.current?.focus()}
  function actions(name: string, canDelete = true, kind?:'llm'|'embedding') {
    const embedding=kind==='embedding'||embeddingModels?.includes(name)
    return <ModelActions name={name} current={embedding?embeddingCurrent||'':current} exact={installedModelName(name,installed)}
      ambiguous={installedVariants(name,installed).length > 1} cloudOnly={false} disabled={locked}
      mutationLocked={mutationLocked} deleting={deleting === name} pulling={pulling === name} canDelete={canDelete}
      onSelect={embedding?onSelectEmbedding||(()=>{}):onSelect} onPull={onPull} onDelete={onDelete} onViewInstalled={() => showInstalled(name)}/>
  }
  const error = recommended ? recommendError : catalogError
  return <ModalHost open={open} onClose={onClose} labelledBy={titleId} className="picker picker-wide nova-model-dialog nova-surface-dialog">
    <header className="picker-header nova-model-header nova-surface-header">
      <div className="nova-model-title"><span className="nova-settings-eyebrow">Nova</span><h1 id={titleId}>{t('modelsTitle')}</h1></div>
      <div className="picker-header-sub">
        <span className="picker-installed-count">{installed ? installed.length+' '+t('installed') : t('modelInventoryUnknown')}</span>
        <button className="picker-update-btn" disabled={updating || actionsDisabled} onClick={onUpdate} title={t('syncModels')}>
          <ModelIcon kind="sync" spin={updating}/><span>{t(updating ? 'syncing' : 'sync')}</span>
        </button>
      </div>
      <button className="picker-close nova-dismiss-button" onClick={onClose} aria-label={t('modelClose')}><NovaIcon name="close" size={20}/></button>
    </header>
    {selectionError && <div className="nova-model-selection-notice" role="alert">{t('modelChangeFailed')}</div>}
    {selectionPending && <div className="nova-model-selection-notice" role="status">{t('modelChanging')}</div>}
    {operationError && <div className="nova-model-selection-notice model-error" role="alert">{t(modelErrorKey(operationError))}</div>}
    {operationNotice && !operationError && <div className="nova-model-selection-notice" role="status">
      {operationNotice.model && <strong>{operationNotice.model} · </strong>}
      {t(operationNotice.kind === 'downloaded' ? 'modelDownloadComplete' : operationNotice.kind === 'deleted' ? 'modelDeleteComplete' : 'modelSyncComplete')}
    </div>}
    {pulling && !operationUnconfirmed && <section className="pull-bar" aria-label={t('downloading')} aria-live="polite">
      <div className="pull-bar-top"><span className="pull-bar-text">{t('downloading')} <strong>{pulling}</strong></span>
        <span className="pull-bar-progress">{percent === null ? '' : percent+'%'}</span></div>
      <div className="pull-bar-gauge" role="progressbar" aria-label={t('downloading')+' '+pulling}
        aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent ?? undefined}>
        <div className={'pull-bar-gauge-fill'+(percent === null ? ' indeterminate' : '')} style={percent !== null ? {width:percent+'%'} : undefined}/>
      </div>
      {pullProgress && <span className="picker-progress-detail">{pullProgress}</span>}
    </section>}
    <section className="picker-panel" aria-label={t('catalog')}>
      <form className="picker-search" onSubmit={event=>{event.preventDefault();if(publicView)library!.search({...library!.state.filters,query:filter},true);input.current?.focus()}}><ModelIcon kind="search"/><input ref={input} type="search" placeholder={t('filterModels')}
        aria-label={t('filterModels')} value={filter} onChange={event => setFilter(event.target.value)}/>
        <button type="submit" className="nova-search-submit" aria-label={t('modelSearchSubmit')} title={t('modelSearchSubmit')}><NovaIcon name="forward" size={18}/></button>
        {(recommended || onRefreshCatalog) && <button type="button" className="picker-refresh nova-search-refresh" onClick={publicView?()=>library!.search({...library!.state.filters,query:filter},true):recommended ? onRequestRecommend : onRefreshCatalog}
          disabled={publicView?updating:actionsDisabled || (recommended ? recommending : catalogLoading)} aria-label={t(publicView?'libraryRefresh':'modelRefresh')} title={t(publicView?'libraryRefresh':'modelRefresh')}>
          <ModelIcon kind="sync" spin={recommended ? recommending : catalogLoading}/></button>}</form>
      <div className="picker-tabs" role="group" aria-label={t('modelCategories')}>
        {catalogSections.map(({id,label}) => <button key={id} className={'picker-tab'+(section === id ? ' active' : '')}
          data-model-section={id} aria-pressed={section === id} onClick={() => selectSection(id)}>{t(label)}</button>)}
      </div>
      {recommended && systemInfo && <div className="picker-system-info" aria-label={t('modelDetectedHardware')}>
        <span>{systemInfo.chip || systemInfo.os || t('modelMetadataUnknown')}</span>
        <span>{typeof systemInfo.ram_gb === 'number' ? systemInfo.ram_gb+' GB RAM' : t('ramUnknown')}</span>
        {systemInfo.gpu && <span>{systemInfo.gpu}</span>}</div>}
      {recommended&&recommendationStatus&&<div className="picker-recommendation-state" role="status">
        {recommending&&<span>{t(recommendationStatus.phase==='catalog'?'recommendationReadingCatalog':'recommendationCheckingVariants')}
          {recommendationStatus.phase==='variants'?` ${recommendationStatus.scanned} / ${recommendationStatus.total}`:''}</span>}
        {recommendationStatus.budget_gb>0&&<span>{t('recommendationMemoryBudget')}: {numberFormat.format(recommendationStatus.budget_gb)} GB</span>}
        {recommendationStatus.offline&&<span>{t('libraryOffline')}</span>}
        {recommendationStatus.stale&&<span>{t('libraryStale')}</span>}
        {recommendationStatus.unavailable>0&&<span>{t('recommendationUnchecked')}: {recommendationStatus.unavailable}</span>}
      </div>}
      {publicView ? <PublicLibraryView library={library!} query={filter} current={current} embeddingCurrent={embeddingCurrent} installed={installed}
        locked={locked} mutationLocked={mutationLocked} pulling={pulling} deleting={deleting}
        onSelect={onSelect} onSelectEmbedding={onSelectEmbedding} onPull={onPull} onDelete={onDelete}/>
        : <><div className="picker-list" aria-busy={recommended ? recommending : catalogLoading}>
        {error && <ModelError code={error} onRetry={recommended ? onRequestRecommend : onRefreshCatalog}
          disabled={actionsDisabled || (recommended ? recommending : catalogLoading)}/>}
        {recommended ? <>
          {(!recommendations||recommending&&!suggestions?.length) && !error ? <Empty>{t('detectingSystem')}</Empty> : suggestions?.map(model => <ModelRow key={model.name}
            name={model.name} display={model.display} description={model.reason==='MEMORY_FIT'?model.description||'':modelLibraryText(model.reason,locale)} size={model.size_gb} sizeLabel={model.size_label}
            metadata={model.kind&&<><Meta value={t(model.kind==='embedding'?'libraryEmbedding':'libraryLLM')}/>
              <Meta value={modelContext(model.context_length)?modelContext(model.context_length)+' ctx':''}/></>}
            extras={model.reason==='MEMORY_FIT'&&<span>{t('recommendationMemoryEstimate')}: {numberFormat.format(model.estimated_memory_gb??0)} GB
              {model.gpu_fit?' · '+t('recommendationGpuFit'):''}</span>}
            selected={installedModelName(model.name,installed) === (model.kind==='embedding'?embeddingCurrent||'':current)} actions={actions(model.name,true,model.kind)}/>)}
          {suggestions?.length === 0 && !error && !recommending && <Empty>{t(recommendations?.length?'noModelMatches':recommendationStatus?.phase==='memory_unknown'?'recommendationMemoryUnknown':recommendationStatus?.unavailable?'recommendationPartialEmpty':'recommendationNoFit')}</Empty>}
        </> : <>
          {!catalog && !error ? <Empty>{t('loadingModels')}</Empty> : section === 'installed' && !installed
            ? <Empty>{t('modelInventoryUnknown')}</Empty> : shownCategories.map(name => <section key={name} aria-label={categoryLabel(name)}>
              <h3 className="picker-category">{categoryLabel(name)}</h3>
              {filtered.filter(model => model.category === name).map(model => <ModelRow key={model.name} name={model.name}
                display={model.display} description={modelLibraryText(model.description,locale)} selected={installedModelName(model.name,installed) === current}
                metadata={<><Meta value={model.params}/><Meta value={modelContext(model.context_length) ? modelContext(model.context_length)+' ctx' : ''}/>
                  {model.release_date && <span className="picker-model-date">{model.release_date}</span>}</>}
                extras={<>{model.strengths?.map(value => <span className="picker-model-strength" key={value}>{modelLibraryText(value,locale)}</span>)}
                  {easeRating(model.ease_of_use) && <span className="picker-ease" title={t('modelRatingSource')+': '+model.ease_of_use+'/5'}
                    aria-label={t('modelRatingSource')+': '+model.ease_of_use+'/5'}>{'★'.repeat(model.ease_of_use!)}{'☆'.repeat(5-model.ease_of_use!)}</span>}</>}
                size={model.size_gb} actions={actions(model.name)}/>)}</section>)}
          {catalog && filtered.length === 0 && !error && (section !== 'installed' || installed) && <Empty>{t('noModelMatches')}</Empty>}
        </>}
      </div>
      <footer className="picker-footer"><span>{recommended ? (suggestions?.length ?? 0) : filtered.length} {t('modelFilterCount')}</span>
        <span>{t(recommended ? 'recommendationHardwareNotice' : 'modelCatalogNotice')}</span></footer></>}
    </section>
  </ModalHost>
}

export function ModelRow({name,display,description,metadata,extras,size,sizeLabel,actions,selected}: {
  name:string;display:string;description:string;metadata?:ReactNode;extras?:ReactNode;size?:number;sizeLabel?:string;actions:ReactNode;selected:boolean
}) {
  return <article className={`picker-model ${selected ? 'current' : ''}`} aria-label={display || name}>
    <div className="picker-model-main"><div className="picker-model-name"><strong>{display || name}</strong>{metadata}</div>
      {display !== name && <div className="picker-model-id">{name}</div>}
      <p className="picker-model-desc">{description}</p><div className="picker-model-meta">{extras}</div></div>
    <div className="picker-model-right">{sizeLabel?<span className="picker-model-size">{sizeLabel}</span>:typeof size === 'number' && Number.isFinite(size) && size > 0 && <span className="picker-model-size">≈ {size} GB</span>}{actions}</div>
  </article>
}
export function ModelActions({name,current,exact,ambiguous,cloudOnly,disabled,mutationLocked,pulling,deleting,canDelete,
  onSelect,onPull,onDelete,onViewInstalled}: {name:string;current:string;exact:string|null;ambiguous:boolean
    cloudOnly:boolean;disabled:boolean;mutationLocked:boolean;pulling:boolean;deleting:boolean;canDelete:boolean
    onSelect:(name:string)=>void;onPull:(name:string)=>void;onDelete:(name:string)=>void;onViewInstalled:()=>void}) {
  const {t}=useI18n()
  const [confirm,setConfirm]=useState(false)
  const timer=useRef<ReturnType<typeof setTimeout>|null>(null)
  useEffect(()=>()=>{if(timer.current)clearTimeout(timer.current)},[])
  useEffect(()=>{if(disabled || mutationLocked)setConfirm(false)},[disabled,mutationLocked])
  useEffect(()=>{setConfirm(false)},[exact,name])
  if(deleting)return <span className="picker-badge pulling-badge">{t('modelDeleting')}…</span>
  if(pulling)return <span className="picker-badge pulling-badge">{t('pulling')}</span>
  if(cloudOnly)return <span className="picker-badge cloud-badge">{t('modelCloudOnly')}</span>
  if(exact === current)return <span className="picker-badge current-badge"><ModelIcon kind="check"/>{t('active')}</span>
  if(ambiguous)return <button className="picker-action use" disabled={disabled} onClick={onViewInstalled}>{t('modelViewInstalled')}</button>
  if(exact)return <div className="picker-model-actions">
    <button className="picker-action use" disabled={disabled || mutationLocked} aria-label={`${t('modelSelectAction')} ${exact}`} onClick={()=>onSelect(exact)}>{t('useModel')}</button>
    {canDelete && <button className="nova-settings-danger" data-confirming={confirm||undefined} disabled={mutationLocked}
      aria-label={`${t(confirm ? 'confirmDelete' : 'modelDeleteAction')} ${exact}`} onClick={()=>{
        if(confirm){setConfirm(false);if(timer.current)clearTimeout(timer.current);onDelete(exact)}
        else{setConfirm(true);timer.current=setTimeout(()=>setConfirm(false),4000)}
      }}>{t(confirm ? 'confirmDelete' : 'deleteModel')}</button>}
  </div>
  return <button className="picker-action download" disabled={mutationLocked} aria-label={`${t('modelDownloadAction')} ${name}`}
    onClick={()=>onPull(name)}><ModelIcon kind="download"/>{t('download')}</button>
}
function Meta({value}:{value:string}){return value ? <span className="picker-model-params">{value}</span> : null}
function Empty({children}:{children:ReactNode}){return <div className="picker-empty" role="status">{children}</div>}
function ModelError({code,onRetry,disabled}:{code:string;onRetry?:()=>void;disabled?:boolean}){
  const {t}=useI18n();return <div className="picker-load-error" role="alert"><p>{t(modelErrorKey(code))}</p>
    {onRetry && <button className="picker-action use" disabled={disabled} onClick={onRetry}>{t('modelRetry')}</button>}</div>
}
function ModelIcon({kind,spin=false}:{kind:'search'|'sync'|'close'|'download'|'check';spin?:boolean}){
  return <svg className={spin ? 'picker-spinning' : undefined} width="17" height="17" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {kind==='search' && <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/></>}
    {kind==='sync' && <><path d="M20 7a9 9 0 0 0-15-2L2 8m0-5v5h5M4 17a9 9 0 0 0 15 2l3-3m0 5v-5h-5"/></>}
    {kind==='close' && <path d="m6 6 12 12M18 6 6 18"/>}
    {kind==='download' && <path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>}
    {kind==='check' && <path d="m5 12 4 4 10-10"/>}
  </svg>
}
