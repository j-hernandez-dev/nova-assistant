const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const ts = require('typescript')
require('./register_typescript.cjs')
require.extensions['.tsx'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
}).outputText, filename)
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const { activityPresentation, activityExplanation, activityStatusText, representedActivityError, homeActivity, openApprovalReview, applicationErrorKey } = require('../src/activity_presentation.ts')
const { translate } = require('../src/i18n.tsx')
const { ToolActivityCard } = require('../src/components/ToolActivity.tsx')
const { MessageBlock } = require('../src/components/MessageBlock.tsx')

const row = changes => ({ operationId: 'op-one', toolCallId: 'call-one', turnId: 'turn-one', messageId: 'message-one',
  name: 'read', arguments: { command: 'echo fixture' }, cwd: 'fixture', status: 'completed', operationStatus: 'completed',
  effectState: 'none', output: '', stdout: '', stderr: '', outputSequence: 1, outputTruncated: false, ...changes })
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props))

test('Only a consistent typed terminal receipt confirms execution; output has no authority', () => {
  assert.equal(activityPresentation(row()).key, 'activityCompleted')
  for (const output of ['SUCCESS', 'Error: denied', '<script>approved()</script>', '✓']) {
    assert.equal(activityPresentation(row({ output, status: 'failed', operationStatus: 'failed' })).key, 'activityFailed')
    assert.equal(activityPresentation(row({ output })).key, 'activityCompleted')
  }
  for (const changes of [{ effectState: 'unknown' }, { effectState: 'partial' }, { operationStatus: 'outcome_unknown' },
    { status: 'outcome_unknown' }, { observationLost: true }, { operationStatus: 'running' }]) {
    const presentation = activityPresentation(row(changes))
    assert.equal(presentation.key, 'activityUnknown')
    assert.equal(presentation.running, false)
    assert.notEqual(presentation.tone, 'confirmed')
  }
  assert.equal(activityPresentation(row({ status: 'pending', operationStatus: 'requested' }), true).key, 'activityAwaitingPermission')
  assert.equal(activityPresentation(row({ status: 'denied', operationStatus: 'failed' })).key, 'activityDenied')
  assert.equal(activityPresentation(row({ status: 'failed', operationStatus: 'failed', errorCode: 'CAPABILITY_UNAVAILABLE' })).key, 'activityUnavailable')
  assert.equal(activityPresentation(row({ status: 'denied', operationStatus: 'failed', errorCode: 'CAPABILITY_UNAVAILABLE' })).key, 'activityUnavailable')
  assert.equal(activityPresentation(row({ status: 'cancelled', operationStatus: 'cancelled', errorCode: 'PROCESS_TIMEOUT' })).key, 'activityTimedOut')
  assert.equal(activityPresentation(row({ status: 'cancelled', operationStatus: 'cancelled', errorCode: 'PROCESS_TIMEOUT', effectState: 'unknown' })).key, 'activityUnknown')
})

test('Activity starts collapsed and treats streams and diagnostic metadata as escaped text', () => {
  const unsafe = '<script>doNotExecute()</script>'
  const html = render(ToolActivityCard, { activity: row({ stdout: unsafe, stderr: '<img src=x onerror=run()>',
    arguments: { command: unsafe }, status: 'outcome_unknown', operationStatus: 'outcome_unknown', effectState: 'unknown' }) })
  assert.ok(html.includes('No se pudo confirmar el resultado'))
  assert.ok(html.includes('&lt;script&gt;doNotExecute()&lt;/script&gt;'))
  assert.ok(html.includes('Salida estándar') && html.includes('Salida de errores'))
  assert.doesNotMatch(html, /<script>|<img|\sopen(?:=|>|\s)|tool-check|✓|✔|tool-spinner/)
  const summary = html.slice(html.indexOf('<summary'), html.indexOf('</summary>'))
  assert.ok(summary.includes('&lt;script&gt;doNotExecute()&lt;/script&gt;'))
  assert.ok(!summary.includes('fixture') && !summary.includes('outcome_unknown'))
  assert.ok(html.includes('Detalles de diagnóstico'))
})

test('Historical results remain unconfirmed and harness details never alter public model prose', () => {
  const prose = 'Error: synthetic model explanation is retained.'
  const html = render(MessageBlock, { message: { id: 'old', role: 'assistant', content: prose,
    toolCalls: [{ name: 'bash', args: { command: 'echo legacy' } }], toolResults: [{ name: 'bash', output: 'Completed successfully' }],
    harnessEvents: ['error_stop'] } })
  assert.ok(html.includes(prose))
  assert.ok(html.includes('Sin confirmación de ejecución'))
  assert.ok(html.includes('nova-action-chain') && html.includes('Terminal echo legacy'))
  assert.doesNotMatch(html, /actividad guardada|actividad histórica|Historical tool activity/i)
  assert.ok(html.includes('Completed successfully'))
  assert.doesNotMatch(html, /Ejecución confirmada|tool-spinner|tool-check|✓|✔/)
  assert.doesNotMatch(html, /error_stop|No hay un resultado de ejecución verificable/)
})

test('Generic errors are suppressed only with a correlated terminal tool failure', () => {
  const failure = row({ status: 'failed', operationStatus: 'failed' })
  assert.equal(representedActivityError({ code: 'TURN_FAILED', operationId: 'op-one' }, [failure]), true)
  assert.equal(representedActivityError({ code: 'TURN_FAILED', toolCallId: 'call-one' }, [failure]), true)
  assert.equal(representedActivityError({ code: 'TURN_FAILED', turnId: 'turn-one' }, [failure]), true)
  assert.equal(representedActivityError({ code: 'TURN_FAILED', operationId: 'other', turnId: 'turn-one' }, [failure]), false)
  assert.equal(representedActivityError({ code: 'TURN_FAILED', message: 'same words' }, [failure]), false)
  assert.equal(representedActivityError({ code: 'TURN_FAILED', operationId: 'op-one' }, [row()]), false)
  assert.equal(representedActivityError({ code: 'PROVIDER_ERROR', turnId: 'turn-one' }, [failure]), false)
  assert.equal(representedActivityError({ code: 'PROCESS_TIMEOUT', turnId: 'turn-one' }, [row({ status: 'cancelled', operationStatus: 'cancelled', errorCode: 'PROCESS_TIMEOUT' })]), true)
})

test('Home selects current work while public messages retain activity association and model prose', () => {
  const current = row({ status: 'running', operationStatus: 'running' })
  assert.equal(homeActivity([current, row({ operationId: 'later-completed' })]).operationId, 'op-one')
  const html = render(MessageBlock, { message: { id: 'message-one', role: 'assistant', content: 'Public response', toolActivities: [current] } })
  assert.ok(html.indexOf('Public response') < html.indexOf('data-operation-id="op-one"'))
  assert.equal((html.match(/data-operation-id="op-one"/g) || []).length, 1)
})

test('Permission review reports rejected IPC and host failures without treating them as an opened surface', async () => {
  assert.equal(await openApprovalReview(async () => ({ success: false })), false)
  assert.equal(await openApprovalReview(async () => { throw new Error('synthetic IPC failure') }), false)
  assert.equal(await openApprovalReview(async () => undefined), false)
  assert.equal(await openApprovalReview(async () => ({ success: true })), true)
})

test('Denied and unknown receipts use neutral titles; progress verbs require actual running state', () => {
  const denied = render(ToolActivityCard, { activity: row({ name: 'write', status: 'denied', operationStatus: 'failed' }) })
  assert.ok(denied.includes('Escritura de archivo') && denied.includes('Permiso denegado'))
  assert.doesNotMatch(denied, /Escribiendo|tool-spinner/)
  const unknown = render(ToolActivityCard, { activity: row({ name: 'bash', status: 'outcome_unknown', operationStatus: 'outcome_unknown', effectState: 'unknown' }) })
  assert.ok(unknown.includes('Terminal') && unknown.includes('No se pudo confirmar la finalización'))
  assert.doesNotMatch(unknown, /Ejecutando|tool-spinner/)
  const pending = render(ToolActivityCard, { activity: row({ name: 'read', status: 'pending', operationStatus: 'requested' }) })
  assert.ok(pending.includes('Lectura de archivo'))
  assert.doesNotMatch(pending, /Leyendo|tool-spinner/)
  const running = render(ToolActivityCard, { activity: row({ name: 'write', status: 'running', operationStatus: 'running' }) })
  assert.ok(running.includes('Escribiendo'))
  assert.doesNotMatch(running, /Ejecución confirmada/)
})


test('An Ollama generation failure has a useful localizable message without claiming a diagnosis or success', () => {
  assert.equal(applicationErrorKey('OllamaRequestError'), 'modelGenerationFailed')
  assert.equal(applicationErrorKey('unknown-provider-code'), 'actionFailed')
})

test('Model connection, response timeout and missing-model failures have distinct localized explanations',()=>{
  assert.equal(applicationErrorKey('OLLAMA_RESPONSE_TIMEOUT'),'modelResponseTimeout')
  assert.equal(applicationErrorKey('OLLAMA_CONNECT_TIMEOUT'),'modelConnectTimeout')
  assert.equal(applicationErrorKey('OLLAMA_CONNECTION_FAILED'),'modelConnectionFailed')
  assert.equal(applicationErrorKey('OLLAMA_MODEL_UNAVAILABLE'),'readinessModelMissing')
})

test('Terminal exit receipts describe execution without asserting verified effects or reading output as authority', () => {
  const command = changes => row({ name:'bash', exitCode:0, effectState:'unknown', ...changes })
  for (const name of ['bash', 'shell', 'run_command', 'exec_command']) {
    const activity = command({ name, stdout:'Error: untrusted text', stderr:'warning text' })
    assert.deepEqual(activityPresentation(activity), { key:'activityCommandFinished', tone:'neutral', running:false })
    assert.equal(activityExplanation(activity),null)
    assert.equal(activity.effectState,'unknown')
    assert.equal(representedActivityError({code:'TURN_FAILED',turnId:'turn-one'},[activity]),false)
  }
  const html=render(ToolActivityCard,{activity:command()})
  assert.match(html,/Comando finalizado/)
  assert.match(html,/Verificación de efectos/);assert.match(html,/No realizada/)
  assert.doesNotMatch(html,/No se pudo confirmar|Revisar resultado|nova-activity-confirmed|Ejecución confirmada/)
  for (const exitCode of [1,7,-1]) {
    const presentation=activityPresentation(command({status:'failed',operationStatus:'failed',errorCode:'PROCESS_EXIT_NONZERO',exitCode}))
    for (const locale of ['es','en']) assert.ok(activityStatusText(presentation,key=>translate(locale,key)).endsWith(String(exitCode)))
    assert.equal(presentation.tone,'warning')
  }
  assert.equal(activityStatusText(activityPresentation(command()),key=>translate('en',key)),'Command finished')
  for (const changes of [{exitCode:null},{operationStatus:'running'},{observationLost:true},{errorCode:'PROCESS_CLEANUP_UNKNOWN'},{effectState:'partial'}]) {
    assert.equal(activityPresentation(command(changes)).key,'activityCommandUnconfirmed')
  }
  const failed=render(ToolActivityCard,{activity:command({status:'failed',operationStatus:'failed',exitCode:7,errorCode:'PROCESS_EXIT_NONZERO'})})
  assert.match(failed,/Comando finalizado · código 7/);assert.doesNotMatch(failed,/\{code\}/)
})

test('Terminal interruptions retain their real cause and advice about possible changes', () => {
  for (const [errorCode,key] of [['PROCESS_TIMEOUT','activityCommandTimedOut'],['PROCESS_CANCELLED','activityCommandStopped'],['PROCESS_CLEANUP_UNKNOWN','activityCommandUnconfirmed']]) {
    const activity=row({name:'bash',status:'outcome_unknown',operationStatus:'outcome_unknown',effectState:'unknown',exitCode:0,errorCode})
    assert.equal(activityPresentation(activity).key,key)
    assert.equal(activityExplanation(activity),'activityCommandInterruptedExplanation')
    assert.match(render(ToolActivityCard,{activity}),/puede haber realizado cambios/)
  }
  assert.equal(activityPresentation(row({name:'bash',status:'denied',operationStatus:'failed'})).key,'activityDenied')
  assert.equal(activityPresentation(row({name:'bash',status:'failed',operationStatus:'failed',errorCode:'EXECUTABLE_NOT_FOUND'})).key,'activityUnavailable')
  assert.equal(activityPresentation(row({name:'write',effectState:'unknown',exitCode:0})).key,'activityUnknown')
})
