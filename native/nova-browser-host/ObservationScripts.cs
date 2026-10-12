namespace NovaBrowserHost;

// Versioned, fixed Infrastructure code. No caller script/selector is interpolated.
// Runs in a CDP isolated world; page globals cannot replace the inspection code.
internal static class ObservationScripts
{
    public const string Version = "nova-wv2-observation-4-leaves";
    public const string Nodes = "Array.from(document.querySelectorAll('a[href],button,input,textarea,select,form,[role=button],[role=link]')).slice(0,128)";
    public const string MetaBody = """
const e=this, tag=e.tagName?.toLowerCase()||'', type=(e.getAttribute('type')||'').toLowerCase();
const labelIds=(e.getAttribute('aria-labelledby')||'').split(/\s+/).filter(Boolean).slice(0,16);
const leaves = n => {let w=document.createTreeWalker(n,NodeFilter.SHOW_TEXT),v=[],t,k=0,total=0;while((t=w.nextNode())){if(++k>4096)throw new Error('OBSERVATION_LIMIT');let p=t.parentElement;if(p?.closest('script,style,template,noscript,input,textarea,[hidden],[aria-hidden=true]')||!p?.getClientRects().length||getComputedStyle(p).visibility==='hidden')continue;const s=t.textContent||'';if(!s.length)continue;total+=s.length;if(s.length>16384||total>16384||v.length>=1024)throw new Error('OBSERVATION_LIMIT');v.push({kind:'LABEL',text:s});}return v;};
const aria=e.getAttribute('aria-label');let nameLeaves=aria?[{kind:'LABEL',text:aria}]:labelIds.flatMap(id=>{const n=document.getElementById(id);return n?leaves(n):[];});
if(!nameLeaves.some(l=>l.text.trim()))nameLeaves=Array.from(e.labels||[]).slice(0,8).flatMap(leaves);
if(!nameLeaves.some(l=>l.text.trim()))nameLeaves=leaves(e);
if(nameLeaves.length>1024||nameLeaves.reduce((n,l)=>n+l.text.length,0)>16384)throw new Error('OBSERVATION_LIMIT');
const name=nameLeaves.map(l=>l.text).join(' ').trim();
if(name.length>16384)throw new Error('OBSERVATION_LIMIT');
const form=tag==='form'?e:e.form;
const secret=['input','textarea','select'].includes(tag)&&(['password','hidden'].includes(type)||/password|passwd|otp|one.time|recovery|card|cvv|private.?key|token|secret/i.test([e.name,e.id,e.autocomplete,name,e.getAttribute('data-sensitivity-hint')].join(' ')));
const credentialForm=!!form?.querySelector('input[type=password],input[autocomplete=one-time-code],input[autocomplete^=cc-]');
const visible=e.isConnected&&!!e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden'&&!e.closest('[hidden],[aria-hidden=true]');
const disabled=!!e.disabled||e.getAttribute('aria-disabled')==='true',readonly=!!e.readOnly;
const kind=tag==='input'?(type||'text'):tag;
let caps=[];
if(visible&&!secret&&!disabled&&!readonly&&!credentialForm){
 if(tag==='a')caps=/^https?:/i.test(e.href)?['CLICK','NAVIGATE','PRESS_KEY','DOWNLOAD']:['CLICK','PRESS_KEY'];
 else if(tag==='input'&&kind==='file')caps=['UPLOAD_FILE'];
 else if(tag==='input'&&['text','search','email','url','tel','number'].includes(kind)||tag==='textarea')caps=['INPUT_TEXT','PRESS_KEY'];
 else if(tag==='input'&&['checkbox','radio','button','submit'].includes(kind)||tag==='button'||['button','link'].includes(e.getAttribute('role')))caps=['CLICK','PRESS_KEY'];
 else if(tag==='select')caps=['SELECT_OPTION'];
 else if(tag==='form')caps=['FORM_SUBMIT'];
}
const cleanUrl=value=>{try{const u=new URL(value,location.href);if(!['http:','https:'].includes(u.protocol))return null;u.username='';u.password='';u.search='';u.hash='';return u.href;}catch{return null;}};
return {tag,kind,name,nameLeaves,role:e.getAttribute('role')||({a:'link',button:'button',input:['checkbox','radio'].includes(kind)?kind:'textbox',textarea:'textbox',select:'combobox',form:'form'}[tag]||tag),
 href:tag==='a'?cleanUrl(e.href):null,formAction:form?cleanUrl(form.action):null,formMethod:form?.method||null,
 connected:e.isConnected,visible,disabled,readonly,secret,credentialForm,caps,state:disabled?'disabled':readonly?'readonly':kind==='checkbox'||kind==='radio'?(e.checked?'checked':'unchecked'):'enabled',
 destinationIdentity:tag==='a'?(e.getAttribute('href')||''):form?(form.getAttribute('action')||''):null};
""";
    public const string Meta = "function(){" + MetaBody + "}";
    public const string Summary = """
(function(){let w=document.createTreeWalker(document.body||document.documentElement,NodeFilter.SHOW_TEXT),leaves=[],n,k=0,total=0;while((n=w.nextNode())){if(++k>20000)throw new Error('OBSERVATION_LIMIT');let p=n.parentElement;if(!p||p.closest('script,style,template,noscript,input,textarea,[hidden],[aria-hidden=true]')||!p.getClientRects().length||getComputedStyle(p).visibility==='hidden')continue;const text=n.textContent||'';if(!text.length)continue;total+=text.length;if(text.length>32768||total>32768||leaves.length>=1024)throw new Error('OBSERVATION_LIMIT');leaves.push({kind:'TEXT',text});}if(document.title.length>16384)throw new Error('OBSERVATION_LIMIT');return {title:document.title,leaves,truncated:false};})()
""";
    public const string Matches = "const matches=(m,expected)=>{const q=JSON.parse(expected);return Object.keys(m).length===Object.keys(q).length&&Object.keys(m).every(k=>JSON.stringify(m[k])===JSON.stringify(q[k]));};";
    public const string Perform = "function(args){"+Matches+"const get=function(){"+MetaBody+"};const m=get.call(this);if(!matches(m,args.expected)||!m.connected||!m.visible||!m.caps.includes(args.action))return {stale:true};const e=this;" + """
switch(args.action){
case 'CLICK': e.click();break;
case 'INPUT_TEXT': {const prototype=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(prototype,'value').set.call(e,args.payload);e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));break;}
case 'SELECT_OPTION': {if(!Array.from(e.options).some(o=>o.value===args.payload&&!o.disabled))return {noEffect:true};Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(e,args.payload);e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));break;}
case 'FORM_SUBMIT': e.requestSubmit();break;
case 'NAVIGATE': {if(!m.href||m.href!==args.destination)return {noEffect:true};location.href=m.href;break;}
default:return {noEffect:true};
}return {performed:true};}
""";
    public const string Submit="function(args,...fields){"+Matches+"const get=function(){"+MetaBody+"};const m=get.call(this);if(!matches(m,args.expected)||!m.caps.includes('FORM_SUBMIT'))return {stale:true};for(let i=0;i<fields.length;i++){const f=fields[i],fm=get.call(f);if(f.form!==this||!matches(fm,args.fieldMeta[i])||!fm.caps.includes('INPUT_TEXT'))return {stale:true};}for(let i=0;i<fields.length;i++){const f=fields[i],fm=get.call(f);if(!matches(fm,args.fieldMeta[i])||f.form!==this)return i?{partial:true}:{stale:true};const p=f.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,'value').set.call(f,args.values[i]);f.dispatchEvent(new Event('input',{bubbles:true}));f.dispatchEvent(new Event('change',{bubbles:true}));}if(!matches(get.call(this),args.expected))return fields.length?{partial:true}:{stale:true};this.requestSubmit();return {performed:true};}";
}
