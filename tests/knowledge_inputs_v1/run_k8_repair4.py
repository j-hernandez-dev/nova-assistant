"""V4 fresh private regression evidence. No original K8 E2E."""
from tests.knowledge_inputs_v1.run_k0 import SELECTIONS,main
SELECTIONS['repair4-audit']=['tests/knowledge_inputs_v1/test_k8_repair4_audit.py']
SELECTIONS['repair4-direct']=['tests/knowledge_inputs_v1/test_k8_repair4_audit.py',
    'tests/knowledge_inputs_v1/test_k8_repair4_output.py',
    'tests/knowledge_inputs_v1/test_k5_integration.py',
    'tests/security_v12/test_s7_runtime.py','tests/security_v12/test_s7_durable_runtime.py']
SELECTIONS['repair4-harness']=['tests/knowledge_inputs_v1/test_k8_repair4_harness.py']
if __name__=='__main__':main()
