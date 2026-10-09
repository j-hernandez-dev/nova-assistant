"""K3 deterministic local document extraction.

This module parses acquired bytes only. It does not fetch, execute, index,
retrieve, call a model, or grant authority to document content.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import PurePath
from uuid import uuid4
from xml.etree import ElementTree

from pypdf import PdfReader
from pypdf.errors import DependencyError, FileNotDecryptedError
from pypdf.generic import ContentStream

from local_cli.core.knowledge import (
    ExtractionStatus, KnowledgeError, KnowledgeErrorCode, LocatorKind,
    SourceLocator, new_revision_id,
)
from local_cli.core.knowledge_store import (
    DocumentBlock, DocumentChunk, ExtractedDocument, PreparedKnowledgeRevision,
)


MAX_PAGES = 500
MAX_ENTRIES = 2000
MAX_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
MAX_XML_BYTES = 50 * 1024 * 1024
SUPPORTED = {
    ".txt": "text/plain", ".md": "text/markdown", ".markdown": "text/markdown",
    ".py": "text/x-python", ".js": "text/javascript", ".ts": "text/typescript",
    ".java": "text/x-java", ".c": "text/x-c", ".cpp": "text/x-c++",
    ".h": "text/x-c", ".hpp": "text/x-c++", ".rs": "text/x-rust",
    ".json": "application/json", ".csv": "text/csv", ".html": "text/html",
    ".htm": "text/html", ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
CODE_EXTENSIONS = {".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".hpp", ".rs"}


@dataclass(frozen=True)
class ExtractedPayload:
    media_type: str
    blocks: tuple[tuple[str, str, SourceLocator, dict], ...]
    title: str | None
    language: str | None
    warnings: tuple[str, ...] = ()
    status: ExtractionStatus = ExtractionStatus.READY


def _error(code: KnowledgeErrorCode):
    raise KnowledgeError(code)


def _text_bytes(data: bytes) -> str:
    if data.startswith(bytes((0xff, 0xfe))) or data.startswith(bytes((0xfe, 0xff))):
        encoding = "utf-16"
    elif data.startswith(bytes((0xef, 0xbb, 0xbf))):
        encoding = "utf-8-sig"
    else:
        encoding = "utf-8"
    try:
        return data.decode(encoding)
    except UnicodeDecodeError:
        _error(KnowledgeErrorCode.INVALID_ENCODING)


def _line_blocks(text: str, kind: str, *, locator=LocatorKind.TEXT_LINES):
    lines = text.splitlines() or [""]
    blocks = []
    for number, line in enumerate(lines, 1):
        if not line and len(lines) > 1:
            continue
        loc = SourceLocator(locator, {"lineStart": number, "lineEnd": number})
        blocks.append((kind, line, loc, {}))
    return tuple(blocks)


class _HTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.title = None
        self._tag = None
        self._buf = []
        self._hidden = None
        self._head = False
        self._links = []
        self._block_tags = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "pre", "code", "td", "th",
                            "div", "section", "article", "blockquote"}

    def handle_starttag(self, tag, attrs):
        if self._hidden:return
        if tag in ('script','style'):
            self._hidden=tag;return
        if tag=='head':self._head=True
        if tag == "title":
            self._flush()
            self._tag = "title"; self._buf = []
        elif tag in self._block_tags:
            if tag=='code' and self._tag in ('p','pre'):return
            self._flush()
            self._tag = tag; self._buf = []
        elif tag=='br' and self._tag:self._buf.append('\n')
        elif tag=='a':
            if not self._tag:self._tag='body'
            href=dict(attrs).get('href')
            if isinstance(href,str) and len(href)<=2048:self._links.append(href)

    def handle_data(self, data):
        if self._hidden or self._head and self._tag!='title':return
        if not self._tag and data.strip():self._tag='body'
        if self._tag:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if self._hidden:
            if tag==self._hidden:self._hidden=None
            return
        if tag=='head':self._head=False
        if tag != self._tag:
            return
        self._flush()

    def _flush(self):
        tag=self._tag
        if not tag:return
        value = " ".join("".join(self._buf).split())
        if tag == "title":
            self.title = value or None
        elif value:
            kind = "code" if tag in {"pre", "code"} else "heading" if tag.startswith("h") else "html_section"
            loc = SourceLocator(LocatorKind.WEB_BLOCK, {"url": "https://local.invalid/source.html", "block": str(len(self.blocks) + 1)})
            self.blocks.append((kind, value, loc, {"tag": tag,"links":json.dumps(self._links,ensure_ascii=True)}))
        self._tag = None; self._buf = []
        self._links=[]

    def close(self):
        super().close();self._flush()


def _json_blocks(text: str):
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        _error(KnowledgeErrorCode.CORRUPT_DOCUMENT)
    if value == {} or value == [] or not isinstance(value,(dict,list)):
        return (("json_value", json.dumps(value, ensure_ascii=False), SourceLocator(LocatorKind.JSON_POINTER, {"pointer": ""}), {}),)
    blocks = []
    from local_cli.core.context import TokenCounter
    from local_cli.core.knowledge_chunking import TARGET
    counter=TokenCounter()
    def walk(item, pointer, depth=0):
        if depth>128:_error(KnowledgeErrorCode.SOURCE_TOO_LARGE)
        # A bounded leaf object is one logical record, including field names.
        # Never merge separate array objects or synthesize a pointer/value.
        if (isinstance(item,dict) and 1<len(item)<=64 and
                all(not isinstance(v,(dict,list)) for v in item.values())):
            rendered=json.dumps(item,ensure_ascii=False,sort_keys=True)
            if counter.count(rendered).tokens<=TARGET:
                blocks.append(('json_value',rendered,SourceLocator(LocatorKind.JSON_POINTER,{'pointer':pointer}),
                    {'projection':'json-logical-object-v1'}));return
        if isinstance(item,(dict,list)) and item:
            entries=item.items() if isinstance(item,dict) else enumerate(item)
            for key,child in entries:
                child_pointer=pointer+'/'+str(key).replace('~','~0').replace('/','~1')
                walk(child,child_pointer,depth+1)
        else:
            blocks.append(('json_value',json.dumps(item,ensure_ascii=False,sort_keys=True),
                SourceLocator(LocatorKind.JSON_POINTER,{'pointer':pointer}),{}))
        if len(blocks)>5000:_error(KnowledgeErrorCode.SOURCE_CAPACITY_EXCEEDED)
    walk(value,'')
    return tuple(blocks)


def _csv_blocks(text: str):
    try:
        reader=csv.reader(io.StringIO(text));rows=[];last=0
        for row in reader:
            rows.append((row,last+1,reader.line_num));last=reader.line_num
    except csv.Error:
        _error(KnowledgeErrorCode.CORRUPT_DOCUMENT)
    if not rows:
        return ()
    return tuple(("table", ", ".join(row), SourceLocator(LocatorKind.TEXT_LINES, {"lineStart": start, "lineEnd": end}), {"columns": len(row)})
                 for row,start,end in rows)


def _pdf_paints_image(stream, resources, reader, seen=None):
    """Inspect parsed drawing operators, not unused resources or byte patterns.

    No image decoding/Pillow, OCR, network or external process is involved.
    Forms may contain images; cycles do not constitute an image by themselves.
    """
    if stream is None:
        return False
    seen = set() if seen is None else seen
    stream = stream.get_object()
    if id(stream) in seen:
        return False
    seen.add(id(stream))
    resources = resources.get_object() if resources is not None else {}
    objects = resources.get("/XObject", {})
    objects = objects.get_object() if hasattr(objects, "get_object") else objects
    for operands, operator in ContentStream(stream, reader).operations:
        if operator == b"INLINE IMAGE":
            return True
        if operator != b"Do":
            continue
        obj = objects[operands[0]].get_object()
        if obj.get("/Subtype") == "/Image":
            return True
        if obj.get("/Subtype") == "/Form" and _pdf_paints_image(
                obj, obj.get("/Resources", resources), reader, seen):
            return True
    return False


def _pdf_blocks(data: bytes):
    """Strict parser-backed text extraction; every locator uses its real page.

    Empty valid pages are not parse failures. A painted image on a textless
    page requires OCR; a mixed document keeps its usable text as PARTIAL.
    Parser exceptions never become an empty READY document.
    """
    try:
        with PdfReader(io.BytesIO(data), strict=True) as reader:
            if reader.is_encrypted:
                _error(KnowledgeErrorCode.UNSUPPORTED_ENCRYPTED_DOCUMENT)
            if len(reader.pages) > MAX_PAGES:
                _error(KnowledgeErrorCode.SOURCE_TOO_LARGE)
            blocks, warnings, ocr_pages, characters = [], [], [], 0
            for number, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                characters += len(text)
                if characters > 5_000_000:
                    _error(KnowledgeErrorCode.SOURCE_TOO_LARGE)
                if "\x00" in text:
                    _error(KnowledgeErrorCode.CORRUPT_DOCUMENT)
                if text.strip():
                    # Line segmentation is within a parsed page, never a page
                    # counter or K4 chunking/retrieval algorithm.
                    for line in text.splitlines():
                        if line.strip():
                            blocks.append(("pdf_text", line,
                                SourceLocator(LocatorKind.PDF_PAGE, {"page": number}), {}))
                elif _pdf_paints_image(page.get_contents(), page.get("/Resources"), reader):
                    ocr_pages.append(number)
                    warnings.append(f"OCR_REQUIRED_PAGE:{number}")
                else:
                    warnings.append(f"NO_TEXT_PAGE:{number}")
            if ocr_pages and not blocks:
                _error(KnowledgeErrorCode.OCR_REQUIRED)
            status = ExtractionStatus.PARTIAL if ocr_pages else ExtractionStatus.READY
            return tuple(blocks), tuple(warnings), status
    except KnowledgeError:
        raise
    except (FileNotDecryptedError, DependencyError):
        _error(KnowledgeErrorCode.UNSUPPORTED_ENCRYPTED_DOCUMENT)
    except MemoryError:
        raise
    except Exception:
        # pypdf documents that malformed input can also raise built-in errors.
        # Never publish recovered partial blocks after a structural failure.
        _error(KnowledgeErrorCode.CORRUPT_DOCUMENT)


def _docx_blocks(data: bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries=archive.infolist()
            if len(entries) > MAX_ENTRIES:
                _error(KnowledgeErrorCode.SOURCE_TOO_LARGE)
            expanded=0;seen=set()
            for entry in entries:
                name=entry.filename
                if (name in seen or name.startswith(('/', '\\')) or '\\' in name or ':' in name
                        or '..' in PurePath(name).parts or '\x00' in name
                        or (entry.external_attr >> 16) & 0o170000 == 0o120000):
                    _error(KnowledgeErrorCode.CORRUPT_DOCUMENT)
                seen.add(name)
                if entry.flag_bits & 1:_error(KnowledgeErrorCode.UNSUPPORTED_ENCRYPTED_DOCUMENT)
                expanded+=entry.file_size
                if expanded>MAX_EXPANDED_BYTES or entry.file_size>MAX_COMPRESSION_RATIO*max(1,entry.compress_size):
                    _error(KnowledgeErrorCode.SOURCE_TOO_LARGE)
            names = set(archive.namelist())
            if "word/document.xml" not in names:
                _error(KnowledgeErrorCode.CORRUPT_DOCUMENT)
            xml = archive.read("word/document.xml")
            if len(xml) > MAX_XML_BYTES:
                _error(KnowledgeErrorCode.SOURCE_TOO_LARGE)
            root = ElementTree.fromstring(xml)
    except KnowledgeError:
        raise
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError):
        _error(KnowledgeErrorCode.CORRUPT_DOCUMENT)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    blocks = []
    body=root.find('w:body',ns)
    if body is None:_error(KnowledgeErrorCode.CORRUPT_DOCUMENT)
    number=0;table=0
    for entry in body:
        if entry.tag=='{'+ns['w']+'}p':
            number+=1
            value=''.join(node.text or '' for node in entry.findall('.//w:t',ns))
            style=entry.find('w:pPr/w:pStyle',ns)
            style=style.get('{'+ns['w']+'}val','') if style is not None else ''
            if value.strip():blocks.append(('heading' if style.lower().startswith('heading') else 'docx_paragraph',value,
                SourceLocator(LocatorKind.DOCX_PARAGRAPH,{'paragraph':number}),{'style':style}))
        elif entry.tag=='{'+ns['w']+'}tbl':
            table+=1
            for row_index,row in enumerate(entry.findall('w:tr',ns),1):
                first=number+1;cells=[]
                for cell in row.findall('w:tc',ns):
                    values=[]
                    for paragraph in cell.findall('.//w:p',ns):
                        number+=1;values.append(''.join(node.text or '' for node in paragraph.findall('.//w:t',ns)))
                    cells.append(' '.join(values))
                value=' | '.join(cells)
                if value.strip():blocks.append(('table',value,SourceLocator(LocatorKind.DOCX_PARAGRAPH,
                    {'paragraph':first,'section':f'table {table} row {row_index}'}),{'columns':len(cells)}))
    if not blocks:
        _error(KnowledgeErrorCode.EXTRACTION_PARTIAL)
    return tuple(blocks)


def extract_bytes(data: bytes, filename: str) -> ExtractedPayload:
    if not isinstance(data, (bytes, bytearray)):
        _error(KnowledgeErrorCode.INVALID_CONTRACT)
    suffix = PurePath(filename).suffix.lower()
    media = SUPPORTED.get(suffix)
    if media is None:
        _error(KnowledgeErrorCode.UNSUPPORTED_FORMAT)
    data = bytes(data)
    if suffix == ".pdf" and data.strip() == b"%PDF":
        _error(KnowledgeErrorCode.CORRUPT_DOCUMENT)
    if suffix == ".pdf" and not re.match(rb"^%PDF-\d\.\d", data):
        _error(KnowledgeErrorCode.TYPE_MISMATCH)
    if suffix == ".docx" and not data.startswith(b"PK"):
        _error(KnowledgeErrorCode.TYPE_MISMATCH)
    if suffix == ".json":
        try:
            json.loads(_text_bytes(data))
        except json.JSONDecodeError:
            _error(KnowledgeErrorCode.CORRUPT_DOCUMENT)
    if suffix in {".html", ".htm"} and b"<" not in data:
        _error(KnowledgeErrorCode.TYPE_MISMATCH)
    if suffix in CODE_EXTENSIONS:
        text = _text_bytes(data)
        blocks = _line_blocks(text, "code")
        language = suffix[1:]
    elif suffix in {".txt", ".md", ".markdown"}:
        text = _text_bytes(data)
        blocks = _line_blocks(text, "paragraph")
        language = None
    elif suffix == ".json":
        text = _text_bytes(data); blocks = _json_blocks(text); language = "json"
    elif suffix == ".csv":
        text = _text_bytes(data); blocks = _csv_blocks(text); language = None
    elif suffix in {".html", ".htm"}:
        parser = _HTML()
        try: parser.feed(_text_bytes(data)); parser.close()
        except Exception: _error(KnowledgeErrorCode.CORRUPT_DOCUMENT)
        blocks, language = tuple(parser.blocks), None
        if not blocks: _error(KnowledgeErrorCode.EXTRACTION_PARTIAL)
        if sum(len(item[1]) for item in blocks) > 5_000_000:
            _error(KnowledgeErrorCode.SOURCE_TOO_LARGE)
        return ExtractedPayload(media, blocks, parser.title, language)
    elif suffix == ".pdf":
        blocks, warnings, status = _pdf_blocks(data)
        return ExtractedPayload(media, blocks, None, None, warnings, status)
    else:
        blocks, language = _docx_blocks(data), None
    if sum(len(item[1]) for item in blocks) > 5_000_000:
        _error(KnowledgeErrorCode.SOURCE_TOO_LARGE)
    return ExtractedPayload(media, blocks, None, language)


def prepare_revision(operation, digest, size, data: bytes, filename: str):
    payload = extract_bytes(data, filename)
    revision_id = operation.revision_id
    from uuid import UUID, uuid5
    from local_cli.core.knowledge_chunking import chunk_document
    blocks = tuple(DocumentBlock(str(uuid5(UUID(revision_id), 'k3-block:'+str(order))), kind, text, locator, order, metadata)
                   for order, (kind, text, locator, metadata) in enumerate(payload.blocks))
    document = ExtractedDocument(revision_id, payload.media_type, blocks, payload.status,
                                payload.warnings, payload.title, payload.language)
    chunks = chunk_document(document)
    from local_cli.core.knowledge import SourceRevision
    revision = SourceRevision(revision_id, operation.source_id, digest,
        __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        payload.media_type, size,
        "knowledge-extractor-v1/pdf-pypdf-6.19.0-strict-v1" if payload.media_type == "application/pdf"
        else "knowledge-extractor-v1/json-logical-object-v4" if payload.media_type=='application/json'
        else "knowledge-extractor-v1/structured-text-v2" if payload.media_type in ('text/csv','text/html',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document') else "knowledge-extractor-v1", payload.status,
        extracted_digest=__import__("hashlib").sha256(document.text.encode("utf-8")).hexdigest(),
        previous_revision_id=operation.previous_revision_id)
    return PreparedKnowledgeRevision(revision, document, chunks)
