"""Host import ONLY. Emits prospective gold candidate; never submits a Turn."""
import argparse
import json
from pathlib import Path
import subprocess
import uuid

from .bridge import Bridge
from .common import DOCS, OUTPUT, ROOT, NetworkAudit, backend, file_tree, now, private_environment, read, sha, write


def prepare():
    corpus, protocol, profile = [read(DOCS / name) for name in ('corpus.json', 'protocol.json', 'execution_profile.json')]
    directory = OUTPUT / 'preparations' / ('ki35-' + uuid.uuid4().hex)
    directory.mkdir(parents=True, exist_ok=False)
    workspace = directory / 'workspace'
    workspace.mkdir()
    state = directory / 'seed-state'
    network = NetworkAudit(directory)
    protected_names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
    protected = {str(ROOT / name): sha(ROOT / name) for name in protected_names
                 if name and (ROOT / name).is_file() and
                 not name.startswith(('tests/knowledge_inputs_v1/source_conflict_focal/', 'docs/knowledge_inputs_v1/source_conflict_focal/'))}
    write(directory / 'preservation_before.json', protected)
    bridge = None
    with private_environment(directory):
        try:
            bridge = Bridge(directory, workspace, state, network=network)
            for document in corpus['documents']:
                path = DOCS / 'fixtures' / document['filename']
                if path.read_text(encoding='utf-8') != document['payload']:
                    raise ValueError('CORPUS_FIXTURE_BYTES_MISMATCH')
                bridge.host('source_import', dict(path=str(path), scope='WORKSPACE'))
            bindings = bridge.bindings(corpus['documents'])
            lifecycle = bridge.states()
            memory = bridge.memory_snapshot()
            if bridge.app._session.turns or bridge.requests or network.chat_requests:
                raise ValueError('PREPARATION_MUST_HAVE_ZERO_TURNS_OR_INFERENCE')
            # Candidate is derived solely from actual imports and prospective
            # declarations. No retrieval/ranking/admission/model response seen.
            gold = dict(schema_version=1, case_id=corpus['case_id'], query=corpus['query'],
                fact=corpus['fact'], expected_bindings=bindings, expected_relation='CONFLICT',
                score_order=protocol['score_order'], expected_retrieval='exact two distinct sources/revisions/chunks',
                expected_admission='both complete actual chunks', expected_response='both exact incompatible values, each attributed by its actual citation, explicitly conflicting, no arbitrary truth selection',
                required_distinct_valid_citations=2, citation_order='NOT_CONTRACTUAL',
                citation_repetition_in_natural_prose='ALLOWED', citation_provenance='exact source/revision/chunk/locator',
                files_mutation=False, memory_mutation=False, documentary_authority=False,
                no_response_json_contract=True, source_lifecycle_before=lifecycle,
                memory_before=memory, scope='WORKSPACE', workspace=str(workspace),
                preparation_session_id=str(bridge.app._session.session_id))
            write(directory / 'gold.candidate.json', gold)
            write(directory / 'lifecycle_before_close.json', lifecycle)
            events = [e.to_dict() for e in bridge.app.poll_events(bridge.app.subscribe_events(
                bridge.app._session.session_id, after_sequence=0, include_internal=True))]
            write(directory / 'preparation_events.json', events)
        finally:
            if bridge:
                bridge.close()
    drift = [p for p, digest in protected.items() if not Path(p).is_file() or sha(p) != digest]
    write(directory / 'preparation_receipt.json', dict(timestamp=now(), directory=str(directory),
        seed_state=str(state), workspace=str(workspace), seed_tree=file_tree(state), workspace_tree=file_tree(workspace),
        bindings=bindings, host_imports=2, source_list=1, turns=0, inference=0, retrieval=0, admission=0,
        network=network.receipt(), product_and_history_preservation=dict(checked=len(protected), errors=drift),
        gold_candidate_sha256=sha(directory / 'gold.candidate.json')))
    if drift:
        raise ValueError('PRESERVATION_DRIFT:' + repr(drift))
    print(json.dumps(dict(preparation=str(directory), gold_candidate=str(directory / 'gold.candidate.json'),
                         inference=0, retrieval=0, admission=0, turns=0)))


if __name__ == '__main__':
    prepare()
