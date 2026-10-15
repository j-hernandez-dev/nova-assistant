"""Conservative imperative intent for harness reminders, never authorization.

Only the original current-user request is inspected. Quoted examples, source
references, negations and chat-only deliverables cannot create pending effects.
The host's immutable Turn restriction remains the definitive separate barrier.
"""
import re
import unicodedata

_VERBS=r'create|write|make|build|implement|generate|add|fix|refactor|edit|modify|save|rename|produce|dump|crea|crear|escribe|escribir|haz|genera|generar|guarda|guardar|modifica|modificar|edita|editar|implementa|corrige'
_REQUEST=re.compile(r'^(?:(?:please|por favor)\s+)?(?:(?:can|could|would) you\s+|(?:puedes|podrias)\s+|(?:i want you to|quiero que)\s+)?(?:'+_VERBS+r')\b',re.I)
_NEGATION=re.compile(r'\b(?:not|never|without|no|don[\W_]*t|sin)\b',re.I)
_CHAT=re.compile(r'\b(?:here|inline|in (?:the )?chat|aqui|en (?:el )?chat)\b',re.I)
_FILE=re.compile(r'\.[a-z0-9]{1,10}\b|\b(?:files?|scripts?|filesystem|disk|archivos?|disco)\b',re.I)
_JA_VERBS=re.compile(r'作成|作って|書いて|保存|編集|修正|実装|追加|生成')


def positive_build_clauses(user_text):
    """Bounded EN/ES imperatives plus the established Japanese mutation verbs.

    Unknown/ambiguous phrasing does not justify a mutation reminder. Negation
    in an action clause conservatively suppresses that clause. File-name dots
    are not sentence boundaries. This is not a new Security/Turn resolver.
    """
    text=re.sub(r'```[\s\S]*?```|`[^`]*`|"[^"\n]*"|\u201c[^\u201d]*\u201d',' ',user_text)
    text='\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('>'))
    text=''.join(c for c in unicodedata.normalize('NFKD',text) if not unicodedata.combining(c))
    for clause in re.split(r'[!?;\n]+|\.(?=\s|$)|\b(?:and|also|but|y|ademas|pero)\b',text,flags=re.I):
        clause=clause.strip()
        if _NEGATION.search(clause) or re.search(r'しない|しないで|禁止',clause):continue
        if _CHAT.search(clause) and not _FILE.search(clause):continue
        if _REQUEST.search(clause) or _JA_VERBS.search(clause):yield clause


def positive_build_intent(user_text):
    return any(positive_build_clauses(user_text))


def positive_file_deliverable(user_text,mentions_file):
    # The action and output reference must occur in the SAME positive clause;
    # unrelated 'document' and a negated 'write' cannot be combined.
    return any(mentions_file(clause) for clause in positive_build_clauses(user_text))
