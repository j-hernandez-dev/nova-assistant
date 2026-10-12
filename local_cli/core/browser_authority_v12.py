"""Closed internal V1.2 binding; not a model schema or a transferable grant."""
from local_cli.core.interactive_browser_v12 import INTERACTIVE_BROWSER_CAPABILITY_ID
from local_cli.core.contracts import json_safe_copy
from datetime import datetime
import math,re
from urllib.parse import urlsplit

PROFILE = 'IB_B4_WEBVIEW2_V5_FIXED_ACTIONS_WINDOWS_X64_V1'
FIELDS = frozenset(('capabilityId','networkIsolation','controlClass','profile','owner',
    'workspace','taskId','taskAuthorityDigest','turnId','operationId','toolCallId',
    'browserSessionRef','pageRef','browserContextEpoch','navigationEpoch','documentIdentity',
    'observationRef','elementRef','observationVersion','targetFingerprint','accessibleLabel',
    'actionKind','payloadDigest','origin','destination','effectClasses','policyRevision','deadline','limits'))


def validate_binding(data,*,profile=PROFILE,extensions=(),action_effects=None,nullable_target=False):
    value=json_safe_copy(data)
    if (set(value)!=FIELDS|set(extensions) or value['capabilityId']!=INTERACTIVE_BROWSER_CAPABILITY_ID or
        value['networkIsolation']!='NOT_PROVIDED' or value['controlClass']!='HOST_UNISOLATED' or
        value['profile']!=profile):
        raise ValueError('INVALID_BROWSER_ACTION_BINDING_V12')
    def need(condition):
        if not condition:raise ValueError('INVALID_BROWSER_ACTION_BINDING_V12')
    for field,prefix in (('owner','ses'),('turnId','turn'),('operationId','op'),('browserSessionRef','bws'),
        ('pageRef','bwp'),('observationRef','bwo'),('elementRef','bwe')):
        if nullable_target and field in ('observationRef','elementRef') and value[field] is None:continue
        need(type(value[field]) is str and re.fullmatch(prefix+'_[0-9a-f]{32}',value[field]) is not None)
    for field in ('taskAuthorityDigest','targetFingerprint','documentIdentity'):
        need(type(value[field]) is str and re.fullmatch('[0-9a-f]{64}',value[field]) is not None)
    for field in ('workspace','taskId','toolCallId'):
        need(type(value[field]) is str and bool(value[field].strip()))
    need(type(value['accessibleLabel']) is str and len(value['accessibleLabel'])<=512)
    for field in ('browserContextEpoch','navigationEpoch','observationVersion','policyRevision'):
        if nullable_target and field=='observationVersion' and value[field] is None:continue
        need(type(value[field]) is int and value[field]>= (1 if field=='policyRevision' else 0))
    catalog=action_effects or {'NAVIGATE':{'NAVIGATION_READ'},'CLICK':{'UNKNOWN_REMOTE_EFFECT'},'PRESS_KEY':{'UNKNOWN_REMOTE_EFFECT'},
        'INPUT_TEXT':{'DATA_DISCLOSURE','UNKNOWN_REMOTE_EFFECT'},'SELECT_OPTION':{'DATA_DISCLOSURE','UNKNOWN_REMOTE_EFFECT'}}
    need(value['actionKind'] in catalog)
    if value['actionKind'] in ('CLICK','DOWNLOAD'):need(value['payloadDigest'] is None)
    else:need(type(value['payloadDigest']) is str and re.fullmatch('[0-9a-f]{64}',value['payloadDigest']) is not None)
    need(type(value['effectClasses']) is list and bool(value['effectClasses']))
    effects=set(value['effectClasses'])
    expected=catalog[value['actionKind']]
    need(effects in (expected,expected|{'HIGH_IMPACT'}))
    for field in ('origin','destination'):
        if field=='destination' and value[field] is None:continue
        need(type(value[field]) is str)
        try:
            parts=urlsplit(value[field]);port=parts.port
            need(parts.scheme in ('http','https') and bool(parts.hostname) and parts.username is None and parts.password is None and not parts.fragment)
            if field=='origin':need(not parts.path and not parts.query)
        except (TypeError,ValueError):raise ValueError('INVALID_BROWSER_ACTION_BINDING_V12') from None
    need(type(value['deadline']) is str)
    try:need(datetime.fromisoformat(value['deadline']).tzinfo is not None)
    except ValueError:raise ValueError('INVALID_BROWSER_ACTION_BINDING_V12') from None
    limits=value['limits']
    times=('lifetime_seconds','action_timeout_seconds','navigation_timeout_seconds','cleanup_timeout_seconds')
    need(type(limits) is dict and set(limits)==set(times)|{'max_pages','max_actions_per_turn','max_navigations_per_turn'})
    for name in times:need(type(limits[name]) in (int,float) and math.isfinite(limits[name]) and limits[name]>0)
    for name,ceiling in (('max_pages',3),('max_actions_per_turn',25),('max_navigations_per_turn',10)):
        need(type(limits[name]) is int and 1<=limits[name]<=ceiling)
    # All values come from validated host context, lifecycle and ref registry.
    # This validator does not issue authority and has no wire constructor.
    return value
