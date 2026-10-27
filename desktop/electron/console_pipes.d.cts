export function installConsolePipeGuard(options?:{
  stdout?:NodeJS.WritableStream;stderr?:NodeJS.WritableStream
  console?:Pick<Console,'log'|'info'|'debug'|'warn'|'error'>
}):{isClosed(channel:'stdout'|'stderr'):boolean;dispose():void}
