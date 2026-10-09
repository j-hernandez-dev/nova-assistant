"""Private regression runner for the independent V2 contracts/corpus."""
from tests.knowledge_inputs_v1.run_k0 import SELECTIONS, main
SELECTIONS['repair2']=['tests/knowledge_inputs_v1/test_k8_repair2_quality.py',
    'tests/knowledge_inputs_v1/test_k8_repair2_contracts.py']
if __name__=='__main__':main()
