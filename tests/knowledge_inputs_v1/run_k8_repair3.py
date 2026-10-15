"""V3 private gates; direct regressions precede any prospective quality."""
from tests.knowledge_inputs_v1.run_k0 import SELECTIONS,main
SELECTIONS['repair3-direct']=['tests/knowledge_inputs_v1/test_k8_repair3_regressions.py',
    'tests/knowledge_inputs_v1/test_k5_context.py',
    'tests/knowledge_inputs_v1/test_k8_repair2_contracts.py',
    'tests/knowledge_inputs_v1/test_k8_repair2_control_regression.py',
    'tests/memory_v1/test_m8_ps_operational.py']
SELECTIONS['repair3-quality']=['tests/knowledge_inputs_v1/test_k8_repair3_quality.py']
SELECTIONS['repair3-harness']=['tests/knowledge_inputs_v1/test_k8_repair3_harness.py']
if __name__=='__main__':main()
