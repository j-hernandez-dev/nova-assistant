"""AW1 contracts against synthetic, deterministic resource adapter only."""
import ast
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta
import json
from pathlib import Path
from threading import Event, Thread

import pytest

from local_cli.application.active_web import BrowserSessionManager
from local_cli.application.cancellation import CancellationController
from local_cli.core.active_web import (
    BrowserPageState as PS, BrowserSessionState as SS, new_browser_page_ref,
    new_browser_session_ref, BrowserActionReceipt, BrowserActionKind, BrowserEffectClass,
    BrowserOutcomeState,
)
from local_cli.core.active_web_lifecycle import (
    BrowserLifecycleError, BrowserLifecycleErrorCode as Code, BrowserLimits, BrowserOwner,
)
from local_cli.core.contracts import (
    BrowserCapabilitySnapshot, EffectState, CapabilityStatus,
    new_session_id, new_turn_id, new_operation_id,
)
from tests.active_web_v1.fake_browser import Clock, DeterministicBrowserPort


def setup(**limit_changes):
    clock = Clock()
    port = DeterministicBrowserPort(clock)
    limits = replace(BrowserLimits(120, 10, 20, 5), **limit_changes)
    manager = BrowserSessionManager(port, limits=limits, now=clock)
    return manager, port, clock, BrowserOwner(new_session_id(), 'synthetic-workspace')


def opened(manager, owner, **kwargs):
    return manager.open(owner, turn_id=kwargs.pop('turn_id', new_turn_id()),
                        network_policy_id='host-policy-public-only',
                        capability_snapshot_id='synthetic-snapshot-unavailable', **kwargs)


def lease(manager, owner, session, **kwargs):
    return manager.begin_operation(owner, session.browser_session_ref,
        kwargs.pop('page_ref', session.page_refs[0]),
        turn_id=kwargs.pop('turn_id', new_turn_id()),
        operation_id=kwargs.pop('operation_id', new_operation_id()), **kwargs)


def assert_error(code, call):
    with pytest.raises(BrowserLifecycleError) as error:
        call()
    assert error.value.code is code
    assert str(error.value) == code.value


def test_open_domain_owner_refs_empty_page_and_frozen_snapshots():
    m, p, clock, owner = setup()
    s = opened(m, owner)
    assert s.owner == owner and s.state is SS.ACTIVE
    assert s.created_at == clock() and s.expires_at == clock() + timedelta(seconds=120)
    assert s.browser_context_epoch == 0 and s.authenticated_state == 'NONE'
    assert len(s.page_refs) == 1 and str(s.browser_session_ref).startswith('bws_')
    page = m.page(owner, s.browser_session_ref, s.page_refs[0])
    assert page.state is PS.ACTIVE and page.navigation_epoch == 0
    assert page.current_origin == page.sanitized_url == page.title == ''
    assert page.active_observation_ref is None
    assert [call[0] for call in p.calls] == ['create_context', 'create_page']
    for dto in (s, page):
        wire = json.loads(json.dumps(dto.to_dict()))
        assert wire['schemaVersion'] == 1
        assert not {'cookies','storageState','password','grant','selector','engineBinding'} & wire.keys()
        with pytest.raises(FrozenInstanceError):
            dto.state = SS.CLOSED
    s.to_dict()['pageRefs'].clear()
    assert s.page_refs


@pytest.mark.parametrize('change', ['session', 'workspace'])
def test_owner_and_workspace_mismatch_cannot_inspect_act_or_close(change):
    m, p, _, owner = setup(); s = opened(m, owner)
    foreign = replace(owner, **({'agent_session_id':new_session_id()} if change=='session'
                               else {'workspace_id':'another-workspace'}))
    before = list(p.calls)
    assert_error(Code.OWNER, lambda:m.session(foreign,s.browser_session_ref))
    assert_error(Code.OWNER, lambda:m.page(foreign,s.browser_session_ref,s.page_refs[0]))
    assert_error(Code.OWNER, lambda:lease(m,foreign,s))
    assert_error(Code.OWNER, lambda:m.close(foreign,s.browser_session_ref))
    if change=='workspace':
        assert_error(Code.OWNER, lambda:m.close_owner(foreign))
    assert p.calls == before


def test_unknown_and_cross_session_page_refs_never_rebind():
    m, p, _, owner = setup(); s = opened(m,owner)
    other = BrowserOwner(new_session_id(),'other-workspace'); t = opened(m,other)
    assert_error(Code.NOT_FOUND, lambda:m.session(owner,new_browser_session_ref()))
    assert_error(Code.NOT_FOUND, lambda:m.page(owner,s.browser_session_ref,new_browser_page_ref()))
    assert_error(Code.NOT_FOUND, lambda:lease(m,owner,s,page_ref=t.page_refs[0]))
    assert len(p.calls)==4


def test_one_session_per_agent_including_another_workspace():
    m,p,_,owner=setup();s=opened(m,owner)
    for actor in (owner,replace(owner,workspace_id='different')):
        assert_error(Code.QUOTA,lambda:opened(m,actor))
    assert len(p.calls)==2
    m.close(owner,s.browser_session_ref)
    t=opened(m,owner)
    assert t.browser_session_ref != s.browser_session_ref


def test_session_survives_turns_but_owner_close_is_terminal():
    m,p,_,owner=setup();s=opened(m,owner)
    for _ in range(3):
        l=lease(m,owner,s);m.finish_operation(owner,s.browser_session_ref,l)
    receipt=m.close_owner(owner)
    assert receipt.state is SS.CLOSED and receipt.context_confirmed
    assert m.session(owner,s.browser_session_ref).state is SS.CLOSED
    assert_error(Code.STATE,lambda:opened(m,owner))
    assert not p.contexts


def test_page_quota_includes_uncertain_pages_and_frees_only_confirmed_close():
    m,p,_,owner=setup();s=opened(m,owner)
    pages=[m.new_page(owner,s.browser_session_ref,turn_id=new_turn_id()) for _ in range(2)]
    assert len(m.session(owner,s.browser_session_ref).page_refs)==3
    assert_error(Code.QUOTA,lambda:m.new_page(owner,s.browser_session_ref,turn_id=new_turn_id()))
    p.page_confirmation=False
    assert m.close_page(owner,s.browser_session_ref,pages[0].page_ref).state is PS.CLEANUP_UNCONFIRMED
    assert_error(Code.QUOTA,lambda:m.new_page(owner,s.browser_session_ref,turn_id=new_turn_id()))
    p.page_confirmation=True
    assert m.close_page(owner,s.browser_session_ref,pages[0].page_ref).state is PS.CLOSED
    new=m.new_page(owner,s.browser_session_ref,turn_id=new_turn_id())
    assert new.page_ref not in s.page_refs and new.page_ref != pages[0].page_ref


@pytest.mark.parametrize('changes',[{'max_pages':4},{'max_pages':0},{'max_pages':True},
    {'max_actions_per_turn':26},{'max_navigations_per_turn':11},{'max_navigations_per_turn':False},
    {'lifetime_seconds':0},{'lifetime_seconds':float('inf')},
    {'action_timeout_seconds':float('nan')},{'navigation_timeout_seconds':-1},
    {'cleanup_timeout_seconds':True}])
def test_host_limits_can_reduce_but_never_exceed_hard_ceilings(changes):
    assert_error(Code.INVALID,lambda:setup(**changes))


def test_action_and_navigation_quotas_count_per_turn_not_generation():
    m,p,_,owner=setup();turn=new_turn_id();s=opened(m,owner,turn_id=turn)
    for _ in range(24):
        l=lease(m,owner,s,turn_id=turn);m.finish_operation(owner,s.browser_session_ref,l)
    assert_error(Code.QUOTA,lambda:lease(m,owner,s,turn_id=turn))
    turn=new_turn_id()
    for _ in range(10):
        l=lease(m,owner,s,turn_id=turn,navigation=True);m.finish_operation(owner,s.browser_session_ref,l)
    assert_error(Code.QUOTA,lambda:lease(m,owner,s,turn_id=turn,navigation=True))
    l=lease(m,owner,s,turn_id=turn);m.finish_operation(owner,s.browser_session_ref,l)
    assert len(p.calls)==2  # Leases are not an action execution bypass.


def test_reduced_quotas_are_enforced():
    m,_,_,owner=setup(max_pages=1,max_actions_per_turn=2,max_navigations_per_turn=1)
    turn=new_turn_id();s=opened(m,owner,turn_id=turn)
    l=lease(m,owner,s,turn_id=turn);m.finish_operation(owner,s.browser_session_ref,l)
    assert_error(Code.QUOTA,lambda:lease(m,owner,s,turn_id=turn))
    assert_error(Code.QUOTA,lambda:m.new_page(owner,s.browser_session_ref,turn_id=new_turn_id()))


def test_page_serialization_and_one_remote_effect_per_session():
    m,_,_,owner=setup();s=opened(m,owner)
    page=m.new_page(owner,s.browser_session_ref,turn_id=new_turn_id())
    l=lease(m,owner,s,remote_effect=True)
    assert_error(Code.BUSY,lambda:lease(m,owner,s))
    assert_error(Code.BUSY,lambda:lease(m,owner,s,page_ref=page.page_ref,remote_effect=True))
    other=lease(m,owner,s,page_ref=page.page_ref)
    m.finish_operation(owner,s.browser_session_ref,other)
    m.finish_operation(owner,s.browser_session_ref,l)
    assert_error(Code.STATE,lambda:lease(m,owner,s,operation_id=l.operation_id))


def test_cancel_turn_requests_no_rollback_preserves_session_and_slot_until_worker_terminal():
    m,p,clock,owner=setup();s=opened(m,owner);turn=new_turn_id()
    l=lease(m,owner,s,turn_id=turn,remote_effect=True)
    outcome=BrowserActionReceipt(l.operation_id,turn,s.browser_session_ref,s.page_refs[0],
        BrowserActionKind.FORM_SUBMIT,(BrowserEffectClass.REMOTE_MUTATION,),
        BrowserOutcomeState.UNKNOWN,EffectState.UNKNOWN,clock())
    c=m.cancel_turn(owner,s.browser_session_ref,turn)
    assert l.cancellation.is_cancel_requested()
    assert c.requested_operations==c.acknowledged_operations==(l.operation_id,)
    assert not c.to_dict()['rollback'] and outcome.outcome is BrowserOutcomeState.UNKNOWN
    assert m.session(owner,s.browser_session_ref).state is SS.ACTIVE
    assert_error(Code.BUSY,lambda:lease(m,owner,s))
    m.finish_operation(owner,s.browser_session_ref,l)
    assert_error(Code.CANCELLED,lambda:lease(m,owner,s,turn_id=turn))
    next_lease=lease(m,owner,s);assert not next_lease.cancellation.is_cancel_requested()
    assert [c[0] for c in p.calls].count('create_context')==1


@pytest.mark.parametrize('confirmation',[False,'yes',1])
def test_cancel_ack_is_not_inferred_from_truthy_values(confirmation):
    m,p,_,owner=setup();s=opened(m,owner);turn=new_turn_id();lease(m,owner,s,turn_id=turn)
    p.cancel_confirmation=confirmation
    c=m.cancel_turn(owner,s.browser_session_ref,turn)
    assert c.requested_operations and not c.acknowledged_operations


def test_parent_cancellation_reuses_core_hierarchy_without_cancelling_future_turns():
    m,_,_,owner=setup();s=opened(m,owner);parent=CancellationController()
    l=lease(m,owner,s,cancellation=parent);parent.request()
    assert l.cancellation.is_cancel_requested()
    m.finish_operation(owner,s.browser_session_ref,l)
    assert_error(Code.CANCELLED,lambda:lease(m,owner,s,cancellation=parent))
    assert not lease(m,owner,s).cancellation.is_cancel_requested()


def test_cancelled_open_never_allocates_and_deadline_equal_now_is_immediate():
    m,p,clock,owner=setup();token=CancellationController();token.request()
    assert_error(Code.CANCELLED,lambda:opened(m,owner,cancellation=token))
    assert_error(Code.DEADLINE,lambda:opened(m,owner,deadline=clock()))
    assert not p.calls


def test_deadlines_are_bounded_by_host_request_and_session_expiry():
    m,p,clock,owner=setup(lifetime_seconds=7);s=opened(m,owner)
    assert all(c[3] <= s.expires_at for c in p.calls)
    l=lease(m,owner,s,navigation=True,deadline=clock()+timedelta(seconds=3))
    assert l.deadline==clock()+timedelta(seconds=3)
    m.finish_operation(owner,s.browser_session_ref,l)
    l=lease(m,owner,s,navigation=True)
    assert l.deadline==s.expires_at
    clock.advance(7)
    assert_error(Code.EXPIRED,lambda:lease(m,owner,s))
    assert l.cancellation.is_cancel_requested()
    receipts=m.expire()
    assert receipts[0].state is SS.CLOSED and not p.contexts


@pytest.mark.parametrize('method',['create_context','create_page'])
def test_create_failure_is_typed_and_partial_resources_are_cleaned(method):
    m,p,_,owner=setup()
    def fault(*_):raise RuntimeError('synthetic-secret-from-backend')
    p.hooks[method]=fault
    assert_error(Code.PORT,lambda:opened(m,owner))
    assert not p.contexts
    assert [call[0] for call in p.calls].count('close_context')==1
    p.hooks.clear();assert opened(m,owner).state is SS.ACTIVE


def test_new_page_failure_does_not_destroy_coherent_session():
    m,p,_,owner=setup();s=opened(m,owner)
    def fault(*_):raise RuntimeError('synthetic corrupt page creation')
    p.hooks['create_page']=fault
    assert_error(Code.PORT,lambda:m.new_page(owner,s.browser_session_ref,turn_id=new_turn_id()))
    assert m.session(owner,s.browser_session_ref).page_refs==s.page_refs
    assert m.session(owner,s.browser_session_ref).state is SS.ACTIVE


def test_cleanup_confirmed_idempotent_and_never_rollback():
    m,p,_,owner=setup();s=opened(m,owner)
    receipt=m.close(owner,s.browser_session_ref);calls=list(p.calls)
    assert receipt.state is SS.CLOSED and receipt.context_confirmed and not receipt.pending_work
    assert receipt.confirmed_pages==s.page_refs and not receipt.unconfirmed_pages
    assert not receipt.to_dict()['rollback']
    assert m.close(owner,s.browser_session_ref)==receipt and p.calls==calls
    assert_error(Code.STATE,lambda:lease(m,owner,s))


@pytest.mark.parametrize('confirmation',[False,None,1,'confirmed'])
def test_uncertain_cleanup_not_closed_and_blocks_replacement(confirmation):
    m,p,_,owner=setup();s=opened(m,owner);p.context_confirmation=confirmation
    receipt=m.close(owner,s.browser_session_ref)
    assert receipt.state is SS.CLEANUP_UNCONFIRMED and not receipt.context_confirmed
    assert_error(Code.QUOTA,lambda:opened(m,owner))
    before=list(p.calls);assert m.session(owner,s.browser_session_ref).state is SS.CLEANUP_UNCONFIRMED
    assert p.calls==before  # No background retry/polling.
    p.context_confirmation=True
    assert m.close(owner,s.browser_session_ref).state is SS.CLOSED  # Explicit new proof.


def test_context_confirmation_covers_children_even_when_page_cleanup_failed():
    m,p,_,owner=setup();s=opened(m,owner)
    def fault(*_):raise RuntimeError('synthetic page close failure')
    p.hooks['close_page']=fault
    assert m.close(owner,s.browser_session_ref).state is SS.CLOSED
    assert m.page(owner,s.browser_session_ref,s.page_refs[0]).state is PS.CLOSED
    assert not p.contexts


def test_cleanup_timeout_is_not_confirmation_even_with_late_true():
    m,p,clock,owner=setup();s=opened(m,owner)
    def delay(*_):clock.advance(6)
    p.hooks['close_context']=delay
    receipt=m.close(owner,s.browser_session_ref)
    assert receipt.state is SS.CLEANUP_UNCONFIRMED and not receipt.context_confirmed


def test_crash_failed_state_preserved_until_explicit_cleanup_no_relaunch():
    m,p,_,owner=setup();s=opened(m,owner);l=lease(m,owner,s,remote_effect=True)
    assert m.fail(owner,s.browser_session_ref).state is SS.FAILED
    assert l.cancellation.is_cancel_requested()
    assert_error(Code.STATE,lambda:lease(m,owner,s))
    assert len(p.calls)==2
    assert m.close(owner,s.browser_session_ref).state is SS.CLOSED


def test_shutdown_closes_all_owners_and_restart_cannot_resume_old_refs():
    m,p,clock,owner=setup();s=opened(m,owner)
    second=BrowserOwner(new_session_id(),'second');opened(m,second)
    assert len(m.shutdown())==2 and not p.contexts
    assert_error(Code.STATE,lambda:opened(m,owner))
    fresh=BrowserSessionManager(DeterministicBrowserPort(clock),limits=m.limits,now=clock)
    assert_error(Code.NOT_FOUND,lambda:fresh.session(owner,s.browser_session_ref))
    assert opened(fresh,owner).browser_session_ref != s.browser_session_ref


def test_concurrent_open_reserves_owner_before_port_and_close_waits_for_pending_work():
    m,p,_,owner=setup();entered=Event();release=Event();results=[]
    def blocking(session,page,token):
        entered.set();assert release.wait(3)
    p.hooks['create_context']=blocking
    def worker():
        try:opened(m,owner)
        except BrowserLifecycleError as error:results.append(error.code)
    thread=Thread(target=worker);thread.start()
    try:
        assert entered.wait(3)
        assert_error(Code.QUOTA,lambda:opened(m,owner))
        receipt=m.close_owner(owner)
        assert receipt.state is SS.CLEANUP_UNCONFIRMED and receipt.pending_work
        assert [call[0] for call in p.calls]==['create_context']
    finally:
        release.set();thread.join(3)
    assert not thread.is_alive() and results==[Code.CANCELLED]
    assert not p.contexts
    assert m.session(owner,receipt.browser_session_ref).state is SS.CLOSED


def test_concurrent_page_creation_reserves_quota_and_no_late_page_resurrection():
    m,p,_,owner=setup(max_pages=2);s=opened(m,owner);entered=Event();release=Event();results=[]
    def blocking(*_):entered.set();assert release.wait(3)
    p.hooks['create_page']=blocking
    def worker():
        try:m.new_page(owner,s.browser_session_ref,turn_id=new_turn_id())
        except BrowserLifecycleError as error:results.append(error.code)
    thread=Thread(target=worker);thread.start()
    try:
        assert entered.wait(3)
        assert_error(Code.QUOTA,lambda:m.new_page(owner,s.browser_session_ref,turn_id=new_turn_id()))
        receipt=m.close(owner,s.browser_session_ref)
        assert receipt.pending_work and receipt.state is SS.CLEANUP_UNCONFIRMED
    finally:
        release.set();thread.join(3)
    assert results==[Code.CANCELLED] and not thread.is_alive()
    assert not p.contexts and m.session(owner,s.browser_session_ref).state is SS.CLOSED


def test_domain_and_port_do_not_import_engine_or_create_a_new_authority_path():
    root=Path(__file__).resolve().parents[2]
    tree=ast.parse((root/'local_cli/core/active_web_lifecycle.py').read_text())
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom) and node.module.startswith('local_cli'):
            assert node.module.startswith('local_cli.core.')
    assert BrowserCapabilitySnapshot().available.status is CapabilityStatus.UNKNOWN
    assert not any(hasattr(BrowserSessionManager,name) for name in
        ('navigate','act','observe','grant','approve','takeover','upload','download'))


def test_creating_and_closing_are_observable_and_distinct_from_success():
    m,p,_,owner=setup();seen=[]
    def creating(session,*_):seen.append(m.session(owner,session).state)
    def closing(session,*_):seen.append(m.session(owner,session).state)
    p.hooks['create_context']=creating;p.hooks['close_context']=closing
    s=opened(m,owner);m.close(owner,s.browser_session_ref)
    assert seen==[SS.CREATING,SS.CLOSING]


def test_partial_context_allocation_before_exception_is_never_leaked_or_retried():
    m,p,_,owner=setup()
    def partial(session,*_):
        p.contexts[session]=set()
        raise RuntimeError('synthetic partial context')
    p.hooks['create_context']=partial
    assert_error(Code.PORT,lambda:opened(m,owner))
    assert [call[0] for call in p.calls]==['create_context','close_context']
    assert not p.contexts


def test_cancel_pending_page_preserves_coherent_parent_for_next_turn():
    m,p,_,owner=setup();s=opened(m,owner);turn=new_turn_id()
    def cancel(session,*_):m.cancel_turn(owner,session,turn)
    p.hooks['create_page']=cancel
    assert_error(Code.CANCELLED,lambda:m.new_page(owner,s.browser_session_ref,turn_id=turn))
    assert m.session(owner,s.browser_session_ref).state is SS.ACTIVE
    assert m.session(owner,s.browser_session_ref).page_refs==s.page_refs
    p.hooks.clear()
    assert m.new_page(owner,s.browser_session_ref,turn_id=new_turn_id()).state is PS.ACTIVE


def test_close_during_pending_page_does_not_publish_late_active_page():
    m,p,_,owner=setup();s=opened(m,owner);seen=[]
    def closing(session,page,*_):seen.append(m.close_page(owner,session,page).state)
    p.hooks['create_page']=closing
    assert_error(Code.CANCELLED,lambda:m.new_page(owner,s.browser_session_ref,turn_id=new_turn_id()))
    assert seen==[PS.CLEANUP_UNCONFIRMED]
    assert m.session(owner,s.browser_session_ref).page_refs==s.page_refs
    assert p.contexts[s.browser_session_ref]==set(s.page_refs)


def test_port_ignoring_create_deadline_cannot_publish_success():
    m,p,clock,owner=setup()
    def late(session,*,deadline,cancellation):
        p.contexts[session]=set();clock.advance(11)
    p.create_context=late
    assert_error(Code.DEADLINE,lambda:opened(m,owner))
    assert not p.contexts


def test_late_close_true_cannot_be_presented_as_timely_confirmation():
    m,p,clock,owner=setup();s=opened(m,owner)
    def late(session,*,deadline):clock.advance(6);return True
    p.close_context=late
    receipt=m.close(owner,s.browser_session_ref)
    assert receipt.state is SS.CLEANUP_UNCONFIRMED and not receipt.context_confirmed


def test_concurrent_close_is_single_flight_and_page_cleanup_never_resurrects_parent():
    m,p,_,owner=setup();s=opened(m,owner);entered=Event();release=Event();receipts=[]
    def blocking(*_):entered.set();assert release.wait(3)
    p.hooks['close_page']=blocking
    worker=Thread(target=lambda:receipts.append(m.close_page(owner,s.browser_session_ref,s.page_refs[0])))
    worker.start()
    try:
        assert entered.wait(3)
        assert_error(Code.BUSY,lambda:m.close_page(owner,s.browser_session_ref,s.page_refs[0]))
        receipt=m.close(owner,s.browser_session_ref)
        assert receipt.state is SS.CLEANUP_UNCONFIRMED and receipt.pending_work
    finally:
        release.set();worker.join(3)
    assert not worker.is_alive() and receipts[0].state is PS.CLOSED
    p.hooks.clear()
    assert m.close(owner,s.browser_session_ref).state is SS.CLOSED


@pytest.mark.parametrize('method',['cancel_page','close_context'])
def test_backend_errors_only_remove_acknowledgement_not_honesty(method):
    m,p,_,owner=setup();s=opened(m,owner)
    def fault(*_):raise RuntimeError('synthetic-private-backend-message')
    p.hooks[method]=fault
    if method=='cancel_page':
        turn=new_turn_id();l=lease(m,owner,s,turn_id=turn)
        c=m.cancel_turn(owner,s.browser_session_ref,turn)
        assert not c.acknowledged_operations and l.cancellation.is_cancel_requested()
    else:
        assert m.close(owner,s.browser_session_ref).state is SS.CLEANUP_UNCONFIRMED


def test_subagent_identity_cannot_steal_parent_browser_ownership():
    m,p,_,owner=setup();s=opened(m,owner)
    child=BrowserOwner(new_session_id(),owner.workspace_id)
    assert_error(Code.OWNER,lambda:lease(m,child,s))
    assert_error(Code.OWNER,lambda:m.cancel_turn(child,s.browser_session_ref,new_turn_id()))
    assert len(p.calls)==2


def test_cancel_repeat_does_not_release_operation_or_reopen_session():
    m,p,_,owner=setup();s=opened(m,owner);turn=new_turn_id();l=lease(m,owner,s,turn_id=turn)
    first=m.cancel_turn(owner,s.browser_session_ref,turn)
    assert m.cancel_turn(owner,s.browser_session_ref,turn)==first
    assert_error(Code.BUSY,lambda:lease(m,owner,s))
    m.finish_operation(owner,s.browser_session_ref,l)
    assert m.session(owner,s.browser_session_ref).state is SS.ACTIVE


@pytest.mark.parametrize('value',['#page','bwp_short',True,[],None])
def test_malformed_resource_refs_fail_typed_before_adapter(value):
    m,p,_,owner=setup();s=opened(m,owner);before=list(p.calls)
    assert_error(Code.INVALID,lambda:m.session(owner,value))
    assert_error(Code.INVALID,lambda:m.page(owner,s.browser_session_ref,value))
    assert p.calls==before
