"""K8 private contract/quality runner; real-model campaign is separate explicit mode."""
from tests.knowledge_inputs_v1.run_k0 import SELECTIONS,main
from tests.knowledge_inputs_v1.k8_regression_manifest import CURRENT_REGRESSION_TESTS
SELECTIONS['k8']=CURRENT_REGRESSION_TESTS
SELECTIONS['contracts']=CURRENT_REGRESSION_TESTS
SELECTIONS['critical']=['tests/knowledge_inputs_v1/test_k1_containment.py','tests/knowledge_inputs_v1/test_k1_recovery.py',
    'tests/knowledge_inputs_v1/test_k2_contracts.py','tests/knowledge_inputs_v1/test_k2_interfaces.py',
    'tests/knowledge_inputs_v1/test_k5_context.py','tests/knowledge_inputs_v1/test_k5_integration.py',
    'tests/knowledge_inputs_v1/test_k7_host.py','tests/knowledge_inputs_v1/test_k7_children.py']
if __name__=='__main__':main()
