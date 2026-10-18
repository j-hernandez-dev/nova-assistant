export function createProjectChatClient(options:{send:(frame:object)=>boolean|void;getView:()=>any}):{
  list(paths:string[]):Promise<any>;clear(path:string):Promise<any>;receive(frame:any):boolean;disconnected():void;busy():boolean
}
