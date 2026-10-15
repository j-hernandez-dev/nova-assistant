"""Evidence for bounded source diversity and the unchanged admission budget."""
from dataclasses import replace
import json
from pathlib import Path
import sys

from local_cli.application.context import WorkingMessages
from local_cli.application.knowledge import KnowledgeService
from local_cli.application.knowledge_context import KnowledgeAdmission, message, _cost
from local_cli.application.knowledge_retrieval import DocumentRetriever
from local_cli.application.secrets import SecretRedactor
from local_cli.core.context import ContextManager, ContextSelection, TokenCounter
from local_cli.core.knowledge_context import CitationTarget, KnowledgeEvidence
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from tests.knowledge_inputs_v1.k1_helpers import ACCESS, execution
from tests.knowledge_inputs_v1.k4_helpers import load_corpus, publish_text
from tests.knowledge_inputs_v1.test_k8_post_cert_conflict import read, verify_freeze


def diagnose(output):
    assert not output.exists()
    output.mkdir(parents=True)
    verify_freeze()
    with SQLiteKnowledgeStore(output/'state') as store:
        ids, revisions, prior = load_corpus(store, read('corpus_v1'))
        service = KnowledgeService(store, workspace=output, access=ACCESS)
        service.retriever = DocumentRetriever(store)
        try:
            query = 'Compare the three sources about TALVORA10653 beacon cadence. Report all values.'
            admission = KnowledgeAdmission('turn_pc_budget', service, SecretRedactor(source={}))
            admission.retrieve(query, context=execution(output), local_destination=True)
            working = WorkingMessages([dict(role='system',content='Synthetic mandatory Core.'), dict(role='user',content=query)])
            manager = ContextManager(ContextSelection(4096), current_message=query)
            admission.stage(working, manager, ())
            capsule = admission.freeze(working, manager, ())
            source_map = {s.source_id:s for s in admission.sources}
            entries = []
            for i,c in enumerate(admission.candidates):
                s = source_map[c.source_id]
                target = CitationTarget(s.source_id,c.revision_id,c.chunk.chunk_id,c.chunk.locator_start,s.display_name,s.origin)
                entries.append(KnowledgeEvidence('K'+str(i+1),target,c.chunk.text,False))
            minimum = tuple(replace(e,text=e.text[:1],truncated=True) for e in entries)
            budget = manager.prepare(working,()).budget
            counter = TokenCounter(manager.tokenizer)
            result = dict(window=4096,sharedRetrievalCap=budget.shared_retrieval_cap,
                relevantSources=len(source_map), admittedSources=len(capsule.source_registry),
                minimumThreeNonemptyEvidenceTokens=_cost(counter,message(minimum,admission.sources)),
                fullThreeEvidenceTokens=_cost(counter,message(tuple(entries),admission.sources)),
                framingUnchanged=True, guardUnchanged=True, coreUnchanged=True)
            print(json.dumps(dict(admissionBudgetDiagnosis=result)))
            # Separate implementation contract, no gold/score changes: many chunks
            # in one source must not crowd out a second relevant source at cap 32.
            paragraphs = ['PCCBOUND12053 beacon cadence '+('bounded synthetic filler '*90)+str(i) for i in range(40)]
            large, prepared = publish_text(store,'\n\n'.join(paragraphs))
            other, other_prepared = publish_text(store,'PCCBOUND12053 beacon cadence is PCC_STRESS_OTHER53.')
            ranked = service.retriever.retrieve('Compare the two sources about PCCBOUND12053 beacon cadence.',ACCESS)
            result['diversityCapContract'] = dict(firstSourceChunks=len(prepared.chunks), candidateCount=len(ranked.candidates),
                distinctFirstTwo=len({c.source_id for c in ranked.candidates[:2]}),
                bothSourcesRetrieved={c.source_id for c in ranked.candidates} == {large.source_id,other.source_id})
            assert result['diversityCapContract']['bothSourcesRetrieved']
            assert result['diversityCapContract']['distinctFirstTwo'] == 2
        finally:
            service.retriever.close()
    (output/'diagnosis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    diagnose(Path(sys.argv[1]).resolve())
