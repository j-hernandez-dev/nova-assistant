"""V1.2 transfer extension of the exact B4 binding. No ambient authority."""
from local_cli.core.browser_authority_v12 import validate_binding as validate_base
import re
from datetime import datetime

PROFILE='IB_B5_WEBVIEW2_V5_TRANSFERS_TAKEOVER_KNOWN_VALUES_WINDOWS_X64_V1'
EFFECTS={'NAVIGATE':{'NAVIGATION_READ'},'CLICK':{'UNKNOWN_REMOTE_EFFECT'},'PRESS_KEY':{'UNKNOWN_REMOTE_EFFECT'},
    'INPUT_TEXT':{'DATA_DISCLOSURE','UNKNOWN_REMOTE_EFFECT'},'SELECT_OPTION':{'DATA_DISCLOSURE','UNKNOWN_REMOTE_EFFECT'},
    'UPLOAD_FILE':{'FILE_UPLOAD','DATA_DISCLOSURE','REMOTE_MUTATION'},'DOWNLOAD':{'FILE_DOWNLOAD'},'HUMAN_TAKEOVER':{'AUTH_SESSION_CHANGE'}}

def validate_binding(value):
    action=value.get('actionKind')
    extras={'transferLimits'}
    if action=='UPLOAD_FILE':extras|={'upload','fileSelection'}
    if action=='DOWNLOAD':extras|={'download','downloadMaxBytes','downloadPermit'}
    if action=='HUMAN_TAKEOVER':extras|={'takeoverReason'}
    result=validate_base(value,profile=PROFILE,extensions=extras,action_effects=EFFECTS,nullable_target=action=='HUMAN_TAKEOVER')
    limits=result['transferLimits']
    if type(limits) is not dict or set(limits)!= {'maxBytes','maxSelections','maxDownloads','maxMimeChars'} or any(type(v) is not int or v<=0 for v in limits.values()):
        raise ValueError('INVALID_V12_TRANSFER_LIMITS')
    if limits['maxMimeChars']>128:raise ValueError('INVALID_V12_TRANSFER_LIMITS')
    if action=='UPLOAD_FILE' and (result['upload'] is not True or type(result['fileSelection']) is not dict):raise ValueError('INVALID_V12_SELECTION_BINDING')
    if action=='DOWNLOAD' and (result['download'] is not True or result['downloadMaxBytes']!=limits['maxBytes'] or type(result['downloadPermit']) is not dict):raise ValueError('INVALID_V12_DOWNLOAD_BINDING')
    if action=='HUMAN_TAKEOVER' and result['takeoverReason'] not in ('LOGIN','CAPTCHA','USER_INTERACTION'):raise ValueError('INVALID_V12_TAKEOVER_REASON')
    if action=='UPLOAD_FILE':
        selection=result['fileSelection']
        expected={'schemaVersion','hostFileSelectionRef','browserSessionRef','filename','size','mime','sha256','identity','revision',
            'ownerAgentSessionId','workspace','taskId','operationId','turnId','pageRef','elementRef','observationRef','navigationEpoch',
            'observationVersion','browserContextEpoch','expiresAt','selectedPathIdentity','targetOrigin','targetFingerprint'}
        if set(selection)!=expected or selection['schemaVersion']!=1:raise ValueError('INVALID_V12_SELECTION_BINDING')
        equality={'ownerAgentSessionId':'owner','workspace':'workspace','taskId':'taskId','operationId':'operationId','turnId':'turnId',
            'browserSessionRef':'browserSessionRef','pageRef':'pageRef','elementRef':'elementRef','observationRef':'observationRef',
            'navigationEpoch':'navigationEpoch','observationVersion':'observationVersion','browserContextEpoch':'browserContextEpoch',
            'targetOrigin':'origin','targetFingerprint':'targetFingerprint'}
        if any(selection[k]!=result[v] for k,v in equality.items()):raise ValueError('V12_SELECTION_SCOPE_MISMATCH')
        for key in ('sha256','identity','revision','selectedPathIdentity'):
            if type(selection[key]) is not str or re.fullmatch('[0-9a-f]{64}',selection[key]) is None:raise ValueError('INVALID_V12_SELECTION_BINDING')
        if type(selection['size']) is not int or not 0<=selection['size']<=limits['maxBytes']:raise ValueError('INVALID_V12_SELECTION_BINDING')
        if type(selection['mime']) is not str or len(selection['mime'])>128 or re.fullmatch('[a-zA-Z0-9.+-]+/[a-zA-Z0-9.+-]+',selection['mime']) is None:raise ValueError('INVALID_V12_SELECTION_BINDING')
        if type(selection['filename']) is not str or not 0<len(selection['filename'])<=255 or selection['filename'] in ('.','..') or any(c in selection['filename'] for c in '/\\:\x00\r\n'):raise ValueError('INVALID_V12_SELECTION_BINDING')
        if type(selection['hostFileSelectionRef']) is not str or re.fullmatch('bwf_[0-9a-f]{32}',selection['hostFileSelectionRef']) is None:raise ValueError('INVALID_V12_SELECTION_BINDING')
        if datetime.fromisoformat(selection['expiresAt']).tzinfo is None:raise ValueError('INVALID_V12_SELECTION_BINDING')
    if action=='DOWNLOAD':
        permit=result['downloadPermit']
        expected={'capabilityId','owner','workspace','taskId','operationId','browserSessionRef','pageRef','elementRef','observationRef',
            'navigationEpoch','observationVersion','browserContextEpoch','deadline','maxBytes','maxMimeChars','oneUse'}
        if set(permit)!=expected or permit['oneUse'] is not True or permit['maxBytes']!=limits['maxBytes'] or permit['maxMimeChars']!=128:
            raise ValueError('INVALID_V12_DOWNLOAD_BINDING')
        if any(permit[k]!=result[k] for k in expected-{'oneUse','maxBytes','maxMimeChars'}):raise ValueError('V12_DOWNLOAD_SCOPE_MISMATCH')
    return result
