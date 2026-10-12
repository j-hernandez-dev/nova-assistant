"""Single optional Active Web composition used by CLI and JSONL/Desktop.

No config flag, generic-tool fallback, installer or availability override.
Discovery remains closed if native exclusive egress has not been proven.
"""
from pathlib import Path
import tempfile

from local_cli.application.active_web import BrowserSessionManager
from local_cli.application.active_web_service import ActiveWebService, usable
from local_cli.application.browser_observation import BrowserObservationService
from local_cli.application.browser_projection import BrowserFrontendBinding, BrowserFrontendProjection
from local_cli.application.browser_takeover import BrowserTakeoverService
from local_cli.application.browser_transfers import BrowserTransferService
from local_cli.core.active_web_lifecycle import BrowserLimits
from local_cli.core.active_web_observation import ObservationLimits
from local_cli.core.active_web_transfers import BrowserTransferLimits
from local_cli.core.contracts import BrowserCapabilitySnapshot, Observation
from local_cli.infrastructure.active_web.download_staging import BrowserDownloadStaging
from local_cli.infrastructure.active_web.productive_backend import ProductiveBrowserBackend
from local_cli.infrastructure.knowledge_acquisition import LocalHostFileAcquisition


class ActiveWebFactory:
    productive = True

    def __init__(self, state_dir, *, backend=None):
        # Dependency injection is host composition, never frontend/model data.
        # A synthetic verified backend is useful only as a wiring contract.
        self.state_dir = Path(state_dir)
        self.backend = backend if backend is not None else ProductiveBrowserBackend()
        self.evidence = None

    def __call__(self, owner, redactor, publish):
        try:
            probe = self.backend.discover()
            cap, self.evidence = probe.capabilities, probe.evidence
        except Exception:
            cap = BrowserCapabilitySnapshot(available=Observation.known(False),
                control_class=Observation.known('HOST_UNISOLATED'))
            self.evidence = {'probeError': 'BROWSER_CAPABILITY_PROBE_FAILED'}
        # Only the complete measured branch may construct a productive engine.
        # Incomplete discovery still projects truthful capability to all UIs.
        try:
            port = self.backend.runtime() if usable(cap) else _UnavailablePort()
        except Exception:
            cap = BrowserCapabilitySnapshot(available=Observation.known(False),
                control_class=Observation.known('HOST_UNISOLATED'))
            self.evidence = {**(self.evidence or {}), 'runtimeError': 'BROWSER_RUNTIME_UNAVAILABLE'}
            port = _UnavailablePort()
        manager = BrowserSessionManager(port, limits=BrowserLimits(1800, 15, 30, 10))
        observations = BrowserObservationService(manager, port,
            limits=ObservationLimits(64, 12000, 256, 2048), redactor=redactor)
        staging = (BrowserDownloadStaging(Path(tempfile.gettempdir()).resolve(),
            max_bytes=8*1024*1024, max_downloads=8) if usable(cap) else _UnavailablePort())
        transfers = BrowserTransferService(manager, LocalHostFileAcquisition(max_bytes=8*1024*1024), staging,
            limits=BrowserTransferLimits(8*1024*1024, 8, 8), redactor=redactor)
        actions = ActiveWebService(owner, manager, observations, port, cap, transfers=transfers,
            takeovers=BrowserTakeoverService(manager, port))
        projection = BrowserFrontendProjection(publish=publish, redactor=redactor, capabilities=cap,
            owner_session_id=owner.agent_session_id)
        return BrowserFrontendBinding(manager, observations, actions, projection, tools=actions.tools)


class _UnavailablePort:
    def __getattr__(self, name):
        raise ValueError('BROWSER_CAPABILITY_UNAVAILABLE')


def active_web_factory(state_dir): return ActiveWebFactory(state_dir)
