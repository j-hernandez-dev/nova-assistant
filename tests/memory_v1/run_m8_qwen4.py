"""Last authorized M8 candidate. Operational admission BEFORE any quality.

Only existing synthetic fixtures/private stores; no pulls, global options,
other candidates, per-Turn warming, new gold or ranking changes. Normal chat
uses Application with qwen3.5:9b. A naturally cold model may be explicitly
prepared ONCE outside Turns; it is never restored after a chat eviction.
"""
import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
from threading import Lock
from time import perf_counter

from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.memory_semantic import SemanticAdmission
from local_cli.core.contracts import new_command_id
from local_cli.core.memory import MemoryAccessScope
from local_cli.infrastructure.memory_embeddings import LocalOllamaEmbeddings, QWEN_MEMORY_QUERY_INSTRUCTION
from local_cli.infrastructure.memory_semantic import NumpySemanticIndex, FORMAT
from tests.memory_v1.m8_quality_isolation import wait_quiescent
from tests.memory_v1.m8_ranked_trace import RankedRecallTrace
from tests.memory_v1.run_m8_quality import create, seed, close
from tests.memory_v1.run_m8_candidate import request, residency, observe_chat_metrics
from tests.memory_v1.run_m8_bge_operational import stats, verify

ROOT = Path(__file__).resolve().parents[2]
MODEL = 'qwen3-embedding:4b'
CHAT = 'qwen3.5:9b'
DIGEST = 'df5bd2e3c74cd8d069d21dc038f1b359fcdc9458fce1c99bd43c9eb1518ff907'
DIMENSION = 2560
WORKLOAD = ROOT/'tests/memory_v1/workloads/m8_quiescence_operational_v1.json'
DATASET = ROOT/'tests/memory_v1/fixtures/m8_bge_final_heldout_v1.json'
WORKLOAD_SHA = 'd64f4a8e62bb39b9cbb040a0d8c250b4acd0f371132a0bb05542a30cf4cc2341'
DATASET_SHA = '97b8d9e98ac74ad4b54efb31f35977eb4fe758ecef45d7e75bf044b2aafc7dfe'
DEADLINES = dict(softMs=350, hardMs=600, guardMs=50)


def space_id():
    identity = ['ollama', MODEL, DIGEST, DIMENSION, 'l2', FORMAT,
        'qwen-memory-query-document-v1', QWEN_MEMORY_QUERY_INSTRUCTION]
    return 'ollama-'+hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding='utf-8')


def capability():
    tags = request('tags')
    tag = next((r for r in tags['models'] if r['name'] == MODEL), None)
    if tag is None or tag['digest'] != DIGEST:
        raise RuntimeError('Installed candidate missing or revision changed; no download permitted')
    info = request('show', {'model': MODEL})
    metadata = {k: v for k, v in info.get('model_info', {}).items() if not k.startswith('tokenizer.')}
    dimensions = {v for k, v in metadata.items() if k.endswith('.embedding_length')}
    if ('embedding' not in info.get('capabilities', []) or dimensions != {DIMENSION}
        or str(metadata.get('general.basename', '')).casefold() != 'qwen3-embedding'):
        raise RuntimeError('Verified Qwen capability/profile/dimension mismatch')
    chat_tag = next((r for r in tags['models'] if r['name'] == CHAT), None)
    if chat_tag is None:
        raise RuntimeError('Required installed chat model missing')
    return dict(tag=tag, capabilities=info['capabilities'], details=info.get('details'),
        modelInfo=metadata, chatTag=chat_tag, ollama=request('version'),
        expectedSpaceId=space_id(), queryInstruction=QWEN_MEMORY_QUERY_INSTRUCTION,
        queryProfile='qwen-memory-query-document-v1', documentProfile='canonical-text-without-instruction',
        residency=residency())


def make_freeze():
    if hashlib.sha256(WORKLOAD.read_bytes()).hexdigest() != WORKLOAD_SHA:
        raise ValueError('Existing gold-free workload changed')
    if hashlib.sha256(DATASET.read_bytes()).hexdigest() != DATASET_SHA:
        raise ValueError('Existing held-out changed')
    files = []
    for folder in ('local_cli', 'tests', 'docs/architecture', 'docs/memory_v1'):
        for path in sorted((ROOT/folder).rglob('*')):
            if path.is_file() and path.suffix in ('.py', '.json', '.md') and '__pycache__' not in path.parts:
                files.append(dict(path=path.relative_to(ROOT).as_posix(),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    return dict(schemaVersion=1, campaign='M8_LAST_CANDIDATE_QWEN4',
        frozenAt=datetime.now(timezone.utc).isoformat(), model=MODEL, expectedDigest=DIGEST,
        expectedSpaceId=space_id(), workloadSha256=WORKLOAD_SHA, datasetSha256=DATASET_SHA,
        deadlines=DEADLINES, authorizedProductChange='Verified family basename case-insensitive recognition only',
        queryInstruction=QWEN_MEMORY_QUERY_INSTRUCTION,
        operationalProfile=dict(chat=CHAT, window=4096, independentQueries=72,
            chatAfterQueryCounts=[24,48,72], quiescenceSeconds=10), files=files)


class HttpObservation:
    """Small forwarding observer; no response hashing inside HTTP latency."""
    def __init__(self, adapter):
        self.calls, self.phase, self.lock = [], 'projection', Lock()
        self.adapter, self.original = adapter, adapter._request
        def observed(path, deadline, data=None):
            start = perf_counter()
            row = dict(phase=self.phase, path=path, errorCode=None)
            try:
                result = self.original(path, deadline, data)
                if path == '/api/embed':
                    row.update(dimensions=[len(v) for v in result.get('embeddings', [])],
                        loadDurationNs=result.get('load_duration'), totalDurationNs=result.get('total_duration'))
                return result
            except Exception as exc:
                row['errorCode'] = str(getattr(exc, 'code', type(exc).__name__))
                raise
            finally:
                row['elapsedMs'] = (perf_counter()-start)*1000
                with self.lock:
                    self.calls.append(row)
        adapter._request = observed

    def restore(self):
        self.adapter._request = self.original


def projection(app, work):
    adapter = LocalOllamaEmbeddings('http://127.0.0.1:11434', MODEL)
    observer = HttpObservation(adapter)
    service = app._memory
    semantic = SemanticAdmission(adapter, lambda space: NumpySemanticIndex(service.store, space))
    service.semantic = semantic
    scope = MemoryAccessScope(service.subject, service.identity.resolve_workspace(str(work)))
    start = perf_counter()
    report = semantic.maintain(service.store, scope, at=datetime.now(timezone.utc), redactor=service.redactor)
    actual = asdict(semantic.index.capabilities())
    if actual['embedding_space_id'] != space_id() or actual['dimension'] != DIMENSION:
        raise RuntimeError('Actual space does not match frozen Qwen query/document profile')
    spaces = [dict(r) for r in service.store._connection.execute('SELECT * FROM embedding_spaces')]
    vectors = service.store._connection.execute('SELECT count(*) FROM memory_embeddings').fetchone()[0]
    if len(spaces) != 1 or vectors != 90 or spaces[0]['embedding_space_id'] != space_id():
        raise RuntimeError('Projection is not a new isolated 90-record synthetic space')
    return dict(report=report, elapsedMs=(perf_counter()-start)*1000, space=actual, spaces=spaces,
        vectors=vectors, oldVectorsReused=False, cache=semantic.index.cache_stats()), adapter, observer


def chat_turn(app, sid, *, case, metrics):
    """Actual normal backend Turn, no gold/answer-quality evaluation."""
    before = residency()
    start = perf_counter()
    response = app.handle(ApplicationCommand(new_command_id(), CommandKind.SUBMIT_USER_INPUT,
        {'content': 'Operational synthetic check '+case+'. Return a brief greeting in the required JSON format.'},
        session_id=sid))
    if not response.accepted:
        raise RuntimeError('Operational normal chat Turn rejected: '+response.error.code)
    turn = app._session.turns[-1]
    if not turn.done.wait(180):
        turn.cancellation.request()
        raise RuntimeError('Operational chat Turn exceeded observation bound')
    return dict(case=case, before=before, after=residency(), elapsedMs=(perf_counter()-start)*1000,
        turnStatus=turn.status.value, terminalCount=turn.terminal_count, errorCode=turn.error_code,
        memory=turn.memory_snapshot.metadata() if turn.memory_snapshot else None,
        ollamaInferenceMetadata=dict(metrics[-1]) if metrics else None, qualityEvaluated=False)


def operational_gate(report):
    rows, chats = report.get('rows', []), report.get('chatTurns', [])
    latencies = stats([r['totalReturnMs'] for r in rows])
    failures = []
    if len(rows) != 72:
        failures.append('incomplete_operational_workload')
    if latencies['p95Ms'] is None or latencies['p95Ms'] > 350:
        failures.append('pipeline_p95')
    if any(r['totalReturnMs'] > 600 for r in rows):
        failures.append('hard_total')
    if any(r['metadata']['embeddingStatus'] != 'WARM' for r in rows):
        failures.append('semantic_not_available_between_turns')
    if any(r['workerBefore']['state'] != 'IDLE' or r.get('workerFinal',{}).get('state') != 'IDLE'
        or not r.get('snapshotUnchangedAfterQuiescence') or r.get('lateResultUsed') is not False for r in rows):
        failures.append('worker_or_late_result_contract')
    if len(chats) != 3 or any(c['turnStatus'] != 'completed' or c['terminalCount'] != 1 or c['errorCode'] for c in chats):
        failures.append('normal_chat_lifecycle')
    # Sampled operational evidence, not a guarantee of physical residency.
    for chat in chats:
        resident = {r.get('digest') for r in chat['after']['ps']['models']}
        if DIGEST not in resident or report['capability']['chatTag']['digest'] not in resident:
            failures.append('models_not_co_resident_after_chat')
            break
        if not chat.get('memory') or chat['memory']['embeddingStatus'] != 'WARM':
            failures.append('semantic_not_available_at_normal_chat_turn')
            break
    if report.get('errorCode'):
        failures.append('harness_or_backend_error')
    return dict(pass_=not failures, failures=failures, pipeline=latencies,
        statuses=dict(Counter(r['metadata']['embeddingStatus'] for r in rows)),
        semanticQuality='NOT_EVALUATED', qualityAuthorized=not failures)


def operational(out, lock):
    verify(lock)
    data = json.loads(WORKLOAD.read_text(encoding='utf-8'))
    assert data['syntheticOnly'] and not data['goldProvided'] and not data['qualityEvaluated']
    assert len(data['samples']) == 72 and not any('gold' in q or 'accepted' in q for q in data['samples'])
    out.mkdir(parents=True); work = out/'workspace'; work.mkdir()
    report = dict(phase='M8', stage='QWEN4_OPERATIONAL_REAL_CHAT_PROFILE',
        measuredAt=datetime.now(timezone.utc).isoformat(), platform=platform.platform(),
        model=MODEL, chatModel=CHAT, expectedSpaceId=space_id(), deadlines=DEADLINES,
        workloadSha256=WORKLOAD_SHA, goldUsed=False, qualityEvaluated=False, heldoutExecuted=False,
        modelsDownloaded=False, globalConfigChanged=False, gpuChanged=False,
        perTurnWarming=False, rows=[], chatTurns=[], httpCalls=[])
    app = audit = observer = trace = None
    try:
        report['capability'] = capability()
        resident = any(r['digest'] == DIGEST for r in report['capability']['residency']['ps']['models'])
        report['coldPreparation'] = dict(required=not resident, outsideTurn=True,
            reason='Single explicit synthetic projection preparation; no override or keep_alive supplied')
        if not resident:
            # This is explicit candidate evaluation setup, not admission or
            # per-Turn cold loading. Never performed again after chat eviction.
            print('Single outside-Turn natural cold preparation of installed Qwen4', flush=True)
            start = perf_counter()
            cold = request('embed', {'model':MODEL, 'input':['Instruct: '+QWEN_MEMORY_QUERY_INSTRUCTION+
                '\nQuery: Synthetic operational preparation, not a quality question.'], 'truncate':False}, timeout=180)
            report['coldPreparation'].update(elapsedMs=(perf_counter()-start)*1000,
                dimension=len(cold['embeddings'][0]), loadDurationNs=cold.get('load_duration'),
                totalDurationNs=cold.get('total_duration'), after=residency())
        app, sid, actor, audit = create(out, work, 4096, CHAT, mode='hybrid')
        mapping = seed(app, sid, actor, data)
        save(out/'report.json', report)
        print('Preparing a NEW 2560D space/projection for 90 synthetic records', flush=True)
        report['projection'], adapter, observer = projection(app, work)
        report['residencyBeforeQueries'] = residency()
        metrics = observe_chat_metrics(app)
        trace = RankedRecallTrace(app._memory)
        with trace:
            try:
                for i, q in enumerate(data['samples']):
                    if trace.state()['state'] != 'IDLE':
                        raise RuntimeError('Operational independent query did not start IDLE')
                    observer.phase = q['id']
                    snapshot, row = trace.recall(q['id'], q['query'], work, datetime.now(timezone.utc))
                    row['teardown'] = wait_quiescent(app._memory.semantic, trace.threads, limit_seconds=10)
                    report['rows'].append(trace.annotate(row, mapping=mapping))
                    if (i+1) in (24,48,72):
                        observer.phase = 'normal-chat-'+str(i+1)
                        chat = chat_turn(app, sid, case=observer.phase, metrics=metrics)
                        chat['teardown'] = wait_quiescent(app._memory.semantic, trace.threads, limit_seconds=10)
                        report['chatTurns'].append(chat)
                        print('Normal chat completed; observing residence without rewarming', flush=True)
                    report['httpCalls'] = list(observer.calls)
                    save(out/'report.json', report)
                    if (i+1)%6 == 0:
                        print(f'Operational {i+1}/72: {snapshot.embedding_status}, {row["totalReturnMs"]:.2f} ms', flush=True)
            finally:
                report['finalTeardown'] = wait_quiescent(app._memory.semantic, trace.threads, limit_seconds=10)
        report['residencyAfterQueries'] = residency()
        report['metadataCache'] = adapter.metadata_cache_stats()
        report['stableFootprint'] = app._memory.maintenance.jobs.usage(stabilize=True)
        verify(lock); report['frozenFilesUnchanged'] = True
    except Exception as exc:
        report.update(errorCode=str(getattr(exc,'code',type(exc).__name__)), error=str(exc))
    finally:
        if observer:
            report['httpCalls'] = list(observer.calls); observer.restore()
        if app:
            close(app, audit)
    endpoints = [r['elapsedMs'] for r in report['httpCalls'] if r['path']=='/api/embed' and
        r['phase']!='projection' and not r['errorCode']]
    report['endpointSuccessful'] = stats(endpoints)
    report['endpointAllAttempts'] = stats([r['elapsedMs'] for r in report['httpCalls'] if
        r['path']=='/api/embed' and r['phase']!='projection'])
    report['perQueryHttpCounts'] = [dict(case=r['case'], **{path:sum(c['phase']==r['case'] and c['path']==path
        for c in report['httpCalls']) for path in ('/api/tags','/api/ps','/api/embed')}) for r in report['rows']]
    report['operationalGate'] = operational_gate(report)
    save(out/'report.json', report)
    print(json.dumps(dict(operationalGate=report['operationalGate'], endpoint=report['endpointSuccessful'],
        errorCode=report.get('errorCode')), ensure_ascii=True), flush=True)
    return report['operationalGate']['pass_']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('preflight','freeze','operational'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--freeze', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('NEW output required; historical evidence is immutable')
    if args.stage == 'preflight':
        proof = capability(); save(args.output, proof)
        print(json.dumps(dict(model=MODEL, digest=DIGEST, dimension=DIMENSION,
            expectedSpaceId=space_id(), queryInstruction=QWEN_MEMORY_QUERY_INSTRUCTION), ensure_ascii=True))
        return
    if args.stage == 'freeze':
        lock = make_freeze(); save(args.output, lock)
        print(json.dumps(dict(files=len(lock['files']), expectedSpaceId=space_id(), deadlines=DEADLINES)))
        return
    if args.freeze is None:
        parser.error('--freeze required before operational measurement')
    lock = json.loads(args.freeze.read_text(encoding='utf-8'))
    if lock['expectedSpaceId'] != space_id() or lock['deadlines'] != DEADLINES:
        raise ValueError('Candidate/protocol freeze mismatch')
    raise SystemExit(0 if operational(args.output, lock) else 1)


if __name__ == '__main__':
    main()
