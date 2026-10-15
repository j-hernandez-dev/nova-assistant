"""S6 known secret redaction, including chunk and retention boundaries."""
import json
import pytest
from local_cli.application.secrets import SecretRedactor, MARKER
from local_cli.core.contracts import ToolResult, ToolStatus, EffectState
from local_cli.session_log import SessionLogger


def redactor():
    return SecretRedactor(source={'UNUSED_SECRET':'dummy-api-key-123','PATH':'safe'})


def test_known_unused_variable_redacted_everywhere_without_mutating_input():
    r = redactor()
    source = {'output':'dummy-api-key-123', 'nested':[{'password':'unregistered'}], 'count':4}
    assert r.value(source) == {'output':MARKER, 'nested':[{'password':MARKER}], 'count':4}
    assert source['output'] == 'dummy-api-key-123'
    assert r.text('safe') == 'safe'


@pytest.mark.parametrize('split', range(1,17))
def test_stream_no_partial_publication_and_finish_masks_prefix(split):
    r = redactor(); stream = r.stream()
    secret = 'dummy-api-key-123'
    output = stream.feed('before '+secret[:split])+stream.feed(secret[split:]+' after')+stream.finish()
    assert output == 'before '+MARKER+' after'
    stream = r.stream()
    assert stream.feed(secret[:split])+stream.finish() == MARKER


def test_tool_result_preserves_status_effect_numeric_and_masks_truncation():
    r = redactor()
    result = ToolResult(ToolStatus.COMPLETED, EffectState.UNKNOWN, stdout='dummy-api-',
        stderr='dummy-api-key-123', exit_code=7, legacy_text='dummy-api-key-123',
        metadata={'truncated':True, 'audit':[{'command':'echo dummy-api-key-123'}]})
    safe = r.tool_result(result)
    assert safe.stdout == safe.stderr == safe.legacy_text == MARKER
    assert safe.exit_code == 7 and safe.effect_state is EffectState.UNKNOWN
    assert safe.metadata['audit'][0]['command'] == 'echo '+MARKER


def test_unicode_json_and_url_encoded_known_value():
    from urllib.parse import quote
    r = SecretRedactor(source={}); r.register('dummy-ñ-"\\')
    assert r.text(quote('dummy-ñ-"\\',safe='')) == MARKER
    assert r.text(json.dumps('dummy-ñ-"\\')[1:-1]) == MARKER


def test_logger_redacts_before_clip_and_exception_serialization(tmp_path):
    logger = SessionLogger(str(tmp_path), cwd=str(tmp_path), enabled=True, redactor=redactor())
    logger.log('trace', exception=ValueError('dummy-api-key-123'), token='dummy-api-key-123')
    logger.log_user('x'*15996+'dummy-api-key-123')
    logger.close()
    saved = logger.path.read_text(encoding='utf-8')
    assert 'dummy-api' not in saved and MARKER in saved


def test_exception_cause_trace_scrubbed():
    import traceback
    r = redactor()
    secret = 'dummy-api-' + 'key-123'
    try:
        try:
            raise ValueError('inner '+secret)
        except ValueError as cause:
            raise RuntimeError('outer '+secret) from cause
    except RuntimeError as exc:
        r.exception(exc)
        assert secret not in ''.join(traceback.format_exception(exc))


def test_event_stream_split_secret_survives_timer_and_cursor(tmp_path):
    from local_cli.application.events import SessionEventStream, EventBufferConfig
    from local_cli.core.contracts import EventKind
    stream = SessionEventStream('session', EventBufferConfig(delta_batch_count=1), redactor=redactor())
    for text in ['dummy-api-', 'key-123']:
        stream.publish(EventKind.ASSISTANT_DELTA, {'text':text}, state_revision=1, generation_id='generation')
        assert 'dummy-api-' not in json.dumps([e.to_dict() for e in stream._journal.read_after(0)])
    stream.publish(EventKind.GENERATION_COMPLETED, {'status':'completed'}, state_revision=1,
                   generation_id='generation', turn_id='turn')
    events = stream._journal.read_after(0)
    assert ''.join(e.payload.get('text','') for e in events) == MARKER


def test_persistence_new_writes_and_reads_safe_without_rewriting_old_file(tmp_path):
    from unittest.mock import Mock
    from local_cli.application.persistence import PersistenceService
    messages = [{'role':'user','content':'dummy-api-key-123'}]
    repo, snapshots = Mock(), Mock()
    repo.load.return_value = messages
    service = PersistenceService(workspace=tmp_path, conversation=repo, snapshots=snapshots, redactor=redactor())
    service.save(messages); service.save_session(messages)
    assert repo.save.call_args.args[0][0]['content'] == MARKER
    assert snapshots.save_session.call_args.args[0][0]['content'] == MARKER
    assert service.load()[0]['content'] == service.restore(workspace=tmp_path)[0]['content'] == MARKER
    assert messages[0]['content'] == 'dummy-api-key-123'


def test_provider_credential_stays_in_adapter_not_prompt_or_split_reply():
    from local_cli.application.providers import ProviderManager
    class Provider:
        name = 'fixture'
        def __init__(self):
            self._api_key = 'dummy-api-key-123'
        def chat_stream(self, model, messages, **kwargs):
            assert messages[0]['content'] == MARKER
            assert self._api_key == 'dummy-api-key-123'
            yield {'message':{'content':'dummy-api-'}}
            yield {'message':{'content':'key-123'}, 'done':True}
    runtime = ProviderManager(Provider(), 'fixture').snapshot()
    chunks = list(runtime.chat_stream('fixture', [{'role':'user','content':'dummy-api-key-123'}]))
    assert ''.join(c['message']['content'] for c in chunks) == MARKER


def test_short_known_value_cannot_rename_public_schema_fields():
    r = SecretRedactor(source={'PROJECT_TOKEN':'a'})
    assert r.value({'arguments':{'command':'a'}, 'a':'a'}) == {
        'arguments':{'command':MARKER}, MARKER:MARKER}


def test_proxy_password_component_is_known_even_when_variable_unused():
    r = SecretRedactor(source={'HTTP_PROXY':'http://dummy:proxy-dummy-123@host.test/'})
    assert r.text('proxy-dummy-123') == MARKER


def test_complete_tool_output_does_not_mask_a_benign_incomplete_prefix():
    r = redactor()
    result = ToolResult(ToolStatus.COMPLETED, EffectState.NONE, stdout='dummy-api-')
    assert r.tool_result(result).stdout == 'dummy-api-'


def test_redaction_expansion_keeps_approved_process_retention_bounds(tmp_path):
    from unittest.mock import Mock
    from local_cli.application.process import ProcessExecutionService
    from local_cli.application.cancellation import CancellationController
    from local_cli.core.process import ProcessReport
    from tests.security_v12.test_s4_contracts import request
    req = request(tmp_path)
    launcher = Mock(); launcher.launch.return_value = ProcessReport(123,0,'x'*1000,'x'*500,
        'completed',None,('running','root_exited','cleanup_confirmed'),cleanup_confirmed=True)
    r = SecretRedactor(source={'PROJECT_TOKEN':'x'})
    report, _ = ProcessExecutionService(launcher, req.limits, redactor=r).execute(req,
        cancellation_token=CancellationController(), deadline=None, validate_launch=lambda: None)
    assert len(report.stdout.encode()) <= req.limits.stdout_bytes
    assert len(report.stderr.encode()) <= req.limits.stderr_bytes
    assert report.stdout_truncated and report.stderr_truncated


def test_redaction_is_idempotent_even_if_known_value_is_in_marker():
    r = SecretRedactor(source={'PROJECT_TOKEN':'R'})
    assert r.text(r.text('R')) == MARKER


