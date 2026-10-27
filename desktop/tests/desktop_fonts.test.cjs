const {test}=require('node:test'),assert=require('node:assert/strict')
const {createDesktopFontService,fontFamilies}=require('../electron/desktop_fonts.cjs')
test('Font inventories contain bounded, deduplicated human family names for each OS',()=>{
  assert.deepEqual(fontFamilies('["Segoe UI","Consolas","segoe ui","Bad\\nFont",""]','win32'),['Consolas','Segoe UI'])
  assert.deepEqual(fontFamilies('Noto Sans,Noto Sans CJK JP\nDejaVu Sans\nNoto Sans\n','linux'),['DejaVu Sans','Noto Sans','Noto Sans CJK JP'])
  assert.deepEqual(fontFamilies('\uFEFF["Menlo","SF Pro"]','darwin'),['Menlo','SF Pro'])
  for(const output of ['not-json','{}','[]'])assert.throws(()=>fontFamilies(output,'win32'))
})
test('Enumeration is read-only, bounded, shared in flight and cached with immutable snapshots',async()=>{
  for(const platform of ['win32','darwin','linux']){
    let calls=0,complete
    const service=createDesktopFontService({platform,execFile:(file,args,options,callback)=>{calls++;assert.equal(options.windowsHide,true);assert.equal(options.shell,false);assert.equal(options.timeout,15000);assert.equal(options.maxBuffer,4*1024*1024);assert.ok(file.includes(platform==='win32'?'powershell':platform==='darwin'?'osascript':'fc-list'));assert.ok(args.every(arg=>typeof arg==='string'));complete=()=>callback(null,platform==='linux'?'Ubuntu\nUbuntu Mono\n':'["Alpha","Beta"]')}})
    const first=service.get(),second=service.get();assert.equal(calls,1);complete();const [a,b]=await Promise.all([first,second]);assert.equal(a.success,true);a.fonts.length=0;assert.equal(b.fonts.length,2);assert.equal((await service.get()).fonts.length,2);assert.equal(calls,1)
  }
})
test('Command errors and malformed inventories return bounded failures and permit retry',async()=>{
  let calls=0
  const service=createDesktopFontService({platform:'linux',execFile:(_file,_args,_options,callback)=>{calls++;callback(calls===1?new Error('private path must not escape'):null,calls===1?'':'DejaVu Sans\n')}})
  const result=await service.get();assert.equal(result.success,false);assert.equal(result.error.code,'DESKTOP_FONTS_UNAVAILABLE');assert.doesNotMatch(result.error.message,/private path/)
  assert.equal((await service.get()).success,true);assert.equal(calls,2)
  const unsupported=createDesktopFontService({platform:'other'});assert.equal((await unsupported.get()).success,false)
})
