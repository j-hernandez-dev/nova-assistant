require('./register_typescript.cjs')
const {test} = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')
const {memoryDialogOptions,forwardingDialogOptions,pickerDialogOptions,oauthPage} = require('../electron/desktop_host_locale.cjs')
const {createDesktopPreferencesStore} = require('../electron/desktop_preferences.cjs')
const {desktopMessagesEnglish,desktopMessagesSpanish,desktopAuthErrorKey} = require('../src/desktop_messages_locale.ts')

test('Sensitive memory dialogs translate chrome while retaining exact operation and conservative decision indices',()=>{
  const request={name:'memory_export',workspace:'C:\\owned\\Project',write:false}
  for(const write of [false,true]) {
    const en=memoryDialogOptions('en',{...request,write})
    const es=memoryDialogOptions('es',{...request,write})
    for(const value of [en,es]) {
      assert.equal(value.type,'warning');assert.equal(value.defaultId,0);assert.equal(value.cancelId,0)
      assert.equal(value.noLink,true);assert.equal(value.buttons.length,2)
      assert.ok(value.detail.includes(request.name));assert.ok(value.detail.includes(request.workspace))
      assert.deepEqual(Object.keys(value).sort(),['type','title','message','detail','buttons','defaultId','cancelId','noLink'].sort())
    }
    assert.deepEqual(en.buttons,['Cancel','Allow']);assert.deepEqual(es.buttons,['Cancelar','Permitir'])
    assert.notEqual(en.message,es.message)
    assert.ok(es.detail.includes('no elimina'));assert.ok(en.detail.includes('does not erase'))
  }
})

test('Remote document forwarding keeps distinct explicit host consent in both languages',()=>{
  const en=forwardingDialogOptions('en'),es=forwardingDialogOptions('es')
  assert.deepEqual([es.defaultId,es.cancelId],[en.defaultId,en.cancelId])
  assert.equal(es.buttons[1],'Permitir');assert.equal(en.buttons[1],'Allow')
  assert.ok(es.detail.includes('ni concede permisos'));assert.ok(en.detail.includes('does not enable'))
  assert.ok(es.detail.includes('no pueden recuperarse'));assert.ok(en.detail.includes('cannot be recalled'))
})

test('Host document/project pickers translate only labels and preserve file/directory operation',()=>{
  for(const locale of ['es','en']) {
    assert.deepEqual(pickerDialogOptions(locale,'document').properties,['openFile'])
    assert.deepEqual(pickerDialogOptions(locale,'refresh').properties,['openFile'])
    assert.deepEqual(pickerDialogOptions(locale,'project').properties,['openDirectory'])
    assert.equal(pickerDialogOptions(locale,'export').defaultPath,'nova-source-export.bin')
  }
  assert.equal(pickerDialogOptions('es','project').buttonLabel,'Seleccionar')
  assert.equal(pickerDialogOptions('en','project').buttonLabel,'Select')
})

test('Native dialogs observe the current persisted Desktop language independently of a prior snapshot',t=>{
  const directory=fs.mkdtempSync(path.join(process.env.NOVA_DESKTOP_TEST_TMP||os.tmpdir(),'nova-desktop-locale-test-'))
  t.after(()=>fs.rmSync(directory,{recursive:true,force:true}))
  const store=createDesktopPreferencesStore(directory)
  const before=store.get()
  assert.equal(forwardingDialogOptions(before.locale).buttons[1],'Permitir')
  assert.equal(store.setLocale('en').success,true)
  assert.equal(forwardingDialogOptions(store.get().locale).buttons[1],'Allow')
  assert.equal(forwardingDialogOptions(before.locale).buttons[1],'Permitir')
  assert.equal(createDesktopPreferencesStore(directory).get().locale,'en')
})

test('OAuth callback pages are static localized Desktop chrome without credentials or old product names',()=>{
  for(const locale of ['en','es']) for(const status of ['success','invalid','failed']) {
    const page=oauthPage(locale,status)
    assert.ok(page.includes('lang="'+locale+'"'))
    assert.ok(page.includes('<meta charset="utf-8">'))
    assert.ok(!page.includes('Local CLI'));assert.ok(!page.includes('<script'))
  }
  assert.ok(oauthPage('es','success').includes('volver a Nova'))
  assert.ok(oauthPage('en','success').includes('return to Nova'))
})

test('Desktop-owned authentication errors use complete ES/EN mappings; unknown payloads never become UI messages',()=>{
  assert.deepEqual(Object.keys(desktopMessagesEnglish).sort(),Object.keys(desktopMessagesSpanish).sort())
  for(const [code,key] of [['AUTH_INVALID_KEY','desktopAuthInvalidKey'],['AUTH_TIMEOUT','desktopAuthTimeout'],
    ['AUTH_NETWORK_FAILED','desktopAuthNetwork'],['AUTH_SAVE_FAILED','desktopAuthSaveFailed']]) {
    assert.equal(desktopAuthErrorKey(code),key)
    assert.ok(desktopMessagesSpanish[key]);assert.notEqual(desktopMessagesEnglish[key],desktopMessagesSpanish[key])
  }
  for(const value of ['secret-fixture-key sk-ant-PRIVATE','<script>alert(1)</script>',null,{},'__proto__']) {
    assert.equal(desktopAuthErrorKey(value),'desktopAuthFailed')
    assert.equal(desktopAuthErrorKey(value,'desktopAuthSaveFailed'),'desktopAuthSaveFailed')
  }
})

test('Native language projection is read at display time and does not replace authority handlers',()=>{
  const source=fs.readFileSync(path.join(__dirname,'../electron/main.ts'),'utf8')
  assert.match(source,/memoryControl\(applicationClient[\s\S]*?memoryDialogOptions\(desktopPreferences\.get\(\)\.locale, request\)/)
  assert.match(source,/remoteKnowledge\(applicationClient[\s\S]*?forwardingDialogOptions\(desktopPreferences\.get\(\)\.locale\)/)
  assert.ok(source.includes('createApprovalSurfaceController'))
  assert.ok(source.includes("getLocale: () => desktopPreferences.get().locale"))
  const helper=fs.readFileSync(path.join(__dirname,'../electron/desktop_host_locale.cjs'),'utf8')
  assert.doesNotMatch(helper,/signApproval|ResolveApproval|applicationClient\.command|sendToPython|Grant/)
})
