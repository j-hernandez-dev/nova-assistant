"""Closed Core/Application contract tests only; never PUBLIC_ONLY certification."""
from dataclasses import replace
from datetime import timedelta
import json

import pytest

from local_cli.core.controlled_fetch import (
    CONTROLLED_FETCH_CAPABILITY_ID as CF, INTERACTIVE_BROWSER_CAPABILITY_ID,
    ControlledFetchError, ControlledFetchErrorCode as Error, ControlledFetchRequest,
    ControlledFetchLimits, ControlledFetchResult, ControlledFetchOutcome as Outcome,
    ControlledFetchOutcomeLedger, ControlledFetchMethod, ControlledFetchResultMode,
    ControlledFetchSecretRef, ControlledFetchNetworkProofRef, ControlledFetchFuturePost,
    ControlledFetchFutureDownload, controlled_fetch_capabilities,
    ControlledFetchOwner,
)
from local_cli.core.contracts import json_safe_copy


def rejection(code, fn, *args, **kwargs):
    with pytest.raises(ControlledFetchError) as caught:fn(*args,**kwargs)
    assert caught.value.code is code


def test_request_private_schema_round_trip(make_fetch):
    f=make_fetch();decoded=ControlledFetchRequest.from_dict(f.request.to_dict())
    assert decoded==f.request and 'canonical_target' not in repr(decoded)
    assert json.dumps(decoded.to_dict()) and type(decoded.method) is ControlledFetchMethod


@pytest.mark.parametrize('prefix',['bws_','bwp_','bwe_','bhi_'])
def test_browser_refs_cannot_be_used_as_fetch_owner(make_fetch,prefix):
    f=make_fetch();rejection(Error.OWNER,ControlledFetchOwner,prefix+'0'*32,f.owner.workspace,f.owner.task_id)


@pytest.mark.parametrize('field',['ip','endpoint','dns','NetworkProofRef','proxy','headers','Cookie','cookieJar',
    'BrowserSession','ElementRef','browserGrant','browserApproval','profile','loginSession','eval','callback','auth'])
def test_private_request_rejects_unknown_network_browser_or_authority_fields(make_fetch,field):
    f=make_fetch();data=f.request.to_dict();data[field]='model-supplied'
    rejection(Error.SCHEMA,ControlledFetchRequest.from_dict,data)


@pytest.mark.parametrize('field',['owner','workspace','task','turn','operationId','policyRevision','deadline',
    'limits','max_response_bytes','maxPublishedText','concurrency','ip','headers','Cookie','NetworkProofRef'])
def test_model_candidate_cannot_supply_host_fields_or_increase_ceilings(make_fetch,field):
    f=make_fetch();data={'capabilityId':CF,'url':f.request.canonical_target,'method':'GET','resultMode':'TEXT',field:999999999}
    rejection(Error.SCHEMA,f.service.request_from_candidate,data,f.context)


@pytest.mark.parametrize('capability',[INTERACTIVE_BROWSER_CAPABILITY_ID,'ACTIVE_WEB_V1','',None,True])
def test_wrong_capability_id_never_constructs_request(make_fetch,capability):
    f=make_fetch();data=f.request.to_dict();data['capabilityId']=capability
    rejection(Error.CAPABILITY,ControlledFetchRequest.from_dict,data)


@pytest.mark.parametrize('method',['POST','PUT','DELETE','CONNECT','OPTIONS','get','head',None,True,{}])
def test_only_get_head_are_initial_methods(make_fetch,method):
    f=make_fetch();data=f.request.to_dict();data['method']=method
    rejection(Error.METHOD,ControlledFetchRequest.from_dict,data)
    assert not f.port.calls


@pytest.mark.parametrize('mode',['BINARY','BINARY_DOWNLOAD','BROWSER','RENDERED_HTML','JAVASCRIPT',None])
def test_unimplemented_modes_are_typed_denials(make_fetch,mode):
    f=make_fetch();data=f.request.to_dict();data['resultMode']=mode
    rejection(Error.MODE,ControlledFetchRequest.from_dict,data)


@pytest.mark.parametrize('field,value',[('timeout_seconds',31),('timeout_seconds',True),('max_redirects',6),
    ('max_header_bytes',32769),('max_response_bytes',2097153),('max_published_chars',32769),
    ('per_turn_requests',9),('concurrency',3),('per_turn_bytes',50331649),('concurrency',0),('timeout_seconds',float('inf'))])
def test_limits_have_finite_non_boolean_architecture_ceilings(field,value):
    rejection(Error.LIMIT,replace,ControlledFetchLimits(),**{field:value})


@pytest.mark.parametrize('url',['https://EXAMPLE.test/a','https://example.test:443/a','http://127.1/',
    'http://2130706433/','http://0x7f000001/','http://0177.0.0.1/','file:///x','data:text/plain,x',
    'javascript:alert(1)','https://user:pass@example.test/','https://example.test/#fragment',
    'https://example..test/','https://-example.test/','https://example-.test/',
    'https://'+'x'*64+'.test/','https://example.test/\r\nHeader:x','https://example.test\\@localhost/'])
def test_private_request_requires_host_canonical_spelling_and_unambiguous_authority(make_fetch,url):
    f=make_fetch();data=f.request.to_dict();data['canonicalTarget']=url
    rejection(Error.URL,ControlledFetchRequest.from_dict,data)


def test_host_normalizes_candidate_then_later_admits_separately(make_fetch):
    f=make_fetch(url='https://EXAMPLE.test:443/a')
    assert f.request.canonical_target=='https://example.test/a' and not f.resolver.calls


@pytest.mark.parametrize('bad_deadline',[None,False,'not a date','2026-10-11T01:00:00'])
def test_request_deadline_schema_is_aware_datetime(make_fetch,bad_deadline):
    f=make_fetch();data=f.request.to_dict();data['deadline']=bad_deadline
    rejection(Error.SCHEMA,ControlledFetchRequest.from_dict,data)


def test_result_round_trip_contains_no_authority_or_network_internals(make_fetch):
    f=make_fetch(url='https://example.test/private-path?token=secret-value')
    result=f.service.execute(f.request,f.context,f.grant);wire=result.to_dict()
    assert ControlledFetchResult.from_dict(wire)==result
    encoded=json.dumps(wire)
    for private in ['private-path','secret-value','93.184.216.34','grant_','canonicalTarget','workspace','endpoint']:
        assert private not in encoded
    assert wire['retryAllowed'] is False and wire['provenance']['publicOnly']=='UNKNOWN'


@pytest.mark.parametrize('field',['browserGrant','nextCapability','activateBrowser','interactionApproval','NetworkProofRef',
    'authHeaders','credentials','proxyCredentials','filesystemPath','owner','Cookie'])
def test_result_cannot_encode_fallback_authority_or_private_material(make_fetch,field):
    f=make_fetch();wire=f.service.execute(f.request,f.context,f.grant).to_dict();wire[field]='forged'
    rejection(Error.SCHEMA,ControlledFetchResult.from_dict,wire)


@pytest.mark.parametrize('ref_type',[ControlledFetchSecretRef,ControlledFetchNetworkProofRef])
def test_host_refs_have_no_public_serializer_or_wire_constructor(ref_type):
    ref=ref_type()
    with pytest.raises(TypeError):json.dumps(ref)
    with pytest.raises(ValueError):json_safe_copy(ref)
    assert not hasattr(ref,'from_dict') and not hasattr(ref,'to_dict') and 'HOST_ONLY' in repr(ref)


def test_future_optional_contracts_exist_but_dispatch_is_unavailable(make_fetch):
    f=make_fetch();secret=f.service.refs.secret(f.request)
    post=ControlledFetchFuturePost(f.request.canonical_target,'a'*64,'application/json',20,secret)
    download=ControlledFetchFutureDownload()
    for optional in (post,secret,download):rejection(Error.OPTIONAL,f.service.execute,optional,f.context,f.grant)
    cap=controlled_fetch_capabilities()
    assert cap['available']['status']==cap['networkEgressControl']['status']==cap['publicOnly']['status']=='UNKNOWN'
    assert cap['POST']['value'] is cap['auth']['value'] is cap['binaryDownload']['value'] is False
    assert not cap['cookieJar'] and not cap['browserSessionImport'] and not f.port.calls


def test_outcome_ledger_requires_started_before_dispatch_and_terminal_once():
    ledger=ControlledFetchOutcomeLedger();rejection(Error.OUTCOME,ledger.dispatch)
    rejection(Error.OUTCOME,ledger.finish,Outcome.SUCCEEDED_OBSERVED)
    ledger.started();ledger.dispatch()
    for invalid in (Outcome.NOT_STARTED,Outcome.FAILED_NO_EFFECT_CONFIRMED):rejection(Error.OUTCOME,ledger.finish,invalid)
    ledger.finish(Outcome.UNKNOWN)
    rejection(Error.OUTCOME,ledger.started);rejection(Error.OUTCOME,ledger.dispatch)
    rejection(Error.OUTCOME,ledger.finish,Outcome.SUCCEEDED_OBSERVED)


def test_no_effect_after_started_requires_never_entering_dispatch():
    ledger=ControlledFetchOutcomeLedger();ledger.started();ledger.finish(Outcome.FAILED_NO_EFFECT_CONFIRMED)
    assert ledger.terminal and not ledger.entered_dispatch
