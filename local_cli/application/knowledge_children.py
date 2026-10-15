"""Only parent-admitted refs; no child store/query/import authority."""
from dataclasses import replace
from local_cli.core.knowledge import KnowledgeError,SourceLifecycle
from local_cli.core.knowledge_context import CitationRegistry,KnowledgeCapsule
from local_cli.core.knowledge_delegation import DelegatedKnowledgeCapsule
from local_cli.core.knowledge_retrieval import DocumentRetrievalFilter
from local_cli.core.context import TokenCounter,ContextError
from local_cli.application.knowledge_context import message,KNOWLEDGE_GUARD,_cost


def child_knowledge_source(admission,*,local_destination,selected_ids=None):
    parent=admission.capsule
    selected=tuple(e for e in parent.evidence if selected_ids is None or e.citation_id in selected_ids)
    if selected_ids is not None and set(selected_ids)!={e.citation_id for e in selected}:
        from local_cli.core.knowledge import KnowledgeErrorCode
        raise KnowledgeError(KnowledgeErrorCode.SOURCE_NOT_AUTHORIZED)
    allowed=DelegatedKnowledgeCapsule(parent.turn_id,selected,
        tuple(dict.fromkeys(e.target.revision_id for e in selected)),parent.token_cost)
    candidates=tuple(c for c in admission.candidates if any(e.target.chunk_id==c.chunk.chunk_id for e in selected))
    def current():
        valid=admission.service.store.validate_candidates(candidates,admission.service.access,DocumentRetrievalFilter())
        keys={(c.source_id,c.revision_id,c.chunk.chunk_id) for c in valid}
        evidence=[];sources=[]
        for e in allowed.selected_evidence_refs:
            if (e.target.source_id,e.target.revision_id,e.target.chunk_id) not in keys:continue
            try:s=admission.service.store.get_source(e.target.source_id,admission.service.access)
            except KnowledgeError:continue
            if s.current_revision_id!=e.target.revision_id or s.lifecycle_state not in (SourceLifecycle.READY,SourceLifecycle.PARTIAL):continue
            if not local_destination and not s.remote_policy.remote_document_forwarding:continue
            evidence.append(e)
            if s not in sources:sources.append(s)
        return replace(allowed,selected_evidence_refs=tuple(evidence),
            allowed_source_revision_ids=tuple(dict.fromkeys(e.target.revision_id for e in evidence))),tuple(sources)
    return current


class ChildKnowledgeAdmission:
    def __init__(self,source,working,manager,tools,redactor):
        self.source,self.working,self.manager,self.tools,self.redactor=source,working,manager,tools,redactor
        self.capsule=None;self.last=None;self.allowed_ids=None;self.turn_id=None

    def refresh(self):
        try:delegated,sources=self.source()
        except Exception:delegated,sources=None,()
        if delegated:
            self.turn_id=delegated.parent_turn_id
            if self.allowed_ids is not None:
                evidence=tuple(e for e in delegated.selected_evidence_refs if e.citation_id in self.allowed_ids)
                delegated=replace(delegated,selected_evidence_refs=evidence,
                    allowed_source_revision_ids=tuple(dict.fromkeys(e.target.revision_id for e in evidence)))
        signature=(delegated.selected_evidence_refs,sources) if delegated else None
        if self.last==signature:return
        self.last=signature
        for row in list(self.working):
            if row.get('_context_kind')=='knowledge' or row.get('_context_knowledge_guard') is True:self.working.remove(row)
        self.manager.invalidate_cache();self.capsule=None
        if delegated is None:return
        evidence=delegated.selected_evidence_refs
        guard={'role':'system','content':KNOWLEDGE_GUARD,'_context_knowledge_guard':True}
        if not evidence:
            if self.allowed_ids is None:self.allowed_ids=set()
            return
        self.working.insert(0,guard)
        try:
            while evidence:
                payload=message(evidence,tuple(s for s in sources if any(e.target.source_id==s.source_id for e in evidence)))
                if _cost(TokenCounter(self.manager.tokenizer),payload)<=delegated.token_budget:break
                evidence=evidence[:-1]
            if not evidence:
                if self.allowed_ids is None:self.allowed_ids=set()
                self.working.remove(guard);return
            payload=self.redactor.messages([payload])[0]
            self.working.insert(1,payload)
            prepared=self.manager.prepare(self.working,self.tools)
            admitted=next((m['content'] for m,k in zip(prepared.messages,prepared.context_kinds) if k=='knowledge'),None)
            import json
            ids={json.loads(line)['id'] for line in admitted.splitlines()[1:-1]} if admitted else set()
            evidence=tuple(e for e in evidence if e.citation_id in ids)
            if self.allowed_ids is None:self.allowed_ids={e.citation_id for e in evidence}
            self.working.remove(payload)
            if not evidence:
                self.working.remove(guard);return
            sources=tuple(s for s in sources if any(e.target.source_id==s.source_id for e in evidence))
            payload=message(evidence,sources);payload=self.redactor.messages([payload])[0]
            self.working.insert(1,payload)
            self.capsule=KnowledgeCapsule(delegated.parent_turn_id,evidence,sources,
                CitationRegistry(delegated.parent_turn_id,evidence),_cost(TokenCounter(self.manager.tokenizer),payload),'lexical')
        except ContextError:
            for row in list(self.working):
                if row.get('_context_kind')=='knowledge' or row.get('_context_knowledge_guard') is True:self.working.remove(row)
            # Optional data never masks a Core mandatory-budget failure.
            self.manager.prepare(self.working,self.tools)

    def receipt(self,text):
        if self.capsule is None:
            return CitationRegistry(self.turn_id).validate(text,turn_id=self.turn_id) if self.turn_id else None
        return self.capsule.citation_registry.validate(text,turn_id=self.capsule.turn_id)
