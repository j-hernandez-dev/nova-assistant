"""Run test-only M0 characterization, without network/models or user state.

python -B -m tests.memory_v1.run_m0 --output <new-report.json>
Existing evidence is never overwritten. Timing is descriptive, not M8 quality.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import tempfile

from tests.memory_v1.context_baseline import (GROWTH, WINDOWS,
    characterize_context, characterize_user_priority)
from tests.memory_v1.advanced_context import matrix
from tests.memory_v1.evaluation import DATASET_PATH, load_dataset, score_observation, unknown_quality
from tests.memory_v1.legacy_baseline import (characterize_child, characterize_knowledge,
    characterize_lexical, characterize_persistence, characterize_rag, characterize_sessions)


def run():
    dataset = load_dataset()
    with tempfile.TemporaryDirectory(prefix='nova-m0-synthetic-') as private:
        root = Path(private)
        legacy = {name: fn(root / name) for name, fn in [
            ('persistence', characterize_persistence), ('rag', characterize_rag),
            ('lexical', characterize_lexical), ('sessions', characterize_sessions),
            ('child', characterize_child), ('knowledge', characterize_knowledge)]}
    return {'schemaVersion': 1, 'phase': 'M0', 'state': 'CHARACTERIZATION_PASSED',
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'runtime': {'python': platform.python_version(), 'platform': platform.platform()},
        'datasetVersion': dataset['datasetVersion'],
        'datasetSha256': hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest(),
        'evidenceCount': len(dataset['evidence']), 'caseCount': len(dataset['cases']),
        'syntheticOnly': True, 'networkCalls': 0, 'realModelInference': False,
        'context': [characterize_context(window, size) for window in WINDOWS for size in GROWTH],
        'userPriority': [characterize_user_priority(window) for window in WINDOWS],
        'advancedContextMatrix': matrix(),
        'legacy': legacy,
        'metricOracleSelfCheck': {
            'classification': 'ORACLE_SELF_CHECK_NOT_PRODUCT_QUALITY',
            'cases': [{ 'id': case['id'], **score_observation(dataset, case,
                ranked_ids=case['relevantIds'], resolution=case['expectedResolution'])}
                for case in dataset['cases']]},
        'productionMemoryQuality': unknown_quality(),
        'performanceGate': 'DESCRIPTIVE_ONLY_NO_M8_THRESHOLDS_RESOLVED'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('report already exists; preserve evidence and select a new path')
    report = run()  # Exceptions/failing assertions fail the run; no fake PASS.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(f"M0 characterization: {report['caseCount']} cases; {len(report['context'])} context measurements.")


if __name__ == '__main__':
    main()
