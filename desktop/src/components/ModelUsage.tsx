import {useEffect,useRef,useState} from 'react'
import {useI18n} from '../i18n'
import {SettingsSelect} from './SettingsSelect'
import {usageRanges,type UsageRange,type ModelUsageResult} from '../../shared/model_usage'

const rangeKeys=['llmToday','llmYesterday','llmLast7','llmLast30','llmThisMonth','llmLastMonth','llmLast6Months'] as const
export function ModelUsage({active,revision,range,onRange,kind='llm',disabled=false}:{active:boolean;revision:unknown;range:UsageRange;onRange:(value:UsageRange)=>void;kind?:'llm'|'embedding';disabled?:boolean}){
  const {t,locale}=useI18n()
  const [result,setResult]=useState<ModelUsageResult|null>(null),[loading,setLoading]=useState(false),[retry,setRetry]=useState(0)
  const epoch=useRef(0)
  useEffect(()=>{
    const sequence=++epoch.current
    if(!active)return
    let pending=false
    const fetch=async()=>{if(pending)return;pending=true;setLoading(true)
      try{const next=await window.api.getModelUsage(range,kind);if(epoch.current===sequence)setResult(next)}
      catch{if(epoch.current===sequence)setResult({success:false,error:{code:'USAGE_UNAVAILABLE'}})}
      finally{pending=false;if(epoch.current===sequence)setLoading(false)}
    }
    setResult(null);void fetch();const timer=setInterval(()=>void fetch(),15000)
    return()=>{++epoch.current;clearInterval(timer)}
  },[active,range,revision,retry,kind])
  const data=result?.success?result.data:null,query=result?.success?result.query:null
  const number=(value:number)=>new Intl.NumberFormat(locale).format(value)
  const values=data?.buckets||[],count=values.length
  const dates=query?.buckets.map(item=>new Date(item.start))||[]
  const dateLabel=(date:Date)=>new Intl.DateTimeFormat(locale,{...(range==='today'||range==='yesterday'?{hour:'2-digit',minute:'2-digit'}:range==='last6Months'?{month:'short',year:'numeric'}:{month:'short',day:'numeric'})}).format(date)
  const tokenMax=Math.max(1,...values.map(item=>item.inputTokens+item.outputTokens)),requestMax=Math.max(1,...values.map(item=>item.requests))
  const width=480,height=190,left=45,top=12,right=10,bottom=28,plotW=width-left-right,plotH=height-top-bottom
  const embeddingUsage=kind==='embedding'
  function chart(kind:'tokens'|'requests'){
    const max=kind==='tokens'?tokenMax:requestMax
    const scaleMax=kind==='requests'?Math.max(2,Math.ceil(max/2)*2):max
    const points=values.map((item,index)=>`${left+(index+.5)*plotW/count},${top+plotH-item.requests/scaleMax*plotH}`)
    return <div className="nova-usage-chart" data-usage-chart={kind} aria-busy={loading}>
      <div className="nova-usage-chart-heading"><span>{t(kind==='tokens'?'llmTokens':'llmRequests')}</span><strong>{data?number(kind==='tokens'?data.inputTokens+data.outputTokens:data.requests):'—'}</strong></div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={t(kind==='tokens'?'llmTokens':'llmRequests')}>
        {[0,.5,1].map(fraction=><g key={fraction}><line className="nova-usage-gridline" x1={left} x2={width-right} y1={top+plotH-fraction*plotH} y2={top+plotH-fraction*plotH}/><text x={left-8} y={top+plotH-fraction*plotH+4} textAnchor="end">{new Intl.NumberFormat(locale,{notation:'compact',maximumFractionDigits:1}).format(scaleMax*fraction)}</text></g>)}
        {kind==='tokens'?values.map((item,index)=>{
          const x=left+(index+.5)*plotW/count,bar=Math.min(14,plotW/count*.65),input=item.inputTokens/scaleMax*plotH,output=item.outputTokens/scaleMax*plotH
          return <g key={index} tabIndex={item.requests?0:undefined} aria-label={`${dateLabel(dates[index])}: ${t('llmInput')} ${number(item.inputTokens)}, ${t('llmOutput')} ${number(item.outputTokens)}`}>
            <title>{`${dateLabel(dates[index])}\n${t('llmInput')}: ${number(item.inputTokens)}\n${t('llmOutput')}: ${number(item.outputTokens)}`}</title>
            <rect className="nova-usage-input" x={x-bar/2} y={top+plotH-input} width={bar} height={input}/><rect className="nova-usage-output" x={x-bar/2} y={top+plotH-input-output} width={bar} height={output} rx={output?1:0}/>
          </g>
        }):<>
          {points.length>0&&<><path className="nova-usage-area" d={`M ${left},${top+plotH} L ${points.join(' L ')} L ${width-right},${top+plotH} Z`}/><polyline className="nova-usage-line" points={points.join(' ')}/></>}
          {values.map((item,index)=><circle key={index} className="nova-usage-dot" cx={left+(index+.5)*plotW/count} cy={top+plotH-item.requests/scaleMax*plotH} r={item.requests?3:0} tabIndex={item.requests?0:undefined} aria-label={`${dateLabel(dates[index])}: ${number(item.requests)} ${t('llmRequests').toLowerCase()}`}><title>{`${dateLabel(dates[index])}: ${number(item.requests)}`}</title></circle>)}
        </>}
        {dates.map((date,index)=>index===0||index===Math.floor((count-1)/2)||index===count-1?<text key={index} x={left+(index+.5)*plotW/count} y={height-7} textAnchor={index===0?'start':index===count-1?'end':'middle'}>{dateLabel(date)}</text>:null)}
      </svg>
      {(!data||!data.requests)&&<div className="nova-usage-empty">{t(loading?'llmUsageLoading':!result||result.success?'llmNoData':'llmUsageFailed')}</div>}
      {kind==='tokens'&&!embeddingUsage&&<div className="nova-usage-legend"><span><i className="nova-usage-input"/>{t('llmInput')}</span><span><i className="nova-usage-output"/>{t('llmOutput')}</span></div>}
    </div>
  }
  return <div className="nova-model-usage">
    <div className="nova-usage-toolbar"><SettingsSelect disabled={disabled} data-settings-select={embeddingUsage?"embeddingUsageRange":"usageRange"} aria-label={t('llmRange')} value={range} options={usageRanges.map((value,index)=>({value,label:t(rangeKeys[index])}))} onChange={value=>onRange(value as UsageRange)}/></div>
    <div className="nova-usage-charts">{chart('tokens')}{chart('requests')}</div>
    <p className="settings-hint">{t(embeddingUsage?'emUsageNote':'llmUsageNote')}</p>
    {data?.unreported? <p className="settings-hint" role="status">{t('llmUsagePartial')}</p>:null}
    {data?.gap&&<p className="nova-settings-error" role="status">{t('llmUsageGap')}</p>}
    {result&&!result.success&&<button className="nova-settings-secondary" type="button" onClick={()=>setRetry(value=>value+1)}>{t('llmRetry')}</button>}
  </div>
}
