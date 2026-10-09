"""K2 compatibility selection using the existing hermetic K0 harness.

No CI exclusions, model runs or alternate product path. A fresh external
output directory is mandatory; subprocess profiles/cache/state stay private.
"""
from tests.knowledge_inputs_v1.run_k0 import main, SELECTIONS

if __name__ == '__main__':
    SELECTIONS['compatibility'] = [
        'tests/test_nova_core_phase8_providers.py',
        'tests/test_nova_core_phase11_characterization.py',
        'tests/test_nova_core_phase14_characterization.py',
        'tests/test_nova_core_phase11_adapter.py',
    ]
    main()
