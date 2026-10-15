"""Auditable K8 test applicability manifest.

Historical certification artifacts remain executable by explicit path, but are
not current-product gates.  This is classification, not pytest skipping.
"""
CURRENT_REGRESSION_TESTS = [
    'tests/knowledge_inputs_v1/test_k8_applicability_contracts.py',
    'tests/knowledge_inputs_v1/test_context_capability_profiles.py',
    'tests/knowledge_inputs_v1/test_k0_contracts.py', 'tests/knowledge_inputs_v1/test_k0_corpus.py',
    'tests/knowledge_inputs_v1/test_k1_application.py', 'tests/knowledge_inputs_v1/test_k1_containment.py',
    'tests/knowledge_inputs_v1/test_k1_recovery.py', 'tests/knowledge_inputs_v1/test_k1_store.py',
    'tests/knowledge_inputs_v1/test_k2_acquisition.py', 'tests/knowledge_inputs_v1/test_k2_application.py',
    'tests/knowledge_inputs_v1/test_k2_composition.py', 'tests/knowledge_inputs_v1/test_k2_contracts.py',
    'tests/knowledge_inputs_v1/test_k2_interfaces.py', 'tests/knowledge_inputs_v1/test_k3_extraction.py',
    'tests/knowledge_inputs_v1/test_k3_pdf_repair.py', 'tests/knowledge_inputs_v1/test_k4_chunking.py',
    'tests/knowledge_inputs_v1/test_k4_legacy.py', 'tests/knowledge_inputs_v1/test_k4_quality.py',
    'tests/knowledge_inputs_v1/test_k4_retrieval.py', 'tests/knowledge_inputs_v1/test_k4_semantic.py',
    'tests/knowledge_inputs_v1/test_k5_context.py', 'tests/knowledge_inputs_v1/test_k5_integration.py',
    'tests/knowledge_inputs_v1/test_k6_passive_web.py', 'tests/knowledge_inputs_v1/test_k7_children.py',
    'tests/knowledge_inputs_v1/test_k7_host.py', 'tests/knowledge_inputs_v1/test_k8_execution.py',
    'tests/knowledge_inputs_v1/test_k8_harness.py', 'tests/knowledge_inputs_v1/test_k8_parser_contracts.py',
    'tests/knowledge_inputs_v1/test_k8_repair_contracts.py', 'tests/knowledge_inputs_v1/test_k8_repair.py',
    'tests/knowledge_inputs_v1/test_k8_repair2_contracts.py', 'tests/knowledge_inputs_v1/test_k8_repair2_control_regression.py',
    'tests/knowledge_inputs_v1/test_k8_repair2_quality.py', 'tests/knowledge_inputs_v1/test_k8_repair3_harness.py',
    'tests/knowledge_inputs_v1/test_k8_repair3_quality.py', 'tests/knowledge_inputs_v1/test_k8_repair3_regressions.py',
    'tests/knowledge_inputs_v1/test_k8_repair4_audit.py', 'tests/knowledge_inputs_v1/test_k8_repair4_harness.py',
    'tests/knowledge_inputs_v1/test_k8_repair4_output.py', 'tests/knowledge_inputs_v1/test_k8_repair5_guard.py',
    'tests/knowledge_inputs_v1/test_k8_repair5_harness.py', 'tests/knowledge_inputs_v1/test_k8_repair6_quality.py',
    'tests/knowledge_inputs_v1/test_k8_repair6_query.py',
]

HISTORICAL_CERTIFICATION_ARTIFACTS = [
    'tests/knowledge_inputs_v1/test_k8_post_cert_conflict.py',
    'tests/knowledge_inputs_v1/test_k8_quality.py',
]
