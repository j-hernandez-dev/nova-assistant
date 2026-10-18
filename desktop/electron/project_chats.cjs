const crypto=require('node:crypto')
function createProjectChatClient({send,getView}){
  const pending=new Map(),settled=new Set()
  function retire(id){settled.add(id);if(settled.size>64)settled.delete(settled.values().next().value)}
  const failure=code=>({success:false,error:{code}})
  function request(type,payload){
    if(!getView().status.ready)return Promise.resolve(failure('PROJECT_CHAT_UNAVAILABLE'))
    return new Promise(resolve=>{
      const id='project-chat-'+crypto.randomUUID()
      const timer=setTimeout(()=>{pending.delete(id);retire(id);resolve(failure('PROJECT_CHAT_UNKNOWN'))},15000);timer.unref?.()
      pending.set(id,{type,resolve,timer})
      try{if(send({id,type,...payload})===false)throw Error('disconnected')}
      catch{clearTimeout(timer);pending.delete(id);resolve(failure('PROJECT_CHAT_UNAVAILABLE'))}
    })
  }
  return {list:paths=>request('project_chats',{paths}),clear:path=>request('clear_project_chat',{path}),
    receive(frame){
      const item=pending.get(frame.id)
      if(!item)return settled.has(frame.id)&&['error','project_chats','clear_project_chat'].includes(frame.type)
      if(item.type!==frame.type&&frame.type!=='error')return false
      pending.delete(frame.id);retire(frame.id);clearTimeout(item.timer)
      item.resolve(frame.type==='error'?failure(typeof frame.code==='string'?frame.code:'PROJECT_CHAT_FAILED'):
        typeof frame.success==='boolean'?frame:failure('PROJECT_CHAT_INVALID_RESPONSE'));return true},
    disconnected(){for(const [id,item] of pending){clearTimeout(item.timer);retire(id);item.resolve(failure('PROJECT_CHAT_UNAVAILABLE'))}pending.clear()},
    busy:()=>[...pending.values()].some(item=>item.type==='clear_project_chat')}
}
module.exports={createProjectChatClient}
