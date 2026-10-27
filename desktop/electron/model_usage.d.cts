export function createModelUsageClient(options:{send:(message:object)=>unknown}):{
  request(query:import('../shared/model_usage').UsageQuery,kind?:"llm"|"embedding"):Promise<import('../shared/model_usage').ModelUsageResult>
  receive(frame:any):boolean;disconnected():void
}
