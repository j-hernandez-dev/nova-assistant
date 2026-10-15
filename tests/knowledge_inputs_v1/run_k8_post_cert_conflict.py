"""Private deterministic post-certification checks; never invokes original E2E."""
from tests.knowledge_inputs_v1.run_k0 import SELECTIONS, main

SELECTIONS['postcert-baseline'] = [
    'tests/knowledge_inputs_v1/test_k8_repair6_query.py',
    'tests/knowledge_inputs_v1/test_k8_repair6_quality.py',
    'tests/knowledge_inputs_v1/test_k4_retrieval.py',
    'tests/knowledge_inputs_v1/test_k5_context.py',
]
SELECTIONS['postcert'] = ['tests/knowledge_inputs_v1/test_k8_post_cert_conflict.py']

if __name__ == '__main__':
    main()
