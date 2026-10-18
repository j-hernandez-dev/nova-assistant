export function createConfirmationSurface(options:any):{
  request(request:{kind:'remove-project'|'clear-chat'|'clear-all';projectName?:string;path?:string;validate:()=>boolean}):Promise<{confirmed:boolean;canceled:boolean}>;
  isPending():boolean;sync():void;updateLocale():void;dispose():void
}
