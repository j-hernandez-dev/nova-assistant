// Fixed test stimuli only. No generic product eval/JS/selector authority.
internal static class Scripts
{
    internal const string Sw="""
importScripts('/sw-import.js');
fetch('/worker-executed');
self.addEventListener('install',e=>e.waitUntil(caches.open('probe').then(c=>c.put('/cached',new Response('fixture-cache'))).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
self.addEventListener('message',e=>e.ports[0]?.postMessage({executed:true,importExecuted:self.importWasExecuted===true}));
self.addEventListener('fetch',e=>{if(new URL(e.request.url).pathname==='/cached'){e.respondWith(caches.match('/cached'));fetch('/worker-fetch');}});
""";
    internal const string Worker="""
(async()=>{
const result={secure:isSecureContext,apiPresent:!!navigator.serviceWorker,registered:false,active:false,errorName:null};
try{const reg=await navigator.serviceWorker.register('/sw.js');result.registered=true;
await Promise.race([navigator.serviceWorker.ready,new Promise((_,reject)=>setTimeout(()=>reject(new Error('bounded')),4000))]);result.active=!!reg.active;
}catch(e){result.errorName=e.name;}return result;
})()
""";
    internal const string WorkerAfterReload="""
(async()=>{let text='';try{text=await (await fetch('/cached')).text();}catch{}let execution=null;
if(navigator.serviceWorker.controller){execution=await Promise.race([new Promise(resolve=>{let ch=new MessageChannel();ch.port1.onmessage=e=>resolve(e.data);navigator.serviceWorker.controller.postMessage('controlled-report',[ch.port2]);}),new Promise(resolve=>setTimeout(()=>resolve({reportTimeout:true}),1000))]);}
return {controller:!!navigator.serviceWorker?.controller,cacheResponse:text==='fixture-cache',execution,registrations:(await navigator.serviceWorker.getRegistrations()).length};})()
""";
    internal static string Rtc(int port)=>"""
(async()=>{
const r={secure:isSecureContext,apiPresent:typeof RTCPeerConnection==='function',constructed:false,dataChannel:false,offer:false,iceStarted:false,iceCandidates:0,iceErrors:0,errorName:null};
let pc;try{pc=new RTCPeerConnection({iceServers:[{urls:'stun:127.0.0.1:PORT'}]});r.constructed=true;
pc.onicecandidate=e=>{if(e.candidate)r.iceCandidates++};pc.onicecandidateerror=()=>r.iceErrors++;
pc.createDataChannel('controlled-probe');r.dataChannel=true;const offer=await pc.createOffer();r.offer=true;
await pc.setLocalDescription(offer);r.iceStarted=pc.iceGatheringState!=='new';
await Promise.race([new Promise(resolve=>pc.onicegatheringstatechange=()=>{if(pc.iceGatheringState==='complete')resolve()}),new Promise(resolve=>setTimeout(resolve,2000))]);
}catch(e){r.errorName=e.name;}finally{pc?.close();}return r;
})()
""".Replace("PORT",port.ToString());
    internal const string Logical="""
(async()=>{const r={};
try{r.fetchStatus=(await fetch('https://c.nova-fixture.test/denied-fetch')).status;}catch(e){r.fetchError=e.name;}
r.xhr=await new Promise(resolve=>{const x=new XMLHttpRequest();x.open('GET','https://c.nova-fixture.test/denied-xhr');x.onload=()=>resolve(x.status);x.onerror=()=>resolve('error');x.send();});
r.image=await new Promise(resolve=>{const i=new Image();i.onload=()=>resolve('load');i.onerror=()=>resolve('error');i.src='https://c.nova-fixture.test/denied-image';document.body.append(i);});
r.iframe=await new Promise(resolve=>{const f=document.createElement('iframe');f.onload=()=>resolve('event');f.src='https://c.nova-fixture.test/denied-frame';document.body.append(f);setTimeout(()=>resolve('bounded'),1000);});
return r;})()
""";
    internal const string SecondOrigin="""
(async()=>{const r={};r.first=(await fetch('/first')).status;r.sameConnectionCandidate=(await fetch('/second')).status;r.secondOrigin=(await fetch('https://b.nova-fixture.test/second-origin')).status;return r;})()
""";
    internal const string RepeatedFetch="""
(async()=>{const r=[];for(let i=0;i<3;i++)r.push((await fetch('/h3-'+i)).status);return {requests:r};})()
""";
}
