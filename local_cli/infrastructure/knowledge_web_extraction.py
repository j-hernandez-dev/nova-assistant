"""K6 remote textual normalization -> real K3 extraction -> K4 projection.

Only already-acquired bytes; no URLs are opened by this module. S5's textual
MIME restriction remains unchanged (remote PDF/DOCX are not advertised).
"""
from dataclasses import replace
from html.parser import HTMLParser
import codecs
import hashlib
import json
from pathlib import PurePosixPath
import re
from urllib.parse import urlsplit

from local_cli.core.knowledge import (KnowledgeError,KnowledgeErrorCode,ExtractionStatus,
    SourceLocator,LocatorKind)
from local_cli.core.knowledge_chunking import chunk_document
from local_cli.infrastructure.knowledge_extraction import prepare_revision,SUPPORTED


class _PassiveHTML(HTMLParser):
    """Remove executable/style payload, never execute or follow a link."""
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.hidden=None;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if self.hidden is not None:return
        if tag in ('script','style'):
            self.hidden=tag;return
        self.parts.append(self.get_starttag_text())
    def handle_endtag(self,tag):
        if self.hidden is not None:
            if tag==self.hidden:self.hidden=None
        else:self.parts.append('</'+tag+'>')
    def handle_data(self,data):
        if self.hidden is None:self.parts.append(data)
    def handle_entityref(self,name):
        if self.hidden is None:self.parts.append('&'+name+';')
    def handle_charref(self,name):
        if self.hidden is None:self.parts.append('&#'+name+';')


def prepare_url_revision(operation,digest,size,snapshot):
    content_type=snapshot.content_type
    media=content_type.split(';',1)[0].strip().lower()
    suffix=PurePosixPath(urlsplit(snapshot.effective_url).path).suffix.lower()
    preferred={v:k for k,v in SUPPORTED.items() if k not in ('.pdf','.docx')}
    if media:
        if media not in preferred:
            raise KnowledgeError(KnowledgeErrorCode.UNSUPPORTED_FORMAT)
        if suffix in SUPPORTED and SUPPORTED[suffix]!=media:
            raise KnowledgeError(KnowledgeErrorCode.TYPE_MISMATCH)
        suffix=preferred[media]
    elif suffix not in preferred.values():
        suffix='.txt'
    body=snapshot.body
    match=re.search(r'(?i)(?:^|;)\s*charset\s*=\s*(?:"([^"]+)"|([^;\s]+))',content_type)
    if body.startswith(b'\xff\xfe\x00\x00') or body.startswith(b'\x00\x00\xfe\xff'):encoding='utf-32'
    elif body.startswith(b'\xff\xfe') or body.startswith(b'\xfe\xff'):encoding='utf-16'
    elif body.startswith(b'\xef\xbb\xbf'):encoding='utf-8-sig'
    else:encoding=(match.group(1) or match.group(2)) if match else 'utf-8'
    try:
        codecs.lookup(encoding)
        text=body.decode(encoding,errors='strict')
    except (LookupError,UnicodeError,ValueError,TypeError):
        raise KnowledgeError(KnowledgeErrorCode.INVALID_ENCODING) from None
    if suffix in ('.html','.htm'):
        sanitizer=_PassiveHTML();sanitizer.feed(text);sanitizer.close()
        text=''.join(sanitizer.parts)
    # A truncated JSON/CSV/etc can lose structure. A parse failure stays typed,
    # never becomes an empty READY; successfully parsed truncation is PARTIAL.
    prepared=prepare_revision(operation,digest,size,text.encode('utf-8'),'remote'+suffix)
    blocks=tuple(replace(b,locator=SourceLocator(LocatorKind.WEB_BLOCK,{
        'url':snapshot.effective_url,'block':str(b.order+1)}),
        metadata={**b.metadata,'originalLocator':json.dumps(b.locator.to_dict(),sort_keys=True)})
        for b in prepared.document.blocks)
    warnings=(*prepared.document.warnings,*(('HTTP_BODY_TRUNCATED',) if snapshot.truncated else ()))
    status=ExtractionStatus.PARTIAL if snapshot.truncated else prepared.document.extraction_completeness
    document=replace(prepared.document,blocks=blocks,warnings=warnings,extraction_completeness=status)
    headers={k:v for k,v in snapshot.safe_headers if k in ('ETag','Last-Modified')
        and isinstance(v,str) and len(v)<=256 and not any(ord(c)<32 for c in v)}
    origin=dict(schemaVersion=1,requestedUrl=snapshot.requested_url,effectiveUrl=snapshot.effective_url,
        acquiredAt=snapshot.acquired_at.isoformat(),contentDigest=digest,mediaType=prepared.revision.media_type,
        contentType=snapshot.content_type,
        headers=headers,truncated=snapshot.truncated)
    revision=replace(prepared.revision,acquired_at=snapshot.acquired_at,
        extractor_profile='knowledge-url-snapshot-v1/'+prepared.revision.extractor_profile,
        extraction_status=status,extracted_digest=hashlib.sha256(document.text.encode()).hexdigest(),
        origin_fingerprint=json.dumps(origin,ensure_ascii=True,sort_keys=True,separators=(',',':')))
    return replace(prepared,revision=revision,document=document,chunks=chunk_document(document))
