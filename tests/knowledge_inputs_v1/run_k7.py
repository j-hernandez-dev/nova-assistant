"""K7 private synthetic interface/delegation/privacy/capacity gate."""
from tests.knowledge_inputs_v1.run_k0 import SELECTIONS,main
SELECTIONS['k7']=['tests/knowledge_inputs_v1/test_k7_host.py','tests/knowledge_inputs_v1/test_k7_children.py']
if __name__=='__main__':main()
