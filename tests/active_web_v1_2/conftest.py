"""B1 contract-only doubles: no DNS/sockets/browser/credentials or native probe."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
import socket

import pytest

from local_cli.application.cancellation import CancellationController
from local_cli.application.controlled_fetch import ControlledFetchContext, ControlledFetchService, ControlledFetchTurnBudget
from local_cli.application.grants import GrantIssuer
from local_cli.application.policy import PolicyEngineV2
from local_cli.core.controlled_fetch import (
    CONTROLLED_FETCH_CAPABILITY_ID as CF, AdmittedControlledFetchRequest, ControlledFetchHop,
    ControlledFetchLimits, ControlledFetchOwner,
)
from local_cli.core.network import NetworkEndpoint
from local_cli.core.security import AuthorityCeiling, Capability, ControlClass, Permission, ResourceScope, ScopeKind


class Clock:
    def __init__(self): self.now = datetime.now(timezone.utc)
    def __call__(self): return self.now
    def advance(self, seconds): self.now += timedelta(seconds=seconds)


class ResolverDouble:
    def __init__(self): self.calls, self.answers, self.on_resolve = [], ('93.184.216.34',), None
    def resolve(self, host, port, budget):
        budget.check(); self.calls.append((host,port,budget,budget.end))
        if self.on_resolve: self.on_resolve()
        return tuple(NetworkEndpoint(ip,socket.AF_INET6 if ':' in ip else socket.AF_INET,port) for ip in self.answers)


class TransportDouble:
    def __init__(self, receipts):
        self.receipts, self.calls, self.plans = receipts, [], []
        self.hops, self.on_dispatch, self.validate_error = [], None, None

    def validate(self, plan):
        assert type(plan) is AdmittedControlledFetchRequest
        if self.validate_error: raise self.validate_error

    def dispatch(self, plan, budget):
        assert self.receipts and self.receipts[0].outcome.value == 'STARTED'
        budget.check(); self.calls.append((plan.request.method.value,plan.canonical_target,budget,budget.end))
        self.plans.append(plan)
        if self.on_dispatch: self.on_dispatch(plan,budget)
        if self.hops:
            item = self.hops.pop(0)
            if isinstance(item,Exception):raise item
            return item
        return ControlledFetchHop(200,'text/plain',b'' if plan.request.method.value=='HEAD' else b'hello',128,
                                  request_header_bytes=64)


@pytest.fixture(autouse=True)
def no_host_network(monkeypatch):
    def denied(*args,**kwargs):pytest.fail('B1 contract test attempted real DNS/socket')
    monkeypatch.setattr(socket,'socket',denied)
    monkeypatch.setattr(socket,'getaddrinfo',denied)


@pytest.fixture
def make_fetch(tmp_path):
    def make(*,method='GET',mode='TEXT',url='https://example.test/a',limits=None,transport=True):
        clock=Clock();limits=limits or ControlledFetchLimits();token=CancellationController()
        owner=ControlledFetchOwner('ses_'+uuid4().hex,str(tmp_path),'task_'+uuid4().hex)
        context=ControlledFetchContext(owner,'turn_'+uuid4().hex,'op_'+uuid4().hex,1,clock()+timedelta(seconds=30),token)
        scope=ResourceScope(ScopeKind.ORIGIN,'https://example.test')
        capability=Capability(Permission('network.fetch'),scope,ControlClass.APPLICATION_ENFORCED,
                              {'capabilityId':CF,'profile':'GET_HEAD_CONTRACT_ONLY'})
        ceiling=AuthorityCeiling('ceiling_cf_b1',1,(capability,))
        issuer=GrantIssuer(ceiling,policy_revision=1,clock=clock);policy=PolicyEngineV2()
        receipts=[];port=TransportDouble(receipts);resolver=ResolverDouble()
        turn=ControlledFetchTurnBudget(owner,context.turn_id,limits)
        service=ControlledFetchService(issuer=issuer,policy=policy,approved_scope=scope,turn_budget=turn,
            record=receipts.append,resolver=resolver,transport=port if transport else None,clock=clock)
        request=service.request_from_candidate(dict(capabilityId=CF,url=url,method=method,resultMode=mode),context)
        grant_request=service.grant_request(request,context);grant=issuer.issue(grant_request,token)
        return SimpleNamespace(service=service,request=request,context=context,issuer=issuer,grant_request=grant_request,
            grant=grant,policy=policy,clock=clock,token=token,scope=scope,turn=turn,limits=limits,
            receipts=receipts,port=port,resolver=resolver,owner=owner)
    return make
