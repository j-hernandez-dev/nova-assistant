"""K3 PDF repair contracts: real parser, real synthetic files/store/audit.

No models are invoked. The provider double in the CLI integration only allows
normal Application composition; it is not evidence of LLM quality.
"""
import hashlib
import subprocess
import socket

import pytest

from local_cli.core.knowledge import ExtractionStatus, KnowledgeError
from local_cli.infrastructure.knowledge_extraction import extract_bytes
from tests.knowledge_inputs_v1.pdf_fixtures import (
    CORRUPT_HEADER, pdf_bytes, two_page_preflight_pdf,
)


def pages(payload):
    return [block[2].coordinates['page'] for block in payload.blocks]


def assert_error(data, code):
    with pytest.raises(KnowledgeError) as exc:
        extract_bytes(data, 'synthetic.pdf')
    assert exc.value.code == code


def test_real_one_page_textual_pdf():
    result = extract_bytes(pdf_bytes(), 'synthetic.pdf')
    assert result.status is ExtractionStatus.READY
    assert [b[1] for b in result.blocks] == ['Synthetic PDF']
    assert pages(result) == [1]


def test_real_two_page_textual_pdf():
    result = extract_bytes(pdf_bytes((('Synthetic page one',), ('Synthetic page two',))), 'synthetic.pdf')
    assert result.status is ExtractionStatus.READY
    assert [b[1] for b in result.blocks] == ['Synthetic page one', 'Synthetic page two']
    assert pages(result) == [1, 2]


def test_preflight_identical_bytes_map_real_pages_1_1_2():
    data = two_page_preflight_pdf()
    assert len(data) == 886
    assert hashlib.sha256(data).hexdigest() == '30eb094dd5a42dd80753d5f25e82403dec30eab4db496814bd42d7ee014ea5ed'
    result = extract_bytes(data, 'synthetic.pdf')
    assert result.status is ExtractionStatus.READY
    assert pages(result) == [1, 1, 2]
    assert [b[1] for b in result.blocks] == ['Synthetic first-page A', 'Synthetic first-page B', 'Synthetic second-page C']


@pytest.mark.parametrize('data', [CORRUPT_HEADER, b'%PDF', b'%PDF-1.7\n'])
def test_header_alone_is_not_pdf_support(data):
    if data == CORRUPT_HEADER:
        assert hashlib.sha256(data).hexdigest() == '4cc2d5ce41de8f3bfcbd70999e8b405372474e5b048ee1c64bad451034ad6a69'
    assert_error(data, 'CORRUPT_DOCUMENT')


@pytest.mark.parametrize('damage', ['half', 'trailer', 'xref'])
def test_truncated_or_corrupt_pdf_never_becomes_ready(damage):
    data = two_page_preflight_pdf()
    if damage == 'half': data = data[:len(data)//2]
    elif damage == 'trailer': data = data[:-70]
    else: data = data.replace(b'\nxref\n', b'\nxraf\n')
    assert_error(data, 'CORRUPT_DOCUMENT')


@pytest.mark.parametrize('password', ['synthetic-test-password', ''])
def test_real_encrypted_pdf_is_rejected_even_with_empty_password(password):
    assert_error(pdf_bytes(password=password), 'UNSUPPORTED_ENCRYPTED_DOCUMENT')


def test_valid_blank_page_is_ready_without_fabricated_blocks():
    result = extract_bytes(pdf_bytes(((),)), 'synthetic.pdf')
    assert result.status is ExtractionStatus.READY and result.blocks == ()
    assert result.warnings == ('NO_TEXT_PAGE:1',)


def test_blank_middle_page_does_not_renumber_text_pages():
    result = extract_bytes(pdf_bytes((('Synthetic first',), (), ('Synthetic third',))), 'synthetic.pdf')
    assert pages(result) == [1, 3] and result.status is ExtractionStatus.READY
    assert result.warnings == ('NO_TEXT_PAGE:2',)


@pytest.mark.parametrize('image_form', [False, True])
def test_painted_image_only_pdf_requires_ocr_without_image_decoder(image_form):
    assert_error(pdf_bytes(('image',), image_form=image_form), 'OCR_REQUIRED')


def test_unused_image_resource_is_not_falsely_ocr_required():
    result = extract_bytes(pdf_bytes(((),), unused_image=True), 'synthetic.pdf')
    assert result.status is ExtractionStatus.READY and result.blocks == ()


def test_text_and_image_only_pages_are_honestly_partial():
    result = extract_bytes(pdf_bytes((('Synthetic usable text',), 'image')), 'synthetic.pdf')
    assert result.status is ExtractionStatus.PARTIAL
    assert pages(result) == [1] and result.blocks[0][1] == 'Synthetic usable text'
    assert result.warnings == ('OCR_REQUIRED_PAGE:2',)


def test_real_page_limit_counts_pages_not_page_tree_nodes():
    result = extract_bytes(pdf_bytes(((),)*500), 'synthetic.pdf')
    assert result.status is ExtractionStatus.READY and len(result.warnings) == 500
    assert_error(pdf_bytes(((),)*501), 'SOURCE_TOO_LARGE')


def test_compressed_stream_escaped_strings_and_metadata_are_not_heuristic_text():
    result = extract_bytes(pdf_bytes((('Synthetic (literal) /Encrypt', 'Synthetic second'),), compressed=True), 'synthetic.pdf')
    assert [b[1] for b in result.blocks] == ['Synthetic (literal) /Encrypt', 'Synthetic second']
    assert pages(result) == [1, 1]


def test_parser_operates_without_network_or_external_process(monkeypatch):
    data = pdf_bytes(compressed=True)
    def forbidden(*args, **kwargs): raise AssertionError('External execution is forbidden')
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    assert extract_bytes(data, 'synthetic.pdf').status is ExtractionStatus.READY


@pytest.mark.parametrize('case', ['text', 'corrupt', 'encrypted', 'image', 'blank', 'mixed'])
def test_normal_cli_k2_k3_import_uses_real_pdf_parser_store_and_audit(tmp_path, monkeypatch, case):
    from local_cli.application.providers import ProviderManager
    from local_cli.application.rag import RAGService
    from local_cli.application.secrets import SecretRedactor
    from local_cli.bootstrap_cli import create_cli_application
    from local_cli.config import Config
    from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
    from local_cli.interfaces.cli_application import CliApplicationClient
    from tests.test_nova_core_phase8_providers import Provider

    data = {'text': two_page_preflight_pdf, 'corrupt': lambda: CORRUPT_HEADER,
        'encrypted': lambda: pdf_bytes(password='synthetic-test-password'),
        'image': lambda: pdf_bytes(('image',)), 'blank': lambda: pdf_bytes(((),)),
        'mixed': lambda: pdf_bytes((('Synthetic usable text',), 'image'))}[case]()
    work = tmp_path/'workspace'; work.mkdir()
    file = tmp_path/'synthetic ñ.pdf'; file.write_bytes(data)
    config = Config(); config.state_dir = str(tmp_path/'private-state'); config.model = 'old'
    provider = Provider(); manager = ProviderManager(provider, 'old'); manager.redactor = SecretRedactor(source={})
    audit = JsonlSecurityAudit(tmp_path/'audit', workspace=work)
    monkeypatch.setattr('local_cli.bootstrap_cli.create_security_audit', lambda w: audit)
    monkeypatch.setattr(CliApplicationClient, '_human_tty', staticmethod(lambda: True))
    cli = create_cli_application(config=config, provider_manager=manager, tools=[], workspace=work,
        base_messages=[{'role':'system', 'content':'Synthetic system'}], persistence=None,
        rag_service=RAGService(None), write=lambda t: None)
    try:
        receipt = cli.knowledge('source_import', {'path':str(file), 'scope':'WORKSPACE'})
        assert receipt['accepted']
        op = cli.application._service_operations[receipt['createdIds']['operationId']]
        assert op.done.wait(5), 'Synthetic PDF import did not finish'
        references = cli.snapshot().services['knowledge']['attachmentRefs']
        service = cli.application._knowledge.service
        errors = {'corrupt':'CORRUPT_DOCUMENT', 'encrypted':'UNSUPPORTED_ENCRYPTED_DOCUMENT', 'image':'OCR_REQUIRED'}
        if case in errors:
            assert op.status.value == 'failed' and op.result['error']['code'] == errors[case]
            assert not any(ref['state'] == 'READY' for ref in references)
            assert service.store._connection.execute('SELECT count(*) FROM source_revisions').fetchone()[0] == 0
        else:
            assert op.status.value == 'completed'
            assert references[0]['state'] == ('PARTIAL' if case == 'mixed' else 'READY')
            prepared = service.store.read_prepared(references[0]['revisionId'], service.access)
            assert prepared.revision.extractor_profile == 'knowledge-extractor-v1/pdf-pypdf-6.19.0-strict-v1'
            assert [b.locator.coordinates['page'] for b in prepared.document.blocks] == (
                [1, 1, 2] if case == 'text' else [1] if case == 'mixed' else [])
        assert provider.requests == [] and cli.snapshot().turns == ()
        assert cli.application._memory is None
    finally:
        cli.close(); assert cli.application._knowledge.closed.wait(5); audit.close()
