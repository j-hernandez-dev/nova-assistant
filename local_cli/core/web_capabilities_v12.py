"""Prospective V1.2 metadata, separate from the PUBLIC_ONLY browser V1 DTO.

Parsing a snapshot is never discovery and never issues operational authority.
All wire fields are closed; refs, credentials and reusable authority have no slot.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from local_cli.core.contracts import Observation

CF = 'CONTROLLED_FETCH_V1_2'
IB = 'INTERACTIVE_BROWSER_V1_2'
SCHEMA = 'WEB_CAPABILITIES_V12_1'
FETCH_EVIDENCE_PROFILE = 'CF_B2_GET_HEAD_HTTP11_WINDOWS_V1'
BROWSER_RISK_ACKNOWLEDGEMENT_VERSION = 'IB_V12_RISK_1'


class WebUnavailableReason(str, Enum):
    FEATURE_DISABLED = 'FEATURE_DISABLED'
    RISK_ACKNOWLEDGEMENT_REQUIRED = 'RISK_ACKNOWLEDGEMENT_REQUIRED'
    EVIDENCE_NOT_CONFIGURED = 'EVIDENCE_NOT_CONFIGURED'
    EVIDENCE_PROFILE_MISMATCH = 'EVIDENCE_PROFILE_MISMATCH'
    SOURCE_IDENTITY_MISMATCH = 'SOURCE_IDENTITY_MISMATCH'
    CONFIGURATION_MISMATCH = 'CONFIGURATION_MISMATCH'
    RUNTIME_INCOMPATIBLE = 'RUNTIME_INCOMPATIBLE'
    POLICY_INCOMPATIBLE = 'POLICY_INCOMPATIBLE'
    SCHEMA_INCOMPATIBLE = 'SCHEMA_INCOMPATIBLE'
    PROTOCOL_INCOMPATIBLE = 'PROTOCOL_INCOMPATIBLE'
    COMPOSITION_INCOMPLETE = 'COMPOSITION_INCOMPLETE'
    TRANSPORT_NOT_CONFIGURED = 'TRANSPORT_NOT_CONFIGURED'
    BROWSER_HOST_UNAVAILABLE = 'BROWSER_HOST_UNAVAILABLE'
    EXTERNAL_PROTOCOL_GUARD_UNAVAILABLE = 'EXTERNAL_PROTOCOL_GUARD_UNAVAILABLE'
    HOST_PROBE_FAILED = 'HOST_PROBE_FAILED'
    HOST_PROBE_INDETERMINATE = 'HOST_PROBE_INDETERMINATE'


def known(value):
    # Delayed import keeps RuntimeCapabilitySnapshot free to own this DTO.
    from local_cli.core.contracts import Observation
    return Observation.known(value)


def unknown(reason):
    from local_cli.core.contracts import Observation
    return Observation.unknown(reason)


def _observation(value, expected=None, *, boolean=False):
    from local_cli.core.contracts import Observation, CapabilityStatus
    if type(value) is not Observation:
        raise ValueError('WEB_V12_INVALID_OBSERVATION')
    if value.status is CapabilityStatus.KNOWN:
        if boolean and type(value.value) is not bool:
            raise ValueError('WEB_V12_INVALID_OBSERVATION')
        if expected is not None and value.value != expected:
            raise ValueError('WEB_V12_INVALID_CLAIM')
    elif len(value.reason) > 128:
        raise ValueError('WEB_V12_INVALID_REASON')


def _available(available, reason):
    _observation(available, boolean=True)
    if reason is not None and type(reason) is not WebUnavailableReason:
        raise ValueError('WEB_V12_INVALID_UNAVAILABLE_REASON')
    if available.value is True and reason is not None:
        raise ValueError('WEB_V12_AVAILABLE_WITH_FAILURE')
    if available.value is False and reason is None:
        raise ValueError('WEB_V12_MISSING_UNAVAILABLE_REASON')


def _parse_observation(data):
    from local_cli.core.contracts import Observation
    if type(data) is not dict or set(data) != {'status', 'value', 'reason'}:
        raise ValueError('WEB_V12_INVALID_OBSERVATION')
    return Observation.from_dict(data)


def _reason(data):
    return None if data is None else WebUnavailableReason(data)


def _same_wire(actual, expected):
    """Boolean JSON flags do not accept integer lookalikes (0/1)."""
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(_same_wire(actual[k], expected[k]) for k in expected)
    if type(expected) is list:
        return len(actual) == len(expected) and all(_same_wire(a, b) for a, b in zip(actual, expected))
    return actual == expected


@dataclass(frozen=True)
class ControlledFetchCapabilityV12:
    available: Observation
    unavailable_reason: WebUnavailableReason | None
    evidence_profile: Observation
    network_egress_control: Observation
    public_only: Observation
    control_class: Observation

    def __post_init__(self):
        _available(self.available, self.unavailable_reason)
        _observation(self.evidence_profile, FETCH_EVIDENCE_PROFILE)
        _observation(self.network_egress_control, 'ENFORCED')
        _observation(self.public_only, 'ENFORCED')
        _observation(self.control_class, 'BROKER_ENFORCED')
        if self.available.value is True and any(x.value is None for x in (
                self.evidence_profile, self.network_egress_control,
                self.public_only, self.control_class)):
            raise ValueError('WEB_V12_AVAILABLE_WITHOUT_COMPATIBLE_EVIDENCE')

    @classmethod
    def state(cls, reason=None, *, compatible=False, indeterminate=False):
        return cls(unknown('HOST_PROBE_INDETERMINATE') if indeterminate else known(reason is None),
            reason, known(FETCH_EVIDENCE_PROFILE) if compatible else unknown('COMPATIBLE_EVIDENCE_REQUIRED'),
            known('ENFORCED') if compatible else unknown('COMPATIBLE_EVIDENCE_REQUIRED'),
            known('ENFORCED') if compatible else unknown('COMPATIBLE_EVIDENCE_REQUIRED'),
            known('BROKER_ENFORCED') if compatible else unknown('COMPATIBLE_EVIDENCE_REQUIRED'))

    def to_dict(self):
        return dict(capabilityId=CF, available=self.available.to_dict(),
            unavailableReason=self.unavailable_reason.value if self.unavailable_reason else None,
            evidenceProfile=self.evidence_profile.to_dict(),
            networkEgressControl=self.network_egress_control.to_dict(),
            publicOnly=self.public_only.to_dict(), controlClass=self.control_class.to_dict(),
            methods=['GET', 'HEAD'], resultModes=['TEXT', 'HTML_STATIC', 'JSON'],
            postAvailable=False, authAvailable=False, binaryDownloadAvailable=False,
            cookieJar=False, browserSessionImport=False)

    @classmethod
    def from_dict(cls, data):
        if type(data) is not dict:
            raise ValueError('WEB_V12_INVALID_FETCH_SNAPSHOT')
        result = cls(_parse_observation(data.get('available')), _reason(data.get('unavailableReason')),
            *(_parse_observation(data.get(k)) for k in (
                'evidenceProfile', 'networkEgressControl', 'publicOnly', 'controlClass')))
        if not _same_wire(data, result.to_dict()):
            raise ValueError('WEB_V12_INVALID_FETCH_SNAPSHOT')
        return result


@dataclass(frozen=True)
class InteractiveBrowserCapabilityV12:
    available: Observation
    unavailable_reason: WebUnavailableReason | None
    evidence_profile: Observation
    external_protocol_guard: Observation
    remote_mutation_control: Observation
    secret_boundary: Observation

    def __post_init__(self):
        _available(self.available, self.unavailable_reason)
        _observation(self.evidence_profile)
        if self.evidence_profile.value is not None and (type(self.evidence_profile.value) is not str or
                not self.evidence_profile.value.startswith('IB_B6_') or len(self.evidence_profile.value) > 128):
            raise ValueError('WEB_V12_INVALID_BROWSER_PROFILE')
        for value in (self.external_protocol_guard, self.remote_mutation_control, self.secret_boundary):
            _observation(value, 'ENFORCED')
        if self.available.value is True and any(x.value is None for x in (
                self.evidence_profile, self.external_protocol_guard,
                self.remote_mutation_control, self.secret_boundary)):
            raise ValueError('WEB_V12_AVAILABLE_WITHOUT_COMPATIBLE_EVIDENCE')

    @classmethod
    def state(cls, reason=None, *, compatible=False, profile=None, indeterminate=False):
        return cls(unknown('HOST_PROBE_INDETERMINATE') if indeterminate else known(reason is None),
            reason, known(profile) if compatible else unknown('COMPATIBLE_EVIDENCE_REQUIRED'),
            known('ENFORCED') if compatible else unknown('COMPATIBLE_EVIDENCE_REQUIRED'),
            known('ENFORCED') if compatible else unknown('COMPATIBLE_EVIDENCE_REQUIRED'),
            known('ENFORCED') if compatible else unknown('COMPATIBLE_EVIDENCE_REQUIRED'))

    def to_dict(self):
        return dict(capabilityId=IB, available=self.available.to_dict(),
            unavailableReason=self.unavailable_reason.value if self.unavailable_reason else None,
            evidenceProfile=self.evidence_profile.to_dict(),
            networkIsolation=known('NOT_PROVIDED').to_dict(),
            controlClass=known('HOST_UNISOLATED').to_dict(), adapter=known('WEBVIEW2').to_dict(),
            externalProtocolGuard=self.external_protocol_guard.to_dict(),
            remoteMutationControl=self.remote_mutation_control.to_dict(),
            secretBoundary=self.secret_boundary.to_dict(), formSubmitAvailable=False,
            subagentsBrowserByDefault=False, persistentSession=False, screenshot=False)

    @classmethod
    def from_dict(cls, data):
        if type(data) is not dict:
            raise ValueError('WEB_V12_INVALID_BROWSER_SNAPSHOT')
        result = cls(_parse_observation(data.get('available')), _reason(data.get('unavailableReason')),
            *(_parse_observation(data.get(k)) for k in (
                'evidenceProfile', 'externalProtocolGuard', 'remoteMutationControl', 'secretBoundary')))
        if not _same_wire(data, result.to_dict()):
            raise ValueError('WEB_V12_INVALID_BROWSER_SNAPSHOT')
        return result


@dataclass(frozen=True)
class WebCapabilitiesV12:
    controlled_fetch: ControlledFetchCapabilityV12
    interactive_browser: InteractiveBrowserCapabilityV12

    def __post_init__(self):
        if type(self.controlled_fetch) is not ControlledFetchCapabilityV12 or type(self.interactive_browser) is not InteractiveBrowserCapabilityV12:
            raise ValueError('WEB_V12_INVALID_SNAPSHOT')

    @classmethod
    def unavailable(cls, reason=WebUnavailableReason.FEATURE_DISABLED):
        return cls(ControlledFetchCapabilityV12.state(reason), InteractiveBrowserCapabilityV12.state(reason))

    def to_dict(self):
        return dict(schemaVersion=1, schema=SCHEMA, controlledFetch=self.controlled_fetch.to_dict(),
                    interactiveBrowser=self.interactive_browser.to_dict())

    @classmethod
    def from_dict(cls, data):
        if type(data) is not dict or set(data) != {'schemaVersion', 'schema', 'controlledFetch', 'interactiveBrowser'} or type(data['schemaVersion']) is not int or data['schemaVersion'] != 1 or data['schema'] != SCHEMA:
            raise ValueError('WEB_V12_INVALID_SNAPSHOT')
        return cls(ControlledFetchCapabilityV12.from_dict(data['controlledFetch']),
                   InteractiveBrowserCapabilityV12.from_dict(data['interactiveBrowser']))
