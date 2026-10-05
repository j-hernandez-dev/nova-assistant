"""Observer/causal-proof unit tests, NOT the qualifying real Ollama E2E."""
from copy import deepcopy
import json
from types import SimpleNamespace
import pytest
from s8_inference_observer import observe_stream, prove_read_write_dependency


def test_observer_forwards_exact_original_arguments_and_chunks(tmp_path):
    data = {'messages': [{'role': 'user', 'content': 'fixture'}]}
    before = deepcopy(data)
    chunks = [{'message': {'content': 'actual chunk'}}, {'done': True}]
    seen = []
    client = SimpleNamespace(base_url='http://127.0.0.1:11434')
    def original(c, path, payload, timeout):
        seen.append((c, path, payload, timeout))
        yield from chunks
    wrapper = observe_stream(original, tmp_path)
    observed = list(wrapper(client, '/api/chat', data, timeout=123))
    assert data == before and len(seen) == 1
    assert seen[0][0] is client and seen[0][2] is data and seen[0][3] == 123
    assert all(a is b for a, b in zip(observed, chunks))
    saved = json.loads(next(tmp_path.glob('ollama_request_*.json')).read_text())
    assert saved['input'] == data and saved['chunks'] == chunks and saved['completed']


def fixture_records():
    marker = 'UNIT_ONLY_RANDOM_CONTENT'
    result = '     1\t' + marker
    def record(index, calls, messages):
        return dict(requestIndex=index, startedNs=index*10, finishedNs=index*10+1,
                    input={'messages': messages}, chunks=[{'message': {'tool_calls': calls}}],
                    completed=True, observerOnly=True, providerScripted=False,
                    endpoint='http://127.0.0.1:11434/api/chat')
    def call(name, args):
        return {'function': {'name': name, 'arguments': args}}
    read = call('read', {'file_path': 'seed.txt'})
    write = call('write', {'file_path': 'result.txt', 'content': marker})
    return marker, result, [record(1, [read], [{'role': 'user', 'content': 'read'}]),
                           record(2, [write], [{'role': 'tool', 'content': result}])]


def test_dependency_accepts_distinct_requests_with_tool_result():
    marker, result, records = fixture_records()
    assert prove_read_write_dependency(records, result, marker)['distinctInferences']


def test_observer_propagates_original_failure_without_inventing_completion(tmp_path):
    def original(*args, **kwargs):
        yield {'message': {'content': 'real partial chunk'}}
        raise RuntimeError('actual failure')
    wrapper=observe_stream(original,tmp_path)
    with pytest.raises(RuntimeError,match='actual failure'):
        list(wrapper(SimpleNamespace(base_url='http://127.0.0.1:11434'),'/api/chat',{}))
    saved=json.loads(next(tmp_path.glob('ollama_request_*.json')).read_text())
    assert not saved['completed'] and saved['exceptionClass']=='RuntimeError'


def test_observer_does_not_record_or_change_other_endpoints(tmp_path):
    data={'model':'fixture'};chunk={'embedding':[1.0]};seen=[]
    def original(client,path,payload):
        seen.append((path,payload));yield chunk
    wrapper=observe_stream(original,tmp_path)
    assert list(wrapper(SimpleNamespace(),'/api/embed',data))[0] is chunk
    assert seen==[('/api/embed',data)] and seen[0][1] is data
    assert not list(tmp_path.iterdir())


def test_multiturn_peer_waits_for_the_requested_terminal_not_a_stale_turn():
    from test_s8_e2e import Peer
    peer=Peer.__new__(Peer)
    old={'kind':'TurnCompleted','turnId':'old'}
    current={'kind':'TurnCompleted','turnId':'current'}
    peer.events=[old]
    def wait(predicate,timeout):
        assert not predicate({'type':'event','event':old})
        assert predicate({'type':'event','event':current})
        return {'event':current}
    peer.wait=wait
    assert peer.terminal('current') is current


@pytest.mark.parametrize('defect', ['same_inference', 'result_missing', 'placeholder',
                                  'scripted', 'marker_in_prompt', 'request_failed'])
def test_dependency_rejects_invalid_claims(defect):
    marker, result, records = fixture_records()
    if defect == 'same_inference':
        records[0]['chunks'][0]['message']['tool_calls'] += records[1]['chunks'][0]['message']['tool_calls']
        records.pop()
    elif defect == 'result_missing':
        records[1]['input']['messages'] = [{'role': 'assistant', 'content': result}]
    elif defect == 'placeholder':
        records[1]['chunks'][0]['message']['tool_calls'][0]['function']['arguments']['content'] = 'placeholder'
    elif defect == 'scripted':
        records[1]['providerScripted'] = True
    elif defect == 'marker_in_prompt':
        records[1]['input']['messages'].append({'role': 'user', 'content': marker})
    elif defect == 'request_failed':
        records[1]['completed'] = False
    with pytest.raises(AssertionError):
        prove_read_write_dependency(records, result, marker)
