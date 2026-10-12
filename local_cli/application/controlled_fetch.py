"""V12-B1 opt-in host composition; never registered in AgentLoop/ToolRuntime.

The existing GrantIssuer owns authority. Model inputs are tiny closed candidates;
Application supplies identity, ceilings, canonicalization, exact grants and fresh
admission. No browser, auth, POST, binary transfer or real transport in B1.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import json
import re
from pathlib import Path
from threading import RLock
from urllib.parse import parse_qsl, urljoin, urlsplit

from local_cli.application.browser_network import BrowserNetworkPolicy
from local_cli.application.grants import GrantIssuer
from local_cli.application.network import canonical_url
from local_cli.application.policy import EffectResourceIntent, PolicyEngineV2, ToolPolicyAction
from local_cli.application.secrets import SecretRedactor
from local_cli.core.controlled_fetch import (
    CONTROLLED_FETCH_CAPABILITY_ID as CF, AdmittedControlledFetchRequest,
    ControlledFetchAbsence as Absence, ControlledFetchCompleteness as Complete,
    ControlledFetchConsumption as Consumption, ControlledFetchError, ControlledFetchErrorCode as Error,
    ControlledFetchHop, ControlledFetchLimits, ControlledFetchMethod as Method,
    ControlledFetchFuturePost, ControlledFetchFutureDownload,
    ControlledFetchNetworkProofRef, ControlledFetchOutcome as Outcome, ControlledFetchOwner,
    ControlledFetchOutcomeLedger,
    ControlledFetchTransportFailure, ControlledFetchTransportEvidence,
    ControlledFetchRequest, ControlledFetchResult, ControlledFetchResultMode as Mode,
    ControlledFetchSecretRef, ControlledFetchTransportPort, aware, canonical_target, closed, label, require,
)
from local_cli.core.network import FetchBudget, FetchLimits, NetworkError
from local_cli.core.contracts import ExecutionContext, RuntimeCapabilitySnapshot, ToolInvocation
from local_cli.core.security import (
    Capability, CapabilityGrant, ControlClass, GrantLifetime, GrantRequest, GrantSubject,
    Permission, ResourceScope, ScopeKind, SecurityError,
)


@dataclass(frozen=True)
class ControlledFetchContext:
    owner: ControlledFetchOwner
    turn_id: str
    operation_id: str
    policy_revision: int
    deadline: datetime
    cancellation: object

    def __post_init__(self):
        require(type(self.owner) is ControlledFetchOwner)
        label(self.turn_id); label(self.operation_id); aware(self.deadline)
        require(type(self.policy_revision) is int and self.policy_revision >= 1)
        require(callable(getattr(self.cancellation, 'is_cancel_requested', None)))


class ControlledFetchTurnBudget:
    """Trusted host turn quota. Atomic reserve, sticky IDs, no redirect reset."""
    def __init__(self, owner, turn_id, limits):
        require(type(owner) is ControlledFetchOwner and type(limits) is ControlledFetchLimits)
        label(turn_id)
        self.owner, self.turn_id, self.limits = owner, turn_id, limits
        self._lock, self._operations = RLock(), set()
        self._active, self._bytes = 0, 0
        self._reservations = {}

    def begin(self, request):
        with self._lock:
            require(request.owner == self.owner and request.turn_id == self.turn_id, Error.OWNER)
            require(self.limits.covers(request.limits), Error.LIMIT)
            require(request.operation_id not in self._operations, Error.REPLAY)
            require(len(self._operations) < min(self.limits.per_turn_requests,request.limits.per_turn_requests), Error.LIMIT)
            require(self._active < min(self.limits.concurrency,request.limits.concurrency), Error.BUSY)
            available=min(self.limits.per_turn_bytes,request.limits.per_turn_bytes)-self._bytes-sum(self._reservations.values())
            require(available>0,Error.LIMIT)
            self._reservations[request.operation_id]=min(available,(request.limits.max_redirects+1)*
                (2*request.limits.max_header_bytes+request.limits.max_response_bytes))
            self._operations.add(request.operation_id); self._active += 1

    def allowance(self, request):
        with self._lock:
            available=self._reservations.get(request.operation_id,0)
            require(available>0,Error.LIMIT)
            return min(available,2*request.limits.max_header_bytes+request.limits.max_response_bytes)

    def consume_bytes(self, count, request):
        with self._lock:
            require(type(count) is int and count >= 0)
            remaining=self._reservations[request.operation_id]
            self._reservations[request.operation_id]=max(0,remaining-count)
            self._bytes += count
            require(count<=remaining and self._bytes <= min(self.limits.per_turn_bytes,request.limits.per_turn_bytes), Error.LIMIT)

    def end(self, operation_id):
        with self._lock:
            require(self._active > 0)
            self._active -= 1
            self._reservations.pop(operation_id,None)


class ControlledFetchHostRefs:
    """Host ledger. Ref identity is nonserializable, never a bearer grant/proof.

    Stores future auth binding metadata only, no credential value or lookup.
    Neither type enables auth or provides network certification in B1.
    """
    def __init__(self, *, clock=None):
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._refs, self._lock = {}, RLock()

    def _issue(self, kind, request, target):
        require(type(request) is ControlledFetchRequest)
        canonical_target(target)
        require(self.clock() < request.deadline <= self.clock()+timedelta(seconds=request.limits.timeout_seconds), Error.EXPIRED)
        with self._lock:
            require(len(self._refs) < 64, Error.LIMIT)
            ref = kind()
            self._refs[ref] = (request.owner, request.operation_id, request.policy_revision,
                               request.deadline, target, CF)
            return ref

    def secret(self, request):
        require(urlsplit(request.canonical_target).scheme == 'https',Error.OPTIONAL)
        return self._issue(ControlledFetchSecretRef, request, request.canonical_target)

    def proof(self, admitted):
        require(type(admitted) is AdmittedControlledFetchRequest)
        return self._issue(ControlledFetchNetworkProofRef, admitted.request, admitted.canonical_target)

    def validate(self, ref, request, *, target, kind):
        with self._lock:
            require(type(ref) is kind and ref in self._refs, Error.REF)
            require(self._refs[ref] == (request.owner, request.operation_id, request.policy_revision,
                    request.deadline, target, CF) and self.clock() < request.deadline, Error.REF)
            if kind is ControlledFetchNetworkProofRef:self._refs.pop(ref)  # One-use private provenance, never a grant.

    def close(self):
        with self._lock:self._refs.clear()


class _StaticHTML(HTMLParser):
    def __init__(self, budget):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], []
        self.budget, self.nodes = budget, 0

    def handle_starttag(self, tag, attrs):
        self.budget.check(); self.nodes+=1; require(self.nodes<=10000,Error.FORMAT)
        if tag in ('script','style','iframe','template','object'):
            self.hidden.append(tag)
            require(len(self.hidden)<=32,Error.FORMAT)

    def handle_endtag(self, tag):
        if self.hidden and tag == self.hidden[-1]: self.hidden.pop()

    def handle_data(self, data):
        self.budget.check(); self.nodes+=1; require(self.nodes<=10000,Error.FORMAT)
        if not self.hidden: self.parts.append(data)


class ControlledFetchService:
    def __init__(self, *, issuer: GrantIssuer, policy: PolicyEngineV2, approved_scope: ResourceScope,
                 turn_budget: ControlledFetchTurnBudget, record, resolver=None,
                 transport: ControlledFetchTransportPort | None = None, clock=None):
        require(type(issuer) is GrantIssuer and isinstance(policy, PolicyEngineV2))
        require(type(approved_scope) is ResourceScope and approved_scope.kind in (ScopeKind.URL,ScopeKind.ORIGIN), Error.AUTHORITY)
        require(type(turn_budget) is ControlledFetchTurnBudget and callable(record))
        self.issuer, self.policy, self.scope, self.turn_budget = issuer, policy, approved_scope, turn_budget
        self.record, self.resolver = record, resolver
        require(transport is None or (callable(getattr(transport,'validate',None)) and callable(getattr(transport,'dispatch',None))))
        self.transport = transport
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.refs = ControlledFetchHostRefs(clock=self.clock)
        self._admitted, self._lock = {}, RLock()
        self._transport_leases = {}

    def _current(self, request, context):
        require(type(request) is ControlledFetchRequest and type(context) is ControlledFetchContext)
        require(request.owner == context.owner, Error.OWNER)
        require((request.turn_id,request.operation_id) == (context.turn_id,context.operation_id), Error.OPERATION)
        require(request.policy_revision == context.policy_revision == self.policy.revision, Error.POLICY)
        require(self.clock() < request.deadline <= min(context.deadline,self.clock()+timedelta(seconds=request.limits.timeout_seconds)), Error.EXPIRED)
        require(self.turn_budget.limits.covers(request.limits), Error.LIMIT)
        require(self.turn_budget.owner == context.owner and self.turn_budget.turn_id == context.turn_id, Error.OWNER)
        cancelled = context.cancellation.is_cancel_requested()
        require(type(cancelled) is bool and not cancelled, Error.CANCELLED)
        require(self.scope.covers(ResourceScope(ScopeKind.URL,request.canonical_target)), Error.AUTHORITY)
        return True

    def request_from_candidate(self, candidate, context):
        """ONLY URL/method/mode enter from model. Identity/limits/target stay host-owned."""
        closed(candidate, ('capabilityId','url','method','resultMode'))
        require(candidate['capabilityId'] == CF, Error.CAPABILITY)
        require(type(candidate['method']) is str and candidate['method'] in ('GET','HEAD'), Error.METHOD)
        require(type(candidate['resultMode']) is str and candidate['resultMode'] in ('TEXT','HTML_STATIC','JSON'), Error.MODE)
        require(type(context) is ControlledFetchContext)
        try:
            target = canonical_url(candidate['url']); canonical_target(target)
        except (NetworkError, SecurityError):
            raise ControlledFetchError(Error.URL) from None
        limits = self.turn_budget.limits
        deadline = min(context.deadline, self.clock()+timedelta(seconds=limits.timeout_seconds))
        request = ControlledFetchRequest(CF, context.owner, context.turn_id, context.operation_id,
                    context.policy_revision, deadline, target, Method(candidate['method']), Mode(candidate['resultMode']), limits)
        self._current(request, context)
        return request

    def grant_request(self, request, context):
        """Private host binding for the EXISTING issuer; never issues/approves a grant."""
        self._current(request, context)
        # Logical Application contract only; no BROKER_ENFORCED transport claim in B1.
        cap = Capability(Permission('network.fetch'), self.scope, ControlClass.APPLICATION_ENFORCED,
                         {'capabilityId':CF,'profile':'GET_HEAD_CONTRACT_ONLY'})
        grant_request=GrantRequest(GrantSubject(request.owner.owner_id,request.turn_id,request.operation_id,'cf_'+request.operation_id),
            'controlled_fetch', request.to_dict(), (cap,), request.owner.workspace, request.owner.workspace,
            'controlled_fetch_'+request.method.value.lower(), request.policy_revision,
            self.issuer.ceiling.ceiling_id, self.issuer.ceiling.revision, self.issuer.ceiling.fingerprint,
            GrantLifetime(self.clock()-timedelta(seconds=1),request.deadline),
            environment_intent={'mode':'none'}, network_intent={
                'capabilityId':CF,'taskId':request.owner.task_id,'target':request.canonical_target,
                'method':request.method.value,'resultMode':request.result_mode.value,
                'approvedScope':self.scope._binding(),'limits':request.limits.to_dict(),
                'deadline':request.deadline.isoformat(),'redirectAuthority':'fresh_admission_same_scope',
                'cookieJar':False,'browserSessionImport':False,'authExecution':False,'retryAllowed':False},
            effect_classification='CONTROLLED_HTTP_REQUEST_SEMANTICS_UNKNOWN')
        execution=ExecutionContext(Path(request.owner.workspace),Path(request.owner.workspace),{},
            request.owner.owner_id,request.operation_id,context.cancellation,request.deadline,
            RuntimeCapabilitySnapshot(captured_at=self.clock(),source='CF_B1_CONTRACT_ONLY'),
            turn_id=request.turn_id,policy_revision=request.policy_revision)
        invocation=ToolInvocation('controlled_fetch',request.to_dict(),'cf_'+request.operation_id,request.operation_id,execution)
        verdict=self.policy.evaluate(invocation,None,self.issuer.ceiling,
            EffectResourceIntent((cap,),grant_request.action,grant_request.effect_classification,grant_request.network_intent))
        require(verdict.action is ToolPolicyAction.ALLOW and verdict.policy_revision==request.policy_revision,Error.AUTHORITY)
        return grant_request

    def _check_grant(self, request, context, grant):
        require(type(grant) is CapabilityGrant, Error.AUTHORITY)
        expected = self.grant_request(request, context)
        # not_before is issuer-owned; all other exact binding fields remain mandatory.
        expected = replace(expected, lifetime=grant.request.lifetime)
        require(grant.request.lifetime.one_shot and grant.request.lifetime.expires_at == request.deadline and
                grant.request.request_digest == expected.request_digest, Error.AUTHORITY)
        return expected

    def _admit(self, request, target, budget, context, grant, lineage, hop):
        self._current(request,context); self.grant_request(request,context); budget.check()
        self.issuer.validate_claimed(grant,grant.request)
        canonical_target(target)
        require(self.scope.covers(ResourceScope(ScopeKind.URL,target)), Error.AUTHORITY)
        require(self.resolver is not None, Error.UNCONFIGURED)
        answers=[]
        resolver=self.resolver
        class AdmissionResolver:
            def resolve(self,host,port,budget):
                result=resolver.resolve(host,port,budget)
                answers.extend(result)
                return result
        policy = BrowserNetworkPolicy(AdmissionResolver(), validate_session=lambda: self._current(request,context))
        url = urlsplit(target)
        if url.scheme == 'https':
            host = '['+url.hostname+']' if ':' in url.hostname else url.hostname
            admission = policy.authorize('CONNECT', host+':'+str(url.port or 443), host+':'+str(url.port or 443), budget)
        else:
            admission = policy.authorize(request.method.value,target,url.netloc,budget)
        self._current(request,context); self.grant_request(request,context); self.issuer.validate_claimed(grant,grant.request)
        plan = AdmittedControlledFetchRequest(request,target,self.scope,admission.endpoint,hop,lineage,
                                             self.turn_budget.allowance(request),tuple(answers))
        with self._lock:
            self._admitted[id(plan)] = plan
            self._transport_leases[id(plan)] = [plan,context,grant,lineage,'ADMITTED']
        return plan

    def transport_guard(self, plan, phase):
        """Private host callback, never wire/model data; no second admission/policy."""
        with self._lock:
            lease=self._transport_leases.get(id(plan))
            require(type(plan) is AdmittedControlledFetchRequest and lease is not None and lease[0] is plan,Error.ADMISSION)
            self._current(plan.request,lease[1])
            # Stream checks use the current monotonic Policy revision + claimed
            # issuer ledger; rebuilding ExecutionContext per byte is unnecessary.
            if phase!='current':self.grant_request(plan.request,lease[1])
            self.issuer.validate_claimed(lease[2],lease[2].request)
            if phase=='validate':require(lease[4]=='ADMITTED' and self._admitted.get(id(plan)) is plan,Error.ADMISSION)
            elif phase=='claim':
                require(lease[4]=='DISPATCH_READY',Error.REPLAY);lease[4]='DISPATCH_CLAIMED'
            elif phase=='current':require(lease[4]=='DISPATCH_CLAIMED',Error.ADMISSION)
            else:require(False,Error.ADMISSION)
        return None

    def validate_admitted(self, plan, request, context, grant, lineage):
        with self._lock:
            require(type(plan) is AdmittedControlledFetchRequest and self._admitted.get(id(plan)) is plan, Error.ADMISSION)
        require(plan.request is request and plan.lineage is lineage and plan.approved_scope == self.scope, Error.ADMISSION)
        self._current(request,context); self.grant_request(request,context); self.issuer.validate_claimed(grant,grant.request)

    @staticmethod
    def redirect_candidate(target, location):
        require(type(location) is str and 0 < len(location) <= 512 and
                not any(c.isspace() or ord(c)<32 or ord(c)==127 for c in location), Error.REDIRECT)
        try:
            candidate = canonical_url(urljoin(target,location)); canonical_target(candidate)
        except (NetworkError,ValueError,TypeError):
            raise ControlledFetchError(Error.REDIRECT) from None
        require(not (urlsplit(target).scheme == 'https' and urlsplit(candidate).scheme != 'https'), Error.REDIRECT)
        return candidate  # Data, never a plan/grant/proof; _admit is required next.

    def _payload(self, request, hop, redactor, budget):
        if request.method is Method.HEAD:
            require(not hop.body, Error.RESPONSE)
            return None, Absence.HEAD_NO_BODY, not hop.complete
        if hop.status==204:
            require(not hop.body,Error.RESPONSE)
            return None,Absence.NO_RESULT,not hop.complete
        mime = hop.content_type.split(';')[0].strip().lower()
        if ';' in hop.content_type:
            require(hop.content_type.split(';',1)[1].strip().lower() in ('charset=utf-8','charset="utf-8"'),Error.FORMAT)
        require(mime in ({Mode.TEXT:{'text/plain'},Mode.HTML_STATIC:{'text/html'},
                         Mode.JSON:{'application/json'}}[request.result_mode]), Error.FORMAT)
        try: text = hop.body.decode('utf-8',errors='strict')
        except UnicodeError: raise ControlledFetchError(Error.FORMAT) from None
        if request.result_mode is Mode.HTML_STATIC:
            parser = _StaticHTML(budget)
            for offset in range(0,len(text),8192):budget.check();parser.feed(text[offset:offset+8192])
            parser.close(); text = ''.join(parser.parts)
        elif request.result_mode is Mode.JSON:
            # Bound lexical nesting before json.loads to avoid recursive parser exhaustion.
            depth, quoted, escape = 0, False, False
            for index,char in enumerate(text):
                if index%4096==0:budget.check()
                if quoted:
                    if escape: escape=False
                    elif char == '\\': escape=True
                    elif char == '"': quoted=False
                elif char == '"': quoted=True
                elif char in '[{':
                    depth+=1; require(depth<=32,Error.FORMAT)
                elif char in ']}': depth-=1
            try:
                value = json.loads(text,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            except (ValueError,RecursionError): raise ControlledFetchError(Error.FORMAT) from None
            nodes=[0]
            def scrub(value):
                nodes[0]+=1; require(nodes[0]<=10000,Error.FORMAT)
                if nodes[0]%100==0:budget.check()
                if isinstance(value,str):
                    require(not any(0xD800<=ord(c)<=0xDFFF for c in value),Error.FORMAT)
                    return redactor.text(value)
                if isinstance(value,list):return [scrub(v) for v in value]
                if isinstance(value,dict):return {scrub(k):scrub(v) for k,v in value.items()}
                return value
            try:text=json.dumps(scrub(value),ensure_ascii=False,allow_nan=False,separators=(',',':'))
            except ValueError:raise ControlledFetchError(Error.FORMAT) from None
        text = redactor.text(text,partial=not hop.complete)
        truncated = not hop.complete or len(text)>request.limits.max_published_chars
        if truncated and request.result_mode is Mode.JSON:
            return None,Absence.PUBLICATION_LIMIT,True
        return text[:request.limits.max_published_chars],None,truncated

    def execute(self, request, context, grant):
        return self._execute(request, context, grant, claimed=False)

    def execute_claimed(self, request, context, grant):
        """Internal productive ToolRuntime seam; never claims a one-use grant twice."""
        self.issuer.validate_claimed(grant, self._check_grant(request, context, grant))
        return self._execute(request, context, grant, claimed=True)

    def _execute(self, request, context, grant, *, claimed):
        if type(request) in (ControlledFetchFuturePost,ControlledFetchFutureDownload,ControlledFetchSecretRef):
            raise ControlledFetchError(Error.OPTIONAL)
        self._current(request,context)
        expected = self._check_grant(request,context,grant)
        self.turn_budget.begin(request)
        budget=FetchBudget(FetchLimits(request.limits.timeout_seconds,request.limits.max_response_bytes,
                                     request.limits.max_redirects,request.limits.max_published_chars),context.cancellation,request.deadline)
        consumed=Consumption(logical_requests=1); lineage=object(); target=request.canonical_target
        entered=False; started=False; plans=[]; outcome_ledger=ControlledFetchOutcomeLedger()
        # No ambient env/provider/browser credential lookup; explicit query values are not public.
        redactor=SecretRedactor(source={})
        def protect(url):
            try: pairs=parse_qsl(urlsplit(url).query,max_num_fields=32)
            except ValueError: raise ControlledFetchError(Error.URL) from None
            for _,value in pairs:redactor.register(value)
        def result(outcome,*,payload=None,absence=Absence.NO_RESULT,error=None,truncated=False,mime=None):
            origin=urlsplit(target).scheme+'://'+urlsplit(target).netloc
            complete=Complete.PARTIAL if outcome is Outcome.PARTIAL else Complete.COMPLETE if outcome is Outcome.SUCCEEDED_OBSERVED else Complete.NONE
            return ControlledFetchResult(CF,request.operation_id,origin+'/[path-redacted]',origin,request.method,
                request.result_mode,outcome,complete,truncated,mime,consumed.response_bytes,consumed,payload,absence,error)
        try:
            if claimed:
                self.issuer.validate_claimed(grant, expected)
            else:
                self.issuer.claim(grant,expected)
            require(self.transport is not None,Error.UNCONFIGURED)
            protect(target)
            for index in range(request.limits.max_redirects+1):
                plan=self._admit(request,target,budget,context,grant,lineage,index);plans.append(plan)
                self.transport.validate(plan)
                self.validate_admitted(plan,request,context,grant,lineage);budget.check()
                if not started:
                    try: require(self.record(result(Outcome.STARTED)) is None,Error.JOURNAL)
                    except Exception: raise ControlledFetchError(Error.JOURNAL) from None
                    outcome_ledger.started();started=True
                self.validate_admitted(plan,request,context,grant,lineage);budget.check()
                # Retire plan immediately before its one dispatch: copied/stale plans cannot replay.
                with self._lock:
                    self._admitted.pop(id(plan))
                    self._transport_leases[id(plan)][4]='DISPATCH_READY'
                outcome_ledger.dispatch();entered=True
                consumed=replace(consumed,hops=consumed.hops+1)
                hop=self.transport.dispatch(plan,budget)
                require(type(hop) is ControlledFetchHop,Error.RESPONSE)
                consumed=replace(consumed,header_bytes=consumed.header_bytes+hop.header_bytes+hop.request_header_bytes,
                                 response_bytes=consumed.response_bytes+len(hop.body))
                self.turn_budget.consume_bytes(hop.header_bytes+hop.request_header_bytes+len(hop.body),request)
                require(hop.header_bytes+hop.request_header_bytes+len(hop.body)<=plan.transfer_byte_allowance,Error.LIMIT)
                require(max(hop.header_bytes,hop.request_header_bytes)<=request.limits.max_header_bytes and len(hop.body)<=request.limits.max_response_bytes,Error.LIMIT)
                self._current(request,context);budget.check();self.issuer.validate_claimed(grant,grant.request)
                if request.method is Method.HEAD:require(not hop.body,Error.RESPONSE)
                if hop.status in (301,302,303,307,308):
                    require(hop.complete and index<request.limits.max_redirects,Error.REDIRECT)
                    candidate=self.redirect_candidate(target,hop.location)
                    # Check scope before replacing effective target; a rejected candidate stays private.
                    require(self.scope.covers(ResourceScope(ScopeKind.URL,candidate)),Error.AUTHORITY)
                    protect(candidate);target=candidate
                    consumed=replace(consumed,redirects=consumed.redirects+1)
                    continue
                require(200<=hop.status<300,Error.RESPONSE)
                payload,absence,truncated=self._payload(request,hop,redactor,budget)
                consumed=replace(consumed,published_chars=len(payload) if payload is not None else 0)
                budget.check();self._current(request,context);self.grant_request(request,context)
                mime=hop.content_type.split(';')[0].strip().lower()
                require((hop.status==204 and not mime) or bool(re.fullmatch('[a-z0-9.+-]+/[a-z0-9.+-]+',mime)),Error.FORMAT)
                terminal=result(Outcome.PARTIAL if truncated else Outcome.SUCCEEDED_OBSERVED,
                    payload=payload,absence=absence,truncated=truncated,mime=mime or None)
                try:require(self.record(terminal) is None,Error.JOURNAL)
                except Exception:
                    outcome_ledger.finish(Outcome.UNKNOWN)
                    return result(Outcome.UNKNOWN,error=Error.JOURNAL)
                outcome_ledger.finish(terminal.outcome)
                return terminal
            raise ControlledFetchError(Error.REDIRECT)
        except Exception as exc:
            evidence=exc.evidence if type(exc) is ControlledFetchTransportFailure else None
            if evidence is not None:
                lease=self._transport_leases.get(id(evidence.plan))
                require(evidence.transport is self.transport and lease is not None and lease[0] is evidence.plan and
                        evidence.plan.request is request and lease[4]=='DISPATCH_CLAIMED',Error.ADMISSION)
                consumed=replace(consumed,header_bytes=consumed.header_bytes+evidence.request_bytes_sent+evidence.response_header_bytes,
                                 response_bytes=consumed.response_bytes+evidence.response_body_bytes)
                try:self.turn_budget.consume_bytes(evidence.request_bytes_sent+evidence.response_header_bytes+evidence.response_body_bytes,request)
                except ControlledFetchError:pass
            code=exc.code if isinstance(exc,ControlledFetchError) else Error.AUTHORITY if isinstance(exc,SecurityError) else (
                Error.TIMEOUT if exc.code=='NETWORK_TIMEOUT' else Error.CANCELLED if exc.code=='NETWORK_CANCELLED'
                else Error.ADMISSION) if isinstance(exc,NetworkError) else Error.TRANSPORT
            # Once dispatch has been entered, no boolean/exception can invent proof of no effect.
            proven_zero=evidence is not None and evidence.request_bytes_sent==0
            terminal=result(Outcome.FAILED_NO_EFFECT_CONFIRMED if proven_zero else Outcome.UNKNOWN if entered else Outcome.FAILED_NO_EFFECT_CONFIRMED if started else Outcome.NOT_STARTED,error=code)
            outcome_ledger.finish(terminal.outcome,no_effect_evidence=evidence)
            try:self.record(terminal)
            except Exception:pass  # Return typed conservative result; never dispatch/retry to repair journal.
            return terminal
        finally:
            with self._lock:
                for plan in plans:
                    self._admitted.pop(id(plan),None)
                    self._transport_leases.pop(id(plan),None)
            self.turn_budget.end(request.operation_id)
