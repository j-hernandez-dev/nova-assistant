"""M3 explicit-only policy. Not AUTO_SAFE, an extractor or an authority grant."""
import re

from local_cli.core.memory import (MemoryError, MemoryErrorCode, MemorySensitivity,
    MemorySourceClass, MemoryWriteDisposition, validate_sensitivity)
from local_cli.application.secrets import sensitive_name


_CREDENTIAL = re.compile(r'(?i)(?:password|passwd|api[_ -]?key|access[_ -]?token|'
    r'authorization|contrase[ñn]a|private[_ -]?key)\s*[:=]\s*\S+|'
    r'\bbearer\s+\S+|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
_SENSITIVE = re.compile(r'(?i)\b(?:diagnos\w*|medical|m[ée]dic\w*|salud|'
    r'health|bank account|cuenta bancaria|social security|ssn)\b')
_ASSIGNMENT = re.compile(r'''["']?([A-Za-z_][A-Za-z0-9_.-]{0,127})["']?\s*[:=]\s*[^\s,}]+''')


class ExplicitMemoryPolicy:
    def __init__(self, redactor):
        self.redactor = redactor

    def classify(self, text, key=None, *, sensitive=False):
        if (not isinstance(text, str) or not text.strip() or '\x00' in text
                or key is not None and (not isinstance(key, str) or not key.strip() or len(key)>256)
                or type(sensitive) is not bool):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        if (self.redactor.text(text) != text or key is not None and self.redactor.text(key) != key
                or _CREDENTIAL.search(text) or key is not None and sensitive_name(key)
                or any(sensitive_name(match.group(1)) for match in _ASSIGNMENT.finditer(text))):
            return MemorySensitivity.SECRET_DENIED
        return MemorySensitivity.SENSITIVE if sensitive or _SENSITIVE.search(text) else MemorySensitivity.NORMAL

    def evaluate(self, proposal, *, explicit_user_action, explicit_sensitive_consent):
        if not explicit_user_action or proposal.source_class is not MemorySourceClass.USER_EXPLICIT_MEMORY:
            return MemoryWriteDisposition.REJECT
        validate_sensitivity(proposal.sensitivity_class,
                             explicit_sensitive_consent=explicit_sensitive_consent)
        return MemoryWriteDisposition.ACCEPT
