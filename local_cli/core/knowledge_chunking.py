"""Deterministic structure-aware K4 projection using the Core token estimator.

Fragments retain original block locators plus exact block-character spans.
A split block still has its real full-block locator; no finer page/line range
is invented. Blank blocks remain in the document but need no search projection.
"""
import hashlib
import unicodedata
from uuid import UUID, uuid5

from local_cli.core.context import TokenCounter
from local_cli.core.knowledge import KnowledgeError, KnowledgeErrorCode, _require
from local_cli.core.knowledge_store import DocumentBlockSpan, DocumentChunk, ExtractedDocument
from local_cli.core.knowledge_retrieval import lexical_text


CHUNK_PROFILE = 'ki-structure-v1/core-utf8_bytes_div_3/700-1000-100'
TARGET, HARD, OVERLAP = 700, 1000, 100


def _prefix(text, budget, counter):
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if counter.count(text[:mid]).tokens <= budget: lo = mid
        else: hi = mid - 1
    # Prefer a real whitespace/line boundary, without dropping characters.
    if lo < len(text):
        cut = max(text.rfind('\n', 0, lo), text.rfind(' ', 0, lo)) + 1
        if cut > lo // 2: lo = cut
    return lo


def _structure(block):
    kind = block.kind
    if kind == 'paragraph' and block.text.lstrip().startswith('#'): return ('heading', block.block_id)
    if kind in ('heading', 'table', 'json_value', 'html_section'): return (kind, block.block_id)
    coords = block.locator.coordinates
    # Never merge across PDF pages, JSON pointers or HTML sections.
    return (kind, block.locator.kind, coords.get('page'), coords.get('pointer'), coords.get('section'))


def chunk_document(document: ExtractedDocument, *, max_chunks=5000):
    _require(isinstance(document, ExtractedDocument) and type(max_chunks) is int and max_chunks > 0)
    counter, chunks = TokenCounter(), []
    blocks = {b.block_id: b for b in document.blocks}

    def text(spans): return '\n'.join(blocks[s.block_id].text[s.start:s.end] for s in spans)

    def publish(spans):
        if not spans: return
        content = text(spans)
        _require(counter.count(content).tokens <= HARD)
        if len(chunks) >= max_chunks:
            raise KnowledgeError(KnowledgeErrorCode.SOURCE_CAPACITY_EXCEEDED)
        digest = hashlib.sha256(unicodedata.normalize('NFKC', content).encode('utf-8')).hexdigest()
        identity = CHUNK_PROFILE + ':' + str(len(chunks)) + ':' + digest + ':' + repr(tuple(spans))
        chunks.append(DocumentChunk(str(uuid5(UUID(document.revision_id), identity)), document.revision_id,
            len(chunks), content, digest, blocks[spans[0].block_id].locator,
            blocks[spans[-1].block_id].locator, lexical_text(content),
            block_spans=tuple(spans), chunking_profile=CHUNK_PROFILE))

    def tail(spans):
        kept = []
        for span in reversed(spans):
            raw = blocks[span.block_id].text[span.start:span.end]
            lo, hi = 0, len(raw)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                trial = [DocumentBlockSpan(span.block_id, span.end-mid, span.end), *kept]
                if counter.count(text(trial)).tokens <= OVERLAP: lo = mid
                else: hi = mid-1
            if lo: kept.insert(0, DocumentBlockSpan(span.block_id, span.end-lo, span.end))
            if lo < len(raw): break
        return kept

    spans, group, overlap_only = [], None, False
    for block in document.blocks:
        if not block.text.strip(): continue
        key = _structure(block)
        if key != group:
            if not overlap_only: publish(spans)
            spans = []; group = key; overlap_only = False
        start = 0
        while start < len(block.text):
            remaining = block.text[start:]
            whole = DocumentBlockSpan(block.block_id, start, len(block.text))
            if counter.count(text([*spans, whole])).tokens <= HARD:
                spans.append(whole); start = len(block.text); overlap_only = False
                # Carry overlap only when more input remains in this structure.
                if counter.count(text(spans)).tokens >= TARGET:
                    publish(spans); spans = tail(spans); overlap_only = True
                continue
            prefix = text(spans) + ('\n' if spans else '')
            budget = max(1, TARGET-counter.count(prefix).tokens)
            take = _prefix(remaining, budget, counter)
            if not take or counter.count(prefix+remaining[:take]).tokens > HARD:
                if not overlap_only: publish(spans)
                spans = []; overlap_only = False; continue
            spans.append(DocumentBlockSpan(block.block_id, start, start+take)); start += take
            publish(spans); spans = tail(spans); overlap_only = True
    if not overlap_only: publish(spans)
    return tuple(chunks)
