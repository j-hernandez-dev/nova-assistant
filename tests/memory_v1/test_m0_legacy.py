"""Synthetic/private integration characterizations, with limitations explicit."""

from tests.memory_v1.legacy_baseline import (characterize_lexical,
    characterize_persistence, characterize_rag, characterize_sessions,
    characterize_child, characterize_knowledge)


def test_current_persistence_and_scope_limitations_are_reproducible(tmp_path):
    report = characterize_persistence(tmp_path)
    assert report['autosave_restored_messages'] == 400
    assert report['manual_restored_messages'] == 450
    assert report['legacy_slug_collision_observed']
    assert report['snapshot_and_flight_recorder_survive_clear']


def test_existing_rag_is_not_memory_and_missing_embeddings_are_nonfatal(tmp_path):
    report = characterize_rag(tmp_path)
    assert report['synthetic_dimension'] == 2
    assert report['real_model_quality'] is None
    assert report['deleted_document_chunk_still_returned']
    assert not report['personal_memory_created']


def test_existing_lexical_matching_works_without_embeddings_but_is_not_memory(tmp_path):
    report = characterize_lexical(tmp_path)
    assert report['embedding_calls'] == 0
    assert report['memory_lexical_recall'] == 'ABSENT'


def test_application_identity_provider_workspace_and_restart_baseline(tmp_path):
    report = characterize_sessions(tmp_path)
    assert report['previous_input_reaches_later_generation']
    assert report['explicit_resume_restores_history_not_turns']
    assert report['durable_subject_id'] == 'ABSENT'


def test_child_private_context_does_not_implicitly_recall_parent(tmp_path):
    report = characterize_child(tmp_path / 'child')
    assert report['parent_transcript_unchanged']
    assert not report['parent_history_implicitly_shared']


def test_live_knowledge_injection_is_budgeted_data_not_personal_memory(tmp_path):
    report = characterize_knowledge(tmp_path)
    assert report['legacy_injection_kind']=='user' and report['retrieval_tag']
    assert report['large_knowledge_overflow'] is None and report['memory_capsule']=='ABSENT'
