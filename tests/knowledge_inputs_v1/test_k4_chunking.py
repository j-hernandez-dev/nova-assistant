from dataclasses import replace
import hashlib
import pytest
from local_cli.core.context import TokenCounter
from local_cli.core.knowledge import KnowledgeError, LocatorKind, SourceLocator, new_revision_id
from local_cli.core.knowledge_store import DocumentBlock, DocumentChunk, ExtractedDocument, PreparedKnowledgeRevision
from local_cli.core.knowledge_chunking import CHUNK_PROFILE, HARD, OVERLAP, chunk_document
from local_cli.infrastructure.knowledge_extraction import prepare_revision
from tests.knowledge_inputs_v1.pdf_fixtures import pdf_bytes
from tests.knowledge_inputs_v1.k1_helpers import begin, ACCESS
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore


def document(texts, kind='paragraph', locs=None):
    from local_cli.core.knowledge import ExtractionStatus
    locs=locs or [SourceLocator(LocatorKind.TEXT_LINES,dict(lineStart=i+1,lineEnd=i+1)) for i in range(len(texts))]
    blocks=tuple(DocumentBlock(new_revision_id(),kind,t,loc,i) for i,(t,loc) in enumerate(zip(texts,locs)))
    return ExtractedDocument(new_revision_id(),'text/plain',blocks,ExtractionStatus.READY)


@pytest.mark.parametrize('kind',['paragraph','code','table','list','json_value','pdf_text','docx_paragraph','html_section','heading'])
def test_chunker_deterministic_bounded_complete_with_exact_block_relationship(kind):
    d=document(['synthetic azure '+('multibyte á中 ' * 900), 'second independent fact '+('orbit ' * 500)],kind)
    first=chunk_document(d)
    assert first==chunk_document(d) and len(first)>1
    assert all(c.chunking_profile==CHUNK_PROFILE and TokenCounter().count(c.text).tokens<=HARD for c in first)
    blocks={b.block_id:b for b in d.blocks}
    covered={b.block_id:set() for b in d.blocks}
    for c in first:
        assert c.text=='\n'.join(blocks[s.block_id].text[s.start:s.end] for s in c.block_spans)
        assert c.locator_start==blocks[c.block_spans[0].block_id].locator
        assert c.locator_end==blocks[c.block_spans[-1].block_id].locator
        for span in c.block_spans: covered[span.block_id].update(range(span.start,span.end))
    assert all(covered[b.block_id]==set(range(len(b.text))) for b in d.blocks)


def test_overlap_is_actual_characters_not_fabricated_line_coordinates():
    d=document(['alpha synthetic words '*600])
    chunks=chunk_document(d)
    assert len(chunks)>2
    assert all(c.locator_start==d.blocks[0].locator and c.locator_end==d.blocks[0].locator for c in chunks)
    for a,b in zip(chunks,chunks[1:]):
        left,right=a.block_spans[-1],b.block_spans[0]
        assert left.end>right.start
        overlap=d.blocks[0].text[right.start:left.end]
        assert 90<=TokenCounter().count(overlap).tokens<=OVERLAP


def test_overlap_between_adjacent_blocks_of_same_structure():
    d=document(['synthetic adjacent paragraph '+str(n)+' '+('cobalt '*20) for n in range(40)])
    chunks=chunk_document(d)
    assert len(chunks)>2
    for a,b in zip(chunks,chunks[1:]):
        blocks={block.block_id:block for block in d.blocks}
        intersections=[blocks[left.block_id].text[max(left.start,right.start):min(left.end,right.end)]
            for left in a.block_spans for right in b.block_spans if left.block_id==right.block_id
            and min(left.end,right.end)>max(left.start,right.start)]
        assert intersections and 90<=TokenCounter().count('\n'.join(intersections)).tokens<=OVERLAP


def test_pdf_grouping_retains_real_pages_and_never_counts_chunks_as_pages():
    locs=[SourceLocator(LocatorKind.PDF_PAGE,{'page':p}) for p in (1,1,2)]
    d=document(['first A','first B','second C'],'pdf_text',locs)
    chunks=chunk_document(d)
    assert [c.locator_start.coordinates['page'] for c in chunks]==[1,2]
    assert len(chunks[0].block_spans)==2 and chunks[0].locator_end.coordinates['page']==1
    assert len(chunks[1].block_spans)==1


def test_structure_boundaries_blank_document_and_maximum_chunk_limit():
    d=document(['before','# Heading','after'])
    assert len(chunk_document(d))==3
    assert chunk_document(document(['','  ']))==()
    with pytest.raises(KnowledgeError) as exc: chunk_document(document(['large synthetic '*1000]),max_chunks=1)
    assert exc.value.code=='SOURCE_CAPACITY_EXCEEDED'


def test_old_chunk_dto_decodes_without_reinterpreting_legacy_vectors():
    d=document(['small'])
    c=chunk_document(d)[0]
    old=c.to_dict(); old.pop('blockSpans'); old.pop('chunkingProfile')
    loaded=DocumentChunk.from_dict(old)
    assert loaded.chunking_profile=='legacy-k3-block-v1' and loaded.block_spans==()
    assert DocumentChunk.from_dict(c.to_dict())==c


def test_prepared_projection_rejects_lost_block_or_wrong_locator(tmp_path):
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        op=begin(store); data=b'first line\nsecond line'
        digest,size=store.stage(op.operation_id,ACCESS,[data],lambda:False)
        p=prepare_revision(op,digest,size,data,'x.txt')
        c=p.chunks[0]
        with pytest.raises(KnowledgeError): PreparedKnowledgeRevision(p.revision,p.document,(replace(c,locator_end=SourceLocator(LocatorKind.TEXT_LINES,{'lineStart':99,'lineEnd':99})),))
        with pytest.raises(KnowledgeError): PreparedKnowledgeRevision(p.revision,replace(p.document,blocks=()),p.chunks)


def test_production_k3_to_k4_is_deterministic_for_same_revision(tmp_path):
    with SQLiteKnowledgeStore(tmp_path/'state') as store:
        op=begin(store); data=b'first line\nsecond line'
        digest,size=store.stage(op.operation_id,ACCESS,[data],lambda:False)
        a=prepare_revision(op,digest,size,data,'x.txt'); b=prepare_revision(op,digest,size,data,'x.txt')
        assert a.document==b.document and a.chunks==b.chunks
        assert len(a.chunks)==1 and len(a.chunks[0].block_spans)==2
