"""V6 isolated deterministic gates. No model calls or original K8 E2E."""
from tests.knowledge_inputs_v1.run_k0 import SELECTIONS, main

SELECTIONS['repair6-baseline'] = [
    'tests/knowledge_inputs_v1/test_k8_repair_contracts.py',
    'tests/knowledge_inputs_v1/test_k8_repair2_control_regression.py',
    'tests/knowledge_inputs_v1/test_k8_repair3_regressions.py',
    'tests/knowledge_inputs_v1/test_k4_retrieval.py']
SELECTIONS['repair6-direct'] = SELECTIONS['repair6-baseline'] + [
    'tests/knowledge_inputs_v1/test_k8_repair6_query.py']
SELECTIONS['repair6-quality'] = ['tests/knowledge_inputs_v1/test_k8_repair6_quality.py']
SELECTIONS['repair6-regression'] = [
    'tests/knowledge_inputs_v1/test_k8_repair.py',
    'tests/knowledge_inputs_v1/test_k8_repair2_quality.py',
    'tests/knowledge_inputs_v1/test_k8_repair3_quality.py']
if __name__ == '__main__': main()
