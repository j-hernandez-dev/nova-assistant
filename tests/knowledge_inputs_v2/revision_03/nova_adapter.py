"""Real Nova campaign adapter, imported only after joint human authorization."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import urllib.request

from scorer import digest
from runner import DOCS, FrozenAbort, read, write

def verify_backend(profile):
    model = profile["llm"]
    def api(path, data=None):
        body = json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request(model["endpoint"] + "/api/" + path, data=body,
                    headers={"Content-Type":"application/json"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=15) as response: return json.load(response)
    tags, resident = api("tags"), api("ps")
    for rows in (tags.get("models", []), resident.get("models", [])):
        if not any(x.get("name") == model["model"] and x.get("digest") == model["digest"] for x in rows):
            raise FrozenAbort("MODEL_DIGEST_NOT_INSTALLED_AND_RESIDENT")
    show = api("show", {"model":model["model"]})
    if "completion" not in show.get("capabilities", []): raise FrozenAbort("COMPLETION_UNAVAILABLE")
    runners = [x.get("details", {}).get("runner") for x in tags.get("models", []) if x.get("name")==model["model"]]
    declared = [x for x in runners if x is not None]
    if declared and declared != [model["runner"]]: raise FrozenAbort("BACKEND_RUNNER_MISMATCH")
    return dict(tags=tags,resident=resident,show=show,model_digest=model["digest"],backend="Ollama")

def workspace_files(workspaces):
    return {str(p.relative_to(workspace))+":"+str(i):hashlib.sha256(p.read_bytes()).hexdigest()
            for i,workspace in enumerate(workspaces) for p in sorted(workspace.rglob("*")) if p.is_file()}

class NovaAdapter:
    def __init__(self, profile, context_profile, corpus):
        self.profile, self.context_profile, self.corpus = profile, context_profile, corpus
        self.clients = {}; self.requests = []; self.bindings = []; self.sources = {}
        self.retrieved = []; self.phase = "INITIAL"
        self.restore_admission = None

    def _create(self, owner, workspace, state, directory, audit):
        # All product/provider imports stay behind the execution gate.
        from local_cli.application.providers import ProviderManager
        from local_cli.application.rag import RAGService
        from local_cli.application.secrets import SecretRedactor
        from local_cli.bootstrap_cli import create_cli_application
        from local_cli.config import Config
        from local_cli.providers.ollama_provider import OllamaProvider
        from local_cli.tools.write_tool import WriteTool
        from local_cli.application.persistence import PersistenceService
        from local_cli.infrastructure.persistence import LegacyConversationRepository, LegacySessionSnapshotStore
        workspace.mkdir(parents=True, exist_ok=True)
        model = self.profile["llm"]
        provider = OllamaProvider(base_url=model["endpoint"])
        original = provider.chat_stream
        def stream(name, messages, **kwargs):
            self.phase = "MODEL"
            options = kwargs.get("options", {})
            if name != model["model"] or options.get("temperature") != model["temperature"] or kwargs.get("think") != model["think"]:
                raise FrozenAbort("INFERENCE_PARAMETERS_DRIFT")
            if options.get("num_ctx") != self.context_profile["contextWindow"] or "seed" in options:
                raise FrozenAbort("CONTEXT_OR_SEED_DRIFT")
            verify_backend(self.profile)
            audit.before_model()
            request = dict(model=name, messages=deepcopy(messages), kwargs=deepcopy(kwargs), response=[])
            self.requests.append(request)
            try:
                for chunk in original(name, messages, **kwargs):
                    request["response"].append(deepcopy(chunk)); yield chunk
            finally: write(directory / "model_requests.json", self.requests)
        provider.chat_stream = stream
        manager = ProviderManager(provider, model["model"])
        manager.redactor = SecretRedactor(source={})
        config = Config(config_file=str(directory / "absent-config"))
        config.state_dir, config.model = str(state), model["model"]
        config.num_ctx = config.context_resource_limit = self.context_profile["contextWindow"]
        config.temperature, config.think_mode = model["temperature"], model["think"]
        config.max_iterations = model["maxIterations"]
        config.memory_embedding_model = ""; config.memory_auto_capture = "off"
        config.web_search_enabled = config.rag = config.auto_approve = config.debug = False
        config.top_p = config.top_k = config.keep_alive = None
        config.context_output_reserve = config.context_safety_margin = None
        config.compact_mode = "truncate"
        persistent = PersistenceService(workspace=workspace,
            conversation=LegacyConversationRepository(directory / (owner+"-transcript"), workspace),
            snapshots=LegacySessionSnapshotStore(directory / (owner+"-transcript")),redactor=manager.redactor)
        system = read(DOCS / "protocol.json")["system"]
        client = create_cli_application(config=config,provider_manager=manager,tools=[WriteTool(cwd=workspace)],
            workspace=workspace,base_messages=[dict(role="system",content=system)],persistence=persistent,
            rag_service=RAGService(None),write=lambda _:None)
        app = client.application
        actor = app.register_knowledge_actor("cli_tty", lambda:True)
        self.clients[owner] = dict(client=client,app=app,actor=actor,workspace=workspace)
        self._host(owner,"source_list",{})  # Initialize all live services before seeding foreign/session data.
        return self.clients[owner]

    def _host(self, owner, name, arguments):
        from local_cli.application.knowledge_host import KnowledgeCommand
        from local_cli.core.contracts import new_command_id
        entry=self.clients[owner]; app=entry["app"]; session=app._session
        receipt=app.execute_knowledge(KnowledgeCommand(new_command_id(),session.session_id,name,arguments,session.state_revision),actor=entry["actor"])
        if not receipt["accepted"]: raise RuntimeError("HOST_REJECTED:"+repr(receipt))
        operation=app._service_operations[receipt["createdIds"]["operationId"]]
        if not operation.done.wait(45): raise TimeoutError("SETUP_OPERATION_TIMEOUT")
        if operation.status.value!="completed": raise RuntimeError("SETUP_OPERATION_FAILED:"+repr(operation.result))
        return operation.result

    def prepare(self, case, directory, audit):
        self.phase="PREPARATION"; self.case,self.directory=case,directory
        state=directory/"state"; target=directory/"workspace-target"
        self._create("target",target,state,directory,audit)
        if case["scope_mode"]=="TWO_SESSIONS_SAME_WORKSPACE": self._create("peer",target,state,directory,audit)
        if case["scope_mode"]=="TWO_WORKSPACES": self._create("foreign",directory/"workspace-foreign",state,directory,audit)
        documents={d["id"]:d for d in self.corpus["documents"]}
        for name in case["setup_documents"]:
            doc=documents[name]; owner=doc["owner"]; entry=self.clients[owner]
            file=directory/"inputs"/(name+".txt"); file.parent.mkdir(exist_ok=True)
            file.write_bytes(doc["payload"].encode("utf-8"))
            previous=self.sources.get(doc["source"])
            before={x.source_id for x in entry["app"]._knowledge.service.store.list_sources(entry["app"]._knowledge.service.access)}
            if previous is None:
                self._host(owner,"source_import",dict(path=str(file),scope=doc["scope"]))
                service=entry["app"]._knowledge.service
                created=[x for x in service.store.list_sources(service.access) if x.source_id not in before]
                if len(created)!=1: raise RuntimeError("AMBIGUOUS_IMPORTED_SOURCE")
                source=created[0]
            else:
                self._host(owner,"source_refresh",dict(sourceId=previous["source_id"],path=str(file)))
                service=entry["app"]._knowledge.service; source=service.store.get_source(previous["source_id"],service.access)
            prepared=service.store.read_prepared(source.current_revision_id,service.access)
            if len(prepared.chunks)!=1: raise RuntimeError("FIXTURE_EXPECTS_ONE_REAL_CHUNK")
            chunk=prepared.chunks[0]
            self.bindings.append(dict(document=name,source_id=source.source_id,revision_id=source.current_revision_id,
                chunk_id=chunk.chunk_id,ordinal=chunk.ordinal,revision=doc["revision"],
                scope=dict(kind=source.scope.kind.value,workspace_id=source.scope.workspace_id,session_id=source.scope.session_id),raw_scope=source.scope.to_dict(),
                payload_sha256=prepared.revision.content_digest,text=chunk.text,text_sha256=digest(chunk.text),locator=chunk.locator_start.to_dict()))
            self.sources[doc["source"]]=dict(source_id=source.source_id,owner=owner)
        for name in case["delete_sources"]:
            doc=documents[name]; binding=self.sources[doc["source"]]
            self._host(binding["owner"],"source_delete",dict(sourceId=binding["source_id"]))
        if case.get("memory"):
            from local_cli.application.memory import MemoryCommand
            from local_cli.core.contracts import new_command_id
            app=self.clients["target"]["app"]; actor=app.register_memory_actor("cli_tty",lambda:True)
            memory=case["memory"]
            result=app.execute_memory(MemoryCommand(new_command_id(),app._session.session_id,"memory_remember",
                dict(kind=memory["kind"],text=memory["text"],key="r3.lumen.personal_theme")),actor=actor)
            if not result["completed"]: raise RuntimeError("MEMORY_SETUP_FAILED")
            write(directory/"memory_seed_receipt.json",result)
        self.setup_states=self._states()
        for entry in self.clients.values():
            app=entry['app']
            if app._memory is None: app._memory=app._memory_factory(entry['workspace'],app.redactor)
        write(directory/"setup_manifest.json",dict(bindings=self.bindings,source_states=self.setup_states))
        app=self.clients["target"]["app"]; service=app._knowledge.service
        original=service.retrieve
        def retrieval(query, **kwargs):
            self.phase="RETRIEVAL"; audit.observe("retrieval")
            result=original(query,**kwargs)
            self.retrieved.extend(dict(source_id=c.source_id,revision_id=c.revision_id,chunk_id=c.chunk.chunk_id,
                text=c.chunk.text,text_sha256=digest(c.chunk.text)) for c in result.candidates)
            write(directory/"retrieval_observations.json",self.retrieved)
            return result
        service.retrieve=retrieval
        import local_cli.application.session as session_module
        self.restore_admission=session_module.admit_capsule
        self.memory_retrieved=[]
        self.memory_retrieved_ids=[]
        def admission(working,manager,tools,recalled):
            self.phase="ADMISSION"; audit.observe("admission")
            self.memory_retrieved=[x.canonical_text for x in recalled.records]
            self.memory_retrieved_ids=[str(x.memory_id) for x in recalled.records]
            return self.restore_admission(working,manager,tools,recalled)
        session_module.admit_capsule=admission

    def _states(self):
        states={}
        for alias,binding in self.sources.items():
            service=self.clients[binding["owner"]]["app"]._knowledge.service
            detail=service.store.source_detail(binding["source_id"],service.access)
            source=detail.summary.source
            # Real read-only relational tombstone observation, not document text.
            with service.store._lock:
                tombstone=service.store._connection.execute("SELECT 1 FROM source_tombstones WHERE source_id=?",(binding["source_id"],)).fetchone() is not None
            states[alias]=dict(source_id=source.source_id,current_revision_id=source.current_revision_id,
                lifecycle=source.lifecycle_state.value,scope=source.scope.to_dict(),tombstone=tombstone,
                revision_publications={r.revision_id:s for r,s in zip(detail.revisions,detail.revision_states)})
        return states

    def turn(self, case, audit):
        from local_cli.application.commands import ApplicationCommand,CommandKind
        from local_cli.core.contracts import new_command_id
        app=self.clients["target"]["app"]
        def memory_stats():
            from local_cli.core.memory import MemoryAccessScope
            service=app._memory
            wid=service.identity.resolve_workspace(str(app._session.workspace),register=False)
            return service.store.export_fixture(MemoryAccessScope(subject_id=service.subject,workspace_id=wid,include_global=True))
        workspaces=list(dict.fromkeys(x["workspace"] for x in self.clients.values()))
        before=workspace_files(workspaces); memory_before=memory_stats()
        receipt=app.handle(ApplicationCommand(new_command_id(),CommandKind.SUBMIT_USER_INPUT,
            dict(content=case["query"]),app._session.session_id))
        if not receipt.accepted: raise RuntimeError("TURN_REJECTED")
        turn=app._session.turns[-1]
        if not turn.done.wait(180):
            turn.cancellation.request()
            if not turn.done.wait(45): raise TimeoutError("TURN_CANCELLATION_TIMEOUT")
        self.phase="OBSERVATION"
        capsule=turn.knowledge_admission.capsule if turn.knowledge_admission else None
        admitted=[]
        if capsule:
            for evidence in capsule.evidence:
                target=evidence.target
                admitted.append(dict(source_id=target.source_id,revision_id=target.revision_id,chunk_id=target.chunk_id,
                    text=evidence.text,text_sha256=digest(evidence.text),citation_id=evidence.citation_id,
                    locator=target.locator.to_dict(),truncated=evidence.truncated))
        prompt=self.requests[-1]["messages"] if self.requests else []
        prompt_evidence=[]
        from local_cli.core.knowledge_context import KNOWLEDGE_HEADER
        for message in prompt:
            content=message.get("content","")
            if content.startswith(KNOWLEDGE_HEADER+"\n"):
                for line in content.splitlines()[1:-1]:
                    row=json.loads(line)
                    match=next((e for e in admitted if e["citation_id"]==row["id"]),None)
                    if match:
                        prompt_evidence.append(dict(match,text=row["text"],text_sha256=digest(row["text"]),truncated=row["truncated"]))
                    else: prompt_evidence.append(dict(citation_id=row["id"],text=row["text"]))
        report=turn.citation_reports[-1] if turn.citation_reports else dict(valid=[],invalid=[])
        validated=[dict(citation_id=v.get("citationId"),source_id=v.get("sourceId"),revision_id=v.get("revisionId"),chunk_id=v.get("chunkId"),locator=v.get("locator")) for v in report["valid"]]
        after=workspace_files(workspaces); memory_after=memory_stats()
        calls=[call for request in self.requests for chunk in request["response"] for call in chunk.get("message",{}).get("tool_calls",[])]
        effects=[]
        if before!=after: effects.append("FILE_WRITE")
        if memory_before!=memory_after: effects.append("MEMORY_MUTATION")
        if calls: effects.append("DOCUMENT_AUTHORITY")  # Every campaign request grants zero tool effects.
        memory=turn.memory_snapshot
        from local_cli.core.context import MEMORY_HEADER
        memory_prompt=next((m["content"] for m in prompt if m.get("content","").startswith(MEMORY_HEADER)),None)
        access=app._knowledge.service.access
        owner_access={name:dict(workspace_id=e['app']._knowledge.service.access.workspace_id,
            session_id=e['app']._knowledge.service.access.session_id) for name,e in self.clients.items()}
        budget=next((r['budget'] for r in reversed(turn.context_reports) if 'budget' in r),{})
        if 'retrieval_tokens' in budget and 'memory_tokens' in budget:
            budget=dict(budget,knowledge_tokens=budget['retrieval_tokens']-budget['memory_tokens'])
        observed=dict(runtime_kind="real_model" if self.requests else "NO_MODEL_REQUEST",bindings=self.bindings,access=dict(workspace_id=access.workspace_id,session_id=access.session_id),owner_access=owner_access,
            retrieved=self.retrieved,admitted=admitted,prompt_evidence=prompt_evidence,
            answer=turn.final_content,invalid_citations=report["invalid"],validated_citations=validated,
            effects=effects,files_before=before,files_after=after,memory_before=memory_before,memory_after=memory_after,
            memory=dict(retrieved_texts=self.memory_retrieved,admitted_texts=[r.canonical_text for r in memory.records] if memory else [],
                retrieved_ids=self.memory_retrieved_ids,record_ids=[str(r.memory_id) for r in memory.records] if memory else [],capsule=memory.capsule if memory else None,prompt_capsule=memory_prompt),
            source_states=self._states(),turn_status=turn.status.value,terminal_count=turn.terminal_count,
            context_reports=turn.context_reports,budget=budget,context_window=self.context_profile['contextWindow'],
            profile_id='4K' if self.context_profile['contextWindow']==4096 else '8K',tool_calls=calls,setup_states=self.setup_states)
        return observed

    def close(self, directory):
        if self.restore_admission is not None:
            import local_cli.application.session as session_module
            session_module.admit_capsule=self.restore_admission
        write(directory/"model_requests.json",self.requests)
        for entry in self.clients.values():
            app=entry["app"]; entry["client"].close(); app.close_knowledge()
            app._knowledge.closed.wait(20)
            if app._memory is not None: app._memory.store.close()
            if app.security_audit is not None: app.security_audit.port.close()
