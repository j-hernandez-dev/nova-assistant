"""Structure/byte reproducibility only; never claim K3 parsing or K8 quality."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from tests.knowledge_inputs_v1.k0_fixtures import corpus, fixture_payload, locator, revision, source


def test_frozen_initial_corpus_and_all_payload_hashes():
    root = Path(__file__).resolve().parents[2]
    lock = json.loads((root/'docs/knowledge_inputs_v1/k0_corpus_freeze.json').read_text(encoding='utf-8'))
    raw = (root/lock['source']).read_bytes().replace(b'\r\n', b'\n')
    assert hashlib.sha256(raw).hexdigest() == lock['sha256Lf']
    assert lock['corpusId'] == corpus()['corpusId']
    assert set(lock['payloads']) == {c['id'] for c in corpus()['cases']}
    for case in corpus()['cases']:
        payload = fixture_payload(case)
        assert lock['payloads'][case['id']] == dict(
            sha256=hashlib.sha256(payload).hexdigest(), byteLength=len(payload))


def test_initial_corpus_structure_not_outcome_selected_or_quality_claim():
    data = corpus(); cases = data['cases']
    assert data['schemaVersion'] == 1 and data['corpusId'] == 'ki-k0-initial-synthetic-v1'
    assert len(cases) == 18 and len({c['id'] for c in cases}) == 18
    assert {c['format'] for c in cases} == {'TXT','MD','CODE','JSON','CSV','HTML','PDF','DOCX'}
    assert {c['scope'] for c in cases} == {'SESSION','WORKSPACE'}
    assert data['futureQualityThresholdsUnchanged'] == dict(parseSuccess=.98, coreRecallAt5=.90,
        corePrecisionAt1=.85, abstention=.95, criticalInvariants=1., invalidAcceptedCitations=0, ftsP95Ms=100)
    assert 'model E2E' in data['notEvaluatedHere']


@pytest.mark.parametrize('case', corpus()['cases'], ids=lambda c:c['id'])
def test_deterministic_synthetic_payload_and_digest(case):
    raw = fixture_payload(case)
    assert isinstance(raw, bytes) and fixture_payload(case) == raw
    assert revision(case).content_digest == hashlib.sha256(raw).hexdigest()
    assert revision(case).byte_length == len(raw)
    if 'locator' in case:
        assert locator(case).schema_version == 1


def test_duplicate_bytes_keep_distinct_source_provenance():
    cases = {c['id']:c for c in corpus()['cases']}
    a, b = cases['duplicate-origin-a'], cases['duplicate-origin-b']
    assert fixture_payload(a) == fixture_payload(b)
    assert revision(a).content_digest == revision(b).content_digest
    assert source(a).source_id != source(b).source_id and source(a).origin != source(b).origin
    assert revision(a).revision_id != revision(b).revision_id


def test_pdf_fixture_real_xref_not_a_pdf_extension_on_plain_text():
    case = next(c for c in corpus()['cases'] if c['id'] == 'pdf-text')
    raw = fixture_payload(case)
    assert raw.startswith(b'%PDF-1.4') and raw.endswith(b'%%EOF\n')
    xref = int(raw.split(b'startxref\n')[1].splitlines()[0])
    assert raw[xref:].startswith(b'xref\n')
    assert b'/Type /Page ' in raw and b'/BaseFont /Helvetica' in raw
    # Container structure only. The product has no PDF extractor in K0.


def test_docx_fixture_deterministic_ooxml_container_not_product_extraction():
    case = next(c for c in corpus()['cases'] if c['id'] == 'docx')
    with ZipFile(BytesIO(fixture_payload(case))) as archive:
        assert set(archive.namelist()) == {'[Content_Types].xml','_rels/.rels','word/document.xml'}
        assert b'Synthetic reference KI-49.' in archive.read('word/document.xml')


def test_docx_fixture_never_recompresses_or_reinterprets_changed_text(monkeypatch):
    import zipfile
    monkeypatch.setattr(zipfile, 'ZipFile', lambda *a, **kw: pytest.fail('No runtime recompression'))
    case = next(c for c in corpus()['cases'] if c['id'] == 'docx')
    assert len(fixture_payload(case)) == 812
    with pytest.raises(ValueError, match='silently reinterpreted'):
        fixture_payload(dict(case, text='An unapproved different fixture'))


def test_json_html_and_hostile_fixtures_not_silently_sanitized_to_pass():
    cases = {c['id']:c for c in corpus()['cases']}
    assert json.loads(cases['json']['text'])['synthetic']['formula'] == 'a < b > c'
    with pytest.raises(json.JSONDecodeError):
        json.loads(cases['corrupt-json']['text'])
    assert '<script>' in cases['html']['text'] and '&amp;' in cases['html']['text']
    assert 'remember this globally' in cases['hostile-data']['text']
