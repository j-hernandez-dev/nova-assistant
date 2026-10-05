"""Known-value redaction at Nova publication/persistence boundaries (S6).

Not a detector of arbitrary files, transformed/unknown credentials or secrets
that HOST_UNISOLATED processes discover themselves. Registry stays in memory.
"""
from collections.abc import Mapping
from dataclasses import replace
import json
import os
import re
from threading import RLock
from urllib.parse import quote

from local_cli.security import SANITIZED_ENV_VARS

MARKER = '[REDACTED]'
_FIELDS = frozenset('''text content role message messages thinking tool_calls function arguments command timeout
    environment names readNames values risk stdout stderr status effectState exitCode error artifacts metadata legacyText
    name tool_name result cached toolCallId operationId turnId sessionId commandId approvalId inputRequestId requestDigest
    policyRevision deadline cwd workspace stateRevision lastSequence transcript turns model modelRuntime capabilities services
    schemaVersion kind payload visibility timestamp causationId agentId generationId approved reason operationType
    processModel pid processOutcome processStates cleanupScope cleanupConfirmed treeControl truncated stdoutTruncated
    stderrTruncated rawStreamsTruncated securityErrorCode processAudit controlClass controlClasses grantId policyDecision
    filesystemControlClass filesystemRootIdentity filesystemBeforeHash filesystemAfterHash verificationWarning
    networkControlClass networkAudit requestedUrl effectiveUrl action executable ts type count nested output exception
    providerId modelId providerRevision providerHealth health endpointRef modelRevision quantization capabilitySource
    inferenceOptions modelContextWindow providerContextWindow maxOutputTokens toolSupport thinkingSupport embeddingSupport
    available errorCode interactions approvals inputs operations rag filesystem persistence revision finalContent
    operationStatus activeGenerationId cancelRequested stopGenerationRequested terminalCount operationTerminalCount
    generations contextReports displayMessages transcriptStart transcriptEnd toolCalls toolResults harnessEvents
    source capturedAt observation value state supported os architecture shell systemRamTotalBytes systemRamAvailableBytes
    gpuDevices vramTotalBytes vramAvailableBytes resourceContextWindow concurrencyLimits'''.split())
_SENSITIVE = re.compile(r'(?i)(secret|password|credential|authorization|api[_-]?key|access[_-]?key|(?:^|[_-])token(?:$|[_-])|(?:access|session|auth|github|gh|npm|pypi|slack)[_-]?token|private[_-]?key|database[_-]?url)')


def sensitive_name(name):
    return name.casefold() in {n.casefold() for n in SANITIZED_ENV_VARS} or bool(_SENSITIVE.search(name))


class SecretRedactor:
    def __init__(self, *, source=None):
        self._lock = RLock()
        self._values = set()
        self._protected = set()
        self.observe_environment(os.environ if source is None else source)

    def register(self, value, *, protected=False):
        if not isinstance(value, str) or not value or value == MARKER:
            return
        with self._lock:
            self._values.update((value, quote(value, safe=''),
                json.dumps(value, ensure_ascii=True)[1:-1],
                json.dumps(value, ensure_ascii=False)[1:-1]))
            if protected:
                self._protected.add(value)

    def observe_environment(self, source):
        for name, value in source.items():
            internal = name.casefold().startswith(('nova_', 'ollama_', 'codex_'))
            provider = name.casefold() in ('openai_api_key', 'anthropic_api_key')
            if sensitive_name(name) or (internal and re.search(r'(?i)key|token|secret|grant|proof', name)):
                self.register(value, protected=internal or provider)
            if name.upper() in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'DATABASE_URL'):
                from urllib.parse import urlsplit, unquote
                try:
                    password = urlsplit(value).password
                    if password:
                        self.register(unquote(password), protected=internal or provider)
                except ValueError:
                    pass

    def observe_provider(self, provider):
        # Built-in adapter's credential; never call arbitrary/dynamic properties.
        value = vars(provider).get('_api_key') if hasattr(provider, '__dict__') else None
        self.register(value, protected=True)

    def protected_value(self, value):
        with self._lock:
            return any(secret in value for secret in self._protected)

    def values(self):
        with self._lock:
            return tuple(sorted(self._values, key=len, reverse=True))

    def text(self, text, *, partial=False):
        if text is None:
            return None
        values = self.values()
        if values:
            # One substitution avoids accidentally matching inside the marker.
            text = re.sub('|'.join([re.escape(MARKER), *(re.escape(s) for s in values)]), lambda _: MARKER, text)
            if partial:
                n = self._suffix(text, values)
                if n:
                    text = text[:-n] + MARKER
        return text

    @staticmethod
    def _suffix(text, values):
        longest = 0
        for secret in values:
            # Linear prefix-function: long configured values must not make
            # prefix detection quadratic on repetitive stdout/stream chunks.
            sequence = list(secret) + [None] + list(text[-(len(secret)-1):] if len(secret) > 1 else '')
            prefix = [0]*len(sequence)
            for i in range(1, len(sequence)):
                j = prefix[i-1]
                while j and sequence[i] != sequence[j]:
                    j = prefix[j-1]
                if sequence[i] == sequence[j]:
                    j += 1
                prefix[i] = j
            longest = max(longest, prefix[-1])
        return longest

    def value(self, value):
        if isinstance(value, Mapping):
            return {(str(k) if str(k) in _FIELDS else self.text(str(k))): (MARKER if sensitive_name(str(k)) and isinstance(v, str)
                    else self.value(v)) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [self.value(v) for v in value]
        return self.text(value) if isinstance(value, str) else value

    def tool_result(self, result):
        cut = bool(result.metadata.get('truncated'))
        return replace(result, stdout=self.text(result.stdout, partial=bool(result.metadata.get('stdoutTruncated', cut))),
            stderr=self.text(result.stderr, partial=bool(result.metadata.get('stderrTruncated', cut))), error=self.text(result.error),
            legacy_text=self.text(result.legacy_text, partial=cut),
            artifacts=tuple(self.text(s) for s in result.artifacts), metadata=self.value(result.metadata))

    def messages(self, messages):
        safe = self.value(messages)
        for original, item in zip(messages, safe):
            # Protocol discriminators are validated structure, not secret text.
            if original.get('role') in ('system', 'user', 'assistant', 'tool'):
                item['role'] = original['role']
        return safe

    def snapshot(self, source):
        """Redact view text while preserving typed lifecycle/correlation fields."""
        safe = self.value(source)
        def preserve(original, target, names):
            for name in names:
                if name in original:
                    target[name] = original[name]
        preserve(source, safe, ('sessionId','status','stateRevision','lastSequence'))
        safe['transcript'] = self.messages(source.get('transcript', []))
        for original, target in zip(source.get('turns', []), safe.get('turns', [])):
            preserve(original, target, ('turnId','operationId','commandId','status','operationStatus',
                'activeGenerationId','terminalCount','operationTerminalCount','transcriptStart','transcriptEnd'))
        original_services = source.get('services', {})
        services = safe.get('services', {})
        for kind, ids in [('approvals', ('approvalId','turnId','operationId','toolCallId',
                'name','policyRevision','requestDigest','deadline','cwd')), ('inputs', ('inputRequestId','turnId','deadline'))]:
            for original, target in zip(original_services.get('interactions', {}).get(kind, []),
                                        services.get('interactions', {}).get(kind, [])):
                preserve(original, target, ids)
        for original, target in zip(original_services.get('operations', []), services.get('operations', [])):
            preserve(original, target, ('operationId','status','service','turnId'))
        return safe

    def exception(self, exc):
        """Scrub exception arguments/chain before allowing a traceback outward."""
        seen = set()
        while exc is not None and id(exc) not in seen:
            seen.add(id(exc))
            exc.args = tuple(self.value(arg) for arg in exc.args)
            exc = exc.__cause__ or exc.__context__

    def stream(self):
        return RedactedStream(self)


class RedactedStream:
    """Hold only a possible known-secret prefix across chunks, incl. terminals."""
    def __init__(self, redactor):
        self.redactor = redactor
        self.pending = ''

    def feed(self, text):
        text = self.redactor.text(self.pending + text)
        n = self.redactor._suffix(text, self.redactor.values())
        self.pending = text[-n:] if n else ''
        return text[:-n] if n else text

    def finish(self):
        result = MARKER if self.pending else ''
        self.pending = ''
        return result

