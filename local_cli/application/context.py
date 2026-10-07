"""Common inference boundary for session, legacy clients and their subagents."""

from dataclasses import replace
from copy import deepcopy
from typing import Callable
import hashlib
import json

from local_cli.core.context import ContextManager, ContextPolicy, ContextSelection
from local_cli.infrastructure.capabilities import capture_capabilities


class _TrackedDict(dict):
    def __init__(self,value,changed):
        self.changed=changed
        super().__init__((k,_tracked(v,changed)) for k,v in value.items())
    def __setitem__(self,k,v):super().__setitem__(k,_tracked(v,self.changed));self.changed()
    def __delitem__(self,k):super().__delitem__(k);self.changed()
    def update(self,*a,**kw):
        for k,v in dict(*a,**kw).items():self[k]=v
    def pop(self,*a):r=super().pop(*a);self.changed();return r
    def popitem(self):r=super().popitem();self.changed();return r
    def __ior__(self,v):self.update(v);return self
    def clear(self):super().clear();self.changed()
    def setdefault(self,k,v=None):
        if k not in self:self[k]=v
        return self[k]
    def __deepcopy__(self,memo):return {k:deepcopy(v,memo) for k,v in self.items()}


class _TrackedList(list):
    def __init__(self,value,changed):self.changed=changed;super().__init__(_tracked(v,changed) for v in value)
    def __setitem__(self,k,v):
        super().__setitem__(k,[_tracked(x,self.changed) for x in v] if isinstance(k,slice) else _tracked(v,self.changed));self.changed()
    def __delitem__(self,k):super().__delitem__(k);self.changed()
    def append(self,v):super().append(_tracked(v,self.changed));self.changed()
    def extend(self,v):super().extend(_tracked(x,self.changed) for x in v);self.changed()
    def insert(self,k,v):super().insert(k,_tracked(v,self.changed));self.changed()
    def pop(self,*a):r=super().pop(*a);self.changed();return r
    def remove(self,v):super().remove(v);self.changed()
    def clear(self):super().clear();self.changed()
    def reverse(self):super().reverse();self.changed()
    def sort(self,*a,**kw):super().sort(*a,**kw);self.changed()
    def __iadd__(self,v):self.extend(v);return self
    def __imul__(self,n):super().__imul__(n);self.changed();return self
    def __deepcopy__(self,memo):return [deepcopy(v,memo) for v in self]


def _tracked(v,changed):
    if isinstance(v,dict):return _TrackedDict(v,changed)
    if isinstance(v,list):return _TrackedList(v,changed)
    return deepcopy(v)


class WorkingMessages(list):
    """Private harness view; compaction never overwrites the canonical list."""
    def __init__(self, transcript, on_append=None):
        self._revision=0;self._projection=None;self._external=[];self._suffix=[]
        self._projection_key=None;self._projection_revision=None;self._external_key=None;self._external_count=0
        self.metrics={'fullMaterializations':0,'boundedMaterializations':0,'sourceMessages':len(transcript)}
        super().__init__(_tracked(m,self._changed) for m in transcript)
        self.appended = []
        self._on_append = on_append

    def append(self, message):
        super().append(message)
        self._external.append(message);self._suffix.append(message)
        self.appended.append(message)
        if self._on_append is not None:
            self._on_append(self.appended)

    def capture_into(self, transcript):
        transcript.extend(deepcopy(self.appended))

    def _changed(self):self._revision+=1
    def __setitem__(self,k,v):
        super().__setitem__(k,v);self._external.extend(v if isinstance(k,slice) else [v]);self._changed()
    def __delitem__(self,k):super().__delitem__(k);self._changed()
    def insert(self,k,v):super().insert(k,v);self._external.append(v);self._changed()
    def remove(self,v):super().remove(v);self._changed()
    def pop(self,*a):r=super().pop(*a);self._changed();return r
    def clear(self):super().clear();self._changed()
    def extend(self,v):
        for m in v:self.append(m)
    def reverse(self):super().reverse();self._changed()
    def sort(self,*a,**kw):super().sort(*a,**kw);self._changed()
    def __iadd__(self,v):self.extend(v);return self
    def __imul__(self,n):super().__imul__(n);self._changed();return self
    def invalidate_inference_cache(self):self._changed();self._projection=None

    def inference_source(self,manager,tools,redactor):
        # Retain the complete PRIVATE working history for harness read gates.
        # Model preparation reuses only its last bounded projection + append
        # delta, not a full deepcopy/redaction/serialize of hidden history.
        tools=list(tools or ())  # Same iterable/schema normalization as Core.
        key=(id(manager),repr(manager.selection),repr(manager.policy),manager.current_message,
            manager.model_limit,manager.provider_limit,manager.max_output_tokens,id(manager.tokenizer),
            hashlib.sha256(json.dumps(tools,sort_keys=True,ensure_ascii=False).encode()).digest(),
            hashlib.sha256(json.dumps(sorted(redactor.values())).encode()).digest() if redactor else None)
        if self._projection_revision!=self._revision:
            alive={id(m) for m in self}
            self._external=[m for m in self._external if id(m) in alive]
        external=hashlib.sha256(json.dumps(self._external[:self._external_count],ensure_ascii=False,sort_keys=True).encode()).digest()
        reusable=(self._projection is not None and self._projection_key==key and
            self._projection_revision==self._revision and self._external_key==external)
        if reusable:
            source=self._projection+ (redactor.messages(self._suffix) if redactor else deepcopy(self._suffix))
            self.metrics['boundedMaterializations']+=1
        else:
            source=redactor.messages(self) if redactor else deepcopy(self)
            self.metrics['fullMaterializations']+=1
        prepared=manager.prepare(source,tools)
        self._projection=prepared.private_view();self._suffix=[]
        self._projection_key=key;self._projection_revision=self._revision
        self._external_count=len(self._external)
        self._external_key=hashlib.sha256(json.dumps(self._external,ensure_ascii=False,sort_keys=True).encode()).digest()
        return self._projection


def policy_from_config(config) -> ContextPolicy:
    return ContextPolicy(output_reserve=getattr(config, "context_output_reserve", None),
                         safety_margin=getattr(config, "context_safety_margin", None),
                         resource_limit=getattr(config, "context_resource_limit", None))


class InferenceContext:
    """Immutable execution inputs. Reports only counts, never prompt/credentials."""

    def __init__(self, manager: ContextManager, capabilities, report: Callable = lambda _: None):
        self.manager, self.capabilities, self.report = manager, capabilities, report
        self.memory_source=None

    def prepare(self, messages, tools):
        prepared = self.manager.prepare(messages, tools or ())
        self.report({"rule": "context_budget", "budget": prepared.budget.to_dict()})
        return prepared

    def observe(self, chunk, budget):
        usage = chunk.get("usage") or {}
        actual = chunk.get("prompt_eval_count", usage.get("input_tokens", usage.get("prompt_tokens")))
        if type(actual) is int and actual >= 0:
            predicted = (budget.system_tokens + budget.tool_schema_tokens +
                         budget.project_instruction_tokens + budget.skill_tokens +
                         budget.current_message_tokens + budget.working_context_tokens +
                         budget.tool_result_tokens + budget.retrieval_tokens)
            self.report({"rule": "context_usage", "estimated": budget.estimated,
                         "countSource": budget.count_source,
                         "countedPromptTokens": predicted, "actualPromptTokens": actual})


def bind_context(bound, *, workspace, tools=(), requested=0, policy=ContextPolicy(),
                 current_message=None, report=lambda _: None, capability_factory=capture_capabilities):
    """Only composition code supplies resource evidence and the selected preset."""
    shell = next((getattr(tool, "descriptor", None) for tool in tools
                  if tool.name == "bash"), None)
    capabilities = capability_factory(model=bound.snapshot, cwd=workspace, shell=shell,
                                      resource_context_limit=policy.resource_limit)
    # Tokenizer is an optional explicit adapter extension. Built-in adapters
    # currently have none; MagicMock/dynamic attributes are not evidence.
    method = getattr(type(bound._provider), "count_tokens", None)
    tokenizer = (lambda text: bound._provider.count_tokens(bound.snapshot.model_id, text)) if callable(method) else None
    manager = ContextManager(ContextSelection(requested, bound.snapshot.provider_revision),
        policy=policy, model_limit=bound.snapshot.model_context_window,
        provider_limit=bound.snapshot.provider_context_window,
        max_output_tokens=bound.snapshot.max_output_tokens, tokenizer=tokenizer,
        current_message=current_message)
    return replace(bound, _context=InferenceContext(manager, capabilities, report))
