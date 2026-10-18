import { useState, useRef, useEffect, useId, type KeyboardEvent, type ReactNode } from 'react'
import { ModalHost } from './ModalHost'
import { useI18n, type TranslationKey } from '../i18n'
import { modelLibraryText } from '../model_catalog_locale'
import { catalogCategories, easeRating, filterCatalog, installedModelName, installedVariants,
  modelCategoryKey, modelContext, modelErrorKey, pullPercent } from '../model_catalog_presentation'

export type CatalogModel = {
  name: string; display: string; category: string; params: string; size_gb: number
  description: string; tags: string[]; installed: boolean; context_length?: number
  release_date?: string; strengths?: string[]; ease_of_use?: number
}
export type Recommendation = {
  name: string; display: string; size_gb: number; reason: string; rank: number; installed: boolean
}
export type SystemInfo = { ram_gb: number | null; chip: string; gpu: string; os: string; arch: string }
export type SearchResult = {
  name: string; description: string; pulls: number; pulls_display: string
  tags: string[]; sizes: string[]; installed: boolean; cloud_only: boolean
}
type Props = {
  open?: boolean
  catalog: { categories: string[]; models: CatalogModel[] } | null; searchResults: SearchResult[]; current: string
  onSelect: (model: string) => void; onPull: (model: string) => void; onDelete: (model: string) => void
  onSearch: (query: string, sort: string, capability: string) => void; onUpdate: () => void; onClose: () => void
  pulling: string | null; pullProgress: string; searching: boolean; updating: boolean
  recommendations: Recommendation[] | null; systemInfo: SystemInfo | null; onRequestRecommend: () => void
  selectionError?: boolean; selectionPending?: boolean; actionsDisabled?: boolean; installedModels?: string[]
  catalogLoading?: boolean; recommending?: boolean; catalogError?: string | null; searchError?: string | null
  recommendError?: string | null; operationError?: string | null; operationUnconfirmed?: boolean
  operationNotice?: {kind: 'downloaded' | 'deleted' | 'synced'; model?: string} | null
  deleting?: string | null; onRefreshCatalog?: () => void
}
type View = 'recommend' | 'catalog' | 'discover'
const views: Array<[View, TranslationKey]> = [['recommend','forYou'],['catalog','catalog'],['discover','discover']]

export function ModelPicker({catalog, searchResults, current, onSelect, onPull, onDelete, onSearch, onUpdate,
  onClose, open = true, pulling, pullProgress, searching, updating, recommendations, systemInfo, onRequestRecommend,
  selectionError = false, selectionPending = false, actionsDisabled = false, installedModels,
  catalogLoading = false, recommending = false, catalogError, searchError, recommendError,
  operationError, operationUnconfirmed = false, operationNotice, deleting = null, onRefreshCatalog}: Props) {
  const {t,locale} = useI18n()
  const id = useId()
  const [view, setView] = useState<View>('catalog')
  const [filter, setFilter] = useState('')
  const [category, setCategory] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState('popular')
  const [capability, setCapability] = useState('')
  const [installedOnly, setInstalledOnly] = useState(false)
  const didSearch = useRef(false)
  const tabs = useRef<Array<HTMLButtonElement | null>>([])
  const input = useRef<HTMLInputElement>(null)
  const locked = selectionPending || actionsDisabled
  const mutationLocked = locked || !!pulling || !!deleting || operationUnconfirmed
  const installed = installedModels ? [...new Set(installedModels)] : undefined
  const percent = pullPercent(pullProgress)
  const categories = catalog ? catalogCategories(catalog.categories, catalog.models) : []
  const filtered = catalog ? filterCatalog(catalog.models, filter, category)
    .filter(model => !installedOnly || !!installedModelName(model.name, installed)) : []
  const shownCategories = [...new Set(filtered.map(model => model.category))]
  const categoryLabel = (value: string) => {const key = modelCategoryKey(value); return key ? t(key) : value}
  useEffect(() => {
    if (view !== 'discover' || didSearch.current || actionsDisabled) return
    didSearch.current = true
    onSearch('', 'popular', '')
  }, [view, actionsDisabled, onSearch])
  function changeView(next: View, keyboard = false) {
    setView(next)
    if (next === 'recommend' && recommendations === null && !recommending) onRequestRecommend()
    if (keyboard) tabs.current[views.findIndex(([value]) => value === next)]?.focus()
  }
  function tabKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let target: number | null = null
    if (event.key === 'ArrowRight') target = (index + 1) % views.length
    if (event.key === 'ArrowLeft') target = (index + views.length - 1) % views.length
    if (event.key === 'Home') target = 0
    if (event.key === 'End') target = views.length - 1
    if (target !== null) {event.preventDefault(); changeView(views[target][0], true)}
  }
  function showInstalled(name: string) {setView('catalog');setCategory(null);setInstalledOnly(true);setFilter(name);input.current?.focus()}
  function actions(name: string, cloudOnly = false, canDelete = false) {
    return <ModelActions name={name} current={current} exact={installedModelName(name,installed)}
      ambiguous={installedVariants(name,installed).length > 1} cloudOnly={cloudOnly} disabled={locked}
      mutationLocked={mutationLocked} deleting={deleting === name} pulling={pulling === name} canDelete={canDelete}
      onSelect={onSelect} onPull={onPull} onDelete={onDelete} onViewInstalled={() => showInstalled(name)}/>
  }
  const error = view === 'catalog' ? catalogError : view === 'discover' ? searchError : recommendError
  return <ModalHost open={open} onClose={onClose} label={t('modelsTitle')} className="picker picker-wide nova-model-dialog">
    <header className="picker-header">
      <div className="picker-view-tabs" role="tablist" aria-label={t('modelTabs')}>
        {views.map(([name,label],index) => <button key={name} ref={element => {tabs.current[index] = element}}
          role="tab" id={`${id}-${name}-tab`} aria-selected={view === name} aria-controls={`${id}-panel`}
          tabIndex={view === name ? 0 : -1} className={`picker-view-tab ${view === name ? 'active' : ''}`}
          onKeyDown={event => tabKey(event,index)} onClick={() => changeView(name)}>{t(label)}</button>)}
      </div>
      <div className="picker-header-sub">
        <span className="picker-installed-count">{installed ? `${installed.length} ${t('installed')}` : t('modelInventoryUnknown')}</span>
        <button className="picker-update-btn" disabled={updating || actionsDisabled} onClick={onUpdate} title={t('syncModels')}>
          <ModelIcon kind="sync" spin={updating}/><span>{t(updating ? 'syncing' : 'sync')}</span>
        </button>
      </div>
      <button className="settings-close picker-close" onClick={onClose} aria-label={t('modelClose')}><ModelIcon kind="close"/></button>
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
        <span className="pull-bar-progress">{percent === null ? '' : `${percent}%`}</span></div>
      <div className="pull-bar-gauge" role="progressbar" aria-label={`${t('downloading')} ${pulling}`}
        aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent ?? undefined}>
        <div className={`pull-bar-gauge-fill ${percent === null ? 'indeterminate' : ''}`} style={percent !== null ? {width:`${percent}%`} : undefined}/>
      </div>
      {pullProgress && <span className="picker-progress-detail">{pullProgress}</span>}
    </section>}
    <section className="picker-panel" role="tabpanel" id={`${id}-panel`} aria-labelledby={`${id}-${view}-tab`}>
      {view === 'catalog' && <>
        <div className="picker-search"><ModelIcon kind="search"/><input ref={input} type="search" placeholder={t('filterModels')}
          aria-label={t('filterModels')} value={filter} onChange={event => setFilter(event.target.value)}/>
          {onRefreshCatalog && <button className="picker-refresh" onClick={onRefreshCatalog} disabled={catalogLoading || actionsDisabled}
            aria-label={t('modelRefresh')} title={t('modelRefresh')}><ModelIcon kind="sync" spin={catalogLoading}/></button>}</div>
        <div className="picker-tabs" role="group" aria-label={t('modelCategories')}>
          <button className={`picker-tab ${!category && !installedOnly ? 'active' : ''}`} aria-pressed={!category && !installedOnly}
            onClick={() => {setCategory(null);setInstalledOnly(false)}}>{t('all')}</button>
          <button className={`picker-tab ${installedOnly ? 'active' : ''}`} aria-pressed={installedOnly}
            onClick={() => {setCategory(null);setInstalledOnly(true)}}>{t('modelInstalledCategory')}</button>
          {categories.filter(name => name !== 'Installed').map(name => <button key={name} className={`picker-tab ${category === name ? 'active' : ''}`}
            aria-pressed={category === name} onClick={() => {setCategory(name);setInstalledOnly(false)}}>{categoryLabel(name)}</button>)}
        </div>
        <div className="picker-list" aria-busy={catalogLoading}>
          {error && <ModelError code={error} onRetry={onRefreshCatalog} disabled={actionsDisabled}/>}
          {!catalog && !error ? <Empty>{t('loadingModels')}</Empty> : shownCategories.map(name => <section key={name} aria-label={categoryLabel(name)}>
            <h3 className="picker-category">{categoryLabel(name)}</h3>
            {filtered.filter(model => model.category === name).map(model => <ModelRow key={model.name} name={model.name}
              display={model.display} description={modelLibraryText(model.description,locale)} selected={installedModelName(model.name,installed) === current}
              metadata={<><Meta value={model.params}/><Meta value={modelContext(model.context_length) ? `${modelContext(model.context_length)} ctx` : ''}/>
                {model.release_date && <span className="picker-model-date">{model.release_date}</span>}</>}
              extras={<>{model.strengths?.map(value => <span className="picker-model-strength" key={value}>{modelLibraryText(value,locale)}</span>)}
                {easeRating(model.ease_of_use) && <span className="picker-ease" title={`${t('modelRatingSource')}: ${model.ease_of_use}/5`}
                  aria-label={`${t('modelRatingSource')}: ${model.ease_of_use}/5`}>{'★'.repeat(model.ease_of_use!)}{'☆'.repeat(5-model.ease_of_use!)}</span>}</>}
              size={model.size_gb} actions={actions(model.name,false,true)}/>)}</section>)}
          {catalog && filtered.length === 0 && !error && <Empty>{t('noModelMatches')}</Empty>}
        </div>
        <footer className="picker-footer"><span>{filtered.length} {t('modelFilterCount')}</span><span>{t('modelCatalogNotice')}</span></footer>
      </>}
      {view === 'discover' && <>
        <form className="picker-search" onSubmit={event => {event.preventDefault();if(!actionsDisabled && !searching)onSearch(query,sort,capability)}}>
          <ModelIcon kind="search"/><input type="search" placeholder={t('searchModels')} aria-label={t('searchModels')}
            value={query} onChange={event => setQuery(event.target.value)}/>
          <button className="picker-action use" disabled={searching || actionsDisabled} type="submit">{t('modelSearchSubmit')}</button>
        </form>
        <div className="picker-discover-filters"><div className="picker-tabs" role="group" aria-label={t('modelSort')}>
          {(['popular','hot','newest'] as const).map(value => <button key={value} className={`picker-tab ${sort === value ? 'active' : ''}`}
            aria-pressed={sort === value} disabled={actionsDisabled} onClick={() => {setSort(value);onSearch(query,value,capability)}}>{t(value)}</button>)}
        </div><div className="picker-tabs" role="group" aria-label={t('modelCapabilities')}>
          {([['','all'],['tools','tools'],['code','code'],['vision','vision'],['thinking','reasoning']] as const).map(([value,label]) =>
            <button key={value} className={`picker-tab ${capability === value ? 'active' : ''}`} aria-pressed={capability === value}
              disabled={actionsDisabled} onClick={() => {setCapability(value);onSearch(query,sort,value)}}>{t(label)}</button>)}
        </div></div>
        <div className="picker-list" aria-busy={searching}>
          {searching && <div className="picker-inline-status" role="status">{t('searching')}</div>}
          {error && <ModelError code={error} disabled={actionsDisabled || searching} onRetry={() => onSearch(query,sort,capability)}/>}
          {searchResults.map(model => <ModelRow key={model.name} name={model.name} display={model.name}
            description={model.description} selected={installedModelName(model.name,installed) === current}
            metadata={model.tags.map(tag => <span key={tag} className="picker-model-tag">{tag}</span>)}
            extras={<>{model.pulls_display && <span className="picker-model-pulls">{model.pulls_display} {t('downloads')}</span>}
              {model.sizes.length > 0 && <span>{model.sizes.join(' · ')}</span>}</>} actions={actions(model.name,model.cloud_only)}/>)}
          {!searching && !error && searchResults.length === 0 && <Empty>{t('noSearchResults')}</Empty>}
        </div><footer className="picker-footer">{t('modelLibraryNotice')}</footer>
      </>}
      {view === 'recommend' && <>
        {systemInfo && <div className="picker-system-info" aria-label={t('modelDetectedHardware')}>
          <span>{systemInfo.chip || systemInfo.os || t('modelMetadataUnknown')}</span>
          <span>{typeof systemInfo.ram_gb === 'number' ? `${systemInfo.ram_gb} GB RAM` : t('ramUnknown')}</span>
          {systemInfo.gpu && <span>{systemInfo.gpu}</span>}</div>}
        <div className="picker-list" aria-busy={recommending}>
          {error && <ModelError code={error} disabled={actionsDisabled || recommending} onRetry={onRequestRecommend}/>}
          {!recommendations && !error ? <Empty>{t('detectingSystem')}</Empty> : recommendations?.map(model => <ModelRow key={model.name}
            name={model.name} display={model.display} description={modelLibraryText(model.reason,locale)} size={model.size_gb}
            selected={installedModelName(model.name,installed) === current} actions={actions(model.name)}/>)}
          {recommendations?.length === 0 && !error && <Empty>{t('systemUnknown')}</Empty>}
        </div><footer className="picker-footer">{t('modelHardwareNotice')}</footer>
      </>}
    </section>
  </ModalHost>
}

export function ModelRow({name,display,description,metadata,extras,size,actions,selected}: {
  name:string;display:string;description:string;metadata?:ReactNode;extras?:ReactNode;size?:number;actions:ReactNode;selected:boolean
}) {
  return <article className={`picker-model ${selected ? 'current' : ''}`} aria-label={display || name}>
    <div className="picker-model-main"><div className="picker-model-name"><strong>{display || name}</strong>{metadata}</div>
      {display !== name && <div className="picker-model-id">{name}</div>}
      <p className="picker-model-desc">{description}</p><div className="picker-model-meta">{extras}</div></div>
    <div className="picker-model-right">{typeof size === 'number' && Number.isFinite(size) && size > 0 && <span className="picker-model-size">≈ {size} GB</span>}{actions}</div>
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
  if(exact === current)return <span className="picker-badge current-badge"><ModelIcon kind="check"/>{t('active')}</span>
  if(ambiguous)return <button className="picker-action use" disabled={disabled} onClick={onViewInstalled}>{t('modelViewInstalled')}</button>
  if(exact)return <div className="picker-model-actions">
    <button className="picker-action use" disabled={disabled || mutationLocked} aria-label={`${t('modelSelectAction')} ${exact}`} onClick={()=>onSelect(exact)}>{t('useModel')}</button>
    {canDelete && <button className={`picker-action del ${confirm ? 'confirm' : ''}`} disabled={mutationLocked}
      aria-label={`${t(confirm ? 'confirmDelete' : 'modelDeleteAction')} ${exact}`} onClick={()=>{
        if(confirm){setConfirm(false);if(timer.current)clearTimeout(timer.current);onDelete(exact)}
        else{setConfirm(true);timer.current=setTimeout(()=>setConfirm(false),4000)}
      }}>{t(confirm ? 'confirmDelete' : 'deleteModel')}</button>}
  </div>
  if(cloudOnly)return <span className="picker-badge cloud-badge">{t('modelCloudOnly')}</span>
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
