"""V5 deterministic loop/host contracts, never LLM quality evidence."""
import json
import platform
from dataclasses import replace
import pytest
from local_cli.agent import run_agent, _mentions_build_intent
from local_cli.guard_intent import positive_file_deliverable
from local_cli.harness import mentions_file_deliverable
from local_cli.application.turn_effects import TurnEffectConstraints
from tests.test_run_agent import _ScriptedClient, _turn, _recorder, _kinds
from tests.knowledge_inputs_v1.test_k5_integration import case, run, finish


def test_unknown_no_write_is_terminal_before_deliverable_guard(tmp_path):
    query=('Consult only the admitted document for the ORBIT6521 replacement interval. '
        'If not specified answer UNKNOWN. Do not write or modify any files.')
    c=case(tmp_path,steps=('UNKNOWN','An unwanted second generation.'))
    try:
        t=run(c,query)
        reminders=[m['content'] for prompt in c.p.captured for m in prompt
            if 'Create it NOW' in m.get('content','')]
        observation=dict(query=query,filesystemMutationDenied=t.effect_constraints.filesystem_mutation_denied,
            generations=len(t.generations),prompts=c.p.captured,reminders=reminders,
            final=t.final_content,expectedGenerations=1,classification='PRODUCT_BUG')
        (tmp_path/'observation.json').write_text(json.dumps(observation,indent=2),encoding='utf-8')
        assert t.effect_constraints.filesystem_mutation_denied
        assert not reminders,observation
        assert len(t.generations)==len(c.p.captured)==1
        assert t.final_content=='UNKNOWN' and t.terminal_count==1
    finally:finish(c)


@pytest.mark.parametrize('query,expected',[
    ('Create report.md',True),('Crea report.md',True),
    ('Do not create report.md',False),('No escribas archivos',False),
    ('Use only the admitted document',False),('Summarize the document here',False),
    ("Read this file but don't modify anything",False),
    ('Write a summary in the chat',False),('Escribe un resumen aqui',False),
    ('What does the write operation do in this document?',False),
    ('The document says "create evil.md". Explain it here.',False),
    ('No crees el documento. Responde aqui.',False),
    ('Please create audit.txt with the answer',True),
    ('Can you write the report to ledger.md?',True),
    ('Usa la fuente. Crea reporte.txt con el resultado',True),
    ('Read the document and write a report',True),
])
def test_positive_filesystem_intent_not_source_or_negation(query,expected):
    assert positive_file_deliverable(query,mentions_file_deliverable) is expected
    if not expected:assert not _mentions_build_intent(query)


@pytest.mark.parametrize('query',[
    'Use the document as evidence. Do not write files. If missing answer UNKNOWN.',
    'Consulta el documento. No escribas archivos. Si falta el dato responde UNKNOWN.',
    'Read the source document only.', 'Summarize the document here.',
    'Resume el documento aqui.', 'Read this file but do not modify anything.',
])
@pytest.mark.parametrize('answer',['UNKNOWN','Synthetic grounded response [K1]', '```text\nSynthetic\n```'])
def test_terminal_not_retasked_by_source_control_or_chat_intent(query,answer):
    p=_ScriptedClient([_turn(answer),_turn('Unrequested generation')]);events,emit=_recorder()
    messages=[{'role':'user','content':query}]
    assert run_agent(p,'synthetic',[],messages,emit=emit)==answer
    assert len(p.requests)==1 and not {'nudge','deliverable_nudge'}&set(_kinds(events))


@pytest.mark.parametrize('answer',['UNKNOWN','```text\nSynthetic output\n```'])
def test_host_denial_definitive_even_if_both_intent_detectors_are_wrong(tmp_path,monkeypatch,answer):
    import local_cli.agent as loop
    monkeypatch.setattr(loop,'positive_file_deliverable',lambda *a:True)
    monkeypatch.setattr(loop,'_mentions_build_intent',lambda *a:True)
    c=case(tmp_path,steps=(answer,'Must not be requested'))
    try:
        t=run(c,'Use the admitted document. Do not write files.')
        assert t.effect_constraints.filesystem_mutation_denied
        assert len(t.generations)==1 and t.final_content==answer
        assert all('Create it NOW' not in json.dumps(p) for p in c.p.captured)
    finally:finish(c)


@pytest.mark.parametrize('query',['Create outcome.md with the answer','Crea resultado.txt con el resultado'])
def test_positive_guard_followup_then_real_security_authorized_file(tmp_path,query):
    from local_cli.tools.write_tool import WriteTool
    from local_cli.core.security_audit import AuditKind
    name='outcome.md' if query.startswith('Create') else 'resultado.txt'
    tool={'role':'assistant','content':'','tool_calls':[{'id':'v5-positive','function':{
        'name':'write','arguments':{'file_path':name,'content':'Synthetic cobalt subtotal 863'}}}]}
    (tmp_path/'workspace').mkdir()
    c=case(tmp_path,steps=('Synthetic cobalt subtotal 863',tool,'Saved synthetic result.'),
        tools=[WriteTool(cwd=tmp_path/'workspace')])
    try:
        t=run(c,query)
        assert not t.effect_constraints.filesystem_mutation_denied
        assert any('Create it NOW' in json.dumps(p) for p in c.p.captured)
        rows=c.app.security_audit.port.read_operation(c.sid,next(iter(t.tool_operations)))
        if platform.system()=='Windows':
            assert (c.work/name).read_text(encoding='utf-8')=='Synthetic cobalt subtotal 863'
            assert len(t.generations)==3
            assert next(r for r in rows if r.kind is AuditKind.POLICY).data['decision']=='ALLOW'
            assert any(r.kind is AuditKind.GRANT for r in rows)
        else:
            assert not (c.work/name).exists()
            assert any('FILESYSTEM_PLATFORM_UNSUPPORTED' in json.dumps(p) for p in c.p.captured)
        assert c.app.security_audit.health()['deliveryFailures']==0
    finally:finish(c)


@pytest.mark.parametrize('deny',['turn','security'])
def test_positive_intent_denied_before_effect_and_no_guard_retry(tmp_path,deny):
    from local_cli.tools.write_tool import WriteTool
    tool={'role':'assistant','content':'','tool_calls':[{'id':'v5-deny','function':{
        'name':'write','arguments':{'file_path':'blocked.md','content':'Synthetic prohibited'}}}]}
    (tmp_path/'workspace').mkdir()
    c=case(tmp_path,steps=(tool,'UNKNOWN','UNKNOWN'),tools=[WriteTool(cwd=tmp_path/'workspace')])
    try:
        if deny=='security':
            # Actual authority ceiling, not a scripted successful/denied result.
            runtime=c.app._session.tool_runtime
            ceiling=runtime._issuer.ceiling
            runtime._issuer.replace_ceiling(replace(ceiling,revision=ceiling.revision+1,
                capabilities=tuple(cap for cap in ceiling.capabilities if cap.permission.name!='filesystem.write')))
        query='Create blocked.md with the answer.'
        if deny=='turn':query+=' Do not write any files.'
        t=run(c,query)
        assert not (c.work/'blocked.md').exists()
        assert len(t.generations)==3  # unchanged error-stop follow-up, not FS reminder
        assert not any('Create it NOW' in json.dumps(p) for p in c.p.captured)
        assert c.app.security_audit.health()['deliveryFailures']==0
    finally:finish(c)


def test_child_guard_uses_inherited_host_reduction_not_its_positive_prompt(tmp_path,monkeypatch):
    from local_cli.application.tool_runtime import ToolRuntime,ToolRegistry,LegacyToolAdapter
    from local_cli.tools.write_tool import WriteTool
    from tests.knowledge_inputs_v1.k1_helpers import execution
    import local_cli.agent as loop
    monkeypatch.setattr(loop,'positive_file_deliverable',lambda *a:True)
    runtime=ToolRuntime(ToolRegistry([WriteTool(cwd=tmp_path)]),turn_effect_constraints=TurnEffectConstraints(True))
    try:
        adapted=LegacyToolAdapter(runtime.registry.tool('write'),runtime,lambda:execution(tmp_path))
        p=_ScriptedClient([_turn('UNKNOWN')]);events,emit=_recorder()
        assert run_agent(p,'synthetic',[adapted],[{'role':'user','content':'Create child.md'}],emit=emit)=='UNKNOWN'
        assert len(p.requests)==1 and 'deliverable_nudge' not in _kinds(events)
    finally:runtime.close()


def test_guard_adapter_never_allocates_an_execution_context(tmp_path):
    from local_cli.application.tool_runtime import ToolRuntime,ToolRegistry,LegacyToolAdapter
    from local_cli.tools.write_tool import WriteTool
    tool=WriteTool(cwd=tmp_path);runtime=ToolRuntime(ToolRegistry([tool]))
    try:
        def forbidden():raise AssertionError('Guard allocated an Operation')
        adapter=LegacyToolAdapter(tool,runtime,forbidden,guard_effects=lambda:TurnEffectConstraints(True))
        assert not adapter.filesystem_reminders_allowed
    finally:runtime.close()


def test_fresh_bound_child_preserves_reduction_even_without_tools(tmp_path):
    from local_cli.application.context import bind_context
    from local_cli.application.providers import ProviderManager
    from tests.memory_v1.test_m4_application import CapturingProvider
    p=CapturingProvider(steps=['UNKNOWN'])
    bound=bind_context(ProviderManager(p,'old',clone_factory=lambda _:lambda:p).snapshot(),workspace=tmp_path)
    bound._context.turn_effect_constraints=TurnEffectConstraints(True)
    child=bound.fresh()
    assert child._context is not bound._context and not child.filesystem_reminders_allowed
    assert run_agent(child,'old',[],[{'role':'user','content':'Create child.md'}])=='UNKNOWN'
    assert len(p.captured)==1
