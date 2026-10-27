export const usageRanges = ['today','yesterday','last7','last30','thisMonth','lastMonth','last6Months'] as const
export type UsageRange = typeof usageRanges[number]
export type UsageQuery = {start:string;end:string;buckets:Array<{start:string;end:string}>}
export type UsageBucket = {requests:number;inputTokens:number;outputTokens:number;unreported:number}
export type ModelUsage = UsageBucket & {schemaVersion:1;buckets:UsageBucket[];gap:boolean}
export type ModelUsageResult = {success:true;data:ModelUsage;query:UsageQuery} | {success:false;error:{code:string}}

/** Local calendar boundaries, including 23/25-hour daylight-saving days. */
export function usageQuery(range:UsageRange, now=new Date()):UsageQuery {
  const start=new Date(now.getFullYear(),now.getMonth(),now.getDate()),end=new Date(start)
  end.setDate(end.getDate()+1)
  if(range==='yesterday'){start.setDate(start.getDate()-1);end.setDate(end.getDate()-1)}
  else if(range==='last7'||range==='last30')start.setDate(start.getDate()-(range==='last7'?6:29))
  else if(range==='thisMonth'){start.setDate(1);end.setFullYear(start.getFullYear(),start.getMonth()+1,1)}
  else if(range==='lastMonth'){end.setFullYear(start.getFullYear(),start.getMonth(),1);start.setFullYear(start.getFullYear(),start.getMonth()-1,1)}
  else if(range==='last6Months')start.setFullYear(start.getFullYear(),start.getMonth()-5,1)
  const buckets:UsageQuery['buckets']=[]
  let cursor=new Date(start)
  while(cursor<end){
    const next=new Date(cursor)
    if(range==='today'||range==='yesterday')next.setTime(next.getTime()+3600000)
    else if(range==='last6Months')next.setMonth(next.getMonth()+1,1)
    else next.setDate(next.getDate()+1)
    if(next>end)next.setTime(end.getTime())
    buckets.push({start:cursor.toISOString(),end:next.toISOString()});cursor=next
  }
  return {start:start.toISOString(),end:end.toISOString(),buckets}
}
