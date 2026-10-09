"""Additional repair contracts, never a substitute for real-model compliance."""
import json
from local_cli.application.context import WorkingMessages
from local_cli.application.knowledge import KnowledgeService
from local_cli.application.knowledge_context import KnowledgeAdmission, KNOWLEDGE_ABSENCE_GUARD
from local_cli.application.knowledge_retrieval import DocumentRetriever
from local_cli.application.secrets import SecretRedactor
from local_cli.core.context import ContextManager, ContextSelection
from local_cli.core.knowledge_retrieval import LEXICAL_FLOOR, LEXICAL_CAP, RRF_K
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from local_cli.infrastructure.knowledge_lexical import documentary_terms
from tests.knowledge_inputs_v1.k1_helpers import ACCESS, execution
from tests.knowledge_inputs_v1.k4_helpers import publish_text
import pytest


def test_documentary_focus_not_authority_and_constants_unchanged():
    assert documentary_terms('Give FERRY27 departure and my remembered preference. Do not write files.')==('ferry27','departure')
    assert documentary_terms('Please explain both sources and cite without choosing a single truth.')==()
    assert LEXICAL_FLOOR==.5 and LEXICAL_CAP==32 and RRF_K==60


@pytest.mark.parametrize('window',[4096,8192,16384,32768,65536])
def test_absence_instruction_bounded_capsule_stays_zero_and_user_first(tmp_path,window):
    with SQLiteKnowledgeStore(tmp_path/'store') as store:
        svc=KnowledgeService(store,workspace=tmp_path,access=ACCESS);svc.retriever=DocumentRetriever(store)
        try:
            current='No documentary fact is available. Do not write files.'
            messages=WorkingMessages([{'role':'system','content':'Host instructions'},{'role':'user','content':current}])
            manager=ContextManager(ContextSelection(window),current_message=current)
            a=KnowledgeAdmission('repair_absence',svc,SecretRedactor(source={}))
            a.retrieve('UNSEEN87 tariff',context=execution(tmp_path),local_destination=True)
            a.stage(messages,manager,());capsule=a.freeze(messages,manager,());prepared=manager.prepare(messages,())
            assert not capsule.evidence and capsule.token_cost==0
            assert prepared.budget.retrieval_tokens==0 and prepared.budget.system_tokens>0
            assert {'role':'user','content':current} in prepared.messages
            assert any(m['content']==KNOWLEDGE_ABSENCE_GUARD for m in prepared.messages)
        finally:svc.retriever.close()


def test_marker_is_supplied_but_alternative_syntax_never_validated(tmp_path):
    with SQLiteKnowledgeStore(tmp_path/'store') as store:
        publish_text(store,'LANE58 boarding platform is Birch Terrace.')
        svc=KnowledgeService(store,workspace=tmp_path,access=ACCESS);svc.retriever=DocumentRetriever(store)
        try:
            a=KnowledgeAdmission('repair_citation',svc,SecretRedactor(source={}))
            a.retrieve('LANE58 boarding platform',context=execution(tmp_path),local_destination=True)
            current='Give the boarding platform and do not write files.'
            messages=WorkingMessages([{'role':'system','content':'Host instructions'},{'role':'user','content':current}])
            manager=ContextManager(ContextSelection(8192),current_message=current)
            a.stage(messages,manager,());capsule=a.freeze(messages,manager,())
            assert capsule.evidence
            line=next(m['content'].splitlines()[1] for m in messages if m.get('_context_kind')=='knowledge')
            assert json.loads(line)['cite']=='[K1]'
            assert a.validate('[K1]')['valid']
            for alternative in ('[Citation: K1]','(K1)','https://invented.invalid/K1'):
                assert not a.validate(alternative)['valid']
        finally:svc.retriever.close()
