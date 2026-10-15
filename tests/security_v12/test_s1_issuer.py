"""S1 logical authority adversarial tests; no dispatcher or host effects.

Application owns the issuer. These tests exercise in-process registry and
binding guarantees, not an OS security boundary against hostile Python code.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest

from local_cli.application.grants import GrantIssuer
from local_cli.core.security import (
    AuthorityCeiling, Capability, ControlClass, GrantLifetime, GrantRequest,
    GrantSubject, Permission, ResourceScope, ScopeKind, SecurityError,
    SecurityErrorCode,
)


@dataclass
class Clock:
    now: datetime

    def __call__(self):
        return self.now


@dataclass
class Token:
    cancelled: bool = False

    def is_cancel_requested(self):
        return self.cancelled


@pytest.fixture
def authority():
    clock = Clock(datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc))
    read = Capability(
        Permission("application.state.read"),
        ResourceScope(ScopeKind.SESSION, "ses_s1"),
        ControlClass.APPLICATION_ENFORCED,
    )
    write = Capability(
        Permission("application.state.write"),
        ResourceScope(ScopeKind.SESSION, "ses_s1"),
        ControlClass.APPLICATION_ENFORCED,
    )
    ceiling = AuthorityCeiling("ceiling_s1", 1, (read, write))
    issuer = GrantIssuer(ceiling, policy_revision=1, clock=clock)
    lifetime = GrantLifetime(
        clock.now - timedelta(seconds=1), clock.now + timedelta(seconds=60),
    )
    request = GrantRequest(
        subject=GrantSubject("ses_s1", "turn_s1", "op_s1", "tool_s1"),
        tool_name="todo_write", arguments={"items": [{"text": "dummy"}]},
        capabilities=(write,), workspace="C:\\S1Artificial", cwd="C:\\S1Artificial",
        action="write_session_state", policy_revision=1,
        ceiling_id=ceiling.ceiling_id, ceiling_revision=ceiling.revision,
        ceiling_fingerprint=ceiling.fingerprint, lifetime=lifetime,
        environment_intent={"mode": "none"}, network_intent={"mode": "none"},
        effect_classification="session_state_mutation",
    )
    return issuer, request, Token(), clock, ceiling, read, write


def expect_code(code, function, *args):
    with pytest.raises(SecurityError) as rejected:
        function(*args)
    assert rejected.value.code is code


def test_registered_grant_is_one_shot(authority):
    issuer, request, token, *_ = authority
    grant = issuer.issue(request, token)
    assert issuer.claim(grant, request) is grant
    expect_code(SecurityErrorCode.GRANT_CONSUMED, issuer.claim, grant, request)


def test_equal_dataclass_clone_is_not_registered_authority(authority):
    issuer, request, token, *_ = authority
    grant = issuer.issue(request, token)
    clone = replace(grant)
    assert clone == grant and clone is not grant
    expect_code(SecurityErrorCode.GRANT_UNKNOWN, issuer.claim, clone, request)
    assert issuer.claim(grant, request) is grant


def test_unknown_grant_id_never_authorizes(authority):
    issuer, request, token, *_ = authority
    grant = issuer.issue(request, token)
    forged = replace(grant, grant_id="grant_not_issued")
    expect_code(SecurityErrorCode.GRANT_UNKNOWN, issuer.claim, forged, request)


def test_another_issuer_cannot_claim_registered_grant(authority):
    issuer, request, token, clock, ceiling, *_ = authority
    grant = issuer.issue(request, token)
    other = GrantIssuer(ceiling, policy_revision=1, clock=clock)
    expect_code(SecurityErrorCode.GRANT_UNKNOWN, other.claim, grant, request)


@pytest.mark.parametrize("field,value", [
    ("session_id", "ses_other"), ("turn_id", "turn_other"),
    ("operation_id", "op_other"), ("tool_call_id", "tool_other"),
    ("agent_id", "agent_other"), ("parent_operation_id", "op_parent_other"),
    ("parent_agent_id", "agent_parent_other"),
])
def test_each_subject_binding_mismatch_rejected_without_consumption(authority, field, value):
    issuer, request, token, *_ = authority
    grant = issuer.issue(request, token)
    changes = {field: value}
    if field == "parent_agent_id":
        changes["parent_operation_id"] = "op_parent_other"
    mismatch = replace(request, subject=replace(request.subject, **changes))
    with pytest.raises(SecurityError):
        issuer.claim(grant, mismatch)
    assert issuer.claim(grant, request) is grant


@pytest.mark.parametrize("field,value", [
    ("tool_name", "ask_user"), ("arguments", {"items": [{"text": "changed"}]}),
    ("workspace", "C:\\"), ("cwd", "C:\\S1Artificial\\child"),
    ("action", "read_session_state"), ("effect_classification", "read_only"),
    ("environment_intent", {"mode": "changed"}),
    ("network_intent", {"mode": "changed"}),
    ("policy_revision", 2), ("ceiling_id", "ceiling_other"),
    ("ceiling_revision", 2), ("ceiling_fingerprint", "0" * 64),
])
def test_each_request_binding_mismatch_rejected_without_consumption(authority, field, value):
    issuer, request, token, *_ = authority
    grant = issuer.issue(request, token)
    mismatch = replace(request, **{field: value})
    with pytest.raises(SecurityError):
        issuer.claim(grant, mismatch)
    assert issuer.claim(grant, request) is grant


def test_lifetime_binding_mismatch_rejected_without_consumption(authority):
    issuer, request, token, *_ = authority
    grant = issuer.issue(request, token)
    lifetime = replace(request.lifetime,
                       expires_at=request.lifetime.expires_at - timedelta(seconds=1))
    expect_code(SecurityErrorCode.REQUEST_MISMATCH, issuer.claim,
                grant, replace(request, lifetime=lifetime))
    assert issuer.claim(grant, request) is grant


def test_capability_binding_mismatch_rejected_without_consumption(authority):
    issuer, request, token, _, _, read, _ = authority
    grant = issuer.issue(request, token)
    expect_code(SecurityErrorCode.REQUEST_MISMATCH, issuer.claim,
                grant, replace(request, capabilities=(read,)))
    assert issuer.claim(grant, request) is grant


def test_issue_refuses_authority_outside_host_ceiling(authority):
    issuer, request, token, *_ = authority
    extra = replace(request.capabilities[0], permission=Permission("application.state.delete"))
    expect_code(SecurityErrorCode.AUTHORITY_EXCEEDED, issuer.issue,
                replace(request, capabilities=(extra,)), token)


@pytest.mark.parametrize("field,value", [
    ("policy_revision", 2), ("ceiling_revision", 2),
    ("ceiling_id", "ceiling_other"), ("ceiling_fingerprint", "0" * 64),
])
def test_issue_refuses_stale_revision_or_ceiling_binding(authority, field, value):
    issuer, request, token, *_ = authority
    with pytest.raises(SecurityError):
        issuer.issue(replace(request, **{field: value}), token)


def test_revoked_grant_cannot_be_claimed(authority):
    issuer, request, token, *_ = authority
    grant = issuer.issue(request, token)
    issuer.revoke(grant)
    expect_code(SecurityErrorCode.GRANT_REVOKED, issuer.claim, grant, request)


def test_cancelled_token_before_issue_rejected(authority):
    issuer, request, token, *_ = authority
    token.cancelled = True
    expect_code(SecurityErrorCode.GRANT_CANCELLED, issuer.issue, request, token)


def test_cancelled_token_after_issue_rejected(authority):
    issuer, request, token, *_ = authority
    grant = issuer.issue(request, token)
    token.cancelled = True
    expect_code(SecurityErrorCode.GRANT_CANCELLED, issuer.claim, grant, request)


@pytest.mark.parametrize("bad_result", [None, 0, 1, "false"])
def test_cancellation_port_unknown_shape_fails_closed(authority, bad_result):
    issuer, request, token, *_ = authority
    grant = issuer.issue(request, token)
    token.is_cancel_requested = lambda: bad_result
    expect_code(SecurityErrorCode.INVALID_CONTRACT, issuer.claim, grant, request)


def test_cancellation_port_exception_is_typed_fail_closed(authority):
    issuer, request, token, *_ = authority
    grant = issuer.issue(request, token)

    def unavailable():
        raise RuntimeError("dummy fixture error")

    token.is_cancel_requested = unavailable
    expect_code(SecurityErrorCode.INVALID_CONTRACT, issuer.claim, grant, request)


def test_cancel_session_invalidates_existing_grant(authority):
    issuer, request, token, *_ = authority
    grant = issuer.issue(request, token)
    issuer.cancel_session(request.subject.session_id)
    expect_code(SecurityErrorCode.GRANT_CANCELLED, issuer.claim, grant, request)


def test_cancelled_session_cannot_issue_new_grant(authority):
    issuer, request, token, *_ = authority
    issuer.cancel_session(request.subject.session_id)
    expect_code(SecurityErrorCode.GRANT_CANCELLED, issuer.issue, request, token)


def test_expiry_exact_boundary_is_rejected(authority):
    issuer, request, token, clock, *_ = authority
    grant = issuer.issue(request, token)
    clock.now = request.lifetime.expires_at
    expect_code(SecurityErrorCode.GRANT_EXPIRED, issuer.claim, grant, request)


def test_observed_expiry_cannot_reactivate_on_clock_rollback(authority):
    issuer, request, token, clock, *_ = authority
    grant = issuer.issue(request, token)
    original = clock.now
    clock.now = request.lifetime.expires_at
    expect_code(SecurityErrorCode.GRANT_EXPIRED, issuer.claim, grant, request)
    clock.now = original
    expect_code(SecurityErrorCode.GRANT_EXPIRED, issuer.claim, grant, request)
    expect_code(SecurityErrorCode.GRANT_EXPIRED, issuer.issue, request, token)


def test_observed_cancel_cannot_reactivate_a_grant(authority):
    issuer, request, token, *_ = authority
    grant = issuer.issue(request, token)
    token.cancelled = True
    expect_code(SecurityErrorCode.GRANT_CANCELLED, issuer.claim, grant, request)
    token.cancelled = False  # An adversarial port cannot undo the observed cancel.
    expect_code(SecurityErrorCode.GRANT_CANCELLED, issuer.claim, grant, request)
    expect_code(SecurityErrorCode.GRANT_CANCELLED, issuer.issue, request, token)


def test_issue_before_not_before_rejected(authority):
    issuer, request, token, clock, *_ = authority
    later = replace(request.lifetime, not_before=clock.now + timedelta(seconds=1))
    expect_code(SecurityErrorCode.GRANT_NOT_YET_VALID, issuer.issue,
                replace(request, lifetime=later), token)


def test_policy_revision_change_invalidates_grant(authority):
    issuer, request, token, *_ = authority
    grant = issuer.issue(request, token)
    issuer.update_policy_revision(2)
    expect_code(SecurityErrorCode.REVISION_MISMATCH, issuer.claim, grant, request)


def test_ceiling_revision_change_invalidates_grant(authority):
    issuer, request, token, _, ceiling, *_ = authority
    grant = issuer.issue(request, token)
    issuer.replace_ceiling(replace(ceiling, revision=2))
    expect_code(SecurityErrorCode.REVISION_MISMATCH, issuer.claim, grant, request)


def test_ceiling_content_change_same_revision_is_not_silent(authority):
    issuer, request, token, _, ceiling, read, _ = authority
    grant = issuer.issue(request, token)
    # Either reject the host update or make the old binding stale. Both are
    # fail-closed; unchanged revision may never keep this grant authoritative.
    try:
        issuer.replace_ceiling(replace(ceiling, capabilities=(read,)))
    except SecurityError:
        return
    expect_code(SecurityErrorCode.REVISION_MISMATCH, issuer.claim, grant, request)


def test_two_concurrent_claims_have_one_winner(authority):
    issuer, request, token, *_ = authority
    grant = issuer.issue(request, token)
    start = Barrier(2)

    def claim_once():
        start.wait(timeout=3)
        try:
            return issuer.claim(grant, request)
        except SecurityError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = tuple(pool.map(lambda _: claim_once(), range(2)))
    assert sum(result is grant for result in attempts) == 1
    assert sum(result is SecurityErrorCode.GRANT_CONSUMED for result in attempts) == 1


def test_reusable_is_explicitly_host_selected(authority):
    issuer, request, token, *_ = authority
    reusable = replace(request, lifetime=replace(request.lifetime, one_shot=False))
    grant = issuer.issue(reusable, token)
    assert issuer.claim(grant, reusable) is grant
    assert issuer.claim(grant, reusable) is grant


def child_request(parent, *, capability=None, lifetime=None):
    request = parent.request
    return replace(
        request,
        subject=GrantSubject(request.subject.session_id, request.subject.turn_id,
                             "op_child", "tool_child", "agent_child",
                             request.subject.operation_id, request.subject.agent_id),
        capabilities=(capability or request.capabilities[0],),
        lifetime=lifetime or replace(request.lifetime, one_shot=True),
        parent_grant_id=parent.grant_id,
        parent_authority_fingerprint=parent.authority_fingerprint,
    )


def reusable_parent(authority):
    issuer, request, token, *_ = authority
    request = replace(request, lifetime=replace(request.lifetime, one_shot=False))
    return issuer.issue(request, token)


def test_derived_grant_claims_exact_child_subject(authority):
    issuer, _, _, *_ = authority
    parent = reusable_parent(authority)
    request = child_request(parent)
    child = issuer.derive(parent, request, Token())
    assert child.request.parent_grant_id == parent.grant_id
    assert issuer.claim(child, request) is child


def test_issue_cannot_bypass_derive_with_parent_fields(authority):
    issuer, _, token, *_ = authority
    parent = reusable_parent(authority)
    expect_code(SecurityErrorCode.PARENT_MISMATCH, issuer.issue,
                child_request(parent), token)


def test_child_cannot_exceed_parent_even_if_ceiling_allows(authority):
    issuer, request, token, _, _, read, write = authority
    parent_request = replace(request, capabilities=(read,),
                             lifetime=replace(request.lifetime, one_shot=False))
    parent = issuer.issue(parent_request, token)
    expect_code(SecurityErrorCode.AUTHORITY_EXCEEDED, issuer.derive,
                parent, child_request(parent, capability=write), Token())


def test_child_cannot_extend_parent_expiry(authority):
    issuer, _, _, *_ = authority
    parent = reusable_parent(authority)
    extended = replace(parent.request.lifetime,
                       expires_at=parent.request.lifetime.expires_at + timedelta(seconds=1))
    expect_code(SecurityErrorCode.AUTHORITY_EXCEEDED, issuer.derive,
                parent, child_request(parent, lifetime=extended), Token())


def test_child_cannot_remove_parent_restriction(authority):
    issuer, request, token, *_ = authority
    bound = replace(request.capabilities[0], restrictions={"operationIntent": "dummy-only"})
    ceiling = replace(issuer.ceiling, revision=2, capabilities=(bound,))
    issuer.replace_ceiling(ceiling)
    request = replace(request, capabilities=(bound,), ceiling_revision=2,
                      ceiling_fingerprint=ceiling.fingerprint,
                      lifetime=replace(request.lifetime, one_shot=False))
    parent = issuer.issue(request, token)
    relaxed = replace(bound, restrictions={})
    expect_code(SecurityErrorCode.AUTHORITY_EXCEEDED, issuer.derive,
                parent, child_request(parent, capability=relaxed), Token())


@pytest.mark.parametrize("field,value", [
    ("session_id", "ses_wrong"), ("turn_id", "turn_wrong"),
    ("parent_operation_id", "op_wrong"), ("parent_agent_id", "agent_wrong"),
])
def test_child_parent_subject_binding_rejected(authority, field, value):
    issuer, _, _, *_ = authority
    parent = reusable_parent(authority)
    request = child_request(parent)
    request = replace(request, subject=replace(request.subject, **{field: value}))
    expect_code(SecurityErrorCode.PARENT_MISMATCH, issuer.derive,
                parent, request, Token())


@pytest.mark.parametrize("field,value", [
    ("parent_grant_id", "grant_wrong"),
    ("parent_authority_fingerprint", "0" * 64),
])
def test_child_parent_authority_binding_rejected(authority, field, value):
    issuer, _, _, *_ = authority
    parent = reusable_parent(authority)
    expect_code(SecurityErrorCode.PARENT_MISMATCH, issuer.derive,
                parent, replace(child_request(parent), **{field: value}), Token())


def test_spent_one_shot_parent_cannot_derive(authority):
    issuer, request, token, *_ = authority
    parent = issuer.issue(request, token)
    issuer.claim(parent, request)
    expect_code(SecurityErrorCode.GRANT_CONSUMED, issuer.derive,
                parent, child_request(parent), Token())


def test_equal_parent_clone_is_not_authority_to_derive(authority):
    issuer, _, _, *_ = authority
    parent = reusable_parent(authority)
    expect_code(SecurityErrorCode.GRANT_UNKNOWN, issuer.derive,
                replace(parent), child_request(parent), Token())


def test_grandparent_revoke_invalidates_entire_descendant_chain(authority):
    issuer, _, _, *_ = authority
    grandparent = reusable_parent(authority)
    parent_request = child_request(grandparent)
    parent_request = replace(parent_request,
                             lifetime=replace(parent_request.lifetime, one_shot=False))
    parent = issuer.derive(grandparent, parent_request, Token())
    request = child_request(parent)
    request = replace(request, subject=replace(request.subject,
                      operation_id="op_grandchild", tool_call_id="tool_grandchild",
                      agent_id="agent_grandchild"))
    child = issuer.derive(parent, request, Token())
    issuer.revoke(grandparent)
    expect_code(SecurityErrorCode.GRANT_REVOKED, issuer.claim, child, request)


def test_revoked_parent_invalidates_already_derived_child(authority):
    issuer, _, _, *_ = authority
    parent = reusable_parent(authority)
    request = child_request(parent)
    child = issuer.derive(parent, request, Token())
    issuer.revoke(parent)
    expect_code(SecurityErrorCode.GRANT_REVOKED, issuer.claim, child, request)


def test_parent_token_cancel_invalidates_child_with_uncancelled_token(authority):
    issuer, request, token, *_ = authority
    request = replace(request, lifetime=replace(request.lifetime, one_shot=False))
    parent = issuer.issue(request, token)
    request = child_request(parent)
    child_token = Token()
    child = issuer.derive(parent, request, child_token)
    token.cancelled = True
    assert not child_token.is_cancel_requested()
    expect_code(SecurityErrorCode.GRANT_CANCELLED, issuer.claim, child, request)


def test_parent_expiry_invalidates_child_chain(authority):
    issuer, _, _, clock, *_ = authority
    parent = reusable_parent(authority)
    request = child_request(parent)
    child = issuer.derive(parent, request, Token())
    clock.now = parent.request.lifetime.expires_at
    expect_code(SecurityErrorCode.GRANT_EXPIRED, issuer.claim, child, request)


def test_ordinary_reusable_parent_claim_does_not_revoke_child(authority):
    issuer, _, _, *_ = authority
    parent = reusable_parent(authority)
    request = child_request(parent)
    child = issuer.derive(parent, request, Token())
    assert issuer.claim(parent, parent.request) is parent
    assert issuer.claim(child, request) is child


def test_existing_child_survives_ordinary_one_shot_parent_claim(authority):
    issuer, request, token, *_ = authority
    parent = issuer.issue(request, token)
    child_req = child_request(parent)
    child = issuer.derive(parent, child_req, Token())
    assert issuer.claim(parent, request) is parent
    assert issuer.claim(child, child_req) is child


def test_issue_before_claim_is_idempotent_for_same_operation(authority):
    issuer, request, token, *_ = authority
    first = issuer.issue(request, token)
    assert issuer.issue(request, token) is first
    # Equivalent immutable request is not a different authorization attempt.
    assert issuer.issue(replace(request), token) is first
    assert issuer.claim(first, request) is first


def test_reissue_after_one_shot_claim_cannot_restore_operation(authority):
    issuer, request, token, *_ = authority
    first = issuer.issue(request, token)
    issuer.claim(first, request)
    expect_code(SecurityErrorCode.GRANT_CONSUMED, issuer.issue, request, token)
    expect_code(SecurityErrorCode.GRANT_CONSUMED, issuer.claim, first, request)


def test_conflicting_request_cannot_reissue_same_operation(authority):
    issuer, request, token, *_ = authority
    first = issuer.issue(request, token)
    conflict = replace(request, arguments={"items": [{"text": "conflict"}]})
    expect_code(SecurityErrorCode.REQUEST_MISMATCH, issuer.issue, conflict, token)
    assert issuer.claim(first, request) is first


def test_changed_cancellation_port_cannot_reissue_same_operation(authority):
    issuer, request, token, *_ = authority
    first = issuer.issue(request, token)
    expect_code(SecurityErrorCode.REQUEST_MISMATCH, issuer.issue, request, Token())
    assert issuer.claim(first, request) is first


def test_concurrent_issue_same_operation_returns_one_registered_object(authority):
    issuer, request, token, *_ = authority
    start = Barrier(2)

    def issue_once():
        start.wait(timeout=3)
        return issuer.issue(request, token)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(lambda _: issue_once(), range(2)))
    assert results[0] is results[1]
    assert issuer.claim(results[0], request) is results[0]
    expect_code(SecurityErrorCode.GRANT_CONSUMED, issuer.claim, results[1], request)


def cross_session_child_request(parent):
    request = child_request(parent)
    return replace(request, subject=replace(
        request.subject, session_id="ses_child", turn_id="turn_child",
        parent_session_id=parent.request.subject.session_id,
        parent_turn_id=parent.request.subject.turn_id,
    ))


def test_cross_session_derivation_requires_and_accepts_exact_lineage(authority):
    issuer, _, _, *_ = authority
    parent = reusable_parent(authority)
    request = cross_session_child_request(parent)
    child = issuer.derive(parent, request, Token())
    assert child.request.subject.session_id != parent.request.subject.session_id
    assert child.request.subject.parent_session_id == parent.request.subject.session_id
    assert child.request.subject.parent_turn_id == parent.request.subject.turn_id
    assert issuer.claim(child, request) is child


@pytest.mark.parametrize("field,value", [
    ("parent_session_id", "ses_wrong_parent"),
    ("parent_turn_id", "turn_wrong_parent"),
    ("parent_turn_id", None),
])
def test_cross_session_wrong_parent_lineage_is_rejected(authority, field, value):
    issuer, _, _, *_ = authority
    parent = reusable_parent(authority)
    request = cross_session_child_request(parent)
    wrong = replace(request, subject=replace(request.subject, **{field: value}))
    expect_code(SecurityErrorCode.PARENT_MISMATCH, issuer.derive,
                parent, wrong, Token())


def test_cross_session_without_explicit_lineage_is_rejected(authority):
    issuer, _, _, *_ = authority
    parent = reusable_parent(authority)
    request = child_request(parent)
    missing = replace(request, subject=replace(request.subject,
                      session_id="ses_child", turn_id="turn_child"))
    expect_code(SecurityErrorCode.PARENT_MISMATCH, issuer.derive,
                parent, missing, Token())


def test_cancel_parent_session_invalidates_child_in_different_session(authority):
    issuer, _, _, *_ = authority
    parent = reusable_parent(authority)
    request = cross_session_child_request(parent)
    child = issuer.derive(parent, request, Token())
    issuer.cancel_session(parent.request.subject.session_id)
    expect_code(SecurityErrorCode.GRANT_CANCELLED, issuer.claim, child, request)


def test_depth_32_is_supported_and_depth_33_has_typed_rejection(authority):
    issuer, _, _, *_ = authority
    parent = reusable_parent(authority)
    for depth in range(1, 33):
        request = child_request(parent)
        request = replace(
            request,
            subject=replace(request.subject, operation_id=f"op_depth_{depth}",
                            tool_call_id=f"tool_depth_{depth}", agent_id=f"agent_depth_{depth}"),
            lifetime=replace(request.lifetime, one_shot=False),
        )
        parent = issuer.derive(parent, request, Token())
    request = child_request(parent)
    request = replace(request, subject=replace(request.subject,
                      operation_id="op_depth_33", tool_call_id="tool_depth_33"))
    expect_code(SecurityErrorCode.INVALID_CONTRACT, issuer.derive,
                parent, request, Token())
    # Rejecting deeper authority does not corrupt the accepted parent chain.
    assert issuer.claim(parent, parent.request) is parent
