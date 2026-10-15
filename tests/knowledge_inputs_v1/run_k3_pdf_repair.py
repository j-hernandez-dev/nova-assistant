"""Focused PDF/K3 gates, reusing the private-state Knowledge runner unchanged."""
from tests.knowledge_inputs_v1.run_k0 import SELECTIONS, main

SELECTIONS['pdf'] = ['tests/knowledge_inputs_v1/test_k3_pdf_repair.py']
SELECTIONS['k3'] = [*SELECTIONS['pdf'], 'tests/knowledge_inputs_v1/test_k3_extraction.py',
                    'tests/knowledge_inputs_v1/test_k2_composition.py']

if __name__ == '__main__':
    main()
