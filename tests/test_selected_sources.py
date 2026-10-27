"""Real Application, copied revisions, request capture and tool execution.

Synthetic provider only: assertions inspect what is sent to inference, not
whether the selected chip exists in the frontend.
"""
import json
import pytest
from local_cli.application.selected_sources import SelectedSourceAdmission
from tests.knowledge_inputs_v1.test_k5_integration import case, run, finish
from tests.knowledge_inputs_v1.k2_helpers import invoke, refs


def test_explicit_filename_question_delivers_complete_copy_without_retrieval(tmp_path):
    c = case(tmp_path)
    try:
        c.file.write_text('Invoke-RestMethod http://127.0.0.1:11434/api/version', encoding='utf-8')
        invoke(c)
        reference = refs(c)
        # Losing the original and disabling both retrieval modes cannot change
        # the explicitly selected, published documentary input.
        c.file.unlink()
        service = c.app._knowledge.service
        service.retrieve = lambda *a, **k: pytest.fail('Explicit selection must not perform RAG or embeddings')
        t = run(c, 'De synthetic.txt cuál es su objetivo?', attached=reference)
        prompt = json.dumps(c.p.captured[0], ensure_ascii=False)
        assert 'Invoke-RestMethod http://127.0.0.1:11434/api/version' in prompt
        assert reference[0]['sourceId'] in prompt and 'copies in Nova' in prompt
        assert t.knowledge_admission.capsule.retrieval_mode == 'explicit'
        assert t.knowledge_admission.retrieval_count == 0
        assert c.app._session.transcript[t.transcript_start]['sourceContext'][0]['status'] == 'complete'
        assert 'sourceContext' not in prompt
        assert t.citation_reports[-1]['valid'][0]['sourceId'] == reference[0]['sourceId']
    finally:
        finish(c)


def test_explicit_multisource_keeps_short_document_beside_large_document(tmp_path):
    c = case(tmp_path, context_selection=16384)
    try:
        c.file.write_text('LONG SOURCE START. ' + 'Lengthy factual content. ' * 5000, encoding='utf-8')
        invoke(c)
        c.file = tmp_path/'second.txt'
        c.file.write_text('SHORT SOURCE UNIQUE VALUE: 582', encoding='utf-8')
        invoke(c)
        reference = refs(c)
        t = run(c, 'Explica las dos fuentes que seleccioné.', attached=reference)
        prompt = json.dumps(c.p.captured[0], ensure_ascii=False)
        assert 'LONG SOURCE START' in prompt and 'SHORT SOURCE UNIQUE VALUE: 582' in prompt
        assert all(row['admittedChunks'] for row in t.knowledge_admission.selection)
        assert sorted(row['status'] for row in t.knowledge_admission.selection) == ['complete','partial']
    finally:
        finish(c)


def test_tool_cannot_read_an_unselected_published_source(tmp_path):
    c = case(tmp_path, context_selection=16384)
    try:
        invoke(c)
        chosen = refs(c)
        c.file = tmp_path/'not-selected.txt'
        c.file.write_text('UNSELECTED PRIVATE VALUE 627', encoding='utf-8')
        invoke(c)
        other = next(r for r in refs(c) if r['sourceId'] != chosen[0]['sourceId'])
        c.p.steps = [{'role':'assistant','content':'','tool_calls':[{'id':'denied-source',
            'function':{'name':'source_read','arguments':{'source_id':other['sourceId']}}}]}, 'Unavailable.']
        t = run(c, 'Lee la fuente seleccionada.', attached=chosen)
        assert 'UNSELECTED PRIVATE VALUE 627' not in json.dumps(c.p.captured)
        assert any('SOURCE_NOT_AUTHORIZED' in m.get('content','') for m in c.p.captured[-1] if m.get('role') == 'tool')
        assert t.knowledge_admission.read_count == 0
    finally:
        finish(c)


def test_source_revocation_removes_evidence_before_next_model_request(tmp_path):
    c = case(tmp_path, context_selection=16384)
    try:
        c.file.write_text('REVOKED COPY VALUE 426',encoding='utf-8')
        invoke(c)
        chosen = refs(c)
        original = c.p.chat_stream
        def revoke(model, messages, **kwargs):
            if not c.p.captured:
                c.app._knowledge.service.store.delete(chosen[0]['sourceId'], c.app._knowledge.service.access)
            return original(model, messages, **kwargs)
        c.p.chat_stream = revoke
        c.p.steps = [{'role':'assistant','content':'','tool_calls':[{'id':'revoked-source',
            'function':{'name':'source_read','arguments':{'source_id':chosen[0]['sourceId']}}}]}, 'Unavailable [K1].']
        t = run(c, 'Lee mi fuente.', attached=chosen)
        assert 'REVOKED COPY VALUE 426' in json.dumps(c.p.captured[0])
        assert 'REVOKED COPY VALUE 426' not in json.dumps(c.p.captured[-1])
        assert not t.knowledge_admission.capsule.evidence
        assert t.knowledge_admission.selection[0]['status'] == 'unavailable'
        assert t.citation_reports[-1]['invalid'] == ['K1']
    finally:
        finish(c)


def test_explicit_large_document_supports_scoped_paged_tool_read_and_citations(tmp_path):
    c = case(tmp_path, context_selection=16384)
    try:
        c.file.write_text(('A synthetic document paragraph with meaningful content.\n\n' * 700)
            + '\nFINAL UNIQUE VALUE: 937', encoding='utf-8')
        invoke(c)
        reference = refs(c)
        source_id = reference[0]['sourceId']
        prepared = c.app._knowledge.service.store.read_prepared(reference[0]['revisionId'], c.app._knowledge.service.access)
        last = len(prepared.chunks)-1
        c.p.steps = [{'role':'assistant','content':'','tool_calls':[{'id':'source-tail',
            'function':{'name':'source_read','arguments':{'source_id':source_id,'chunk':last,'limit':8000}}}]},
            'The final value is 937 [K11].']
        t = run(c, 'Resume la fuente seleccionada.', attached=reference)
        assert len(c.p.captured) >= 2
        output = next(m['content'] for m in c.p.captured[-1] if m.get('role') == 'tool')
        assert 'FINAL UNIQUE VALUE: 937' in output
        assert t.citation_reports[-1]['valid'][0]['citationId'] == 'K11'
        assert t.knowledge_admission.selection[0]['status'] == 'partial'
        operations = list(t.tool_activities.values())
        assert any(row['name'] == 'source_read' and row['status'] == 'completed' for row in operations)
        assert t.knowledge_admission.read_count == 1
    finally:
        finish(c)


def test_automatic_retrieval_still_runs_without_explicit_selection(tmp_path):
    c = case(tmp_path)
    try:
        invoke(c)
        t = run(c)
        assert not isinstance(t.knowledge_admission, SelectedSourceAdmission)
        assert t.knowledge_admission.retrieval_count == 1
        assert t.knowledge_admission.capsule.evidence
    finally:
        finish(c)


def test_reader_denies_unselected_sources_and_old_turn_does_not_carry_source_text(tmp_path):
    c = case(tmp_path)
    try:
        c.file.write_text('PRIVATE EXPLICIT ONLY 792',encoding='utf-8')
        invoke(c)
        reference = refs(c)
        c.p.steps = [{'role':'assistant','content':'','tool_calls':[{'id':'read-source',
            'function':{'name':'source_read','arguments':{'source_id':reference[0]['sourceId']}}}]},
            'Answer [K11].', 'No evidence.']
        first = run(c, 'Lee mi fuente.', attached=reference)
        assert first.knowledge_admission.read_count == 1
        assert 'PRIVATE EXPLICIT ONLY 792' in next(m['content'] for m in c.p.captured[-1] if m.get('role') == 'tool')
        run(c, 'Unrelated xylophone question')
        assert 'PRIVATE EXPLICIT ONLY 792' not in json.dumps(c.p.captured[-1])
        assert 'Previous-Turn source read omitted' in json.dumps(c.p.captured[-1])
    finally:
        finish(c)
