"""Private K5 contract/integration gate; no real model quality claims."""
from tests.knowledge_inputs_v1.run_k0 import SELECTIONS, main
SELECTIONS['k5']=['tests/knowledge_inputs_v1/test_k5_context.py','tests/knowledge_inputs_v1/test_k5_integration.py']
SELECTIONS['compatibility']=['tests/test_nova_core_phase0_characterization.py','tests/test_nova_core_phase10_services.py']
if __name__=='__main__': main()
