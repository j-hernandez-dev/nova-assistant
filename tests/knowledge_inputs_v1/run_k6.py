"""K6 synthetic passive-web contracts; private state, no public web/inference."""
from tests.knowledge_inputs_v1.run_k0 import SELECTIONS, main
SELECTIONS['k6']=['tests/knowledge_inputs_v1/test_k6_passive_web.py']
SELECTIONS['s5']=['tests/security_v12/test_s5_contracts.py','tests/security_v12/test_s5_runtime.py']
if __name__=='__main__': main()
