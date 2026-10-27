/* Real Vite optimizer regression. Uses copied modules, an owned root and loopback only. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{pathToFileURL}=require('node:url')
const {shortcutDependencies}=require('../dev/shortcut_dependencies.cjs')
assert.ok(process.argv[2]&&process.argv[3],'Supply owned output and the previous keyboard module')
const output=path.resolve(process.argv[2]),root=path.join(output,'root'),modulePath=path.join(root,'keyboard_shortcuts.cjs'),cache=path.join(output,'vite-cache')
fs.mkdirSync(root,{recursive:true})
fs.writeFileSync(path.join(root,'package.json'),JSON.stringify({name:'nova-shortcut-cache-fixture',private:true}))
fs.writeFileSync(path.join(root,'index.html'),'<!doctype html><script type="module" src="/entry.js"></script>')
fs.writeFileSync(path.join(root,'entry.js'),'import {shortcutDefinitions} from "@nova/keyboard-shortcuts";window.definitions=shortcutDefinitions')
const current=fs.readFileSync(path.resolve(__dirname,'../shared/keyboard_shortcuts.cjs'),'utf8'),previous=fs.readFileSync(path.resolve(process.argv[3]),'utf8')
let server;const phases=[],pause=ms=>new Promise(resolve=>setTimeout(resolve,ms))
;(async()=>{try{
 const {createServer}=await import(pathToFileURL(path.resolve(__dirname,'../node_modules/vite/dist/node/index.js')).href)
 async function start(fixed){server=await createServer({configFile:false,root,cacheDir:cache,logLevel:'error',resolve:{alias:{'@nova/keyboard-shortcuts':modulePath}},optimizeDeps:{include:['@nova/keyboard-shortcuts']},plugins:fixed?[shortcutDependencies(modulePath)]:[],server:{host:'127.0.0.1',port:0}});await server.listen()}
 async function optimized(){
  const url='http://127.0.0.1:'+server.httpServer.address().port
  const response=await fetch(url+'/entry.js'),entry=await response.text();assert.equal(response.status,200)
  const dependency=entry.match(/from\s*["']([^"']*keyboard-shortcuts[^"']*)["']/)?.[1];assert.ok(dependency,entry)
  const moduleResponse=await fetch(new URL(dependency,url)),source=await moduleResponse.text();assert.equal(moduleResponse.status,200)
  return source
 }
 fs.writeFileSync(modulePath,previous);await start(false)
 assert.equal((await optimized()).includes('shortcutSources'),false);await server.close();server=null
 fs.writeFileSync(modulePath,current);await start(false)
 const stale=await optimized();assert.equal(stale.includes('shortcutSources'),false,'Reproduce the warm Vite cache serving the previous local CJS definitions')
 phases.push('Reproduced: a changed local shortcut module stays stale with the existing warm optimizer cache')
 await server.close();server=null
 await start(true)
 const fresh=await optimized();assert.ok(fresh.includes('shortcutSources')&&fresh.includes('shortcutMemories'))
 phases.push('Fixed: startup rebuilds the optimized module and exposes both new actions')
 let restarts=0;const restart=server.restart.bind(server);server.restart=async force=>{restarts++;await restart(force)}
 fs.writeFileSync(modulePath,current.replace("default: 'Mod+Shift+N'","default: 'Mod+Alt+N'"))
 let updated=false
 for(let i=0;i<100;i++){
  await pause(60)
  try{if(restarts&&(await optimized()).includes('Mod+Alt+N')){updated=true;break}}catch{/* A restart briefly closes the owned listening socket. */}
 }
 assert.equal(updated,true);assert.equal(restarts,1)
 phases.push('Fixed: editing the shared shortcut source during development restarts optimization once and serves the changed binding')
 await server.close();server=null
 fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'PASS',phases,restarts},null,2))
 }catch(error){if(server)await server.close().catch(()=>{});fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({status:'FAIL',error:error.stack,phases},null,2));process.exitCode=1}})()
