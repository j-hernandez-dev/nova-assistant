import { useEffect, useId, useRef, useState } from 'react'
import type { DesktopSessionView } from '../../shared/application'
import { useI18n } from '../i18n'
import { SettingsActionFeedback, useSettingsAction } from '../settings_actions'

type Props = { view: DesktopSessionView | null }
export type MemoryInspection = { memoryId: string; revision: number; canonicalText: string; kind: string;
  scopeKind: string; status: string; sensitivityClass?: string; hidden: boolean }
type Proposal = { jobId: string; revision: number; proposalId: string; text: string; kind: string; scopeKind: string }
const kinds = ['PREFERENCE', 'SEMANTIC_FACT', 'WORKSPACE_FACT', 'EPISODE', 'PROCEDURE'] as const
const kindKeys = ['memorySettingsPreference', 'memorySettingsFact', 'memorySettingsProjectFact', 'memorySettingsEpisode', 'memorySettingsProcedure'] as const
const statusKeys = { ACTIVE: 'memorySettingsActive', SUPERSEDED: 'memorySettingsSuperseded', CONFLICTED: 'memorySettingsConflicted',
  RETRACTED: 'memorySettingsRetracted', EXPIRED: 'memorySettingsExpired', DELETED: 'memorySettingsDeleted' } as const
const object = (value: any) => value && typeof value === 'object' && !Array.isArray(value)
const identity = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value.length <= 128

/** Inspection data never becomes a chat message, a tool argument or authority. */
export function memoryInspection(value: any): MemoryInspection | null {
  if (!object(value) || !identity(value.memoryId) || !Number.isSafeInteger(value.revision) || value.revision < 1
    || typeof value.canonicalText !== 'string' || !kinds.includes(value.kind) || !['WORKSPACE', 'GLOBAL_PROFILE'].includes(value.scopeKind)
    || !Object.prototype.hasOwnProperty.call(statusKeys, value.status)) return null
  return { memoryId: value.memoryId, revision: value.revision, canonicalText: value.canonicalText,
    kind: value.kind, scopeKind: value.scopeKind, status: value.status, sensitivityClass: value.sensitivityClass,
    hidden: value.sensitivityClass === 'SENSITIVE' && value.canonicalText === '[SENSITIVE — explicit inspection required]' }
}
export function memoryProposals(value: unknown): Proposal[] {
  return Array.isArray(value) ? value.flatMap(row => object(row) && identity(row.jobId) && Number.isSafeInteger(row.revision)
    && row.revision >= 1 && object(row.proposal) && identity(row.proposal.proposalId)
    && typeof row.proposal.text === 'string' && kinds.includes(row.proposal.kind)
    && ['WORKSPACE', 'GLOBAL_PROFILE'].includes(row.proposal.scopeKind)
    ? [{ jobId: row.jobId, revision: row.revision, proposalId: row.proposal.proposalId,
      text: row.proposal.text, kind: row.proposal.kind, scopeKind: row.proposal.scopeKind }] : []) : []
}
export function memoryRecordMutation(record: MemoryInspection, text?: string, consentSensitive = false): Record<string, unknown> {
  return { memoryId: record.memoryId, revision: record.revision,
    ...(text !== undefined ? { text, ...(consentSensitive ? { consentSensitive: true } : {}) } : {}) }
}
export function memoryProposalMutation(proposal: Proposal, resolution?: 'create' | 'supersede' | 'conflict'): Record<string, unknown> {
  return { jobId: proposal.jobId, proposalId: proposal.proposalId, revision: proposal.revision,
    ...(resolution ? { resolution } : {}) }
}

type InspectionState = { scope: string; records: MemoryInspection[] | null; nextCursor: string | null;
  selected: MemoryInspection | null; proposals: Proposal[] | null; status: Record<string, any> | null; exported: Record<string, any> | null }
const empty = (scope: string): InspectionState => ({scope, records:null, nextCursor:null, selected:null, proposals:null, status:null, exported:null})

/** Explicit controls of the existing Memory service. No automatic recall, capture or schema changes. */
export function MemorySettings({ view }: Props) {
  const { t } = useI18n(), id = useId()
  const scope = `${view?.sessionId || ''}:${view?.workspace || ''}:${!!view?.status.connected}`
  const action = useSettingsAction(scope)
  const liveScope = useRef(scope), alive = useRef(true)
  liveScope.current = scope
  const [loaded, setLoaded] = useState<InspectionState>(() => empty(scope))
  const data = loaded.scope === scope ? loaded : empty(scope)
  const [filterScope, setFilterScope] = useState('WORKSPACE')
  const [includeSensitive, setIncludeSensitive] = useState(false)
  const [query, setQuery] = useState('')
  const [text, setText] = useState(''), [key, setKey] = useState('')
  const [kind, setKind] = useState<string>('WORKSPACE_FACT')
  const [writeScope, setWriteScope] = useState('WORKSPACE')
  const [sensitive, setSensitive] = useState(false)
  const [correction, setCorrection] = useState(''), [correctionConsent, setCorrectionConsent] = useState(false)
  const [forgetConfirmation, setForgetConfirmation] = useState(false)
  const [resolution, setResolution] = useState<'create'|'supersede'|'conflict'>('create')
  const [uncertainEffect, setUncertainEffect] = useState(false)
  const memory = view?.memory
  const ready = !!view?.status.ready && !view.recovering && !view.gap && !!memory?.lexicalRecall
  const disabled = !ready || !!view?.activeTurnId || !!view?.activeGenerationId || action.busy
  const mutationDisabled = disabled || uncertainEffect || action.errorCode === 'OUTCOME_UNKNOWN'

  useEffect(() => { setLoaded(empty(scope)); setQuery(''); setText(''); setKey(''); setIncludeSensitive(false)
    setSensitive(false); setCorrection(''); setCorrectionConsent(false); setForgetConfirmation(false)
    setFilterScope('WORKSPACE'); setWriteScope('WORKSPACE'); setKind('WORKSPACE_FACT'); setUncertainEffect(false)
  }, [scope])
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])

  const invoke = async (name: string, args: Record<string, unknown>, mutation = false) => {
    if (disabled || (mutation && mutationDisabled)) return null
    const receipt = await action.run(async () => {
      const result = await window.api.memoryCommand(name, args)
      if (alive.current && liveScope.current === scope && mutation
          && (result.error?.outcomeUnknown || result.error?.code === 'OUTCOME_UNKNOWN')) setUncertainEffect(true)
      return result
    })
    return alive.current && liveScope.current === scope && receipt?.completed ? receipt.data || null : null
  }
  const inspectPage = async (search = false, cursor?: string) => {
    const result = await invoke(search ? 'memory_search' : 'memory_list', { scope: filterScope, limit:20, includeSensitive,
      ...(search ? {query:query.trim()} : cursor ? {cursor} : {}) })
    if (result) setLoaded(old => ({...old, scope, records:Array.isArray(result.records)
      ? result.records.map(memoryInspection).filter((row: MemoryInspection|null):row is MemoryInspection => !!row) : [],
      nextCursor:!search && typeof result.nextCursor === 'string' ? result.nextCursor : null, selected:null}))
    setForgetConfirmation(false)
  }
  const inspectRecord = async (record: MemoryInspection) => {
    const result = await invoke('memory_show',{memoryId:record.memoryId,includeSensitive})
    const selected = memoryInspection(result?.record)
    if (selected) { setLoaded(old => ({...old,scope,selected})); setCorrection(selected.hidden ? '' : selected.canonicalText)
      setCorrectionConsent(false); setForgetConfirmation(false) }
  }
  const remember = async () => {
    const result = await invoke('memory_remember',{kind,text,scope:writeScope,...(key.trim() ? {key:key.trim()} : {}),
      ...(sensitive ? {sensitive:true,consentSensitive:true} : {})},true)
    if (result) { setText(''); setKey(''); setSensitive(false); setLoaded(empty(scope)) }
  }
  const mutateRecord = async (forget = false) => {
    if (!data.selected) return
    const result = await invoke(forget ? 'memory_forget' : 'memory_correct',
      memoryRecordMutation(data.selected,forget ? undefined : correction,correctionConsent),true)
    if (result) { setLoaded(empty(scope)); setCorrection(''); setCorrectionConsent(false); setForgetConfirmation(false) }
  }
  const inspectProposals = async () => {
    const result = await invoke('memory_proposals',{})
    if (result) setLoaded(old => ({...old,scope,proposals:memoryProposals(result.proposals)}))
  }
  const decideProposal = async (proposal: Proposal, confirm: boolean) => {
    const result = await invoke(confirm ? 'memory_confirm' : 'memory_reject',memoryProposalMutation(proposal,confirm ? resolution : undefined),true)
    // Revision belongs to the whole proposal job; reload rather than reuse siblings with the old revision.
    if (result) setLoaded(old => ({...old,scope,proposals:null,records:null,nextCursor:null,selected:null}))
  }

  return <div className="nova-memory-settings">
    <section className="nova-settings-card">
      <h3>{t('memorySettingsState')}</h3><p className="settings-hint">{t('memorySettingsReadonly')}</p>
      {!memory && <p role="status">{t('memorySettingsUnavailable')}</p>}
      {(['lexicalRecall','semantic','autoCapture','allowRemoteMemoryInjection'] as const).map((field,index) => <div className="nova-settings-row" key={field}>
        <span>{t((['memorySettingsLexical','memorySettingsSemantic','memorySettingsCapture','memorySettingsRemote'] as const)[index])}</span>
        <span>{t(!memory ? 'settingsUnknown' : memory[field] ? 'settingsOn' : 'settingsOff')}</span>
      </div>)}
      <button disabled={disabled} onClick={async () => { const status = await invoke('memory_status',{}); if (status) setLoaded(old => ({...old,scope,status})) }}>{t('memorySettingsStatusDetail')}</button>
      {data.status && <details><summary>{t('memorySettingsMetadata')}</summary><pre>{JSON.stringify(data.status,null,2)}</pre></details>}
    </section>
    <SettingsActionFeedback action={action}/>
    {uncertainEffect && <p className="settings-feedback" role="alert">{t('memorySettingsUnconfirmed')}</p>}
    <section className="nova-settings-card">
      <h3>{t('memorySettingsInspect')}</h3>
      <label htmlFor={`${id}-scope`}>{t('memorySettingsScope')}</label>
      <select id={`${id}-scope`} value={filterScope} disabled={action.busy} onChange={event => {
        setFilterScope(event.target.value); setLoaded(empty(scope)); setForgetConfirmation(false)
      }}><option value="WORKSPACE">{t('memorySettingsWorkspace')}</option><option value="GLOBAL_PROFILE">{t('memorySettingsGlobal')}</option><option value="ALL">{t('memorySettingsAll')}</option></select>
      <label><input type="checkbox" checked={includeSensitive} disabled={action.busy} onChange={event => {
        setIncludeSensitive(event.target.checked); setLoaded(empty(scope)); setForgetConfirmation(false)
      }}/>{t('memorySettingsSensitive')}</label><p className="settings-hint">{t('memorySettingsSensitiveHint')}</p>
      <form onSubmit={event => {event.preventDefault(); void inspectPage(true)}}>
        <label htmlFor={`${id}-query`}>{t('memorySettingsQuery')}</label>
        <input id={`${id}-query`} value={query} maxLength={4096} disabled={action.busy} onChange={event => setQuery(event.target.value)}/>
        <div className="nova-settings-actions"><button disabled={disabled || !query.trim()} type="submit">{t('memorySettingsSearch')}</button>
          <button type="button" disabled={disabled} onClick={() => void inspectPage()}>{t('memorySettingsList')}</button>
          {data.nextCursor && <button type="button" disabled={disabled} onClick={() => void inspectPage(false,data.nextCursor!)}>{t('memorySettingsNext')}</button>}</div>
      </form>
      <p className="settings-hint">{t('memorySettingsPageHint')}</p>
      {data.records === null ? <p>{t('memorySettingsNotLoaded')}</p> : data.records.length === 0 ? <p>{t('memorySettingsEmpty')}</p> :
        <div className="settings-memory-list">{data.records.map(record => <MemoryRecordRow key={record.memoryId} record={record} disabled={disabled} onInspect={() => void inspectRecord(record)}/>)}</div>}
      {data.selected && <section className="settings-memory-detail">
        <h4>{t('memorySettingsRecord')}</h4><MemoryRecordRow record={data.selected}/>
        {!data.selected.hidden && <>
          <label htmlFor={`${id}-correction`}>{t('memorySettingsText')}</label><textarea id={`${id}-correction`} value={correction} maxLength={4096} rows={4} disabled={mutationDisabled} onChange={event => setCorrection(event.target.value)}/>
          {data.selected.sensitivityClass === 'SENSITIVE' && <label><input type="checkbox" checked={correctionConsent} disabled={mutationDisabled} onChange={event => setCorrectionConsent(event.target.checked)}/>{t('memorySettingsWriteSensitive')}</label>}
          <div className="nova-settings-actions"><button disabled={mutationDisabled || !correction.trim() || correction === data.selected.canonicalText
            || (data.selected.sensitivityClass === 'SENSITIVE' && !correctionConsent)} onClick={() => void mutateRecord()}>{t('memorySettingsCorrect')}</button>
            <button disabled={action.busy} onClick={() => {setCorrection(data.selected!.canonicalText);setCorrectionConsent(false);setForgetConfirmation(false)}}>{t('memorySettingsCancelEdit')}</button></div>
        </>}
        <p className="settings-hint">{t('memorySettingsForgetHint')}</p>
        <div className="nova-settings-actions">{forgetConfirmation ? <>
          <button disabled={mutationDisabled} onClick={() => void mutateRecord(true)}>{t('memorySettingsForgetConfirm')}</button>
          <button disabled={action.busy} onClick={() => setForgetConfirmation(false)}>{t('memorySettingsForgetCancelled')}</button>
        </> : <button disabled={mutationDisabled} onClick={() => setForgetConfirmation(true)}>{t('memorySettingsForget')}</button>}</div>
      </section>}
    </section>
    <form className="nova-settings-card" onSubmit={event => {event.preventDefault(); void remember()}}>
      <h3>{t('memorySettingsNew')}</h3><p className="settings-hint">{t('memorySettingsWriteHint')}</p>
      <label htmlFor={`${id}-kind`}>{t('memorySettingsKind')}</label><select id={`${id}-kind`} value={kind} disabled={mutationDisabled} onChange={event => setKind(event.target.value)}>
        {kinds.map((value,index) => <option key={value} value={value}>{t(kindKeys[index])}</option>)}</select>
      <label htmlFor={`${id}-write-scope`}>{t('memorySettingsScope')}</label><select id={`${id}-write-scope`} value={writeScope} disabled={mutationDisabled} onChange={event => setWriteScope(event.target.value)}>
        <option value="WORKSPACE">{t('memorySettingsWorkspace')}</option><option value="GLOBAL_PROFILE">{t('memorySettingsGlobal')}</option></select>
      <label htmlFor={`${id}-text`}>{t('memorySettingsText')}</label><textarea id={`${id}-text`} value={text} maxLength={4096} rows={4} disabled={mutationDisabled} onChange={event => setText(event.target.value)}/>
      <label htmlFor={`${id}-key`}>{t('memorySettingsKey')}</label><input id={`${id}-key`} value={key} maxLength={256} disabled={mutationDisabled} onChange={event => setKey(event.target.value)}/>
      <label><input type="checkbox" checked={sensitive} disabled={mutationDisabled} onChange={event => setSensitive(event.target.checked)}/>{t('memorySettingsWriteSensitive')}</label>
      <div className="nova-settings-actions"><button type="submit" disabled={mutationDisabled || !text.trim()}>{t('memorySettingsRemember')}</button></div>
    </form>
    <section className="nova-settings-card">
      <h3>{t('memorySettingsProposals')}</h3><button disabled={disabled} onClick={() => void inspectProposals()}>{t('memorySettingsLoadProposals')}</button>
      {data.proposals?.length === 0 && <p>{t('memorySettingsNoProposals')}</p>}
      {!!data.proposals?.length && <><label htmlFor={`${id}-resolution`}>{t('memorySettingsResolution')}</label>
        <select id={`${id}-resolution`} value={resolution} disabled={mutationDisabled} onChange={event => setResolution(event.target.value as typeof resolution)}>
          <option value="create">{t('memorySettingsCreate')}</option><option value="supersede">{t('memorySettingsSupersede')}</option><option value="conflict">{t('memorySettingsConflict')}</option></select>
        {data.proposals.map(proposal => <article className="settings-memory-record" key={`${proposal.jobId}:${proposal.proposalId}`}>
          <p>{proposal.text}</p><small>{t(kindKeys[kinds.indexOf(proposal.kind as typeof kinds[number])])} · {t(proposal.scopeKind === 'WORKSPACE' ? 'memorySettingsWorkspace' : 'memorySettingsGlobal')}</small>
          <div className="nova-settings-actions"><button disabled={mutationDisabled} onClick={() => void decideProposal(proposal,true)}>{t('memorySettingsConfirm')}</button>
            <button disabled={mutationDisabled} onClick={() => void decideProposal(proposal,false)}>{t('memorySettingsReject')}</button></div>
        </article>)}</>}
    </section>
    <section className="nova-settings-card"><h3>{t('memorySettingsExport')}</h3><p className="settings-hint">{t('memorySettingsExportHint')}</p>
      <button disabled={disabled} onClick={async () => {const exported = await invoke('memory_export',{includeSensitive}); if (exported) setLoaded(old => ({...old,scope,exported}))}}>{t('memorySettingsExport')}</button>
      {data.exported && <details open><summary>{t('memorySettingsExportData')}</summary><pre>{JSON.stringify(data.exported,null,2)}</pre></details>}
    </section>
  </div>
}

export function MemoryRecordRow({record,disabled,onInspect}:{record:MemoryInspection;disabled?:boolean;onInspect?:()=>void}) {
  const {t} = useI18n()
  return <article className="settings-memory-record"><p>{record.hidden ? t('memorySettingsHidden') : record.canonicalText}</p>
    <small>{t(kindKeys[kinds.indexOf(record.kind as typeof kinds[number])])} · {t(record.scopeKind === 'WORKSPACE' ? 'memorySettingsWorkspace' : 'memorySettingsGlobal')}
      {' · '}{t(statusKeys[record.status as keyof typeof statusKeys])}{' · '}{t('memorySettingsRevision')} {record.revision}</small>
    {onInspect && <button type="button" disabled={disabled} onClick={onInspect}>{t('memorySettingsDetail')}</button>}
  </article>
}
