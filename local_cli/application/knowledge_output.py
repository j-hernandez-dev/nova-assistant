"""Bounded representation of a model's explicit Knowledge abstention.

No evidence/question/gold inspection: this cannot select abstention. Ambiguous
or factual content passes through unchanged. No citation/tool/authority changes.
"""
from copy import deepcopy
import re

MAX_PENDING_CHARS = 2048
_DECISION = re.compile(
    r'(?:(?:Therefore|Thus|Hence|Consequently|Por tanto|Por lo tanto|En consecuencia)'
    r'[, :]\s*|(?:Therefore|Thus|Hence|Consequently|Por tanto|Por lo tanto|En consecuencia)\s+)?'
    r'(?:(?:the answer is|my answer is|la respuesta es)\s+)?UNKNOWN[.!]?\s*$', re.I)
_ABSENCE = tuple(re.compile(pattern, re.I) for pattern in (
    r'(?:the|this) [\w -]{1,160} (?:is|are|was|were) not '
    r'(?:provided|available|stated|specified|documented|present|given|supported)'
    r'(?: (?:in|by|from) (?:the |this |admitted |provided )?[\w -]{1,100})?',
    r'(?:the|this) (?:source|document|evidence|record|material) '
    r'(?:does not|doesn\x27t) (?:provide|contain|state|specify|document|give|support) [\w -]{1,140}',
    r'there (?:is|are) no (?:evidence|information|data|answer|support)(?: [\w -]{1,140})?',
    r'(?:la|el|las|los) [\w -]{1,160} no (?:esta|está|estan|están) '
    r'(?:disponible|disponibles|documentado|documentada|especificado|especificada|presente)'
    r'(?: en [\w -]{1,100})?',
    r'(?:la|el) (?:fuente|documento|evidencia|registro) no '
    r'(?:proporciona|contiene|indica|especifica|documenta) [\w -]{1,140}',
    r'no (?:hay|se proporciona|se indica|se especifica) [\w -]{1,140}',
))


def _absence_only(text):
    clean=re.sub(r'\[K[1-9][0-9]*\]', '', text).strip()
    sentences=[s.strip() for s in re.split(r'[.!?\n]+',clean) if s.strip()]
    return bool(sentences) and len(sentences)<=3 and all(
        any(p.fullmatch(s) for p in _ABSENCE) for s in sentences)


def canonical_terminal(text):
    """Normalize only an unambiguous terminal sentinel, never inferred unknowns."""
    stripped=text.strip()
    if re.fullmatch(r'UNKNOWN[.!]?',stripped):return 'UNKNOWN'
    if len(text)>MAX_PENDING_CHARS or any(c in text for c in ('"','`','“','”','=', ';')):
        return text
    match=_DECISION.search(stripped)
    if not match or not re.search(r'\bUNKNOWN[.!]?\s*$',stripped):return text
    prefix=stripped[:match.start()].strip()
    if 'unknown' in prefix.casefold():return text
    if not prefix or _absence_only(prefix):return 'UNKNOWN'
    return text


class _Pending:
    def __init__(self):self.text='';self.passthrough=False

    def feed(self,text,*,terminal=False,tool=False):
        if self.passthrough:return text
        self.text+=text
        if tool or len(self.text)>MAX_PENDING_CHARS:
            self.passthrough=True;return self.release()
        if terminal:
            value=canonical_terminal(self.text);self.text='';self.passthrough=True;return value
        roots=('unknown','the ','this ','there ','i ','la ','el ','las ','los ','no ',
            'therefore','thus','hence','consequently','por tanto','por lo tanto','en consecuencia')
        leading=self.text.lstrip().casefold()
        possible=not leading or any(leading.startswith(r) or r.startswith(leading) for r in roots)
        first=re.split(r'[.!?\n]',self.text,maxsplit=1)
        if not possible or len(first)>1 and not _absence_only(first[0]) and canonical_terminal(self.text)==self.text:
            self.passthrough=True;return self.release()
        return ''

    def release(self):
        value=self.text;self.text='';return value


def canonical_stream(stream):
    """Yield progress for cancellation/retry, never canonize a tool request.

    Ordinary prose is released at its first non-absence sentence; only possible
    abstention is held to completion, bounded by MAX_PENDING_CHARS. Errors flush
    unchanged partial content, not a fabricated successful UNKNOWN. Generator
    close discards pending text. Original usage/finish/tool fields are preserved.
    """
    pending=_Pending()
    try:
        for chunk in stream:
            safe=deepcopy(chunk);message=safe.get('message') or {}
            text=message.get('content') or ''
            value=pending.feed(text,terminal=bool(chunk.get('done')),
                tool=bool(message.get('tool_calls')) or chunk.get('done_reason') not in (None,'stop'))
            if text or value:safe.setdefault('message',{})['content']=value
            yield safe
        if not pending.passthrough and pending.text:
            yield {'message':{'role':'assistant','content':pending.feed('',terminal=True)}}
    except Exception:
        partial=pending.release()
        if partial:yield {'message':{'role':'assistant','content':partial}}
        raise
    finally:
        close=getattr(stream,'close',None)
        if close is not None:close()


def canonical_message(result):
    message=result.get('message') or {}
    if (message.get('tool_calls') or result.get('done_reason') not in (None,'stop')
            or not isinstance(message.get('content'),str)):return result
    value=canonical_terminal(message['content'])
    if value==message['content']:return result
    safe=deepcopy(result);safe['message']['content']=value;return safe
