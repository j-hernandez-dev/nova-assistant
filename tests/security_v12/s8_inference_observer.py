"""Opt-in S8 observation of the actual prepared Ollama request/response.

No request, message, chunk, model, tool or security adapter is substituted.
Only private fixture payloads are recorded; never enable for user sessions.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import time


def observe_stream(original, directory):
    """Forward the original method unchanged and record each actual request."""
    directory = Path(directory)
    counter = 0

    def observed(client, path, data, *args, **kwargs):
        nonlocal counter
        if path != '/api/chat':
            yield from original(client, path, data, *args, **kwargs)
            return
        counter += 1
        filename = directory / f'ollama_request_{os.getpid()}_{counter:04d}.json'
        record = dict(pid=os.getpid(), requestIndex=counter,
                      endpoint=client.base_url + path, input=deepcopy(data),
                      startedNs=time.time_ns(), chunks=[], completed=False,
                      observerOnly=True, providerScripted=False)

        def save():
            filename.write_text(json.dumps(record, ensure_ascii=False, indent=2),
                                encoding='utf-8')

        save()
        try:
            for chunk in original(client, path, data, *args, **kwargs):
                record['chunks'].append(deepcopy(chunk))
                yield chunk
            record['completed'] = True
        except BaseException as exc:
            record['exceptionClass'] = type(exc).__name__
            raise
        finally:
            record['finishedNs'] = time.time_ns()
            save()

    return observed


def request_calls(record):
    calls = []
    for chunk in record['chunks']:
        for call in chunk.get('message', {}).get('tool_calls', []):
            function = call['function']
            args = function['arguments']
            if isinstance(args, str):
                args = json.loads(args)
            calls.append(dict(name=function['name'], arguments=args))
    return calls


def prove_read_write_dependency(records, tool_result, marker):
    """Fail if literal write lacks the preceding real read result in its input.

    The caller must independently establish real broker effects and correlate
    the supplied tool_result with the normal backend transcript/lifecycle.
    """
    records = sorted(records, key=lambda r: r['requestIndex'])
    assert records and marker in tool_result
    for record in records:
        assert record['observerOnly'] and not record['providerScripted']
        assert record['completed'] and record['endpoint'] == 'http://127.0.0.1:11434/api/chat'
        assert marker not in json.dumps([m for m in record['input']['messages']
                                         if m['role'] == 'user'])
    reads = [r for r in records if any(c['name'] == 'read' and
             c['arguments'].get('file_path') == 'seed.txt' for c in request_calls(r))]
    writes = [r for r in records if any(c['name'] == 'write' and
              c['arguments'].get('file_path') == 'result.txt' for c in request_calls(r))]
    assert len(reads) == len(writes) == 1, 'One source read and one final write are required'
    source, target = reads[0], writes[0]
    assert target['requestIndex'] > source['requestIndex'], 'Dependent calls precomputed in one inference'
    assert source['finishedNs'] < target['startedNs']
    assert any(m['role'] == 'tool' and m.get('content') == tool_result
               for m in target['input']['messages']), 'Real read ToolResult absent from write inference'
    call = next(c for c in request_calls(target) if c['name'] == 'write')
    assert call['arguments']['content'] in (marker, marker + '\n'), 'Write is not the literal read content'
    return dict(readRequest=source['requestIndex'], writeRequest=target['requestIndex'],
                sourceToolResult=tool_result, writeArguments=call['arguments'],
                distinctInferences=True, realToolResultInWriteInput=True,
                markerAbsentFromUserInputs=True)
