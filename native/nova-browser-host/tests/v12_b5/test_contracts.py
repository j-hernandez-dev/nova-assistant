"""Closed B5 descriptors/authority contracts; no native claim from doubles."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from dataclasses import replace
import pytest
from local_cli.application.browser_actions_v12_b5 import V12B5BrowserTool,SCHEMAS
from local_cli.application.policy import validate_arguments,PolicyInputError
from local_cli.core.contracts import new_operation_id,new_turn_id,new_session_id,new_tool_call_id
from local_cli.core.browser_transfers_v12 import validate_binding,PROFILE,EFFECTS
from local_cli.core.browser_authority_v12 import FIELDS

@pytest.mark.parametrize('tool',['browser_upload','browser_download','browser_takeover'])
@pytest.mark.parametrize('field',['path','file_path','fileHandle','selector','Knowledge','cookies','profile','grant','approval',
    'ControlledFetchNetworkProofRef','ControlledFetchGrant','publicOnly','deadline','owner','taskId','maxBytes','genericJS'])
def test_no_model_file_path_or_reusable_authority(tool,field):
    args={'capabilityId':'INTERACTIVE_BROWSER_V1_2','browserSessionRef':'bws_'+'0'*32,'pageRef':'bwp_'+'0'*32}
    if tool=='browser_takeover':args['reason']='LOGIN'
    else:args.update(elementRef='bwe_'+'0'*32,observationRef='bwo_'+'0'*32,navigationEpoch=0,observationVersion=1)
    if tool=='browser_upload':args['fileRef']='bwf_'+'0'*32
    args[field]='model authority'
    with pytest.raises(PolicyInputError):validate_arguments(args,SCHEMAS[tool])

@pytest.mark.parametrize('name',['browser_form_submit','generic_command','eval','browser_execute_js'])
def test_no_submit_or_generic_expansion(name):
    with pytest.raises(PolicyInputError):V12B5BrowserTool(name)

def test_default_tools_still_not_productive():
    from local_cli.tools import get_default_tools
    assert not any(t.name.startswith('browser_') for t in get_default_tools())
    for name in SCHEMAS:
        tool=V12B5BrowserTool(name)
        assert 'NOT_PROVIDED' in tool.description and 'NOT_ENABLED' in tool.description
        with pytest.raises(PolicyInputError):tool.execute()

def binding(action):
    return dict(capabilityId='INTERACTIVE_BROWSER_V1_2',networkIsolation='NOT_PROVIDED',controlClass='HOST_UNISOLATED',profile=PROFILE,
        owner='ses_'+'0'*32,workspace='C:/bounded/fixture',taskId='task',taskAuthorityDigest='0'*64,turnId='turn_'+'0'*32,
        operationId='op_'+'0'*32,toolCallId='call',browserSessionRef='bws_'+'0'*32,pageRef='bwp_'+'0'*32,
        browserContextEpoch=1,navigationEpoch=1,documentIdentity='0'*64,observationRef='bwo_'+'0'*32,elementRef='bwe_'+'0'*32,
        observationVersion=1,targetFingerprint='0'*64,accessibleLabel='Fixture',actionKind=action,
        payloadDigest=None if action=='DOWNLOAD' else '0'*64,origin='https://fixture.invalid',destination='https://fixture.invalid/data.txt',
        effectClasses=list(EFFECTS[action]),policyRevision=1,deadline=(datetime.now(timezone.utc)+timedelta(seconds=20)).isoformat(),
        limits=dict(lifetime_seconds=180,action_timeout_seconds=25,navigation_timeout_seconds=20,cleanup_timeout_seconds=15,
            max_pages=3,max_actions_per_turn=25,max_navigations_per_turn=10),
        transferLimits=dict(maxBytes=4096,maxSelections=8,maxDownloads=4,maxMimeChars=128))

@pytest.mark.parametrize('action',['UPLOAD_FILE','DOWNLOAD','HUMAN_TAKEOVER'])
def test_transfer_binding_namespace_and_risk(action):
    value=binding(action)
    if action=='UPLOAD_FILE':
        selection={k:value[k] for k in ('workspace','taskId','operationId','turnId','browserSessionRef','pageRef','elementRef','observationRef','navigationEpoch','observationVersion','browserContextEpoch','targetFingerprint')}
        selection.update(schemaVersion=1,hostFileSelectionRef='bwf_'+'0'*32,filename='owned.txt',size=12,mime='text/plain',sha256='0'*64,
            identity='0'*64,revision='0'*64,ownerAgentSessionId=value['owner'],expiresAt=value['deadline'],selectedPathIdentity='0'*64,targetOrigin=value['origin'])
        value.update(upload=True,fileSelection=selection)
    if action=='DOWNLOAD':
        permit={k:value[k] for k in ('capabilityId','owner','workspace','taskId','operationId','browserSessionRef','pageRef','elementRef','observationRef','navigationEpoch','observationVersion','browserContextEpoch','deadline')}
        permit.update(maxBytes=4096,maxMimeChars=128,oneUse=True)
        value.update(download=True,downloadMaxBytes=4096,downloadPermit=permit)
    if action=='HUMAN_TAKEOVER':value.update(takeoverReason='LOGIN',elementRef=None,observationRef=None,observationVersion=None)
    assert validate_binding(value)['networkIsolation']=='NOT_PROVIDED'
    for field,replacement in [('networkIsolation','ENFORCED'),('capabilityId','CONTROLLED_FETCH_V1_2'),('effectClasses',['OBSERVE_ONLY'])]:
        corrupt=deepcopy(value);corrupt[field]=replacement
        with pytest.raises(ValueError):validate_binding(corrupt)
