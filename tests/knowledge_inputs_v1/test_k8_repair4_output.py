"""Prospective V4 sentinel contracts; doubles are not real LLM quality."""
from copy import deepcopy
import pytest
from local_cli.application.knowledge_output import (canonical_terminal,canonical_stream,
    canonical_message,MAX_PENDING_CHARS)
from local_cli.core.contracts import EventKind
from tests.knowledge_inputs_v1.test_k5_integration import case,run,finish
from tests.memory_v1.test_m4_application import CapturingProvider,make_app,turn,close

POSITIVE=(
    'UNKNOWN',' UNKNOWN\n','UNKNOWN.',
    'The source does not provide it. Therefore UNKNOWN.',
    'The requested service interval is not stated in the document [K1]. Thus, the answer is UNKNOWN.',
    'There is no evidence for the requested date. Hence UNKNOWN.',
    'La fuente no proporciona la medida solicitada [K1]. Por tanto, la respuesta es UNKNOWN.',
    'The answer is UNKNOWN',
)
NEGATIVE=(
    "I don't know",'UNKNOWNNESS','preUNKNOWN','unknown',
    'The document literally contains the word UNKNOWN',
    'The status field is UNKNOWN [K1].',
    'The label is "UNKNOWN" [K1].',
    'UNKNOWN is the value printed on the device [K1].',
    'The document says UNKNOWN. But the verified value is 47 [K1].',
    'The interval is 47 days [K1]. Therefore UNKNOWN.',
    'The answer is "UNKNOWN".',
    'The source does not provide it. Therefore UNKNOWN. Also use 47 days.',
    'UNKNOWN [K1]','The fabric is silver linen [K1].',
    'The source literally contains UNKNOWN. Therefore UNKNOWN.',
    'The source does not provide it. Therefore unknown.',
)


@pytest.mark.parametrize('text',POSITIVE)
def test_explicit_terminal_sentinel_only(text):
    assert canonical_terminal(text)=='UNKNOWN'


@pytest.mark.parametrize('text',NEGATIVE)
def test_factual_quoted_nonterminal_and_invented_value_untouched(text):
    assert canonical_terminal(text)==text


@pytest.mark.parametrize('text',POSITIVE+NEGATIVE)
@pytest.mark.parametrize('size',[1,7,10000])
def test_fragmentation_independent_and_usage_unchanged(text,size):
    parts=[text[i:i+size] for i in range(0,len(text),size)]
    raw=[{'message':{'role':'assistant','content':p}} for p in parts]
    raw.append({'done':True,'prompt_eval_count':101,'eval_count':17,'message':{'content':''}})
    saved=deepcopy(raw);result=list(canonical_stream(iter(raw)))
    assert ''.join(c.get('message',{}).get('content','') for c in result)==canonical_terminal(text)
    assert result[-1]['prompt_eval_count']==101 and result[-1]['eval_count']==17
    assert raw==saved


def test_tool_call_bypasses_output_rule_and_preserves_request():
    request={'message':{'content':'UNKNOWN','tool_calls':[{'function':{'name':'write',
        'arguments':{'file_path':'allowed.txt','content':'synthetic tool body'}}}]},'done':True}
    assert list(canonical_stream(iter([request])))==[request]
    assert canonical_message(request) is request


def test_nonstream_message_uses_same_representation_without_mutation():
    raw={'message':{'content':POSITIVE[3]},'eval_count':29,'done':True}
    safe=canonical_message(raw)
    assert safe['message']['content']=='UNKNOWN' and safe['eval_count']==29
    assert raw['message']['content']==POSITIVE[3]


def test_truncated_completion_never_rewritten_as_successful_abstention():
    raw={'message':{'content':POSITIVE[3]},'done_reason':'length','done':True}
    assert canonical_message(raw) is raw
    assert list(canonical_stream(iter([raw])))==[raw]


def test_midstream_failure_preserves_partial_not_success_or_silent_retry():
    def broken():
        yield {'message':{'content':'The source does not provide it. '}}
        raise RuntimeError('synthetic transport failure')
    stream=canonical_stream(broken());chunks=[]
    with pytest.raises(RuntimeError,match='transport'):
        while True:chunks.append(next(stream))
    assert ''.join(c['message'].get('content','') for c in chunks)=='The source does not provide it. '
    assert chunks[0]['message']['content']=='' # progress is still visible to collector


def test_close_preserves_cancellation_and_closes_underlying_without_terminal():
    closed=[]
    def pending():
        try:
            yield {'message':{'content':'The source does not provide it. '}}
            yield {'message':{'content':'Therefore UNKNOWN.'},'done':True}
        finally:closed.append(True)
    stream=canonical_stream(pending());assert next(stream)['message']['content']==''
    stream.close();assert closed==[True]


def test_pending_bound_passes_through_without_truncating_or_inventing():
    text='The '+('long synthetic prose '*MAX_PENDING_CHARS)
    result=list(canonical_stream(iter([{'message':{'content':text}},{'done':True}])))
    assert ''.join(c.get('message',{}).get('content','') for c in result)==text


class FragmentProvider(CapturingProvider):
    def chat_stream(self,*args,**kwargs):
        for result in super().chat_stream(*args,**kwargs):
            content=(result.get('message') or {}).get('content','')
            if (result.get('message') or {}).get('tool_calls'):
                yield result;continue
            for i in range(0,len(content),7):
                yield {'message':{'role':'assistant','content':content[i:i+7]}}
            yield {'done':True,'message':{'role':'assistant','content':''},'eval_count':19}


@pytest.mark.parametrize('text',[POSITIVE[3],NEGATIVE[4],NEGATIVE[-3]])
def test_normal_application_public_stream_display_transcript_and_terminal_agree(tmp_path,text):
    c=case(tmp_path,provider=FragmentProvider(steps=[text]))
    try:
        t=run(c,content='Synthetic alabaster schedule. Do not write files.')
        expected=canonical_terminal(text)
        assert t.final_content==expected
        assert c.app._session.transcript[-1]['content']==expected
        assert ''.join(m.get('content','') for m in t.display_messages if m['role']=='assistant')==expected
        cursor=c.app.subscribe_events(c.sid,after_sequence=0)
        deltas=[e for e in c.app.poll_events(cursor) if e.kind is EventKind.ASSISTANT_DELTA]
        assert ''.join(e.payload.get('text','') for e in deltas)==expected
        assert t.terminal_count==1 and len(t.generations)==1
        assert t.knowledge_admission.retrieval_count==1
    finally:finish(c)


def test_memory_only_application_output_is_not_changed(tmp_path):
    text=POSITIVE[3]
    app,sid,actor,audit,provider,work=make_app(tmp_path,provider=FragmentProvider(steps=[text]))
    try:
        t=turn(app,sid,'Synthetic ordinary conversation')
        assert t.final_content==text
        assert not t.model_runtime._context.knowledge_output
    finally:close(app,audit)


def test_model_write_attempt_normal_backend_denied_audited_without_effect(tmp_path):
    from local_cli.tools.write_tool import WriteTool
    from local_cli.core.security_audit import AuditKind
    from local_cli.application.security_audit import reconstruct_operation
    tool={'role':'assistant','content':'','tool_calls':[{'id':'v4-attempt','function':{
        'name':'write','arguments':{'file_path':'prohibited.txt','content':'synthetic forbidden value'}}}]}
    (tmp_path/'workspace').mkdir()
    # The existing Core error-stop guard asks once more after a denied tool.
    c=case(tmp_path,provider=FragmentProvider(steps=[tool,POSITIVE[3],POSITIVE[3]]),
        tools=[WriteTool(cwd=tmp_path/'workspace')])
    try:
        t=run(c,content='Synthetic apricot fixture question. Do not write files.')
        assert t.final_content=='UNKNOWN' and len(t.generations)==3 and t.terminal_count==1
        assert not (c.work/'prohibited.txt').exists()
        operation=next(iter(t.tool_operations))
        rows=c.audit.read_operation(c.sid,operation)
        actual=reconstruct_operation(rows)
        assert actual['outcome']=='denied' and actual['effectState']=='none'
        assert next(r for r in rows if r.kind is AuditKind.POLICY).data['reason']=='TURN_FILESYSTEM_MUTATION_DENIED'
        assert c.app.security_audit.health()['deliveryFailures']==0
        assert any(m.get('role')=='tool' and 'TURN_FILESYSTEM_MUTATION_DENIED' in m.get('content','')
            for m in c.p.captured[1])
    finally:finish(c)
