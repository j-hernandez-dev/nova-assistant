"""Fresh host compatibility checks for the frozen V1.2 product candidate.

Profiles/probes are private composition inputs, with no model or JSONL decoder.
Installation alone is not evidence. Every capture verifies current byte identity
and live host primitives; no cached available=True survives revocation.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Callable

from local_cli.core.web_capabilities_v12 import (
    CF, IB, FETCH_EVIDENCE_PROFILE, BROWSER_RISK_ACKNOWLEDGEMENT_VERSION,
    WebCapabilitiesV12, ControlledFetchCapabilityV12, InteractiveBrowserCapabilityV12,
    WebUnavailableReason as R,
)


def _pairs(value):
    return (type(value) is tuple and all(type(x) is tuple and len(x) == 2 and
        all(type(y) is str and y and len(y) <= 4096 for y in x) for x in value) and
        len({x[0] for x in value}) == len(value))


@dataclass(frozen=True)
class FileIdentityProfile:
    """Host-pinned candidate sealed after its focal productive recertification.

Construction is a trusted deployment decision. There is deliberately no wire
constructor: an untrusted certified=true or a digest string cannot install one.
The pin set includes relevant sources, host binary and configuration artifacts.
"""
    capability_id: str
    evidence_profile: str
    pins: tuple[tuple[str, str], ...]
    runtime: tuple[tuple[str, str], ...]
    configuration_digest: str
    policy_revision_family: str
    schema_version: int = 1
    protocol_version: str = '1'
    required_components: tuple[str, ...] = ()

    def __post_init__(self):
        if self.capability_id not in (CF, IB) or not _pairs(self.pins) or not self.pins or not _pairs(self.runtime) or not self.runtime:
            raise ValueError('WEB_V12_INVALID_HOST_PROFILE')
        if any(not re.fullmatch('[0-9a-f]{64}', x[1]) for x in self.pins) or not re.fullmatch('[0-9a-f]{64}', self.configuration_digest):
            raise ValueError('WEB_V12_INVALID_HOST_PROFILE')
        if (type(self.schema_version) is not int or self.schema_version != 1 or
                type(self.protocol_version) is not str or not self.protocol_version or
                type(self.policy_revision_family) is not str or not self.policy_revision_family or
                type(self.required_components) is not tuple or not self.required_components or
                any(type(x) is not str or not x or len(x) > 128 for x in self.required_components)):
            raise ValueError('WEB_V12_INVALID_HOST_PROFILE')
        if (self.capability_id == CF and self.evidence_profile != FETCH_EVIDENCE_PROFILE or
                self.capability_id == IB and (type(self.evidence_profile) is not str or
                    not self.evidence_profile.startswith('IB_B6_') or len(self.evidence_profile) > 128)):
            raise ValueError('WEB_V12_INVALID_HOST_PROFILE')


@dataclass(frozen=True)
class HostProbeResult:
    """Observed by installed host code; never accepted from product messages.

The probe must inspect the actual configured transport/host/guard and composition
objects. These runtime identities are compared with the sealed candidate, not
treated as approval or as an independent certification declaration.
"""
    runtime: tuple[tuple[str, str], ...]
    configuration_digest: str
    policy_revision_family: str
    schema_version: int
    protocol_version: str
    components: tuple[str, ...]
    failure_reason: R | None = None

    def __post_init__(self):
        if not _pairs(self.runtime) or type(self.components) is not tuple or any(type(x) is not str for x in self.components):
            raise ValueError('WEB_V12_INVALID_HOST_PROBE')
        if self.failure_reason is not None and type(self.failure_reason) is not R:
            raise ValueError('WEB_V12_INVALID_HOST_PROBE')


@dataclass(frozen=True)
class WebV12FeatureConfiguration:
    """Host configuration, changed only after authenticated product interaction.

Risk acknowledgement enables a feature; it is not an operation Approval/Grant.
Do not instantiate this type using model/JSONL/renderer-supplied authority flags.
"""
    controlled_fetch_enabled: bool = False
    interactive_browser_enabled: bool = False
    risk_acknowledgement_version: str | None = None

    def __post_init__(self):
        if type(self.controlled_fetch_enabled) is not bool or type(self.interactive_browser_enabled) is not bool:
            raise ValueError('WEB_V12_INVALID_HOST_CONFIGURATION')
        if self.risk_acknowledgement_version not in (None, BROWSER_RISK_ACKNOWLEDGEMENT_VERSION):
            raise ValueError('WEB_V12_INVALID_RISK_ACKNOWLEDGEMENT')


class HostProbeIndeterminate(RuntimeError):
    """Only for a genuinely indeterminate host observation, not a known failure."""


class WebV12Discovery:
    def __init__(self, repo_root, *, fetch_profile=None, browser_profile=None,
                 fetch_probe=None, browser_probe=None, configuration=None):
        self.repo_root = Path(repo_root).resolve()
        for profile, capability in ((fetch_profile, CF), (browser_profile, IB)):
            if profile is not None and (type(profile) is not FileIdentityProfile or profile.capability_id != capability):
                raise ValueError('WEB_V12_WRONG_HOST_PROFILE')
        self.fetch_profile, self.browser_profile = fetch_profile, browser_profile
        self.fetch_probe, self.browser_probe = fetch_probe, browser_probe
        self.configuration = configuration or (lambda: WebV12FeatureConfiguration())
        self.last_compatibility = {}

    def _identity(self, profile):
        for raw, expected in profile.pins:
            candidate = Path(raw)
            if not candidate.is_absolute():
                if '..' in candidate.parts:
                    return R.SOURCE_IDENTITY_MISMATCH
                candidate = self.repo_root / candidate
            try:
                # Follow no symlink/reparse alias into a different composition.
                if candidate.is_symlink() or any(p.is_symlink() for p in candidate.parents):
                    return R.SOURCE_IDENTITY_MISMATCH
                stat = candidate.stat()
                if getattr(stat, 'st_file_attributes', 0) & 0x400:
                    return R.SOURCE_IDENTITY_MISMATCH
                if not candidate.is_file() or hashlib.sha256(candidate.read_bytes()).hexdigest() != expected:
                    return R.SOURCE_IDENTITY_MISMATCH
            except (OSError, ValueError):
                return R.SOURCE_IDENTITY_MISMATCH
        return None

    def _check(self, profile, probe):
        if profile is None:
            return R.EVIDENCE_NOT_CONFIGURED
        if probe is None:
            return R.TRANSPORT_NOT_CONFIGURED if profile.capability_id == CF else R.BROWSER_HOST_UNAVAILABLE
        failure = self._identity(profile)
        if failure:
            return failure
        try:
            report = probe()
        except HostProbeIndeterminate:
            return R.HOST_PROBE_INDETERMINATE
        except Exception:
            return R.HOST_PROBE_FAILED
        if type(report) is not HostProbeResult:
            return R.HOST_PROBE_FAILED
        if report.failure_reason:
            return report.failure_reason
        if dict(report.runtime) != dict(profile.runtime):
            return R.RUNTIME_INCOMPATIBLE
        if report.configuration_digest != profile.configuration_digest:
            return R.CONFIGURATION_MISMATCH
        if report.policy_revision_family != profile.policy_revision_family:
            return R.POLICY_INCOMPATIBLE
        if type(report.schema_version) is not int or report.schema_version != profile.schema_version:
            return R.SCHEMA_INCOMPATIBLE
        if report.protocol_version != profile.protocol_version:
            return R.PROTOCOL_INCOMPATIBLE
        if not set(profile.required_components).issubset(report.components):
            return R.COMPOSITION_INCOMPLETE
        return None

    def capture(self):
        try:
            config = self.configuration()
            if type(config) is not WebV12FeatureConfiguration:
                raise ValueError('WEB_V12_INVALID_HOST_CONFIGURATION')
        except Exception:
            return WebCapabilitiesV12.unavailable(R.CONFIGURATION_MISMATCH)
        # Disabled browser is never started or probed as a side effect of capture.
        cf_reason = self._check(self.fetch_profile, self.fetch_probe) if config.controlled_fetch_enabled else R.FEATURE_DISABLED
        ib_reason = (R.FEATURE_DISABLED if not config.interactive_browser_enabled else
            R.RISK_ACKNOWLEDGEMENT_REQUIRED if config.risk_acknowledgement_version != BROWSER_RISK_ACKNOWLEDGEMENT_VERSION else
            self._check(self.browser_profile, self.browser_probe))
        self.last_compatibility = {CF: cf_reason.value if cf_reason else 'COMPATIBLE',
                                   IB: ib_reason.value if ib_reason else 'COMPATIBLE'}
        return WebCapabilitiesV12(
            ControlledFetchCapabilityV12.state(cf_reason, compatible=cf_reason is None,
                indeterminate=cf_reason is R.HOST_PROBE_INDETERMINATE),
            InteractiveBrowserCapabilityV12.state(ib_reason, compatible=ib_reason is None,
                profile=self.browser_profile.evidence_profile if self.browser_profile else None,
                indeterminate=ib_reason is R.HOST_PROBE_INDETERMINATE))

    snapshot = capture
