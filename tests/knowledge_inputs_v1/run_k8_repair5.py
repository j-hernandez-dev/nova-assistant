"""V5 fresh private guard evidence; no original K8 E2E."""
from tests.knowledge_inputs_v1.run_k0 import SELECTIONS,main
SELECTIONS['repair5-prefixed']=['tests/knowledge_inputs_v1/test_k8_repair5_guard.py::test_unknown_no_write_is_terminal_before_deliverable_guard']
SELECTIONS['repair5-direct']=['tests/knowledge_inputs_v1/test_k8_repair5_guard.py',
    'tests/test_harness_deliverable_guard.py','tests/test_agent.py','tests/test_run_agent.py',
    'tests/knowledge_inputs_v1/test_k8_repair4_audit.py','tests/knowledge_inputs_v1/test_k8_repair4_output.py']
SELECTIONS['repair5-harness']=['tests/knowledge_inputs_v1/test_k8_repair5_harness.py']
SELECTIONS['repair5-core']=['tests/test_harness_deliverable_guard.py','tests/test_agent.py',
    'tests/test_run_agent.py','tests/test_sub_agent.py','tests/test_nova_core_phase4_session.py',
    'tests/test_nova_core_phase8_providers.py','tests/test_nova_core_phase14_architecture.py',
    'tests/knowledge_inputs_v1/test_k8_repair5_guard.py']
if __name__=='__main__':main()
