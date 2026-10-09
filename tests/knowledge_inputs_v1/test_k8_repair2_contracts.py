"""V2 intent/effect contracts and actual parser-backed JSON lineage."""
from dataclasses import replace
from types import SimpleNamespace
import json
import pytest
from local_cli.application.turn_effects import resolve_turn_effects, TurnEffectConstraints, TurnEffectDenied
from local_cli.application.tool_runtime import ToolRuntime, ToolRegistry
from local_cli.core.contracts import ToolInvocation, ToolStatus, EffectState, EventKind, new_tool_call_id
from local_cli.core.context import TokenCounter
from local_cli.core.knowledge_chunking import HARD
from local_cli.infrastructure.knowledge_extraction import extract_bytes
from local_cli.infrastructure.knowledge_lexical import documentary_terms
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from local_cli.tools.write_tool import WriteTool
from local_cli.tools.edit_tool import EditTool
from tests.knowledge_inputs_v1.k1_helpers import execution
from tests.knowledge_inputs_v1.k4_helpers import publish_text


@pytest.mark.parametrize('text',[
    'Do not write files.','Please do not modify anything.','Never delete documents.',
    "Don't create files.",'No escribas archivos.','No modifiques nada.',
    'No borres archivos.','Por favor no cambies nada.',
    'Do not write files; create output.txt anyway.', 'No files should be written.',
    'Files must not be modified.'])
def test_trusted_imperative_denies(text):
    assert resolve_turn_effects(text).filesystem_mutation_denied


@pytest.mark.parametrize('text',[
    'Create report.md.','Crea report.md.', 'The manual says "do not write files".',
    '`No modifiques nada` is a code example.', '> Do not write files\nExplain this quotation.',
    'Do not write personal MEMORY.'])
def test_data_and_non_filesystem_request_do_not_grant_or_deny(text):
    assert not resolve_turn_effects(text).filesystem_mutation_denied


@pytest.mark.parametrize('name,args',[
    ('write',{'file_path':'kept.txt','content':'tampered'}),
    ('edit',{'file_path':'kept.txt','old_string':'original','new_string':'tampered'})])
def test_runtime_denies_before_effect_idempotent_no_grants(tmp_path,name,args):
    work=tmp_path/'work';work.mkdir();(work/'kept.txt').write_text('original')
    outside=tmp_path/'sentinel';outside.write_text('outside')
    ctx=execution(work,turn_id='turn-v2');events=[]
    runtime=ToolRuntime(ToolRegistry([WriteTool(cwd=work),EditTool(cwd=work)]),publish=events.append)
    try:
        runtime.install_authority(work,ctx.session_id);before=runtime._issuer.ceiling.fingerprint
        runtime.bind_turn_effects(ctx.session_id,ctx.turn_id,resolve_turn_effects('No modifiques nada.'))
        inv=ToolInvocation(name,args,new_tool_call_id(),ctx.operation_id,ctx)
        result=runtime.execute(inv)
        assert result.status is ToolStatus.DENIED and result.effect_state is EffectState.NONE
        assert result.metadata['turnConstraintCode']=='TURN_FILESYSTEM_MUTATION_DENIED'
        assert runtime.execute(inv)==result
        assert [e[0] for e in events]==[EventKind.TOOL_REQUESTED,EventKind.TOOL_FAILED]
        assert (work/'kept.txt').read_text()=='original' and outside.read_text()=='outside'
        assert runtime._issuer.ceiling.fingerprint==before
        assert not runtime._issuer._issued
        with pytest.raises(ValueError,match='IMMUTABLE'):
            runtime.bind_turn_effects(ctx.session_id,ctx.turn_id,TurnEffectConstraints())
    finally:runtime.close()


def test_unrestricted_is_not_security_authority_and_child_cannot_lift():
    effect=SimpleNamespace(effect='filesystem.write')
    resolve_turn_effects('create report.md').check(effect) # no grant issued
    parent=resolve_turn_effects('Do not write files.')
    with pytest.raises(TurnEffectDenied):parent.check(effect)
    with pytest.raises(TurnEffectDenied):parent.check(SimpleNamespace(effect='process.execute.HOST_UNISOLATED'))
    parent.check(SimpleNamespace(effect='filesystem.read'))


def test_inherited_constraint_cannot_be_lifted_by_child_binding(tmp_path):
    ctx=execution(tmp_path,turn_id='child-turn')
    runtime=ToolRuntime(ToolRegistry([WriteTool(cwd=tmp_path)]),
        turn_effect_constraints=resolve_turn_effects('Do not write files.'))
    try:
        runtime.bind_turn_effects(ctx.session_id,ctx.turn_id,TurnEffectConstraints())
        result=runtime.execute(ToolInvocation('write',{'file_path':'child.txt','content':'data'},
            new_tool_call_id(),ctx.operation_id,ctx))
        assert result.status is ToolStatus.DENIED and result.effect_state is EffectState.NONE
        assert not (tmp_path/'child.txt').exists() and not runtime._issuer._issued
    finally:runtime.close()


def test_allowed_turn_cannot_expand_security(tmp_path):
    from local_cli.core.security import AuthorityCeiling
    from local_cli.application.grants import GrantIssuer
    ctx=execution(tmp_path,turn_id='allowed-turn')
    runtime=ToolRuntime(ToolRegistry([WriteTool(cwd=tmp_path)]))
    try:
        runtime.install_authority(tmp_path,ctx.session_id)
        old=runtime._issuer.ceiling
        restricted=AuthorityCeiling(old.ceiling_id,old.revision,
            tuple(c for c in old.capabilities if c.permission.name!='filesystem.write'))
        runtime._issuer=GrantIssuer(restricted,policy_revision=runtime.policy.revision)
        runtime.bind_turn_effects(ctx.session_id,ctx.turn_id,resolve_turn_effects('Create report.md.'))
        result=runtime.execute(ToolInvocation('write',{'file_path':'report.md','content':'data'},
            new_tool_call_id(),ctx.operation_id,ctx))
        assert result.status is ToolStatus.DENIED and result.effect_state is EffectState.NONE
        assert result.metadata['securityErrorCode']=='RESOURCE_SCOPE_VIOLATION'
        assert not (tmp_path/'report.md').exists() and not runtime._issuer._issued
    finally:runtime.close()


@pytest.mark.parametrize('tail',[
    'If the evidence does not contain the answer, respond UNKNOWN.',
    'Unless the source supplies the answer, say UNKNOWN.',
    'Si el dato no aparece en la fuente, responde UNKNOWN.',
    'Usa las citas proporcionadas. No modifiques nada.',
    'Use the provided citation markers. Do not write files.'])
def test_control_clause_separation_not_observed_word_stoplist(tail):
    assert documentary_terms('VAULT759 insulation. '+tail)==('vault759','insulation')


def test_factual_conditions_are_not_erased():
    assert 'pressure' in documentary_terms('If pressure is high, which valve setting is documented?')


def test_json_objects_keep_sibling_association_and_real_escaped_pointer(tmp_path):
    data={'a/b~c':[{'key':'UNIT782','finish':'blue cork'},{'key':'UNIT783','finish':'black felt'}]}
    payload=extract_bytes(json.dumps(data).encode(),'objects.json')
    assert [b[2].coordinates['pointer'] for b in payload.blocks]==['/a~1b~0c/0','/a~1b~0c/1']
    assert all('key' in b[1] and 'finish' in b[1] for b in payload.blocks)
    with SQLiteKnowledgeStore(tmp_path/'store') as store:
        _,prepared=publish_text(store,json.dumps(data),filename='objects.json')
        assert len(prepared.chunks)==2
        assert all(TokenCounter().count(c.text).tokens<=HARD and c.block_spans for c in prepared.chunks)
        assert 'UNIT783' not in prepared.chunks[0].text


def test_large_json_not_full_document_concatenation(tmp_path):
    data={str(i):'long value '*350 for i in range(70)}
    with SQLiteKnowledgeStore(tmp_path/'store') as store:
        _,prepared=publish_text(store,json.dumps(data),filename='large.json')
        assert len(prepared.document.blocks)==70
        assert all(TokenCounter().count(c.text).tokens<=HARD for c in prepared.chunks)
        assert all(c.locator_start.coordinates['pointer'] in {'/'+str(i) for i in range(70)} for c in prepared.chunks)
