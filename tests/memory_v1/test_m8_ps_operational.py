"""New no-gold workload and frozen guard, never semantic-quality evidence."""
import json
import hashlib

import pytest

from tests.memory_v1.run_m8_ps_operational import WORKLOAD,IMPLEMENTATION_FREEZE,no_cold_load_request
from tests.memory_v1.run_m8_bge_operational import verify
from tests.memory_v1.run_m8_bge_operational import ROOT


def test_new_workload_is_forty_distinct_gold_free_queries():
    data=json.loads(WORKLOAD.read_text(encoding='utf-8'))
    assert data['syntheticOnly'] and not data['goldProvided'] and not data['qualityEvaluated']
    assert len(data['samples'])==len({r['query'] for r in data['samples']})==40
    for filename in ('m8_metadata_operational_v1.json','m8_bge_operational_v1.json'):
        old=json.loads(WORKLOAD.with_name(filename).read_text(encoding='utf-8'))
        assert not {r['query'] for r in data['samples']} & {r['query'] for r in old['samples']}
    assert all(set(r)=={'id','query'} for r in data['samples'])


def historical_adapter_bytes(current):
    # Explicit later human authorization, NOT a rewrite of the historical
    # freeze or a wildcard exception. Every other byte (including admission,
    # PS/embed/post-TAGS, spaces and deadlines) must still match that freeze.
    authorized = (b"            basename = info.get('model_info',{}).get('general.basename')\n"
        b"            instruction = (QWEN_MEMORY_QUERY_INSTRUCTION if\n"
        b"                isinstance(basename,str) and basename.casefold()=='qwen3-embedding' else None)")
    historical = (b"            instruction = (QWEN_MEMORY_QUERY_INSTRUCTION if\n"
        b"                info.get('model_info',{}).get('general.basename')=='qwen3-embedding' else None)")
    if current.count(authorized)!=1:
        raise ValueError('Expected exactly the authorized Qwen family recognition delta')
    return current.replace(authorized,historical)


def verify_admission_harness_version(current, historical_sha):
    # K0 explicitly reconciles CI. Keep the historical freeze untouched and
    # accept only its original test OR the reviewed deterministic-clock repair.
    # This exception is test-only; all productive admission bytes remain pinned.
    original = 'baf9c6f75077b3af4f59633546aa1533b4156850bac05382ad53b0b2821b9692'
    k0_repair = '40a9b16ed22b19648e830c9951a924c69bf5d11e144c528f692bb77851d421f1'
    if historical_sha != original or hashlib.sha256(current).hexdigest() not in (original,k0_repair):
        raise ValueError('Unrecognized admission test revision; historical freeze remains authoritative')


def historical_sub_agent_bytes(current):
    """Reverse ONLY explicit K7 and authorized K8 child transport deltas.

    The historical campaign used the original child. HEAD legitimately adds
    Knowledge delegation under §62, not new M8 behavior. The hash after reversal
    must still equal the original, including all MEMORY/timeout/security bytes.
    """
    # K8 REPAIR V3 authorization: transport of a host-owned reduction, not a
    # MEMORY/product change. Match exactly once; all other bytes stay pinned.
    effect_transport=(b"                              redactor=self._redactor, security_audit=self._security_audit,\n"
        b"                              turn_effect_constraints=getattr(self,'_turn_effect_constraints',None))")
    historical_transport=b"                              redactor=self._redactor, security_audit=self._security_audit)"
    if current.count(effect_transport)!=1 or current.count(b'turn_effect_constraints=')!=1:
        raise ValueError('Unrecognized K8 TurnEffectConstraints transport delta')
    current=current.replace(effect_transport,historical_transport)
    deltas=[
        (b'    knowledge_citations: dict | None = None\n',b''),
        (b"        if self.knowledge_citations:\n            lines.append('Knowledge citations (structural only): '+json.dumps(self.knowledge_citations,ensure_ascii=True))\n",b''),
        (b'        self._knowledge_delegate=None\n',b''),
        (b"        child_knowledge=None\n        if self._knowledge_delegate is not None:\n            from local_cli.application.context import WorkingMessages\n            from local_cli.application.knowledge_children import ChildKnowledgeAdmission\n            if not isinstance(self._messages,WorkingMessages):self._messages=WorkingMessages(self._messages)\n            context=getattr(self._provider,'_context',None)\n            if context is not None:\n                child_knowledge=ChildKnowledgeAdmission(self._knowledge_delegate,self._messages,context.manager,\n                    self._provider.format_tools(self._tools),self._redactor)\n                context.knowledge_source=child_knowledge.refresh\n                child_knowledge.refresh()\n",b''),
        (b'            if not isinstance(self._messages,WorkingMessages):self._messages=WorkingMessages(self._messages)\n',b'            self._messages=WorkingMessages(self._messages)\n'),
        (b'            context.memory_source=None;context.knowledge_source=None;context.manager.invalidate_cache()\n',b'            context.memory_source=None;context.manager.invalidate_cache()\n'),
        (b'            knowledge_citations=child_knowledge.receipt(final_content) if child_knowledge else None,\n',b''),
        (b'    def bind_knowledge_delegate(self,source):\n        """Application-owned data callback; never a store/retriever/authority."""\n        self._knowledge_delegate=source\n\n',b''),
    ]
    for authorized,historical in deltas:
        if current.count(authorized)!=1:raise ValueError('Unrecognized K7 child delegation delta')
        current=current.replace(authorized,historical)
    return current


def test_historical_guard_preserves_product_and_only_explicit_qwen_k0_and_k7_deltas():
    lock=json.loads(IMPLEMENTATION_FREEZE.read_text(encoding='utf-8'))
    adapter_path='local_cli/infrastructure/memory_embeddings.py'
    admission_test='tests/memory_v1/test_m8_metadata_admission.py'
    child_path='local_cli/sub_agent.py'
    verify({'files':[r for r in lock['files'] if r['path'] not in (adapter_path,admission_test,child_path)]})
    child_frozen=next(r for r in lock['files'] if r['path']==child_path)
    assert hashlib.sha256(historical_sub_agent_bytes((ROOT/child_path).read_bytes())).hexdigest()==child_frozen['sha256']
    admission_frozen=next(r for r in lock['files'] if r['path']==admission_test)
    verify_admission_harness_version((ROOT/admission_test).read_bytes(),admission_frozen['sha256'])
    frozen=next(r for r in lock['files'] if r['path']==adapter_path)
    assert hashlib.sha256(historical_adapter_bytes((ROOT/adapter_path).read_bytes())).hexdigest()==frozen['sha256']
    assert (lock['softMs'],lock['hardMs'],lock['fallbackReserveMs'],lock['semanticCutoffMs'])==(350,600,50,550)
    assert len(lock['files'])==9


def test_k7_delta_does_not_allow_timeout_memory_or_unrelated_child_changes():
    current=(ROOT/'local_cli/sub_agent.py').read_bytes()
    lock=json.loads(IMPLEMENTATION_FREEZE.read_text(encoding='utf-8'))
    expected=next(r['sha256'] for r in lock['files'] if r['path']=='local_cli/sub_agent.py')
    assert hashlib.sha256(historical_sub_agent_bytes(current)).hexdigest()==expected
    assert hashlib.sha256(historical_sub_agent_bytes(current+b'\n# unrelated change\n')).hexdigest()!=expected
    with pytest.raises(ValueError):historical_sub_agent_bytes(current.replace(b'child_knowledge.refresh()',b'child_knowledge.refresh_wrong()'))


def test_k0_harness_exception_rejects_any_unreviewed_test_change():
    current=(ROOT/'tests/memory_v1/test_m8_metadata_admission.py').read_bytes()
    frozen=json.loads(IMPLEMENTATION_FREEZE.read_text(encoding='utf-8'))
    original=next(r['sha256'] for r in frozen['files'] if r['path']=='tests/memory_v1/test_m8_metadata_admission.py')
    verify_admission_harness_version(current,original)
    with pytest.raises(ValueError):
        verify_admission_harness_version(current+b'\n# unrelated change\n',original)


def test_k0_harness_exception_cannot_replace_historical_pin():
    current=(ROOT/'tests/memory_v1/test_m8_metadata_admission.py').read_bytes()
    with pytest.raises(ValueError):
        verify_admission_harness_version(current,'0'*64)


def test_authorized_family_delta_does_not_allow_any_other_adapter_change():
    original=(ROOT/'local_cli/infrastructure/memory_embeddings.py').read_bytes()
    with pytest.raises(ValueError):historical_adapter_bytes(original.replace(b'basename.casefold()',b'basename.lower()'))
    frozen=json.loads(IMPLEMENTATION_FREEZE.read_text(encoding='utf-8'))
    expected=next(r['sha256'] for r in frozen['files'] if r['path']=='local_cli/infrastructure/memory_embeddings.py')
    assert hashlib.sha256(historical_adapter_bytes(original+b'\n# unrelated change\n')).hexdigest()!=expected


def test_measurement_never_automatically_loads_a_cold_model():
    with pytest.raises(RuntimeError,match='no auto-load'):
        no_cold_load_request('embed',dict(model='BGE-M3:latest',input=['Synthetic cold preparation']))
