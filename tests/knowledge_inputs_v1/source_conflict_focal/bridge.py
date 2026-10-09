"""Normal CLI Application composition; only observe calls, never alter results."""
from copy import deepcopy
from pathlib import Path

from .common import StopExecution, append, backend, file_tree, now, read, text_sha, write, DOCS


class Bridge:
    def __init__(self, directory, workspace, state, *, network, execution=False, check=None):
        from local_cli.application.providers import ProviderManager
        from local_cli.application.rag import RAGService
        from local_cli.application.secrets import SecretRedactor
        from local_cli.bootstrap_cli import create_cli_application
        from local_cli.config import Config
        from local_cli.providers.ollama_provider import OllamaProvider
        from local_cli.tools.write_tool import WriteTool
        from local_cli.application.persistence import PersistenceService
        from local_cli.infrastructure.persistence import LegacyConversationRepository, LegacySessionSnapshotStore
        self.directory, self.workspace, self.network = directory, workspace, network
        self.profile = read(DOCS / 'execution_profile.json')
        self.protocol = read(DOCS / 'protocol.json')
        self.requests, self.retrieved, self.tool_events = [], [], []
        self.retrieval_calls, self.transport_errors = 0, []
        self.last_turn = None
        self.execution, self.check = execution, check
        provider = OllamaProvider(base_url=self.profile['endpoint'])
        original = provider.chat_stream
        def stream(name, messages, **kwargs):
            if not self.execution or not self.network.allow_chat:
                raise StopExecution('PREPARATION_INFERENCE_FORBIDDEN')
            self.check()  # Pins/runtime/authorization immediately before every generation.
            from .common import runtime_identity
            expected = runtime_identity(self.profile)['effective_options']
            if name != self.profile['model'] or kwargs.get('options') != expected or kwargs.get('think') is not False:
                raise StopExecution('MODEL_REQUEST_PARAMETERS_DRIFT')
            if kwargs.get('format') is not None or 'seed' in kwargs.get('options', {}):
                raise StopExecution('RESPONSE_FORMAT_OR_SEED_DRIFT')
            identity = backend(self.profile)
            request = dict(timestamp=now(), model=name, messages=deepcopy(messages),
                           kwargs=deepcopy(kwargs), identity_before=identity, response=[])
            self.requests.append(request)
            write(directory / 'model_requests.json', self.requests)
            try:
                for chunk in original(name, messages, **kwargs):
                    request['response'].append(deepcopy(chunk))
                    append(directory / 'model_chunks.jsonl', dict(request_index=len(self.requests), chunk=chunk))
                    yield chunk
            except Exception as error:
                request['transport_exception'] = dict(type=type(error).__name__, message=str(error))
                # Not every Python exception is a genuine transport incident.
                if type(error).__name__ in ('OllamaConnectionError', 'OllamaRequestError', 'OllamaStreamError'):
                    self.transport_errors.append(request['transport_exception'])
                raise
            finally:
                write(directory / 'model_requests.json', self.requests)
        provider.chat_stream = stream
        def disallowed(*args, **kwargs):
            raise StopExecution('ONLY_AUTHORIZED_NORMAL_CHAT_STREAM_ALLOWED')
        provider.chat = disallowed
        manager = ProviderManager(provider, self.profile['model'])
        manager.redactor = SecretRedactor(source={})
        config = Config(config_file=str(directory / 'absent-config'))
        config.state_dir, config.model = str(state), self.profile['model']
        config.ollama_host = self.profile['endpoint']
        config.num_ctx = config.context_resource_limit = 8192
        config.temperature, config.think_mode = 0, False
        config.max_iterations = 6
        config.memory_embedding_model, config.memory_auto_capture = '', 'off'
        config.web_search_enabled = config.rag = config.auto_approve = config.debug = False
        config.top_p = config.top_k = config.keep_alive = None
        config.context_output_reserve = config.context_safety_margin = None
        config.compact_mode = 'truncate'
        persistent = PersistenceService(workspace=workspace,
            conversation=LegacyConversationRepository(directory / 'transcript', workspace),
            snapshots=LegacySessionSnapshotStore(directory / 'transcript'), redactor=manager.redactor)
        self.cli = create_cli_application(config=config, provider_manager=manager, tools=[WriteTool(cwd=workspace)],
            workspace=workspace, base_messages=[dict(role='system', content=self.protocol['system'])],
            persistence=persistent, rag_service=RAGService(None), write=lambda _: None)
        self.app = self.cli.application
        self.actor = self.app.register_knowledge_actor('cli_tty', lambda: True)
        self.host('source_list', {})  # One real owner, no competing application.

    def host(self, name, arguments):
        from local_cli.application.knowledge_host import KnowledgeCommand
        from local_cli.core.contracts import new_command_id
        app = self.app
        receipt = app.execute_knowledge(KnowledgeCommand(new_command_id(), app._session.session_id,
            name, arguments, app._session.state_revision), actor=self.actor)
        if not receipt['accepted']:
            raise StopExecution('HOST_REJECTED:' + repr(receipt))
        operation = app._service_operations[receipt['createdIds']['operationId']]
        if not operation.done.wait(45) or operation.status.value != 'completed':
            raise StopExecution('HOST_OPERATION_FAILED:' + repr(operation.result))
        append(self.directory / 'host_operations.jsonl', dict(name=name, arguments=arguments,
               receipt=receipt, result=operation.result))
        return operation.result

    def bindings(self, documents):
        service = self.app._knowledge.service
        result = []
        sources = service.store.list_sources(service.access)
        for document in documents:
            matching = [s for s in sources if s.display_name == document['filename']]
            if len(matching) != 1:
                raise StopExecution('SOURCE_BINDING_AMBIGUOUS')
            source = matching[0]
            prepared = service.store.read_prepared(source.current_revision_id, service.access)
            if len(prepared.chunks) != 1:
                raise StopExecution('FIXTURE_EXPECTED_ONE_CHUNK_PER_SOURCE')
            chunk = prepared.chunks[0]
            result.append(dict(document_id=document['id'], filename=document['filename'], value=document['value'],
                source_id=source.source_id, revision_id=source.current_revision_id, chunk_id=chunk.chunk_id,
                text=chunk.text, text_sha256=text_sha(chunk.text), payload_sha256=prepared.revision.content_digest,
                locator=chunk.locator_start.to_dict(), locator_end=chunk.locator_end.to_dict(),
                source=source.to_dict(), revision=prepared.revision.to_dict(), scope=source.scope.to_dict()))
        if len(sources) != 2:
            raise StopExecution('SEED_HAS_EXTRA_SOURCES')
        return result

    def states(self):
        service = self.app._knowledge.service
        result = []
        for source in service.store.list_sources(service.access):
            detail = service.store.source_detail(source.source_id, service.access)
            with service.store._lock:
                tombstone = service.store._connection.execute(
                    'SELECT 1 FROM source_tombstones WHERE source_id=?', (source.source_id,)).fetchone() is not None
            result.append(dict(source=source.to_dict(), revision_states=dict(zip(
                [r.revision_id for r in detail.revisions], detail.revision_states)), tombstone=tombstone))
        return sorted(result, key=lambda s: s['source']['sourceId'])

    def memory_snapshot(self):
        from local_cli.core.memory import MemoryAccessScope
        app = self.app
        if app._memory is None:
            app._memory = app._memory_factory(self.workspace, app.redactor)
        memory = app._memory
        wid = memory.identity.resolve_workspace(str(self.workspace), register=False)
        return memory.store.export_fixture(MemoryAccessScope(subject_id=memory.subject, workspace_id=wid, include_global=True))

    def authority_snapshot(self):
        runtime = self.app._session.tool_runtime
        issuer = runtime._issuer
        return dict(policy_revision=runtime.policy.revision,
            ceiling=dict(ceiling_id=issuer.ceiling.ceiling_id, revision=issuer.ceiling.revision,
                         fingerprint=issuer.ceiling.fingerprint) if issuer is not None else None,
            grants=sorted(issuer._issued) if issuer is not None else [],
            approvals=sorted(k for k, state in self.app._session.approval_gate._states.items()
                             if state.decision is True))

    def instrument(self):
        service = self.app._knowledge.service
        original = service.retrieve
        def retrieve(query, **kwargs):
            self.retrieval_calls += 1
            result = original(query, **kwargs)
            observation = dict(query=query, mode=result.mode, semantic_state=result.semantic_state,
                candidates=[dict(source_id=c.source_id, revision_id=c.revision_id,
                    chunk_id=c.chunk.chunk_id, locator=c.chunk.locator_start.to_dict(),
                    text=c.chunk.text, text_sha256=text_sha(c.chunk.text)) for c in result.candidates])
            self.retrieved.append(observation)
            write(self.directory / 'retrieval.json', self.retrieved)
            return result
        service.retrieve = retrieve
        runtime = self.app._session.tool_runtime
        publish = runtime._publish
        def capture(event):
            self.tool_events.append(event)
            kind, invocation, result = event
            append(self.directory / 'tools.jsonl', dict(kind=kind.value, operation_id=str(invocation.operation_id),
                name=invocation.name, arguments=dict(invocation.arguments), result=result.to_dict() if result else None))
            publish(event)  # Original owner receives unchanged event/result.
        runtime._publish = capture

    def run_turn(self, query):
        from local_cli.application.commands import ApplicationCommand, CommandKind
        from local_cli.core.contracts import new_command_id
        from local_cli.core.knowledge_context import KNOWLEDGE_HEADER
        from tests.knowledge_inputs_v1.ready_harness.focused import HostSnapshot, observe_tool
        self.instrument()
        before = dict(files=file_tree(self.workspace), memory=self.memory_snapshot(),
                      authority=self.authority_snapshot(), lifecycle=self.states())
        write(self.directory / 'before.json', before)
        receipt = self.app.handle(ApplicationCommand(new_command_id(), CommandKind.SUBMIT_USER_INPUT,
            dict(content=query), self.app._session.session_id))
        write(self.directory / 'submit_receipt.json', receipt.to_dict())
        if not receipt.accepted:
            raise StopExecution('TURN_REJECTED')
        turn = self.app._session.turns[-1]
        self.last_turn = turn
        if not turn.done.wait(self.protocol['wait_seconds']):
            turn.cancellation.request()
            turn.done.wait(self.protocol['cancel_wait_seconds'])
            raise TimeoutError('TURN_TIMEOUT_PRESERVED_NO_RETRY')
        capsule = turn.knowledge_admission.capsule if turn.knowledge_admission else None
        admitted = [dict(citation_id=e.citation_id, source_id=e.target.source_id,
            revision_id=e.target.revision_id, chunk_id=e.target.chunk_id, locator=e.target.locator.to_dict(),
            text=e.text, text_sha256=text_sha(e.text), truncated=e.truncated)
            for e in capsule.evidence] if capsule else []
        after = dict(files=file_tree(self.workspace), memory=self.memory_snapshot(),
                     authority=self.authority_snapshot(), lifecycle=self.states())
        prompts = [dict(index=i, rows=[m for m in r['messages']
            if m.get('content', '').startswith(KNOWLEDGE_HEADER + '\n')]) for i, r in enumerate(self.requests)]
        reports = turn.citation_reports
        citations = reports[-1] if reports else dict(valid=[], invalid=[])
        terminal_tools = [e for e in self.tool_events if e[2] is not None]
        host_before = HostSnapshot(before['files'], before['memory'], {})
        host_after = HostSnapshot(after['files'], after['memory'], {})
        tools = [observe_tool(inv, result, self.tool_events, host_before, host_after)
                 for _, inv, result in terminal_tools]
        # No current-user tool authority; independent issuance/approval/policy
        # deltas fail conservatively rather than deriving authority from requests.
        authority_changes = before['authority'] != after['authority']
        events = [e.to_dict() for e in self.app.poll_events(self.app.subscribe_events(
            self.app._session.session_id, after_sequence=0, include_internal=True))]
        observation = dict(runtime_kind='real_local_model' if self.requests else 'NO_INFERENCE',
            turn_id=str(turn.turn_id), turn_status=turn.status.value, terminal_count=turn.terminal_count,
            error_code=turn.error_code, answer=turn.final_content, retrieved=self.retrieved,
            admitted=admitted, citation_registry=[e.target.to_dict() | {'citationId': e.citation_id}
                for e in capsule.evidence] if capsule else [], citation_reports=reports,
            valid_citations=citations['valid'], invalid_citations=citations['invalid'], prompt_evidence=prompts,
            before=before, after=after, tool_observations=tools,
            authority=dict(document_derived_authority='NOT_OBSERVED' if not authority_changes else 'UNRESOLVED',
                independent_authority_change=authority_changes, observation_basis='host policy/ceiling/grants/approvals before-after + ToolRuntime events/results'),
            context_reports=turn.context_reports, events=events,
            counters=dict(inference=self.network.chat_requests, retrieval=self.retrieval_calls,
                          admission=1 if turn.knowledge_admission is not None else 0),
            transport_errors=self.transport_errors)
        write(self.directory / 'after.json', after)
        write(self.directory / 'observation.json', observation)
        return observation

    def close(self):
        write(self.directory / 'model_requests.json', self.requests)
        self.cli.close()
        self.app.close_knowledge()
        if not self.app._knowledge.closed.wait(20):
            raise StopExecution('KNOWLEDGE_CLOSE_TIMEOUT')
        if self.app._memory is not None:
            self.app._memory.store.close()
        if self.app.security_audit is not None:
            self.app.security_audit.port.close()
