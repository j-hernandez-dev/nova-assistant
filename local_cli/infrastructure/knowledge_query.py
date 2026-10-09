"""Private deterministic EN/ES query plan. Offsets address unchanged user input.

Recognizers describe bounded speech acts, never authority. Unrecognized content
stays factual. Source references are hints only: host source/revision/scope
filters remain authoritative. No gold, score, document or model chooses spans.
"""
from dataclasses import dataclass
import re

from local_cli.application.turn_effects import prohibits_filesystem
from local_cli.core.knowledge_retrieval import lexical_text, terms


@dataclass(frozen=True)
class QuerySpan:
    start: int
    end: int
    kind: str


@dataclass(frozen=True)
class KnowledgeQueryPlan:
    factual_spans: tuple[QuerySpan, ...]
    identifiers: tuple[QuerySpan, ...]
    source_constraints: tuple[QuerySpan, ...]
    output_controls: tuple[QuerySpan, ...]
    effect_controls: tuple[QuerySpan, ...]
    profile: str = 'knowledge-query-plan-en-es-v1'
    comparison_controls: tuple[QuerySpan, ...] = ()
    cardinality_controls: tuple[QuerySpan, ...] = ()
    epistemic_controls: tuple[QuerySpan, ...] = ()
    source_cardinality: int = 1
    source_diversity: bool = False

    @property
    def presentation_controls(self):
        # output_controls retains its prior compatibility view. These explicit
        # subsets let new consumers distinguish speech acts without rewriting input.
        return tuple(s for s in self.output_controls
            if s not in self.comparison_controls and s not in self.epistemic_controls)

    @property
    def controls(self):
        return tuple(sorted((*self.source_constraints, *self.output_controls,
            *self.effect_controls), key=lambda s: s.start))


@dataclass(frozen=True)
class QueryParts:
    factual: tuple[QuerySpan, ...]
    controls: tuple[QuerySpan, ...]


_OUTPUT = r'(?:answer|respond|reply|say|state|report|show|present|confirm|give|summarize|explain|responde|responder|contesta|di|indica|muestra|presenta|informa|confirma|proporciona|resume|explica)'
_WRITE = r'(?:create|write|save|store|make|crea|crear|escribe|escribir|guarda|guardar)'
_FILE = r'(?:[\w/\\-]+\.[\w-]+|(?:a |the |el |un )?(?:file|archivo|documento)\b)'
_LEAD = r'(?:(?:please|then|por favor|luego|despu[eé]s)\s+)?'
_REFERENCE = (r'(?:(?:only|solo|s[oó]lo)\s+)?(?:(?:the|this|that|el|este|ese|la|esta)\s+)?'
    r'(?:(?:admitted|attached|provided|selected|local|admitido|adjunto|proporcionado|seleccionado|local)\s+)?'
    r'(?:source document|document|file|source|documento|archivo|fuente)'
    r'(?:\s+(?:admitido|adjunto|proporcionado|seleccionado))?'
    r'(?:\s+(?:only|solo|s[oó]lo|as (?:the )?source|como fuente))?')
_SOURCE = re.compile(r'^\s*'+_LEAD+r'(?:use|using|according to|based on|usa|utiliza|usando|utilizando|seg[uú]n)\s+'+_REFERENCE+r'(?=\s*[,;:]|\s*$)', re.I)
_FORMAT = r'(?:citation|citations|marker|markers|answer|response|format|claims|value|values|alternative|alternatives|result|results|cita|citas|marcador|marcadores|respuesta|formato|afirmaciones|valor|valores|alternativas|resultado|resultados)'
_REFERENTIAL = re.compile(r'^\s*(?:(?:the|that|this|its|their|both|all|ese|esa|este|esta|el|la|los|las|ambos|ambas|su|sus)\s+)?(?:(?:two|conflicting|dos|contradictorios)\s+)?'+_FORMAT+r'\b', re.I)
_GROUNDING = re.compile(r'^(?:if|unless|otherwise|si|en caso)\s+'
    r'(?:(?:the|that|this|la|el|ese|esa|este|esta)\s+)?(?:absent|not provided|not present|unsupported|evidence|source|information|fact|dato|evidencia|fuente|falta|no aparece|no se proporciona)\b', re.I)
_OUTPUT_GRAMMAR = frozenset(('answer response result results claims value values alternative alternatives citation citations marker markers '
    'format short table list bullet bullets points exact provided given supplied identifiers end final reply too '
    'here chat only both all two conflicting without choosing single truth not their your its that this '
    'respuesta resultado resultados afirmaciones valores cita citas marcador marcadores formato '
    'breve tabla lista exacto exacta proporcionados proporcionadas suministrados identificadores '
    'final despues tambien aqui solo ambas ambos sin elegir unica verdad tu ese esa este esta').split())

# Anchored source-reference speech acts, not content-word stoplists. A named
# subject following about/sobre remains documentary content. Quoted clauses and
# ordinary factual uses of source/truth/compare never enter this grammar.
_COUNT = r'(?:both|all|two|three|four|five|\d+|ambas|ambos|todas|todos|dos|tres|cuatro|cinco)'
_SOURCE_GROUP = (r'(?:(?:the|las|los)\s+)?(?P<count>'+_COUNT+r')?\s*'
    r'(?:(?:the|las|los)\s+)?'
    r'(?:(?:conflicting|distinct|different|contradictorias|distintas|diferentes)\s+)?'
    r'(?:sources|claims|accounts|versions|documents|fuentes|afirmaciones|versiones|documentos)\b')
_TOPIC = r'(?:about|for|on|regarding|sobre|de|acerca de)'
_COMPARISON = re.compile(r'^'+_LEAD+r'(?:compare|contrast|compara|contrasta|explain|explica)\s+'
    +_SOURCE_GROUP+r'(?:\s+'+_TOPIC+r'\s+)?', re.I)
_SOURCE_QUESTION = re.compile(r'^'+_LEAD+r'(?:what\s+do\s+'+_SOURCE_GROUP
    +r'\s+(?:say|state|report|claim)\s+'+_TOPIC+r'\s+)', re.I)
_SOURCE_QUESTION_ES = re.compile(r'^'+_LEAD+r'(?:qu[eé]\s+(?:dicen|afirman|indican|declaran)\s+'
    +_SOURCE_GROUP+r'\s+'+_TOPIC+r'\s+)', re.I)
_EPISTEMIC = re.compile(r'^'+_LEAD+r'(?:'
    r'(?:do not|don[\x27\u2019]t|never)\s+(?:choose|select|treat|assume|prefer)\s+'
    r'(?:one|either|a single (?:source|claim)|one (?:source|claim))\s+as\s+(?:the\s+)?(?:truth|definitive)'
    r'|no\s+(?:elijas|selecciones|trates|asumas|prefieras)\s+(?:una|uno|una (?:fuente|afirmaci[oó]n))\s+como\s+(?:la\s+)?verdad'
    r'|(?:without choosing|sin elegir)\s+(?:a single truth|one as truth|una verdad|una como verdad)'
    r')\s*$', re.I)


def _cardinality(value):
    value = (value or '').casefold()
    counts = dict(two=2, both=2, dos=2, ambas=2, ambos=2, three=3, tres=3,
        four=4, cuatro=4, five=5, cinco=5)
    return min(32, int(value)) if value.isdecimal() and len(value) <= 2 else (32 if value.isdecimal() else counts.get(value, 2))


def _generic_reference(text):
    # A bounded grammar INSIDE an output complement, not a query stoplist.
    # Unknown names/predicates preserve ambiguity instead of being stripped.
    words=lexical_text(re.sub(r'\[K#\]', '', text)).split()
    return bool(words and _REFERENTIAL.match(text) and set(words)<=_OUTPUT_GRAMMAR)


def clauses(text):
    # Quoted punctuation is data; internal filename/version dots are too.
    start, quote = 0, None
    for i, char in enumerate(text):
        if char in ('"', chr(96), '\u201c', '\u201d'):
            if quote is None: quote = '\u201d' if char == '\u201c' else char
            elif char == quote: quote = None
        if quote or char not in '.!?;\n': continue
        if char == '.' and i and i+1 < len(text) and text[i-1].isalnum() and text[i+1].isalnum(): continue
        if start < i: yield start, i
        start = i+1
    if start < len(text): yield start, len(text)


def _has_key(text):
    return any(any(c.isalpha() for c in t) and any(c.isdigit() for c in t)
        for t in lexical_text(text).split())


def presentation(clause):
    """Conservative generic output speech act, not a factual imperative."""
    if _has_key(clause): return False
    raw = re.sub(r'^\s*'+_LEAD, '', clause, flags=re.I)
    if re.match(r'^(?:cite|cita|citar)\b', raw, re.I):
        match=re.match(r'^(?:cite|cita|citar)(?:\s+(?:the |your |la |las |el |tus )?(?:sources|source|fuentes|fuente|answer|respuesta)\b)?\s*',raw,re.I)
        rest=raw[match.end():]
        return not rest or bool(re.fullmatch(r'(?:without choosing|sin elegir)\s+(?:a single truth|una verdad)',rest,re.I))
    if re.match(r'^(?:use|add|attach|include|emit|usa|utiliza|agrega|anade|a[nñ]ade|incluye|emite)\b', raw, re.I):
        tail=re.sub(r'^\w+\s*','',raw)
        words=lexical_text(tail).split()
        return _generic_reference(tail) or bool(set(words)<=_OUTPUT_GRAMMAR and re.search(r'\b(?:citation|citations|marker|markers|cita|citas|marcador|marcadores)\b', tail, re.I))
    match = re.match(r'^'+_OUTPUT+r'\s+', raw, re.I)
    if not match: return False
    tail = raw[match.end():]
    if re.fullmatch(r'(?:briefly|brevemente|concisely|concisamente)(?:\s+(?:using|usando|utilizando|seg[uú]n)\s+'+_REFERENCE+r')?',tail,re.I):return True
    if re.match(r'^(?:here|aqu[ií]|in (?:the )?chat|en (?:el )?chat)\b', tail, re.I): return True
    tail = re.sub(r'^(?:(?:the|el|la)\s+)?(?:exact|exacto|exacta)\s+', '', tail, flags=re.I)
    if _generic_reference(tail): return True
    if re.fullmatch(r'(?:that|this|ese|esa)\s+\w+\s+(?:in your (?:answer|reply)|en tu respuesta)(?:\s+.*)?',tail,re.I): return True
    return bool(re.fullmatch(_REFERENCE+r'\s+(?:here|aqu[ií])(?:\s+.*)?', tail, re.I))


def plan_query(text):
    terms(text)  # Existing type/NUL validation.
    facts, sources, outputs, effects = [], [], [], []
    comparisons, cardinalities, epistemics = [], [], []
    cardinality, diversity = 1, False
    def add(start, end, kind, target):
        while start < end and text[start].isspace(): start += 1
        while end > start and text[end-1].isspace(): end -= 1
        if start < end: target.append(QuerySpan(start, end, kind))

    def analyze(start, end):
        nonlocal cardinality, diversity
        while start < end and text[start] in ' \t\r\n,¿': start += 1
        while end > start and text[end-1] in ' \t\r\n,': end -= 1
        if start >= end: return
        raw = text[start:end]
        # Quotes/code are data, including control-looking documentary facts.
        if raw.startswith(('"', chr(96), '\u201c', '>')):
            add(start, end, 'factual', facts); return
        if _EPISTEMIC.fullmatch(raw):
            add(start, end, 'epistemic_control', outputs)
            epistemics.append(outputs[-1]); return
        if re.match(r'^'+_LEAD+r'(?:'+_OUTPUT[3:-1]+r'\s+)?(?:my|mi|mis)\s+.*\b(?:remembered|preference|preferences|memory|preferencia|preferencias|memoria)\b',raw,re.I):
            add(start,end,'memory_request',outputs);return
        # A grounding conditional is one speech act, including its comma. Do
        # not split its antecedent into documentary tokens. Factual conditions
        # (e.g. if pressure is high) do not match this bounded grammar.
        if (_GROUNDING.match(raw) and re.search(r'\b'+_OUTPUT+r'\b', raw,re.I)
                and re.search(r'\bUNKNOWN\b',raw,re.I) and not _has_key(raw)):
            add(start,end,'grounding_condition',outputs); return
        if presentation(raw): add(start,end,'presentation',outputs); return
        # Split conjunctions only when the right side is a control speech act.
        for boundary in re.finditer(r'[,;]|\b(?:and|also|plus|but|y|adem[aá]s|pero)\b', raw, re.I):
            right = raw[boundary.end():].strip()
            memory = re.match(r'^(?:my|mi|mis)\s+.*\b(?:remembered|preference|preferences|memory|preferencia|preferencias|memoria)\b', right, re.I)
            directive = re.match(r'^'+_LEAD+r'(?:'+_OUTPUT[3:-1]+'|'+_WRITE[3:-1]+r'|cite|cita|use|usa|include|incluye|if|unless|si|do not|don[\x27\u2019]t|no)\b', right, re.I)
            if memory or directive:
                analyze(start, start+boundary.start())
                if memory: add(start+boundary.start(), end, 'memory_request', outputs)
                else: analyze(start+boundary.end(), end)
                return
        source = _SOURCE.match(raw)
        if source:
            cut=start+source.end(); add(start, cut, 'source_reference', sources)
            analyze(cut, end); return
        if prohibits_filesystem(raw):
            add(start, end, 'filesystem_prohibition', effects); return
        if re.match(r'^'+_LEAD+r'(?:do not|don[\x27\u2019]t|never|no)\s+(?:search|fetch|browse|execute|follow|use|busques|consultes|navegues|ejecutes|sigas|uses)\b', raw, re.I):
            add(start, end, 'effect_prohibition', effects); return
        if re.match(r'^(?:this|the|esta|la)\b.*\b(?:file|archivo)\b.*\b(?:authoriz|autoriz)', raw, re.I):
            add(start, end, 'effect_authorization', effects); return
        effect=re.match(r'^'+_LEAD+_WRITE+r'\s+["\x27]?'+_FILE+r'["\x27]?\s*', raw, re.I)
        if effect:
            payload=re.match(r'\s*(?:containing|with(?:\s+the\s+content)?|con(?:\s+el\s+contenido)?|que\s+contenga|conteniendo|:)\s*', raw[effect.end():], re.I)
            cut=start+effect.end()+(payload.end() if payload else 0)
            if not payload: add(start, end, 'filesystem_effect', effects); return
            add(start, cut, 'filesystem_effect', effects)
            tail=text[cut:end]
            if _generic_reference(tail) and not _has_key(tail):
                add(cut, end, 'answer_reference', outputs)
            else: analyze(cut, end)
            return
        comparison = _COMPARISON.match(raw) or _SOURCE_QUESTION.match(raw) or _SOURCE_QUESTION_ES.match(raw)
        if comparison:
            cut=start+comparison.end(); add(start, cut, 'comparison_operator', outputs)
            comparisons.append(outputs[-1])
            count = comparison.group('count')
            cardinality = max(cardinality, _cardinality(count))
            diversity = True
            if count:
                add(start+comparison.start('count'), start+comparison.end('count'), 'source_cardinality', cardinalities)
            analyze(cut, end); return
        if re.match(r'^'+_LEAD+r'(?:without|sin)\s+(?:choosing|elegir)\b', raw, re.I):
            add(start, end, 'comparison_output', outputs); return
        suffix=re.search(r'\b(?:using|with|use|utilizando|usando|con)\s+'
            r'(?:(?:the|their|los|las|sus)\s+)?(?:(?:provided|given|exact|proporcionados|proporcionadas)\s+)?'
            r'(?:citation(?:s|\s+markers)?|markers|marcadores(?:\s+de\s+cita)?|citas)\b', raw, re.I)
        if suffix and not _has_key(raw[suffix.start():]):
            add(start+suffix.start(), end, 'citation_format', outputs)
            analyze(start, start+suffix.start()); return
        if presentation(raw): add(start, end, 'presentation', outputs); return
        # Information-request operators, not content words in any position.
        request=re.match(r'^'+_LEAD+r'(?:give|tell me|show|explain|report|dime|indica|explica|informa)\s+', raw, re.I)
        if request:
            cut=start+request.end(); add(start, cut, 'request_operator', outputs)
            analyze(cut, end); return
        add(start, end, 'factual', facts)

    for start, end in clauses(text): analyze(start, end)
    keys=[]
    for span in facts:
        for match in re.finditer(r'[^\W_]+(?:[-/][^\W_]+)*', text[span.start:span.end]):
            value=match.group()
            if (any(c.isalpha() for c in value) and any(c.isdigit() for c in value)) or value.isupper() and len(value)>2:
                keys.append(QuerySpan(span.start+match.start(),span.start+match.end(),'identifier'))
    return KnowledgeQueryPlan(tuple(facts),tuple(keys),tuple(sources),tuple(outputs),tuple(effects),
        comparison_controls=tuple(comparisons), cardinality_controls=tuple(cardinalities),
        epistemic_controls=tuple(epistemics), source_cardinality=cardinality, source_diversity=diversity)


def decompose_query(text):
    """Compatibility view for prior private consumers; no input rewrite."""
    plan=plan_query(text)
    return QueryParts(plan.factual_spans,plan.controls)
