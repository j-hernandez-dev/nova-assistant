"""Complete one-shot productive runner, frozen before separate authorization.

Default command is identity/preflight only. --execute requires separate
human authorization and exclusive persistent reservation; no automatic retry.
"""
import argparse
import json
from pathlib import Path
import shutil
import traceback

from .bridge import Bridge
from .common import DOCS, OUTPUT, ROOT, NetworkAudit, StopExecution, backend, file_tree, now, preflight, private_environment, read, sha, write
from .scorer import score


def index(directory):
    write(directory / 'evidence_index.json', dict(timestamp=now(), self_excluded=True,
        files=[dict(path=str(p.relative_to(directory)), sha256=sha(p))
            for p in sorted(directory.rglob('*')) if p.is_file() and p.name != 'evidence_index.json']))


def execute(authorization_path):
    auth = read(authorization_path)
    check = preflight(auth)
    if check['errors']:
        raise StopExecution(json.dumps(check))
    freeze = read(DOCS / 'freeze.json')
    corpus = read(DOCS / 'corpus.json')
    if not auth['execution_id'].replace('-', '').replace('_', '').isalnum():
        raise StopExecution('INVALID_EXECUTION_ID')
    output = OUTPUT / 'executions' / auth['execution_id']
    if output.exists():
        raise StopExecution('OUTPUT_ALREADY_EXISTS')
    ledger = OUTPUT / 'ledger'
    ledger.mkdir(parents=True, exist_ok=True)
    reservation = ledger / (sha(DOCS / 'freeze.json') + '.json')
    # Reservation is exclusive and permanent even for incidents. No CLI permits
    # reusing/replacing it. A later human decision must be separately recorded.
    with reservation.open('x', encoding='utf-8') as stream:
        json.dump(dict(timestamp=now(), freeze_sha256=sha(DOCS / 'freeze.json'),
            execution_id=auth['execution_id'], quality_attempt_reserved=1, automatic_retries=0), stream, indent=2)
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'authorization_used.json', auth)
    write(output / 'preflight.json', check)
    network = NetworkAudit(output)
    bridge = None
    result = None
    try:
        shutil.copytree(Path(freeze['seed_state']), output / 'state')
        if file_tree(output / 'state') != freeze['seed_tree']:
            raise StopExecution('SEED_COPY_DRIFT')
        with private_environment(output):
            def immediate_check():
                # Workspace mutations during the Turn are quality/effect
                # failures, not a way to reclassify them as harness drift.
                latest = preflight(auth, check_workspace=not bool(bridge and bridge.last_turn))
                if latest['errors']:
                    raise StopExecution(json.dumps(latest))
            bridge = Bridge(output, Path(freeze['workspace']), output / 'state',
                network=network, execution=True, check=immediate_check)
            bindings = bridge.bindings(corpus['documents'])
            if bindings != read(DOCS / 'gold.json')['expected_bindings']:
                raise StopExecution('REOPENED_STORE_BINDINGS_DRIFT')
            write(output / 'reopened_bindings.json', bindings)
            immediate_check()
            write(output / 'identity_before.json', backend(read(DOCS / 'execution_profile.json')))
            network.allow_chat = True
            observation = bridge.run_turn(corpus['query'])
            network.allow_chat = False
            result = score(read(DOCS / 'gold.json'), observation)
            if observation['transport_errors']:
                # Raw independently observed transport exception, not quality failure.
                result = dict(result='SOURCE_CONFLICT_FOCAL_INCIDENT', incident='OLLAMA_TRANSPORT',
                              preserved_score=result, raw_transport_errors=observation['transport_errors'])
            write(output / 'identity_after.json', backend(read(DOCS / 'execution_profile.json')))
            postflight = preflight(auth, check_workspace=False)
            write(output / 'postflight.json', postflight)
            if postflight['errors']:
                result = dict(result='SOURCE_CONFLICT_FOCAL_INCIDENT', incident='POST_EXECUTION_DRIFT',
                              preserved_score=result, errors=postflight['errors'])
    except Exception as error:
        network.allow_chat = False
        result = dict(result='SOURCE_CONFLICT_FOCAL_INCIDENT', incident='UNRESOLVED_HARNESS_OR_ENVIRONMENT',
            type=type(error).__name__, message=str(error), traceback=traceback.format_exc(),
            no_automatic_retry=True, no_quality_failure_relabeling=True)
        write(output / 'incident.json', result)
    finally:
        if bridge:
            try:
                bridge.close()
            except Exception as error:
                write(output / 'cleanup_incident.json', dict(type=type(error).__name__, message=str(error)))
                result = dict(result='SOURCE_CONFLICT_FOCAL_INCIDENT', incident='CLEANUP', preserved_result=result)
        write(output / 'network_receipt.json', network.receipt())
        write(output / 'result.json', dict(timestamp=now(), case_id=corpus['case_id'], result=result,
            freeze_sha256=sha(DOCS / 'freeze.json'), authorization_sha256=sha(authorization_path),
            counters=dict(quality_attempts=1, inference=network.chat_requests,
                          retrieval=bridge.retrieval_calls if bridge else 0,
                          admission=1 if bridge and bridge.last_turn and bridge.last_turn.knowledge_admission is not None else 0),
            k8_v2_untouched=True, official_k8_v2_result='K8 CERTIFICATION V2 FAIL', ready=False))
        index(output)
    print(json.dumps(dict(output=str(output), result=result)))
    return 0 if result['result'] == 'SOURCE_CONFLICT_FOCAL_PASS' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--preflight-output', type=Path)
    args = parser.parse_args()
    if args.execute:
        if not args.authorization:
            parser.error('--execute requires separate human authorization')
        return execute(args.authorization)
    result = preflight()
    if args.preflight_output:
        if args.preflight_output.exists():
            parser.error('Never overwrite preflight evidence')
        write(args.preflight_output, result)
    print(json.dumps(dict(status=result['status'], errors=result['errors'], pins_checked=result['pins_checked'],
                         freeze_sha256=result['freeze_sha256'], inference=0, retrieval=0, admission=0,
                         authorization=result['authorization'])))
    return 0 if not result['errors'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
