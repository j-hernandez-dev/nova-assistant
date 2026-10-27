const crypto=require('node:crypto')
/** A read-only JSONL channel. Late replies can never become chat messages. */
function createModelUsageClient({send}){
  const pending=new Map(),retired=new Set()
  const failure=code=>({success:false,error:{code}})
  const retire=id=>{retired.add(id);if(retired.size>128)retired.delete(retired.values().next().value)}
  return {
    request(query,kind="llm"){return new Promise(resolve=>{
      const id='model-usage-'+crypto.randomUUID()
      const timer=setTimeout(()=>{pending.delete(id);retire(id);resolve(failure('USAGE_UNAVAILABLE'))},10000);timer.unref?.()
      pending.set(id,{resolve,timer,query})
      try{if(send({id,type:'model_usage',query,...(kind==='embedding'?{kind}: {})})===false)throw Error('offline')}
      catch{clearTimeout(timer);pending.delete(id);retire(id);resolve(failure('USAGE_UNAVAILABLE'))}
    })},
    receive(frame){
      const item=pending.get(frame.id)
      if(!item)return retired.has(frame.id)
      if(frame.type!=='model_usage'&&frame.type!=='error')return false
      clearTimeout(item.timer);pending.delete(frame.id);retire(frame.id)
      const count=n=>Number.isSafeInteger(n)&&n>=0
      const valid=b=>b&&['requests','inputTokens','outputTokens','unreported'].every(k=>count(b[k]))
      const data=frame.data
      const success=frame.success===true&&data?.schemaVersion===1&&valid(data)&&typeof data.gap==='boolean'&&Array.isArray(data.buckets)&&data.buckets.length===item.query.buckets.length&&data.buckets.every(valid)
      item.resolve(success?{success:true,data,query:item.query}:failure('USAGE_UNAVAILABLE'));return true
    },
    disconnected(){for(const [id,item] of pending){clearTimeout(item.timer);retire(id);item.resolve(failure('USAGE_UNAVAILABLE'))}pending.clear()}
  }
}
module.exports={createModelUsageClient}
