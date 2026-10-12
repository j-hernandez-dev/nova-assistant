"""V12-B1 closed contracts. No socket, browser, issuer, credential lookup or probe.

Requests are private host DTOs, not model tool arguments or reusable authority.
Admitted plans/refs have no wire constructor. Python host code is trusted; these
types are not isolation against arbitrary code executing inside that host.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from enum import Enum
import ipaddress
import re
from typing import Protocol
from urllib.parse import urlsplit

from local_cli.core.active_web import BrowserOutcomeState as ControlledFetchOutcome
from local_cli.core.contracts import Observation
from local_cli.core.network import FetchBudget, NetworkEndpoint
from local_cli.core.security import PathStyle, ResourceScope, ScopeKind, SecurityError

CONTROLLED_FETCH_CAPABILITY_ID = 'CONTROLLED_FETCH_V1_2'
INTERACTIVE_BROWSER_CAPABILITY_ID = 'INTERACTIVE_BROWSER_V1_2'


class ControlledFetchErrorCode(str, Enum):
    SCHEMA = 'CONTROLLED_FETCH_INVALID_SCHEMA'
    CAPABILITY = 'CONTROLLED_FETCH_WRONG_CAPABILITY'
    OWNER = 'CONTROLLED_FETCH_OWNER_MISMATCH'
    OPERATION = 'CONTROLLED_FETCH_OPERATION_MISMATCH'
    POLICY = 'CONTROLLED_FETCH_STALE_POLICY'
    EXPIRED = 'CONTROLLED_FETCH_EXPIRED'
    URL = 'CONTROLLED_FETCH_URL_DENIED'
    METHOD = 'CONTROLLED_FETCH_UNSUPPORTED_METHOD'
    MODE = 'CONTROLLED_FETCH_UNSUPPORTED_MODE'
    OPTIONAL = 'CONTROLLED_FETCH_OPTIONAL_NOT_AVAILABLE'
    AUTHORITY = 'CONTROLLED_FETCH_AUTHORITY_DENIED'
    ADMISSION = 'CONTROLLED_FETCH_ADMISSION_DENIED'
    REF = 'CONTROLLED_FETCH_HOST_REF_DENIED'
    REDIRECT = 'CONTROLLED_FETCH_REDIRECT_DENIED'
    LIMIT = 'CONTROLLED_FETCH_LIMIT_EXCEEDED'
    BUSY = 'CONTROLLED_FETCH_CONCURRENCY_LIMIT'
    REPLAY = 'CONTROLLED_FETCH_REPLAY_DENIED'
    UNCONFIGURED = 'CONTROLLED_FETCH_TRANSPORT_NOT_CONFIGURED'
    TRANSPORT = 'CONTROLLED_FETCH_TRANSPORT_FAILED'
    RESPONSE = 'CONTROLLED_FETCH_INVALID_RESPONSE'
    FORMAT = 'CONTROLLED_FETCH_INVALID_CONTENT'
    JOURNAL = 'CONTROLLED_FETCH_RECEIPT_RECORD_FAILED'
    OUTCOME = 'CONTROLLED_FETCH_INVALID_OUTCOME'
    CANCELLED = 'CONTROLLED_FETCH_CANCELLED'
    TIMEOUT = 'CONTROLLED_FETCH_TIMEOUT'
    TLS = 'CONTROLLED_FETCH_TLS_FAILED'
    CONNECT = 'CONTROLLED_FETCH_CONNECT_FAILED'
    FRAMING = 'CONTROLLED_FETCH_FRAMING_DENIED'


class ControlledFetchError(ValueError):
    def __init__(self, code: ControlledFetchErrorCode):
        if type(code) is not ControlledFetchErrorCode:
            code = ControlledFetchErrorCode.SCHEMA
        self.code = code
        super().__init__(code.value)  # Never echo URL, exception, headers or refs.


def require(condition, code=ControlledFetchErrorCode.SCHEMA):
    if not condition:
        raise ControlledFetchError(code)


def closed(value, keys):
    require(type(value) is dict and set(value) == set(keys))


def label(value):
    require(type(value) is str and 0 < len(value) <= 512 and
            not any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value))


def aware(value):
    require(type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None)


def canonical_target(value):
    """Validate canonical spelling only; Application owns canonicalization/admission."""
    try:
        require(type(value) is str, ControlledFetchErrorCode.URL)
        require(ResourceScope(ScopeKind.URL, value).resource == value, ControlledFetchErrorCode.URL)
        host = urlsplit(value).hostname
        dns_label = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
        require(bool(host) and (':' in host or (len(host)<=253 and re.fullmatch(dns_label+r'(?:\.'+dns_label+r')*', host))), ControlledFetchErrorCode.URL)
        if ':' in host or re.fullmatch(r'[0-9.]+', host) or host.startswith('0x'):
            ipaddress.ip_address(host)
    except (SecurityError, ValueError, TypeError):
        raise ControlledFetchError(ControlledFetchErrorCode.URL) from None


class ControlledFetchMethod(str, Enum):
    GET = 'GET'
    HEAD = 'HEAD'


class ControlledFetchResultMode(str, Enum):
    TEXT = 'TEXT'
    HTML_STATIC = 'HTML_STATIC'
    JSON = 'JSON'


class ControlledFetchCompleteness(str, Enum):
    NONE = 'NONE'
    COMPLETE = 'COMPLETE'
    PARTIAL = 'PARTIAL'


class ControlledFetchAbsence(str, Enum):
    NO_RESULT = 'NO_RESULT'
    HEAD_NO_BODY = 'HEAD_NO_BODY'
    PUBLICATION_LIMIT = 'PUBLICATION_LIMIT'


@dataclass(frozen=True)
class ControlledFetchOwner:
    owner_id: str
    workspace: str = field(repr=False)
    task_id: str

    def __post_init__(self):
        for value in (self.owner_id, self.workspace, self.task_id):
            label(value)
        require(not self.owner_id.startswith(('bws_', 'bwp_', 'bwe_', 'bhi_')), ControlledFetchErrorCode.OWNER)
        try:
            ResourceScope(ScopeKind.DIRECTORY_TREE, self.workspace,
                          PathStyle.POSIX if self.workspace.startswith('/') else PathStyle.WINDOWS)
        except SecurityError:
            raise ControlledFetchError(ControlledFetchErrorCode.OWNER) from None

    def to_dict(self):
        return dict(ownerId=self.owner_id, workspace=self.workspace, taskId=self.task_id)

    @classmethod
    def from_dict(cls, data):
        closed(data, ('ownerId', 'workspace', 'taskId'))
        return cls(data['ownerId'], data['workspace'], data['taskId'])


@dataclass(frozen=True)
class ControlledFetchLimits:
    timeout_seconds: int = 30
    max_redirects: int = 5
    max_header_bytes: int = 32768
    max_response_bytes: int = 2097152
    max_published_chars: int = 32768
    per_turn_requests: int = 8
    concurrency: int = 2
    per_turn_bytes: int = 50331648

    def __post_init__(self):
        ceilings = (30, 5, 32768, 2097152, 32768, 8, 2, 50331648)
        for item, ceiling in zip(fields(self), ceilings):
            value = getattr(self, item.name)
            require(type(value) is int and (0 if item.name == 'max_redirects' else 1) <= value <= ceiling,
                    ControlledFetchErrorCode.LIMIT)

    def covers(self, other):
        return type(other) is type(self) and all(getattr(other, f.name) <= getattr(self, f.name) for f in fields(self))

    def to_dict(self):
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, data):
        closed(data, (f.name for f in fields(cls)))
        return cls(**data)


@dataclass(frozen=True)
class ControlledFetchRequest:
    capability_id: str
    owner: ControlledFetchOwner
    turn_id: str
    operation_id: str
    policy_revision: int
    deadline: datetime
    canonical_target: str = field(repr=False)
    method: ControlledFetchMethod
    result_mode: ControlledFetchResultMode
    limits: ControlledFetchLimits

    def __post_init__(self):
        require(self.capability_id == CONTROLLED_FETCH_CAPABILITY_ID, ControlledFetchErrorCode.CAPABILITY)
        require(type(self.owner) is ControlledFetchOwner)
        label(self.turn_id); label(self.operation_id)
        require(type(self.policy_revision) is int and self.policy_revision >= 1, ControlledFetchErrorCode.POLICY)
        aware(self.deadline); canonical_target(self.canonical_target)
        require(type(self.method) is ControlledFetchMethod, ControlledFetchErrorCode.METHOD)
        require(type(self.result_mode) is ControlledFetchResultMode, ControlledFetchErrorCode.MODE)
        require(type(self.limits) is ControlledFetchLimits)

    def to_dict(self):
        """PRIVATE host schema; never used as a public result/audit/context DTO."""
        return dict(capabilityId=self.capability_id, owner=self.owner.to_dict(), turnId=self.turn_id,
                    operationId=self.operation_id, policyRevision=self.policy_revision,
                    deadline=self.deadline.isoformat(), canonicalTarget=self.canonical_target,
                    method=self.method.value, resultMode=self.result_mode.value, limits=self.limits.to_dict())

    @classmethod
    def from_dict(cls, data):
        closed(data, ('capabilityId','owner','turnId','operationId','policyRevision','deadline','canonicalTarget','method','resultMode','limits'))
        require(data['capabilityId'] == CONTROLLED_FETCH_CAPABILITY_ID, ControlledFetchErrorCode.CAPABILITY)
        require(type(data['method']) is str and data['method'] in ('GET','HEAD'), ControlledFetchErrorCode.METHOD)
        require(type(data['resultMode']) is str and data['resultMode'] in ('TEXT','HTML_STATIC','JSON'), ControlledFetchErrorCode.MODE)
        require(type(data['deadline']) is str)
        try:
            deadline = datetime.fromisoformat(data['deadline'])
        except ValueError:
            raise ControlledFetchError(ControlledFetchErrorCode.SCHEMA) from None
        return cls(data['capabilityId'], ControlledFetchOwner.from_dict(data['owner']), data['turnId'],
                   data['operationId'], data['policyRevision'], deadline, data['canonicalTarget'],
                   ControlledFetchMethod(data['method']), ControlledFetchResultMode(data['resultMode']),
                   ControlledFetchLimits.from_dict(data['limits']))


@dataclass(frozen=True)
class ControlledFetchConsumption:
    logical_requests: int = 0
    hops: int = 0
    redirects: int = 0
    header_bytes: int = 0
    response_bytes: int = 0
    published_chars: int = 0

    def __post_init__(self):
        for f in fields(self):
            require(type(getattr(self, f.name)) is int and getattr(self, f.name) >= 0)
        require(self.logical_requests <= 1 and self.redirects <= 5 and self.hops <= 6 and
                self.header_bytes <= 12*32768 and self.response_bytes <= 6*2097152 and self.published_chars <= 32768)

    def to_dict(self):
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, data):
        closed(data, (f.name for f in fields(cls)))
        return cls(**data)


@dataclass(frozen=True)
class ControlledFetchProvenance:
    source: str = 'V12_B1_CONTRACT_COMPOSITION'
    trust: str = 'UNTRUSTED_REMOTE_DATA'
    network_egress_control: str = 'UNKNOWN'
    public_only: str = 'UNKNOWN'

    def __post_init__(self):
        require(self.source == 'V12_B1_CONTRACT_COMPOSITION' and self.trust == 'UNTRUSTED_REMOTE_DATA' and
                self.network_egress_control == self.public_only == 'UNKNOWN')

    def to_dict(self):
        return dict(source=self.source, trust=self.trust, networkEgressControl=self.network_egress_control, publicOnly=self.public_only)


@dataclass(frozen=True)
class ControlledFetchResult:
    capability_id: str
    operation_id: str
    sanitized_url: str
    origin: str
    method: ControlledFetchMethod
    result_mode: ControlledFetchResultMode
    outcome: ControlledFetchOutcome
    completeness: ControlledFetchCompleteness
    truncated: bool
    content_type: str | None
    counted_bytes: int
    consumed: ControlledFetchConsumption
    payload: str | None = field(repr=False)
    absence: ControlledFetchAbsence | None
    error: ControlledFetchErrorCode | None
    provenance: ControlledFetchProvenance = field(default_factory=ControlledFetchProvenance)

    def __post_init__(self):
        require(self.capability_id == CONTROLLED_FETCH_CAPABILITY_ID, ControlledFetchErrorCode.CAPABILITY)
        label(self.operation_id)
        try:
            require(ResourceScope(ScopeKind.ORIGIN, self.origin).resource == self.origin)
        except SecurityError:
            raise ControlledFetchError(ControlledFetchErrorCode.SCHEMA) from None
        require(self.sanitized_url == self.origin + '/[path-redacted]')
        require(type(self.method) is ControlledFetchMethod and type(self.result_mode) is ControlledFetchResultMode)
        require(type(self.outcome) is ControlledFetchOutcome and type(self.completeness) is ControlledFetchCompleteness)
        require(type(self.truncated) is bool and type(self.counted_bytes) is int and self.counted_bytes >= 0)
        require(self.content_type is None or (type(self.content_type) is str and
                re.fullmatch(r'[a-z0-9.+-]+/[a-z0-9.+-]+', self.content_type) and len(self.content_type) <= 128))
        require(type(self.consumed) is ControlledFetchConsumption and self.counted_bytes == self.consumed.response_bytes)
        require(type(self.provenance) is ControlledFetchProvenance)
        require((type(self.payload) is str and len(self.payload) <= 32768 and self.absence is None) or
                (self.payload is None and type(self.absence) is ControlledFetchAbsence))
        if self.payload is not None:require(not any(0xD800<=ord(c)<=0xDFFF for c in self.payload))
        require(self.error is None or type(self.error) is ControlledFetchErrorCode)
        if self.outcome in (ControlledFetchOutcome.NOT_STARTED, ControlledFetchOutcome.STARTED,
                            ControlledFetchOutcome.FAILED_NO_EFFECT_CONFIRMED, ControlledFetchOutcome.UNKNOWN):
            require(self.payload is None and self.completeness is ControlledFetchCompleteness.NONE, ControlledFetchErrorCode.OUTCOME)
        if self.outcome is ControlledFetchOutcome.SUCCEEDED_OBSERVED:
            require(self.error is None and not self.truncated and self.completeness is ControlledFetchCompleteness.COMPLETE,
                    ControlledFetchErrorCode.OUTCOME)
        if self.outcome is ControlledFetchOutcome.PARTIAL:
            require(self.completeness is ControlledFetchCompleteness.PARTIAL, ControlledFetchErrorCode.OUTCOME)
        if self.method is ControlledFetchMethod.HEAD:
            require(self.payload is None, ControlledFetchErrorCode.OUTCOME)
            if self.outcome is ControlledFetchOutcome.SUCCEEDED_OBSERVED:
                require(self.counted_bytes == 0 and self.absence is ControlledFetchAbsence.HEAD_NO_BODY)
        if self.payload is not None:
            require(self.consumed.published_chars == len(self.payload))

    def to_dict(self):
        return dict(capabilityId=self.capability_id, operationId=self.operation_id, sanitizedUrl=self.sanitized_url,
                    origin=self.origin, method=self.method.value, resultMode=self.result_mode.value,
                    outcome=self.outcome.value, completeness=self.completeness.value, truncated=self.truncated,
                    contentType=self.content_type, countedBytes=self.counted_bytes, consumed=self.consumed.to_dict(),
                    payload=self.payload, absence=self.absence.value if self.absence else None,
                    error=self.error.value if self.error else None, provenance=self.provenance.to_dict(), retryAllowed=False)

    @classmethod
    def from_dict(cls, data):
        closed(data, ('capabilityId','operationId','sanitizedUrl','origin','method','resultMode','outcome','completeness',
                      'truncated','contentType','countedBytes','consumed','payload','absence','error','provenance','retryAllowed'))
        require(data['retryAllowed'] is False)
        p = data['provenance']; closed(p, ('source','trust','networkEgressControl','publicOnly'))
        try:
            return cls(data['capabilityId'], data['operationId'], data['sanitizedUrl'], data['origin'],
                ControlledFetchMethod(data['method']), ControlledFetchResultMode(data['resultMode']),
                ControlledFetchOutcome(data['outcome']), ControlledFetchCompleteness(data['completeness']),
                data['truncated'], data['contentType'], data['countedBytes'], ControlledFetchConsumption.from_dict(data['consumed']),
                data['payload'], ControlledFetchAbsence(data['absence']) if data['absence'] is not None else None,
                ControlledFetchErrorCode(data['error']) if data['error'] is not None else None,
                ControlledFetchProvenance(p['source'],p['trust'],p['networkEgressControl'],p['publicOnly']))
        except (ValueError, TypeError):
            raise ControlledFetchError(ControlledFetchErrorCode.SCHEMA) from None


@dataclass(frozen=True)
class AdmittedControlledFetchRequest:
    """Private plan. Application additionally requires identity in its admission ledger.

    No from_dict/to_dict: a matching dataclass or endpoint from a caller is not admission.
    The endpoint is generated by BrowserNetworkPolicy/S5, never model arguments.
    """
    request: ControlledFetchRequest = field(repr=False)
    canonical_target: str = field(repr=False)
    approved_scope: ResourceScope = field(repr=False)
    endpoint: NetworkEndpoint = field(repr=False)
    hop: int
    lineage: object = field(repr=False, compare=False)
    transfer_byte_allowance: int
    dns_answers: tuple[NetworkEndpoint, ...] = field(default=(), repr=False)

    def __post_init__(self):
        require(type(self.request) is ControlledFetchRequest and type(self.approved_scope) is ResourceScope)
        canonical_target(self.canonical_target)
        require(type(self.endpoint) is NetworkEndpoint and type(self.hop) is int and 0 <= self.hop <= self.request.limits.max_redirects)
        require(type(self.transfer_byte_allowance) is int and 1 <= self.transfer_byte_allowance <= self.request.limits.per_turn_bytes)
        require(type(self.dns_answers) is tuple and len(self.dns_answers)<=64 and all(type(e) is NetworkEndpoint for e in self.dns_answers))


@dataclass(frozen=True)
class ControlledFetchTransportEvidence:
    """Private measured counters, not a model proof/Grant. Bound by Application at use."""
    plan: AdmittedControlledFetchRequest = field(repr=False)
    transport: object = field(repr=False,compare=False)
    request_bytes_sent: int
    response_header_bytes: int
    response_body_bytes: int
    connected: bool
    connected_endpoint: tuple | None = field(repr=False)
    error: ControlledFetchErrorCode | None

    def __post_init__(self):
        require(type(self.plan) is AdmittedControlledFetchRequest)
        require(all(type(v) is int and v>=0 for v in (self.request_bytes_sent,self.response_header_bytes,self.response_body_bytes)))
        require(type(self.connected) is bool)


class ControlledFetchTransportFailure(ControlledFetchError):
    def __init__(self, evidence: ControlledFetchTransportEvidence):
        require(type(evidence) is ControlledFetchTransportEvidence and type(evidence.error) is ControlledFetchErrorCode)
        self.evidence=evidence
        super().__init__(evidence.error)


@dataclass(frozen=True)
class ControlledFetchHop:
    """Private bounded transport response. No headers/cookies/credentials or engine handles."""
    status: int
    content_type: str
    body: bytes = field(repr=False)
    header_bytes: int
    location: str | None = field(default=None, repr=False)
    complete: bool = True
    request_header_bytes: int = 0
    content_encoding: str = 'identity'

    def __post_init__(self):
        require(type(self.status) is int and 100 <= self.status <= 599, ControlledFetchErrorCode.RESPONSE)
        require(type(self.body) is bytes and len(self.body) <= 2097152, ControlledFetchErrorCode.LIMIT)
        require(type(self.header_bytes) is int and 0 <= self.header_bytes <= 32768, ControlledFetchErrorCode.LIMIT)
        require(type(self.request_header_bytes) is int and 0 <= self.request_header_bytes <= 32768, ControlledFetchErrorCode.LIMIT)
        require(self.content_encoding == 'identity', ControlledFetchErrorCode.RESPONSE)
        require(type(self.content_type) is str and len(self.content_type) <= 256 and '\r' not in self.content_type and '\n' not in self.content_type)
        require(self.location is None or (type(self.location) is str and 0 < len(self.location) <= 512), ControlledFetchErrorCode.REDIRECT)
        require(type(self.complete) is bool)


class ControlledFetchTransportPort(Protocol):
    """Host-only seam. No DNS/redirect/retry/auth handling in a transport.

    validate() MUST have no dispatch effect. dispatch() sends exactly one GET or
    HEAD to the plan's numeric endpoint and counts headers/body under the SAME
    budget and the host-reserved transfer_byte_allowance (request/response headers
    plus response bytes); no concurrent/hop allocation can reset that allowance.
    Application records STARTED synchronously BEFORE entering dispatch.
    Real adapter/pinning/TLS/framing proof is deferred to B2. No model callbacks.
    """
    def validate(self, admitted: AdmittedControlledFetchRequest) -> None: ...
    def dispatch(self, admitted: AdmittedControlledFetchRequest, budget: FetchBudget) -> ControlledFetchHop: ...


def controlled_fetch_capabilities():
    """Descriptive only. Importing these contracts never probes/enables a capability."""
    return dict(capabilityId=CONTROLLED_FETCH_CAPABILITY_ID,
                available=Observation.unknown('V12-B2 transport certification not executed').to_dict(),
                networkEgressControl=Observation.unknown('V12-B1 contracts only').to_dict(),
                publicOnly=Observation.unknown('V12-B1 contracts only').to_dict(),
                initialMethods=['GET','HEAD'], POST=Observation.known(False).to_dict(),
                auth=Observation.known(False).to_dict(), binaryDownload=Observation.known(False).to_dict(),
                cookieJar=False, browserSessionImport=False)


class ControlledFetchSecretRef:
    """Opaque future host identity; no wire constructor/serializer or credential bytes."""
    __slots__ = ()
    def __repr__(self):
        return '<ControlledFetchSecretRef HOST_ONLY>'


class ControlledFetchNetworkProofRef:
    """Opaque operation-scoped admission reference; NOT an enforcement certificate."""
    __slots__ = ()
    def __repr__(self):
        return '<ControlledFetchNetworkProofRef HOST_ONLY>'


class ControlledFetchOutcomeLedger:
    """One operation, terminal once. No post-dispatch no-effect proof accepted in B1."""
    def __init__(self):
        self.state = ControlledFetchOutcome.NOT_STARTED
        self.entered_dispatch = False
        self.terminal = False

    def started(self):
        require(not self.terminal and self.state is ControlledFetchOutcome.NOT_STARTED, ControlledFetchErrorCode.OUTCOME)
        self.state = ControlledFetchOutcome.STARTED

    def dispatch(self):
        require(not self.terminal and self.state is ControlledFetchOutcome.STARTED, ControlledFetchErrorCode.OUTCOME)
        self.entered_dispatch = True  # Repeated hops are redirects, not retries; service validates lineage.

    def finish(self, outcome, *, no_effect_evidence=None):
        require(not self.terminal and type(outcome) is ControlledFetchOutcome, ControlledFetchErrorCode.OUTCOME)
        require(outcome is not ControlledFetchOutcome.STARTED, ControlledFetchErrorCode.OUTCOME)
        if outcome is ControlledFetchOutcome.NOT_STARTED:
            require(self.state is ControlledFetchOutcome.NOT_STARTED and not self.entered_dispatch, ControlledFetchErrorCode.OUTCOME)
        elif outcome is ControlledFetchOutcome.FAILED_NO_EFFECT_CONFIRMED:
            require(not self.entered_dispatch or (type(no_effect_evidence) is ControlledFetchTransportEvidence and
                    no_effect_evidence.request_bytes_sent==0), ControlledFetchErrorCode.OUTCOME)
        elif outcome in (ControlledFetchOutcome.SUCCEEDED_OBSERVED,ControlledFetchOutcome.PARTIAL,ControlledFetchOutcome.UNKNOWN):
            require(self.entered_dispatch, ControlledFetchErrorCode.OUTCOME)
        self.state, self.terminal = outcome, True


@dataclass(frozen=True)
class ControlledFetchFuturePost:
    """Prospective private binding only. No dispatcher supports this type in B1."""
    canonical_target: str = field(repr=False)
    body_digest: str = field(repr=False)
    content_type: str
    request_bytes: int
    secret_ref: ControlledFetchSecretRef | None = field(default=None, repr=False)

    def __post_init__(self):
        canonical_target(self.canonical_target)
        require(type(self.body_digest) is str and re.fullmatch('[a-f0-9]{64}', self.body_digest))
        require(type(self.request_bytes) is int and 0 <= self.request_bytes <= 262144)
        require(type(self.content_type) is str and re.fullmatch('[a-z0-9.+-]+/[a-z0-9.+-]+', self.content_type))
        require(self.secret_ref is None or type(self.secret_ref) is ControlledFetchSecretRef)


@dataclass(frozen=True)
class ControlledFetchFutureDownload:
    """Prospective bounded transfer contract; never a TEXT/HTML/JSON result."""
    max_bytes: int = 20971520
    timeout_seconds: int = 60
    per_turn_downloads: int = 2

    def __post_init__(self):
        for value, ceiling in ((self.max_bytes,20971520),(self.timeout_seconds,60),(self.per_turn_downloads,2)):
            require(type(value) is int and 1 <= value <= ceiling)
