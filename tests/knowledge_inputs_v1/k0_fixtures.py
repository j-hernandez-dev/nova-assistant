"""Deterministic synthetic bytes/DTO fixtures, not productive extractors."""
from datetime import datetime, timezone
from base64 import b64decode
import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from local_cli.core.knowledge import (ExtractionStatus, KnowledgeScope, KnowledgeScopeKind,
    LocatorKind, Source, SourceKind, SourceLocator, SourceRevision, SourceTrustClass)


AT = datetime(2026, 10, 7, tzinfo=timezone.utc)
CORPUS = Path(__file__).with_name('k0_corpus_v1.json')


def corpus():
    return json.loads(CORPUS.read_text(encoding='utf-8'))


def fixture_payload(case):
    """PDF xref and ZIP are real containers; no parsing quality claimed in K0."""
    recipe = case.get('recipe')
    if recipe == 'single-page-text-pdf-v1':
        text = case['text'].replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        stream = ('BT /F1 12 Tf 72 720 Td (' + text + ') Tj ET').encode('ascii')
        objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
            b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream']
        raw = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'
        offsets = []
        for i, obj in enumerate(objects, 1):
            offsets.append(len(raw))
            raw += str(i).encode() + b' 0 obj\n' + obj + b'\nendobj\n'
        xref = len(raw)
        raw += b'xref\n0 6\n0000000000 65535 f \n'
        raw += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets)
        return raw + b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n' + str(xref).encode() + b'\n%%EOF\n'
    if recipe == 'minimal-docx-v1':
        # Same frozen payload, not regenerated ZIP bytes that vary by zlib.
        wire = json.loads(Path(__file__).with_name('k0_docx_payload_v1.json').read_text(encoding='utf-8'))
        if wire['schemaVersion'] != 1 or case['text'] != wire['text']:
            raise ValueError('Frozen DOCX fixture cannot be silently reinterpreted')
        raw = b64decode(wire['base64'], validate=True)
        if len(raw) != wire['byteLength'] or hashlib.sha256(raw).hexdigest() != wire['sha256']:
            raise ValueError('Frozen DOCX payload changed')
        return raw
    if recipe is not None:
        raise ValueError('Unknown synthetic fixture recipe')
    return case['text'].encode(case.get('encoding', 'utf-8'))


def source(case=None):
    case = case or corpus()['cases'][0]
    kind = KnowledgeScopeKind(case['scope'])
    scope = KnowledgeScope(kind, 'synthetic-workspace-A',
        'synthetic-session-A' if kind is KnowledgeScopeKind.SESSION else None)
    return Source(str(uuid5(NAMESPACE_URL, 'nova-k0-source:' + case['id'])),
        SourceKind.ATTACHMENT if kind is KnowledgeScopeKind.SESSION else SourceKind.WORKSPACE_IMPORT,
        scope, 'synthetic-origin:' + case['id'], case['id'], SourceTrustClass.USER_SELECTED_LOCAL, AT)


def revision(case=None):
    case = case or corpus()['cases'][0]
    raw = fixture_payload(case)
    return SourceRevision(str(uuid5(NAMESPACE_URL, 'nova-k0-revision:' + case['id'])),
        source(case).source_id, hashlib.sha256(raw).hexdigest(), AT, case['mediaType'],
        len(raw), 'k0-not-extracted-v1', ExtractionStatus.NOT_STARTED)


def locator(case=None):
    spec = (case or corpus()['cases'][0])['locator']
    return SourceLocator(LocatorKind(spec['kind']), spec['coordinates'])
