"""Executed HEAD characterization using private stores and synthetic adapters.

Observed legacy limitations stay visible; assertions document baseline, not
future MEMORY semantics. No installed model, user state or ambient secrets read.
"""

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
import sqlite3

from local_cli.application.persistence import PersistenceService
from local_cli.application.rag import RAGService, create_rag_service
from local_cli.application.secrets import SecretRedactor
from local_cli.conversation_store import ConversationStore
from local_cli.infrastructure.persistence import LegacyConversationRepository, LegacySessionSnapshotStore
from local_cli.session_log import SessionLogger, project_slug
from local_cli.skills import SkillsLoader


def persistence(workspace, state):
    return PersistenceService(workspace=workspace,
        conversation=LegacyConversationRepository(state, workspace),
        snapshots=LegacySessionSnapshotStore(state), redactor=SecretRedactor(source={}))


def characterize_persistence(root):
    workspace = root / 'workspace'
    workspace.mkdir(parents=True)
    state = root / 'state'
    svc = persistence(workspace, state)
    rows = [{'role': 'user', 'content': f'Synthetic message {i}'} for i in range(450)]
    started = perf_counter()
    svc.save(rows)
    save_ms = (perf_counter() - started) * 1000
    restarted = persistence(workspace, state)
    started = perf_counter()
    loaded = restarted.load()
    load_ms = (perf_counter() - started) * 1000
    assert loaded == rows[-400:]
    key = svc.save_session(rows, 'synthetic-manual')
    assert restarted.restore(workspace=workspace, snapshot_key=key) == rows
    autosave = ConversationStore(str(state), cwd=str(workspace)).path
    autosave_bytes = autosave.stat().st_size
    snapshot_bytes = (state / 'sessions' / f'{key}.jsonl').stat().st_size
    # Legacy namespace is a slug, not a trusted hashed MEMORY workspace ID.
    a, b = root / 'Alpha_One', root / 'Alpha-One'
    assert project_slug(str(a)) == project_slug(str(b))
    collision_a = persistence(a, state)
    collision_a.save([{'role': 'user', 'content': 'Synthetic source workspace A'}])
    collision_b = persistence(b, state)
    assert collision_b.load()[0]['content'] == 'Synthetic source workspace A'
    cross_manual = persistence(root / 'Other', state).restore(
        workspace=root / 'Other', snapshot_key=key)
    assert cross_manual == rows
    contradictions = [{'role': 'user', 'content': 'Synthetic badge: green.'}] * 12 + [
        {'role': 'user', 'content': 'Synthetic badge: yellow.'}]
    svc.save(contradictions)
    assert restarted.load() == contradictions  # no consolidation/conflict policy
    logger = SessionLogger(str(state), cwd=str(workspace), enabled=True,
        session_id='synthetic-flight', redactor=SecretRedactor(source={}))
    try:
        logger.log('synthetic_event', content='Synthetic diagnostic, not personal memory')
    finally:
        logger.close()
    svc.clear()
    assert svc.load() == [] and logger.path.is_file()
    assert svc.snapshots.load_session(key) == rows
    return {'autosave_input_messages': 450, 'autosave_restored_messages': len(loaded),
        'manual_restored_messages': len(rows), 'autosave_bytes': autosave_bytes,
        'manual_snapshot_bytes': snapshot_bytes, 'save_ms': round(save_ms, 3),
        'load_ms': round(load_ms, 3), 'restart_roundtrip': True,
        'legacy_slug_collision_observed': True, 'manual_cross_workspace_restore_observed': True,
        'repeat_count_preserved': 12, 'contradiction_preserved': True,
        'clear_removes_autosave_only': True, 'snapshot_and_flight_recorder_survive_clear': True,
        'memory_subject_identity': 'ABSENT', 'memory_correction_delete_policy': 'ABSENT'}


class SyntheticEmbeddings:
    """2-D test vector generator for existing RAG plumbing, NOT semantic quality."""
    def __init__(self):
        self.calls = []
        self.unavailable = False

    def embed(self, model, texts):
        self.calls.append((model, isinstance(texts, list)))
        if self.unavailable:
            raise RuntimeError('Synthetic embedding unavailable')
        values = texts if isinstance(texts, list) else [texts]
        return [[0., 1.] if 'Beta' in t else [1., 0.] for t in values]


def characterize_rag(root):
    workspace = root / 'workspace'
    workspace.mkdir(parents=True)
    alpha = workspace / 'Alpha.txt'
    alpha.write_text('Synthetic Alpha document: parser tokens.', encoding='utf-8')
    (workspace / 'Beta.txt').write_text('Synthetic Beta document: database rows.', encoding='utf-8')
    client = SyntheticEmbeddings()
    service = create_rag_service(client=client, workspace=workspace, top_k=2)
    assert service.query('Synthetic Alpha question').context_message() is None
    assert not client.calls
    indexed = service.set_enabled(True)
    assert not indexed.error and indexed.stats['chunks_indexed'] == 2
    started = perf_counter()
    response = service.query('Synthetic Alpha question')
    query_ms = (perf_counter() - started) * 1000
    assert not response.error and response.matches[0]['content'].startswith('Synthetic Alpha')
    assert response.matches[0]['score'] == 1 and response.matches[1]['score'] == 0
    assert response.context_message()['_context_kind'] == 'retrieval'
    with sqlite3.connect(workspace / 'rag_index.db') as connection:
        columns = [row[1] for row in connection.execute('PRAGMA table_info(chunks)')]
    alpha.unlink()  # Synthetic source only, not real user data.
    assert not service.set_enabled(True).error
    stale = service.query('Synthetic Alpha question')
    assert any('Synthetic Alpha' in r['content'] for r in stale.matches)
    client.unavailable = True
    missing = service.query('Synthetic Alpha question')
    assert missing.error.code == 'RAG_EMBEDDING_UNAVAILABLE' and missing.context_message() is None
    service.set_enabled(False)
    count = len(client.calls)
    assert service.query('Synthetic Alpha question').context_message() is None
    assert len(client.calls) == count
    absent = RAGService(None)
    assert absent.set_enabled(True).error.code == 'RAG_UNAVAILABLE'
    return {'existing_algorithm': 'LegacyProjectRetrieval/RAGEngine SQLite + Python cosine scan',
        'mock_embedding_model': 'SYNTHETIC_VECTOR_GENERATOR_NOT_A_MODEL',
        'configured_embedding_model': 'all-minilm', 'synthetic_dimension': 2,
        'real_model_dimension': None, 'real_model_quality': None,
        'query_ms_with_mock_embedding': round(query_ms, 3), 'top_k': 2,
        'indexed_chunks': 2, 'schema_columns': columns,
        'score_is_cosine_not_factual_confidence': True,
        'deleted_document_chunk_still_returned': True,
        'disabled_embedding_calls': 0, 'unavailable_error': missing.error.code,
        'existing_lexical_rag_fallback': 'ABSENT', 'personal_memory_created': False}


def characterize_lexical(root):
    skill = root / 'skills' / 'synthetic'
    skill.mkdir(parents=True)
    (skill / 'SKILL.md').write_text('---\nname: synthetic\ntriggers: [parser, analizador]\n'
        'description: Synthetic lexical fixture\n---\nSynthetic procedural instructions.', encoding='utf-8')
    loader = SkillsLoader(str(root / 'skills'))
    assert len(loader.discover_skills()) == 1
    exact = loader.get_matching_skills('PARSER sample')
    paraphrase = loader.get_matching_skills('recognize a language grammar')
    assert len(exact) == 1 and not paraphrase
    return {'existing_lexical': 'SkillsLoader keyword/substring matching',
        'case_insensitive_keyword_matches': 1, 'unmatched_paraphrase_matches': 0,
        'embedding_calls': 0, 'memory_lexical_recall': 'ABSENT',
        'not_rag_or_personal_memory': True}


class SyntheticProvider:
    """Scripted plumbing probe only: no claim of real local model quality/E2E."""
    def __init__(self, name='ollama'):
        self.name = name
        self.requests = []

    def chat_stream(self, model, messages, **kwargs):
        self.requests.append(deepcopy(messages))
        yield {'message': {'role': 'assistant', 'content': 'SYNTHETIC_ACK'}, 'done': True}

    def list_models(self):
        return [{'name': 'synthetic-old'}, {'name': 'synthetic-new'}]

    def get_model_info(self, model):
        return {'name': model, 'model_info': {'synthetic.context_length': 8192}}


def characterize_sessions(root):
    from local_cli.application.commands import ApplicationCommand, CommandKind
    from local_cli.application.providers import ProviderManager
    from local_cli.application.session import AgentSessionCoordinator
    from local_cli.core.contracts import RuntimeCapabilitySnapshot, new_command_id

    a, b = root / 'Alpha', root / 'Beta'
    a.mkdir(parents=True)
    b.mkdir()
    state = root / 'state'
    provider = SyntheticProvider()
    providers = [provider]
    def factory(name):
        p = SyntheticProvider(name)
        providers.append(p)
        return p
    def base(workspace):
        return [{'role': 'system', 'content': f'Synthetic base {workspace.name}'}]
    def assemble():
        # Avoid reading the host environment through default redactor construction.
        with patch('local_cli.application.providers.SecretRedactor',
                   side_effect=lambda: SecretRedactor(source={})):
            pm = ProviderManager(provider, 'synthetic-old', provider_factory=factory,
                clone_factory=lambda p: lambda: SyntheticProvider(p.name))
        return AgentSessionCoordinator(provider=provider, model='synthetic-old',
            provider_manager=pm, tool_factory=lambda ws: [],
            prompt_factory=lambda tools, ws: base(ws)[0]['content'], environment_source={},
            capability_factory=lambda **kw: RuntimeCapabilitySnapshot(
                datetime.now(timezone.utc), 'M0_SYNTHETIC_NO_HOST_PROBE'),
            persistence_factory=lambda ws: persistence(ws, state),
            workspace_rebinder=lambda ws: {'base_messages': base(ws),
                'persistence': persistence(ws, state), 'rag': RAGService(None), 'data': {'workspace': ws.name}})
    def command(c, kind, session=None, payload=None):
        return c.handle(ApplicationCommand(command_id=new_command_id(), kind=kind,
            session_id=session, payload=payload or {}))
    with patch('local_cli.application.session.get_sanitized_env', return_value={}):
        c = assemble()
        start = command(c, CommandKind.START_SESSION, payload={'workspace': str(a)})
        assert start.accepted
        session_id = start.session_id
        assert not command(c, CommandKind.START_SESSION, payload={'workspace': str(b)}).accepted
        receipt = command(c, CommandKind.SUBMIT_USER_INPUT, session_id,
            {'content': 'SYNTHETIC_REMEMBER_TOKEN_ALPHA'})
        assert receipt.accepted and c.wait_for_turn(receipt.created_ids['turnId'], 10)
        first = c.get_snapshot(session_id)
        assert first.turns[-1]['terminalCount'] == 1
        changed = command(c, CommandKind.CHANGE_MODEL, session_id, {'modelId': 'synthetic-new'})
        assert changed.accepted
        assert c.get_snapshot(session_id).transcript == first.transcript
        changed_provider = command(c, CommandKind.CHANGE_PROVIDER, session_id,
            {'providerId': 'llama-server', 'modelId': 'synthetic-new'})
        assert changed_provider.accepted
        c.change_workspace(session_id, str(b))
        assert any(m.get('content') == 'SYNTHETIC_REMEMBER_TOKEN_ALPHA' for m in c.get_snapshot(session_id).transcript)
        receipt = command(c, CommandKind.SUBMIT_USER_INPUT, session_id, {'content': 'Synthetic follow-up'})
        assert receipt.accepted and c.wait_for_turn(receipt.created_ids['turnId'], 10)
        assert any(m.get('content') == 'SYNTHETIC_REMEMBER_TOKEN_ALPHA' for m in providers[-1].requests[-1])
        new_c = assemble()
        new_start = command(new_c, CommandKind.START_SESSION, payload={'workspace': str(a)})
        fresh = new_c.get_snapshot(new_start.session_id)
        assert new_start.session_id != session_id and len(fresh.transcript) == 1
        resumed = command(new_c, CommandKind.EXECUTE_COMMAND, new_start.session_id, {'name': 'resume'})
        assert resumed.accepted and len(new_c.get_snapshot(new_start.session_id).transcript) > 1
        assert not new_c.get_snapshot(new_start.session_id).turns
        # All worker Turns finished above. HEAD has a CloseSession DTO but no
        # handler; do not invent a cleanup lifecycle or change Core in M0.
    return {'provider': 'SCRIPTED_PLUMBING_ONLY_NOT_REAL_MODEL',
        'one_principal_session_enforced': True, 'new_session_id_after_restart': True,
        'fresh_session_auto_restore': False, 'explicit_resume_restores_history_not_turns': True,
        'idle_model_switch_preserves_history': True, 'idle_provider_switch_preserves_history': True,
        'workspace_rebind_retains_previous_history': True,
        'previous_input_reaches_later_generation': True, 'first_turn_terminal_count': 1,
        'durable_subject_id': 'ABSENT'}


def characterize_child(root):
    from local_cli.sub_agent import SubAgent
    root.mkdir(parents=True)
    provider = SyntheticProvider()
    parent_history = [{'role': 'user', 'content': 'SYNTHETIC_PARENT_PRIVATE_TOKEN'}]
    original = deepcopy(parent_history)
    with patch('local_cli.application.providers.SecretRedactor',
               side_effect=lambda: SecretRedactor(source={})):
        child = SubAgent(provider, 'synthetic-old', [], 'SYNTHETIC_DELEGATED_TASK',
            cwd=root, environment={}, redactor=SecretRedactor(source={}))
        result = child.run()
    assert result.status == 'success' and provider.requests
    assert any(m.get('content') == 'SYNTHETIC_DELEGATED_TASK' for m in provider.requests[0])
    assert not any(m.get('content') == 'SYNTHETIC_PARENT_PRIVATE_TOKEN' for m in provider.requests[0])
    assert parent_history == original and not list(root.rglob('*.jsonl'))
    return {'provider': 'SCRIPTED_PLUMBING_ONLY_NOT_REAL_MODEL',
        'delegated_input_received': True, 'parent_history_implicitly_shared': False,
        'parent_transcript_unchanged': True, 'child_created_conversation_store': False,
        'durable_memory_access': 'NOT_IMPLEMENTED_NOT_A_MEMORY_AUTHORIZATION_PROOF'}


def characterize_knowledge(root):
    from local_cli.application.auxiliary import AuxiliaryServices
    from local_cli.core.context import ContextError, ContextManager, message_kind
    from local_cli.knowledge import KnowledgeStore
    store = KnowledgeStore(str(root / 'knowledge'))
    store.save_item('synthetic-item', 'Synthetic explicit knowledge', 'Synthetic artifact')
    store.add_artifact('synthetic-item', 'notes.txt', 'k' * 30000)
    result = AuxiliaryServices(knowledge=store).execute('knowledge_load', {'name': 'synthetic-item'})
    # Live HEAD characterization changed normatively in M7. Archived M0 evidence
    # still describes the old mandatory-system failure and is not rewritten.
    assert result.context_message['role'] == 'user' and message_kind(result.context_message) == 'retrieval'
    prepared=ContextManager().prepare([dict(result.context_message), {'role':'user','content':'Synthetic current'}])
    assert {'role':'user','content':'Synthetic current'} in prepared.messages
    assert prepared.budget.retrieval_tokens<=int(.15*prepared.budget.available)
    return {'legacy_injection_kind':'user','retrieval_tag':True,'large_knowledge_overflow':None,
        'memory_capsule':'ABSENT','normative_revision':'M7 optional untrusted knowledge; M0 archive unchanged'}
