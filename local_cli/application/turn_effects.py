"""Host-owned, immutable reductions of a Turn's effects, never grants.

This deliberately supports a bounded EN/ES imperative grammar, not arbitrary
natural-language understanding. Only current SubmitUserInput is resolved.
Documents, model arguments, approvals and later generations cannot lift it.
"""
from dataclasses import dataclass
import re
import unicodedata


class TurnEffectDenied(ValueError):
    code = 'TURN_FILESYSTEM_MUTATION_DENIED'


def unquoted_clauses(text):
    # Quoted examples/code are not trusted current-user imperatives.
    text=re.sub(r'```[\s\S]*?```|`[^`]*`|"[^"\n]*"|\u201c[^\u201d]*\u201d', ' ', text)
    text='\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('>'))
    return tuple(c.strip() for c in re.split(r'[.!?;\n]+|\b(?:and|also|y|además)\b',text,flags=re.I) if c.strip())


def normalized_words(text):
    return re.findall(r'[^\W_]+',''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c)))


def prohibits_filesystem(clause):
    words=normalized_words(clause)
    while words and words[0] in ('please','por','favor'):words.pop(0)
    if words and words[0] in ('file','files','documents','archivos'):
        if re.search(r'\b(?:must|should|may|can) not (?:be )?(?:written|modified|created|deleted|edited)\b',' '.join(words[1:])):
            return True
    prefixes=(('do','not'),('don','t'),('never',),('no',))
    prefix=next((p for p in prefixes if tuple(words[:len(p)])==p),None)
    if prefix is None:return False
    rest=words[len(prefix):]
    verbs={'write','edit','modify','change','create','delete','remove','save','overwrite',
        'escribas','escriba','escribir','modifiques','modifique','modificar','cambies','cambiar',
        'crees','crear','borres','borrar','guardes','guardar','edites','editar','elimines','eliminar'}
    targets={'file','files','filesystem','document','documents','disk','anything','nothing',
        'archivos','archivo','documentos','documento','disco','nada'}
    if rest and rest[0] in targets and re.search(r'\b(?:should|must|may|can) be (?:written|modified|created|deleted|edited)\b',' '.join(rest[1:])):
        return True
    return bool(rest and rest[0] in verbs and set(rest[1:])&targets)


@dataclass(frozen=True)
class TurnEffectConstraints:
    filesystem_mutation_denied: bool = False

    def __post_init__(self):
        if type(self.filesystem_mutation_denied) is not bool:raise TypeError('invalid Turn effects')

    def check(self, intent):
        if self.filesystem_mutation_denied and (intent.effect.startswith('filesystem.write') or
                intent.effect.startswith('process.execute')):
            # HOST_UNISOLATED process mutations cannot be ruled out. Deny its
            # launch under this reduction, do not pretend to sandbox a shell.
            raise TurnEffectDenied()


def resolve_turn_effects(current_user_input):
    if not isinstance(current_user_input,str):raise TypeError('current input must be text')
    return TurnEffectConstraints(any(prohibits_filesystem(c) for c in unquoted_clauses(current_user_input)))
