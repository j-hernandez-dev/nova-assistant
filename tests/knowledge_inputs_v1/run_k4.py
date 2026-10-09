"""Focused K4 gates reusing the private-state runner; no inference/downloads."""
from tests.knowledge_inputs_v1.run_k0 import SELECTIONS, main
SELECTIONS['chunking']=['tests/knowledge_inputs_v1/test_k4_chunking.py']
SELECTIONS['k4']=['tests/knowledge_inputs_v1/test_k4_chunking.py',
    'tests/knowledge_inputs_v1/test_k4_retrieval.py', 'tests/knowledge_inputs_v1/test_k4_semantic.py',
    'tests/knowledge_inputs_v1/test_k4_legacy.py']
SELECTIONS['quality']=['tests/knowledge_inputs_v1/test_k4_quality.py']
if __name__=='__main__': main()
