"""B6 productive smoke: real Application -> ToolRuntime -> B2 TCP/TLS candidate.

Owned synthetic DNS resolves to an already assigned PUBLIC IPv6. No admission,
DNS answer, socket, TLS/framing or transport double is used by positive cases.
The test CA is exact/process-scoped; production trust defaults stay unchanged.
This is a focal product smoke, not a repeat of the B2 certification campaign.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import ssl
import time

import pytest

from local_cli.application.cancellation import CancellationController
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.session import AgentSessionCoordinator
from local_cli.bootstrap_web_v12 import (
    WebV12Factory, CF_COMPONENTS, FETCH_CONFIG, POLICY_FAMILY, config_digest, fetch_runtime,
)
from local_cli.core.contracts import (
    ExecutionContext, ToolInvocation, ToolStatus, EffectState,
    new_command_id, new_operation_id, new_tool_call_id,
)
from local_cli.core.network import NetworkEndpoint
from local_cli.core.security import Capability, Permission, ResourceScope, ScopeKind, ControlClass, SecurityError
from local_cli.core.controlled_fetch import ControlledFetchError
from local_cli.core.web_capabilities_v12 import CF, IB, FETCH_EVIDENCE_PROFILE, BROWSER_RISK_ACKNOWLEDGEMENT_VERSION
from local_cli.infrastructure.controlled_fetch_dns import ProcessScopedDNSResolver
from local_cli.infrastructure.controlled_fetch_transport import RealControlledFetchTransport
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from local_cli.infrastructure.web_discovery_v12 import FileIdentityProfile
from tests.controlled_fetch_v12_b2.native_harness import Environment
from tests.test_nova_core_phase4_session import ScriptedProvider

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(os.environ['NOVA_B5_TEST_OUTPUT']).resolve()
PROFILE_SOURCE_PATHS = (
    'local_cli/core/controlled_fetch.py', 'local_cli/application/controlled_fetch.py',
    'local_cli/infrastructure/controlled_fetch_transport.py',
    'local_cli/infrastructure/controlled_fetch_dns.py', 'local_cli/application/browser_network.py',
    'local_cli/application/network.py', 'local_cli/infrastructure/http_fetch.py',
    'local_cli/core/network.py', 'local_cli/core/security.py', 'local_cli/core/contracts.py',
    'local_cli/application/policy.py', 'local_cli/application/grants.py',
    'local_cli/application/tool_runtime.py', 'local_cli/application/web_product_v12.py',
    'local_cli/bootstrap_web_v12.py', 'local_cli/infrastructure/web_discovery_v12.py',
    'local_cli/core/web_capabilities_v12.py', 'local_cli/application/web_routing_v12.py',
)


def output(name, value):
    assert OUTPUT.is_absolute() and not OUTPUT.is_relative_to(ROOT)
    folder = OUTPUT / 'productive_fetch'
    folder.mkdir(parents=True, exist_ok=True)
    # pytest parameter IDs can contain URL colons/slashes; retain uniqueness while
    # producing bounded legal Windows leaf names inside the owned output root.
    leaf = re.sub(r'[^A-Za-z0-9_.-]', '_', name)[:80] + '-' + hashlib.sha256(name.encode()).hexdigest()[:16]
    if type(value) is dict:
        value = {'caseName': name, **value}
    (folder / (leaf + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2,
        default=str) + '\n', encoding='utf-8')


def framed(body, *, mime='text/plain', status='200 OK'):
    return (f'HTTP/1.1 {status}\r\nContent-Type: {mime}\r\nContent-Length: {len(body)}\r\n'
            'Connection: close\r\n\r\n').encode('ascii') + body


@pytest.fixture(scope='module')
def native_fetch_environment():
    address = os.environ.get('NOVA_CF_B6_PUBLIC_IPV6') or os.environ.get('NOVA_CF_B2_PUBLIC_IPV6')
    openssl = os.environ.get('NOVA_CF_B6_OPENSSL') or os.environ.get('NOVA_CF_B2_OPENSSL')
    assert address and openssl, 'B6 productive evidence requires explicit owned public IPv6 and OpenSSL fixture'
    environment = Environment(address, openssl)
    # Native canary/observer calibration is scoped to this capability's connects.
    before = len(environment.private.connections)
    attempts = len(environment.socket_attempts)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as stream:
        stream.settimeout(2)
        assert stream.connect_ex(('127.0.0.1', 80)) == 0
        stream.sendall(b'GET /b6-calibration HTTP/1.1\r\nHost: fixture\r\nConnection: close\r\n\r\n')
        stream.recv(4096)
    time.sleep(.02)
    assert len(environment.private.connections) - before == 1
    assert len(environment.socket_attempts) - attempts == 1
    output('native_fixture', dict(source='PRODUCTIVE_FETCH_COMPOSITION',
        topology='OWNED_REAL_ASSIGNED_GLOBAL_IPV6_SYNTHETIC_DNS_TEST_ONLY',
        publicIPv6=environment.address, nativePrivateCanaryCalibrationHits=1,
        tlsTrust='EXACT_FIXTURE_PROCESS_SCOPED_ONLY', fixtureCertificateSha256=environment.cert_sha256,
        globalCAStoreModified=False, productionPublicOnlyExceptions=False))
    try:
        yield environment
    finally:
        environment.close()
        output('native_fixture_cleanup', dict(listenersClosed=True, socketObserverRestored=True,
            ownedTLSFilesRemoved=not environment.work.exists(), globalCAStoreModified=False))


class ProductiveFetch:
    def __init__(self, environment, root):
        self.environment, self.root = environment, root
        self.workspace = (root / 'workspace').resolve()
        self.workspace.mkdir(parents=True)
        historical_transport = json.loads((ROOT / 'docs/active_web_v1_2/v12_b2_controlled_fetch_public_only/transport_identity.json').read_text(encoding='utf-8'))
        original_pins = {pin['path']: pin['sha256'] for pin in historical_transport['dependencyPins']}
        preserved_transport = ('local_cli/infrastructure/controlled_fetch_transport.py',
            'local_cli/infrastructure/controlled_fetch_dns.py', 'local_cli/application/browser_network.py',
            'local_cli/application/network.py', 'local_cli/infrastructure/http_fetch.py')
        for source in preserved_transport:
            assert hashlib.sha256((ROOT / source).read_bytes()).hexdigest() == original_pins[source], (
                'B6 smoke must use the exact preserved B2 transport/S5 primitives: ' + source)
        pins = tuple((path, hashlib.sha256((ROOT / path).read_bytes()).hexdigest()) for path in PROFILE_SOURCE_PATHS)
        self.profile = FileIdentityProfile(CF, FETCH_EVIDENCE_PROFILE, pins, fetch_runtime(),
            config_digest(FETCH_CONFIG), POLICY_FAMILY, 1, 'HTTP11_GET_HEAD_1', CF_COMPONENTS)
        self.dns, self.transport, self.rows = [], [], []
        resolver = ProcessScopedDNSResolver(NetworkEndpoint('127.0.0.1', socket.AF_INET, environment.dns.port),
            observe=self.dns.append)
        # The only trust adjustment is this exact fixture context injected by harness.
        tls = ssl.create_default_context(cafile=str(environment.cert))
        assert tls.verify_mode == ssl.CERT_REQUIRED and tls.check_hostname
        self.factory = WebV12Factory(root / 'state', repo_root=ROOT, fetch_profile=self.profile,
            resolver=resolver, tls_context=tls, transport_observer=self.transport.append)
        self.store = JsonlSecurityAudit(root / 'audit', workspace=self.workspace)
        self.provider = ScriptedProvider(['task accepted'])
        self.app = AgentSessionCoordinator(provider=self.provider, model='synthetic',
            tool_factory=lambda _: [], web_v12_factory=self.factory, security_audit_port=self.store,
            auto_approve=True)
        receipt = self.app.handle(ApplicationCommand(new_command_id(), CommandKind.START_SESSION,
            {'workspace': str(self.workspace)}))
        assert receipt.accepted
        self.session = receipt.session_id
        self.service = self.app._web_v12
        self.runtime = self.app._session.tool_runtime
        assert self.service is self.runtime._web_v12
        before = self.app.get_snapshot(self.session).to_dict()['services']['webCapabilitiesV12']
        assert before['controlledFetch']['available']['value'] is False
        actor = self.app.register_browser_actor('desktop_host', lambda: True)
        configured = self.app.execute_browser_control(dict(commandId=new_command_id(), sessionId=self.session,
            name='configure_web_v12', arguments=dict(controlledFetchEnabled=True,
                interactiveBrowserEnabled=False, acknowledgementVersion=BROWSER_RISK_ACKNOWLEDGEMENT_VERSION)),
            actor=actor)
        assert configured['capabilities']['controlledFetch']['available']['value'] is True
        assert configured['capabilities']['interactiveBrowser']['available']['value'] is False
        assert self.service.browser is None
        self.last_invocation, self.last_result = None, None

    def bind(self, target, *, human_text=None):
        receipt = self.app.handle(ApplicationCommand(new_command_id(), CommandKind.SUBMIT_USER_INPUT,
            {'content': human_text or 'Lee ' + target + ' mediante recuperación HTTP controlada.'},
            session_id=self.session))
        assert receipt.accepted and self.app.wait_for_turn(receipt.created_ids['turnId'], 5)
        return receipt.created_ids['turnId']

    def invocation(self, target, *, turn=None, method='GET', result_mode='TEXT', interaction=False, reason='',
                   agent_id=None, additional_arguments=None):
        turn = turn or self.bind(target)
        operation = new_operation_id()
        context = ExecutionContext(self.workspace, self.workspace, {}, self.session, operation,
            CancellationController(), datetime.now(timezone.utc)+timedelta(seconds=15),
            self.app._session.capabilities, turn, agent_id=agent_id, policy_revision=self.runtime.policy.revision)
        args = dict(url=target, method=method, resultMode=result_mode, requiresInteraction=interaction, reason=reason)
        if additional_arguments:
            args.update(additional_arguments)
        return ToolInvocation('web_access', args, new_tool_call_id(), operation, context)

    def execute(self, target, **options):
        environment = self.environment
        inv = self.invocation(target, **options)
        before_transport, before_dns = len(self.transport), len(self.dns)
        before_http, before_https = len(environment.http.events), len(environment.https.events)
        before_private, before_sockets = len(environment.private.connections), len(environment.socket_attempts)
        result = self.runtime.execute(inv)
        time.sleep(.02)
        self.last_invocation, self.last_result = inv, result
        parsed = json.loads(result.stdout) if result.stdout.startswith('{') else None
        row = dict(source='PRODUCTIVE_FETCH_COMPOSITION', operationId=inv.operation_id,
            productivePath=['AgentSessionCoordinator', 'WebV12Factory', 'ToolRuntime', 'WebProductV12',
                'PolicyEngineV2', 'GrantIssuer', 'ControlledFetchService', 'RealControlledFetchTransport'],
            status=result.status.value, effectState=result.effect_state.value, error=result.error,
            outcome=parsed.get('outcome') if parsed else None,
            resultMode=options.get('result_mode', 'TEXT'), method=options.get('method', 'GET'),
            payloadSha256=hashlib.sha256((parsed.get('payload') or '').encode()).hexdigest() if parsed else None,
            countedBytes=parsed.get('countedBytes') if parsed else None,
            transport=self.transport[before_transport:], dns=self.dns[before_dns:],
            serverEvents=environment.http.events[before_http:]+environment.https.events[before_https:],
            forbiddenPrivateCanaryHits=len(environment.private.connections)-before_private,
            nativeTCPConnectAttempts=environment.socket_attempts[before_sockets:],
            browserCreated=self.service.browser is not None,
            capabilitySnapshot=self.app.get_snapshot(self.session).to_dict()['services']['webCapabilitiesV12'],
            limitsProfile=FETCH_CONFIG, exactFixtureProcessOnlyTrust=True,
            authorityValuesPubliclySerialized=False)
        self.rows.append(row)
        return result, parsed, row

    def close(self):
        self.store.flush()
        receipts = []
        for path in (self.root / 'state' / 'web_v12').glob('*.receipts.jsonl'):
            for line in path.read_text(encoding='utf-8').splitlines():
                value = json.loads(line)
                receipts.append(dict(operationId=value['operationId'], outcome=value['outcome'],
                    countedBytes=value.get('countedBytes'), consumed=value.get('consumed')))
        self.app.close_browser()
        self.store.close()
        return receipts


@pytest.fixture
def productive_fetch(native_fetch_environment, tmp_path, request):
    product = ProductiveFetch(native_fetch_environment, tmp_path)
    try:
        yield product
    finally:
        receipts = product.close()
        output(request.node.name, dict(source='PRODUCTIVE_FETCH_COMPOSITION',
            cases=product.rows, receipts=receipts, browserWasNeverCreated=product.service.browser is None,
            sourcePins=list(product.profile.pins)))


@pytest.mark.parametrize('tls,method', [(False, 'GET'), (False, 'HEAD'), (True, 'GET'), (True, 'HEAD')])
def test_exact_productive_http_https_get_head_chain(productive_fetch, tls, method):
    product = productive_fetch
    target = ('https' if tls else 'http') + '://cf-public.test/b6-positive'
    result, body, row = product.execute(target, method=method)
    assert result.status is ToolStatus.COMPLETED and body['outcome'] == 'SUCCEEDED_OBSERVED'
    assert body['capabilityId'] == CF and body['method'] == method
    assert len(row['serverEvents']) == len(row['transport']) == len(row['nativeTCPConnectAttempts']) == 1
    transport = row['transport'][0]
    assert transport['admittedEndpoint'] == transport['connectedEndpoint'] == [product.environment.address, 443 if tls else 80]
    assert transport['httpRequestBytesSent'] > 0 and transport['dnsAnswers']
    event = row['serverEvents'][0]
    assert event['method'] == method and event['version'] == 'HTTP/1.1' and event['host'] == 'cf-public.test'
    assert event['acceptEncoding'] == 'identity' and event['connection'] == 'close'
    assert not event['forbiddenHeadersPresent'] and row['forbiddenPrivateCanaryHits'] == 0
    assert row['browserCreated'] is False
    assert type(product.service._plans[product.last_invocation.operation_id]['service'].transport) is RealControlledFetchTransport
    snapshot = row['capabilitySnapshot']
    assert snapshot['controlledFetch']['evidenceProfile']['value'] == FETCH_EVIDENCE_PROFILE
    assert snapshot['controlledFetch']['publicOnly']['value'] == 'ENFORCED'
    assert snapshot['interactiveBrowser']['networkIsolation']['value'] == 'NOT_PROVIDED'
    if method == 'HEAD':
        assert body['payload'] is None and body['countedBytes'] == 0 and body['absence'] == 'HEAD_NO_BODY'
    if tls:
        assert product.environment.https.snis[-1] == 'cf-public.test'


@pytest.mark.parametrize('mode', ['JSON', 'HTML_STATIC'])
def test_productive_static_modes_never_load_discovered_resources(productive_fetch, mode):
    product = productive_fetch
    path = '/b6-static-' + mode
    content = (b'{"data":"bounded-json","link":"http://127.0.0.1/never-requested"}' if mode == 'JSON' else
        b'<html><body>bounded-html<img src="http://127.0.0.1/never-requested"><iframe src="http://127.0.0.1/frame"></iframe>'
        b'<script>window.fetch("http://127.0.0.1/script")</script><meta http-equiv="refresh" content="0;url=http://127.0.0.1/meta"></body></html>')
    product.environment.http.routes[path] = framed(content, mime='application/json' if mode == 'JSON' else 'text/html')
    result, body, row = product.execute('http://cf-public.test' + path, result_mode=mode)
    assert result.status is ToolStatus.COMPLETED and body['resultMode'] == mode
    assert len(row['serverEvents']) == len(row['nativeTCPConnectAttempts']) == 1
    assert row['forbiddenPrivateCanaryHits'] == 0 and not row['browserCreated']
    if mode == 'JSON':
        assert json.loads(body['payload'])['data'] == 'bounded-json'
    else:
        assert 'bounded-html' in body['payload'] and 'window.fetch' not in body['payload']


@pytest.mark.parametrize('target,behavior', [('http://127.0.0.1/b6-private', None),
    ('http://cf-private.test/b6-private', 'private'), ('http://cf-mixed.test/b6-mixed', 'mixed')])
def test_productive_public_only_denial_never_opens_forbidden_socket_or_browser(productive_fetch, target, behavior):
    product = productive_fetch
    if behavior:
        product.environment.dns.behavior[target.split('/')[2]] = behavior
    result, body, row = product.execute(target)
    assert result.status is ToolStatus.DENIED and result.effect_state is EffectState.NONE
    assert body['outcome'] == 'NOT_STARTED' and body['error'] == 'CONTROLLED_FETCH_ADMISSION_DENIED'
    assert not row['nativeTCPConnectAttempts'] and not row['serverEvents'] and not row['transport']
    assert row['forbiddenPrivateCanaryHits'] == 0 and not row['browserCreated']
    assert product.service.router.ledger.blocks(product.service.task_id, target)
    # Even an independently explicit browser task cannot turn this same objective
    # denial into automatic browser authority within the bounded task lineage.
    turn = product.bind(target, human_text='Usa el navegador para interactuar con ' + target)
    denied, _, later = product.execute(target, turn=turn, interaction=True, reason='EXPLICIT_BROWSER_REQUEST')
    assert denied.status is ToolStatus.DENIED
    assert not later['nativeTCPConnectAttempts'] and not later['browserCreated']
    assert 'CONTROLLED_FETCH_DENIAL_NO_BROWSER_BYPASS' in (denied.error or denied.stdout)


@pytest.mark.parametrize('status', ['401 Unauthorized', '403 Forbidden'])
def test_productive_http_errors_never_retry_or_automatically_escalate(productive_fetch, status):
    product = productive_fetch
    path = '/b6-status-' + status[:3]
    product.environment.http.routes[path] = framed(b'not available', status=status)
    target = 'http://cf-public.test' + path
    result, body, row = product.execute(target)
    assert result.status is not ToolStatus.COMPLETED and body['outcome'] == 'UNKNOWN'
    assert len(row['nativeTCPConnectAttempts']) == len(row['serverEvents']) == 1
    assert not row['browserCreated']
    denied, _, later = product.execute(target, interaction=True, reason='HTTP_' + status[:3])
    assert denied.status is ToolStatus.DENIED and not later['nativeTCPConnectAttempts']
    assert not later['browserCreated']


def test_productive_ambient_proxy_environment_is_not_used(productive_fetch, monkeypatch):
    product = productive_fetch
    for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        monkeypatch.setenv(name, 'http://127.0.0.1:80')
    result, _, row = product.execute('https://cf-public.test/b6-no-ambient-proxy')
    assert result.status is ToolStatus.COMPLETED
    assert row['forbiddenPrivateCanaryHits'] == 0 and len(row['nativeTCPConnectAttempts']) == 1
    assert row['nativeTCPConnectAttempts'][0]['target'] == [product.environment.address, 443]


@pytest.mark.parametrize('field', ['BrowserSession', 'ElementRef', 'Cookie', 'browserGrant', 'NetworkProofRef',
    'ControlledFetchSecretRef', 'profile', 'Authorization'])
def test_productive_tool_schema_rejects_cross_capability_authority_before_effect(productive_fetch, field):
    result, _, row = productive_fetch.execute('http://cf-public.test/b6-closed-authority',
        additional_arguments={field: 'fake-reusable-authority'})
    assert result.status is ToolStatus.DENIED
    assert not row['nativeTCPConnectAttempts'] and not row['transport'] and not row['browserCreated']


def test_productive_fetch_grant_cannot_be_relabelled_or_cloned_as_browser_authority(productive_fetch):
    product = productive_fetch
    result, _, row = product.execute('http://cf-public.test/b6-grant-separation')
    assert result.status is ToolStatus.COMPLETED
    operation = product.last_invocation.operation_id
    grant = next(state.grant for state in product.runtime._issuer._issued.values()
        if state.grant.request.subject.operation_id == operation)
    fake_browser_cap = Capability(Permission('browser.read'), ResourceScope(ScopeKind.SESSION, 'bws_'+'1'*32),
        ControlClass.APPLICATION_ENFORCED, {'capabilityId': IB, 'networkIsolation': 'NOT_PROVIDED'})
    fake_browser_request = replace(grant.request, capabilities=(fake_browser_cap,), tool_name='browser_act',
        network_intent={'capabilityId': IB, 'actionKind': 'CLICK'})
    fake_browser_grant = replace(grant, request=fake_browser_request)
    with pytest.raises(SecurityError):
        product.runtime._issuer.validate_claimed(fake_browser_grant, fake_browser_request)
    plan = product.service._plans[operation]
    with pytest.raises(ControlledFetchError):
        plan['service']._check_grant(plan['cf'], plan['ctx'], fake_browser_grant)
    assert not product.service.browser
    output('productive_grant_separation', dict(source='PRODUCTIVE_FETCH_COMPOSITION',
        originalFetchGrantHostIssued=True, clonedBrowserGrantRejected=True,
        browserGrantRejectedAsFetchAuthority=True, browserNeverCreated=True,
        additionalTCPConnections=0, evidenceKind='PRODUCTIVE_ISSUER_CONTRACT_NOT_NATIVE_BROWSER_CERTIFICATION'))


def test_productive_subagent_has_no_inherited_fetch_authority(productive_fetch):
    result, _, row = productive_fetch.execute('http://cf-public.test/b6-subagent', agent_id='subagent-1')
    assert result.status is ToolStatus.DENIED
    assert not row['nativeTCPConnectAttempts'] and not row['transport'] and not row['browserCreated']


def test_actual_agentloop_proposal_executes_same_productive_fetch_composition(productive_fetch):
    product = productive_fetch
    target = 'https://cf-public.test/b6-agentloop'
    arguments = dict(url=target, method='GET', resultMode='TEXT', requiresInteraction=False, reason='')
    # Only proposal production is scripted; the actual AgentLoop, LegacyToolAdapter,
    # ToolRuntime, Policy, issuer, DNS, TLS and upstream fixture remain real.
    product.provider.turns = [dict(role='assistant', content='',
        tool_calls=[dict(function=dict(name='web_access', arguments=arguments))]),
        'La recuperación HTTP controlada terminó.']
    environment = product.environment
    before_transport, before_dns = len(product.transport), len(product.dns)
    before_https, before_private = len(environment.https.events), len(environment.private.connections)
    before_sockets = len(environment.socket_attempts)
    receipt = product.app.handle(ApplicationCommand(new_command_id(), CommandKind.SUBMIT_USER_INPUT,
        {'content': 'Lee ' + target + ' mediante recuperación HTTP controlada.'}, session_id=product.session))
    assert receipt.accepted and product.app.wait_for_turn(receipt.created_ids['turnId'], 15)
    time.sleep(.02)
    snapshot = product.app.get_snapshot(product.session).to_dict()
    turn = next(t for t in snapshot['turns'] if t['turnId'] == receipt.created_ids['turnId'])
    outcomes = [result for _, result in product.runtime._outcomes.values()
        if result.metadata.get('capabilityId') == CF]
    assert turn['status'] == 'completed' and len(outcomes) == 1
    result = outcomes[0]
    assert result.status is ToolStatus.COMPLETED
    body = json.loads(result.stdout)
    transport = product.transport[before_transport:]
    server = environment.https.events[before_https:]
    assert body['outcome'] == 'SUCCEEDED_OBSERVED' and body['capabilityId'] == CF
    assert len(transport) == len(server) == len(environment.socket_attempts)-before_sockets == 1
    assert transport[0]['admittedEndpoint'] == transport[0]['connectedEndpoint'] == [environment.address, 443]
    assert server[0]['method'] == 'GET' and server[0]['host'] == 'cf-public.test'
    assert len(environment.private.connections)-before_private == 0 and product.service.browser is None
    assert product.runtime._web_v12 is product.app._web_v12 is product.service
    product.rows.append(dict(source='PRODUCTIVE_FETCH_COMPOSITION',
        proposalProducer='SCRIPTED_PROVIDER_ONLY_REAL_AGENTLOOP',
        productivePath=['AgentSessionCoordinator', 'AgentLoop', 'LegacyToolAdapter', 'ToolRuntime',
            'WebProductV12', 'PolicyEngineV2', 'GrantIssuer', 'ControlledFetchService', 'RealControlledFetchTransport'],
        operationId=body['operationId'], turnId=turn['turnId'], status=result.status.value,
        effectState=result.effect_state.value, outcome=body['outcome'],
        transport=transport, dns=product.dns[before_dns:], serverEvents=server,
        nativeTCPConnectAttempts=environment.socket_attempts[before_sockets:],
        forbiddenPrivateCanaryHits=0, browserCreated=False,
        capabilitySnapshot=snapshot['services']['webCapabilitiesV12'],
        payloadSha256=hashlib.sha256((body['payload'] or '').encode()).hexdigest(),
        exactFixtureProcessOnlyTrust=True, automaticRetryObserved=False))
