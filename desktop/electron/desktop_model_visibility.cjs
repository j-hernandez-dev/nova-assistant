const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto')
const valid=names=>Array.isArray(names)&&names.length<=4096&&new Set(names).size===names.length&&names.every(name=>typeof name==='string'&&name.length>0&&name.length<=256&&!/[\s\u0000-\u001f\u007f]/.test(name))
function createModelVisibilityStore(directory){
  const file=path.join(directory,'desktop-model-visibility.json')
  let hidden=[]
  try{if(fs.statSync(file).size<=1024*1024){const data=JSON.parse(fs.readFileSync(file,'utf8'));if(data.schemaVersion===1&&valid(data.hiddenModels))hidden=[...data.hiddenModels]}}catch{}
  return {get:()=>({hiddenModels:[...hidden]}),set(value){
    if(!value||typeof value!=='object'||Object.keys(value).join(',')!=='hiddenModels'||!valid(value.hiddenModels))return {success:false,error:{code:'INVALID_MODEL_VISIBILITY'}}
    const temporary=path.join(directory,'.model-visibility-'+crypto.randomUUID()+'.tmp')
    try{fs.mkdirSync(directory,{recursive:true});fs.writeFileSync(temporary,JSON.stringify({schemaVersion:1,hiddenModels:value.hiddenModels})+'\n',{encoding:'utf8',flag:'wx',mode:0o600});fs.renameSync(temporary,file);hidden=[...value.hiddenModels];return {success:true,preferences:{hiddenModels:[...hidden]}}}
    catch{try{fs.unlinkSync(temporary)}catch{}return {success:false,error:{code:'MODEL_VISIBILITY_SAVE_FAILED'}}}
  }}
}
module.exports={createModelVisibilityStore}
