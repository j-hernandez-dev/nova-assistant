"""S7 evidence coordination, separate from events/transcript/logger."""
from datetime import datetime, timezone
from threading import RLock
from types import SimpleNamespace
from dataclasses import replace
from uuid import uuid4
from urllib.parse import urlsplit, urlunsplit

from local_cli.core.security_audit import AuditKind, SecurityAuditPort, SecurityAuditRecord, SecurityAuditError


def safe_url(value):
    """Drop query, credentials and fragment rather than relying on detection."""
    if not isinstance(value, str) or not value:
        return None
    try:
        p = urlsplit(value)
        host = p.hostname or ''
        if ':' in host:
            host = '[' + host + ']'
        if p.port:
            host += ':' + str(p.port)
        return urlunsplit((p.scheme, host, p.path, '', ''))
    except (ValueError, TypeError):
        return None


class SecurityAuditService:
    """OD-05: durable admission; delivery loss never rewrites an observed effect."""
    def __init__(self, port: SecurityAuditPort, *, redactor):
        self.port, self.redactor = port, redactor
        self.stream_id = str(uuid4())
        self._sequence = 0
        self._lock = RLock()
        self.last_error = None
        self.delivery_failures = 0
        self._lost_operations = set()

    def _failed(self, invocation):
        self.last_error = 'SECURITY_AUDIT_DELIVERY_FAILED'
        self.delivery_failures += 1
        self._lost_operations.add((invocation.context.session_id, invocation.operation_id))

    def before_effect(self, invocation, *, parents=None, origin=None):
        with self._lock:
            key = (invocation.context.session_id, invocation.operation_id)
            try:
                # Optional for explicit old fixture ports; production OD-05
                # implements this check for every current ExecutionContext.
                validate = getattr(self.port, 'validate_workspace', None)
                if validate is not None:
                    validate(str(invocation.context.workspace))
            except Exception:
                self._failed(invocation)
                raise SecurityAuditError('SECURITY_AUDIT_PRE_EFFECT_FAILED') from None
            delivered = self.record(invocation, AuditKind.DISPATCH, {
                'observationScope': 'dispatch_requested_not_proof_of_effect'}, parents=parents, origin=origin)
            if delivered and key not in self._lost_operations:
                try:
                    self.port.flush()
                    return
                except Exception:
                    self._failed(invocation)
            raise SecurityAuditError('SECURITY_AUDIT_PRE_EFFECT_FAILED')

    def annotate_result(self, invocation, result):
        key = (invocation.context.session_id, invocation.operation_id)
        lost = key in self._lost_operations
        metadata = {**result.metadata, 'securityAudit': {
            'status': 'gap' if lost else 'durable_terminal',
            'gap': lost, 'retryAllowed': False if lost else None,
            'errorCode': 'SECURITY_AUDIT_DELIVERY_FAILED' if lost else None,
            'storageGapCodes': sorted({g['code'] for g in getattr(self.port, 'gaps', ())})}}
        if not lost:
            return replace(result, metadata=metadata)
        warning = 'Warning: SECURITY_AUDIT_DELIVERY_FAILED; audit gap. Observed result retained; no retry/rollback.'
        return replace(result, metadata=metadata,
            legacy_text=((result.legacy_text + '\n') if result.legacy_text else '')+warning)

    def health(self):
        return {'deliveryFailures': self.delivery_failures, 'lastError': self.last_error,
            'storageGapCodes': sorted({g['code'] for g in getattr(self.port, 'gaps', ())})}

    def record(self, invocation, kind, data, *, parents=None, origin=None):
        ctx = invocation.context
        with self._lock:
            self._sequence += 1
            try:
                validate = getattr(self.port, 'validate_workspace', None)
                if validate is not None:
                    validate(str(ctx.workspace))
                safe = self.redactor.value({**data, **(parents or {})})
                entry = SecurityAuditRecord(str(uuid4()), self.stream_id, self._sequence,
                    datetime.now(timezone.utc).isoformat(), kind, str(ctx.session_id),
                    str(invocation.operation_id), invocation.name,
                    (origin if origin is not None else 'application' if kind in (AuditKind.AGENT_STARTED, AuditKind.AGENT_TERMINAL)
                     else 'subagent_runtime' if ctx.agent_id else 'agent_runtime'), safe,
                    str(ctx.turn_id) if ctx.turn_id else None,
                    str(invocation.tool_call_id) if invocation.tool_call_id is not None else None,
                    str(ctx.agent_id) if ctx.agent_id else None)
                self.port.append(entry)
                if kind in (AuditKind.TERMINAL, AuditKind.AGENT_TERMINAL):
                    self.port.flush()
                self.last_error = None
                return True
            except Exception:
                # Never serialize the exception: a failing adapter can carry
                # private path/content/credentials in its exception message.
                self._failed(invocation)
                return False

    def request(self, invocation, *, parents=None, origin=None):
        args = invocation.arguments
        data = {'cwd': str(invocation.context.cwd)}
        if invocation.name == 'bash':
            data['command'] = args.get('command') if isinstance(args.get('command'), str) else None
        elif invocation.name == 'web_fetch':
            data['resource'] = safe_url(args.get('url'))
        elif invocation.name in ('read', 'write', 'edit', 'glob', 'grep'):
            resource = args.get('file_path', args.get('path', '.'))
            data['resource'] = resource if isinstance(resource, str) else None
        return self.record(invocation, AuditKind.REQUEST, data, parents=parents, origin=origin)

    def agent(self, context, operation_id, agent_id, *, started, outcome=None):
        invocation = SimpleNamespace(context=replace(context, operation_id=operation_id, agent_id=agent_id),
            operation_id=operation_id, name='agent', tool_call_id=None)
        return self.record(invocation, AuditKind.AGENT_STARTED if started else AuditKind.AGENT_TERMINAL, {
            'parentSessionId': context.session_id, 'parentTurnId': context.turn_id,
            'parentOperationId': context.operation_id if context.operation_id != operation_id else None,
            'parentAgentId': context.agent_id, 'childAgentId': agent_id,
            'outcome': 'running' if started else outcome,
            'effectState': 'unknown', 'observationScope': 'observed_subagent_lifecycle_only'})

    def authorization(self, invocation, request, decision, *, parents=None):
        return self.record(invocation, AuditKind.POLICY, {
            'requestDigest': request.request_digest, 'policyRevision': request.policy_revision,
            'ceilingRevision': request.ceiling_revision, 'decision': decision.action.value,
            'reason': decision.reason, 'effectClassification': request.effect_classification,
            'controlClasses': sorted({c.control_class.value for c in request.capabilities}),
            'environmentNames': sorted(request.environment_intent),
            'deadline': request.lifetime.expires_at.isoformat()}, parents=parents)

    def grant(self, invocation, grant, *, parents=None, origin=None):
        request = grant.request
        summaries = []
        for cap in request.capabilities:
            resource = cap.scope.resource
            if cap.permission.name.startswith('network.'):
                resource = safe_url(resource)
            summaries.append({'permission': cap.permission.name,
                'scopeKind': cap.scope.kind.value, 'resource': resource,
                'controlClass': cap.control_class.value})
        return self.record(invocation, AuditKind.GRANT, {
            'grantId': grant.grant_id, 'parentGrantId': request.parent_grant_id,
            'requestDigest': request.request_digest, 'permissions': summaries,
            'policyRevision': request.policy_revision,
            'ceilingRevision': request.ceiling_revision}, parents=parents, origin=origin)

    def observations(self, invocation, result, filesystem_binding=None, *, parents=None):
        m = result.metadata
        if invocation.name == 'bash':
            for observation in m.get('processAudit', ()):
                self.record(invocation, AuditKind.PROCESS, {
                    'action': observation.get('kind'), 'cwd': observation.get('cwd'),
                    'command': observation.get('command'), 'executable': observation.get('executable'),
                    'observedTimestamp': observation.get('timestamp'), 'pid': observation.get('pid'),
                    'exitCode': observation.get('exit_code'), 'processModel': 'HOST_UNISOLATED',
                    'treeControl': 'BEST_EFFORT', 'processOutcome': observation.get('outcome'),
                    'processStates': observation.get('states', ()),
                    'cleanupScope': observation.get('cleanup_scope'),
                    'cleanupConfirmed': observation.get('cleanup_confirmed'),
                    'stdoutTruncated': m.get('stdoutTruncated', False),
                    'stderrTruncated': m.get('stderrTruncated', False),
                    'observationScope': 'launch_and_report_only_not_internal_process_effects'}, parents=parents)
        if invocation.name in ('read', 'write', 'edit', 'glob', 'grep') and filesystem_binding:
            target = filesystem_binding.get('target')
            applied = result.effect_state.value == 'applied'
            self.record(invocation, AuditKind.FILESYSTEM, {
                'path': filesystem_binding.get('path'), 'rootIdentity': filesystem_binding.get('rootIdentity'),
                'beforeObjectIdentity': target.get('identity') if target else None,
                'afterObjectIdentity': m.get('filesystemObjectIdentity'),
                'action': ('create' if target is None else 'modify') if applied and invocation.name in ('write', 'edit') else invocation.name,
                'beforeHash': m.get('filesystemBeforeHash'), 'afterHash': m.get('filesystemAfterHash'),
                'beforeHashStatus': 'observed' if m.get('filesystemBeforeHash') else 'not_observed_no_extra_read_authority',
                'controlClasses': ['BROKER_ENFORCED'], 'outcome': result.status.value,
                'effectState': result.effect_state.value,
                'observationScope': 'mediated_operation_only'}, parents=parents)
        if invocation.name == 'web_fetch' and 'networkAudit' in m:
            self.record(invocation, AuditKind.NETWORK, {
                'requestedUrl': safe_url(m.get('requestedUrl')),
                'effectiveUrl': safe_url(m.get('effectiveUrl')),
                'hops': m['networkAudit'], 'httpDispatched': m.get('httpDispatched'),
                'truncated': m.get('truncated', False), 'controlClasses': ['BROKER_ENFORCED'],
                'observationScope': 'controlled_http_client_only'}, parents=parents)

    def terminal(self, invocation, result, *, parents=None):
        m = result.metadata
        states = m.get('processStates', ())
        return self.record(invocation, AuditKind.TERMINAL, {
            'outcome': result.status.value, 'effectState': result.effect_state.value,
            'errorCode': m.get('securityErrorCode'), 'requestDigest': m.get('requestDigest'),
            'policyRevision': m.get('policyRevision'), 'grantId': m.get('grantId'),
            'exitCode': result.exit_code, 'pid': m.get('pid'),
            'cancelRequested': invocation.context.cancellation_token.is_cancel_requested(),
            'timeoutRequested': 'timeout_requested' in states,
            'stdoutTruncated': m.get('stdoutTruncated', False),
            'stderrTruncated': m.get('stderrTruncated', False),
            'retryAllowed': False if result.status.value == 'outcome_unknown' else None}, parents=parents)


def reconstruct_operation(records):
    """Only summarize observed records; a missing terminal is NOT success."""
    records = tuple(records)
    subjects = {(r.session_id, r.operation_id, r.audit_stream_id) for r in records}
    if len(subjects) > 1:
        raise ValueError('AUDIT_SUBJECT_CONFLICT')
    ordered = sorted(records, key=lambda r: r.audit_sequence)
    terminal = [r for r in ordered if r.kind in (AuditKind.TERMINAL, AuditKind.AGENT_TERMINAL)]
    if len(terminal) > 1:
        raise ValueError('AUDIT_TERMINAL_CONFLICT')
    requested = any(r.kind in (AuditKind.REQUEST, AuditKind.AGENT_STARTED) for r in ordered)
    return {'records': [r.to_dict() for r in ordered],
        'requestObserved': requested, 'terminalObserved': bool(terminal),
        'completeObservedLifecycle': requested and bool(terminal),
        'outcome': terminal[0].data['outcome'] if terminal else 'not_observed',
        'effectState': terminal[0].data['effectState'] if terminal else 'unknown',
        'processInternalEffectsKnown': False}
