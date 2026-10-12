"""WEBVIEW2_TAKEOVER_NATIVE_TEST: declared secret survives document replacement.

No raw credential in assertions, logs or evidence. The value is generated solely
by the existing certification UI driver, never supplied through model/IPC.
"""
import json
import time
import pytest
from test_webview2_transfers import specimen5 as original_specimen5,human_driver,begin_human,drive,capture,deadline
from test_sensitive_continuity import continuity_proof_build
from terminal_expectation_proof.proof import assert_lost_terminal_denial

@pytest.fixture
def specimen5(continuity_proof_build,tmp_path):
    yield from original_specimen5.__wrapped__(continuity_proof_build,tmp_path)

def test_declared_human_secret_not_projected_after_same_origin_navigation(specimen5,human_driver):
    d=specimen5;content=d['tmp']/'local'
    html=(content/'index.html').read_text(encoding='utf-8').replace("location.href='mailto:guard-test@example.invalid'","location.href='other.html#'+encodeURIComponent(document.getElementById('password').value)")
    # Keep the certification UI driver's established click geometry stable:
    # reflected inline text must not push the navigation button down. The
    # destination still reflects the entered secret and the assertions remain.
    html=html.replace('<span id="echo">','<span id="echo" style="display:none">')
    (content/'index.html').write_text(html,encoding='utf-8')
    (content/'other.html').write_text("<!doctype html><html><body>Transition pending<script>document.body.textContent='Controlled post-login status '+decodeURIComponent(location.hash.slice(1));</script></body></html>",encoding='utf-8')
    d['port'].navigate_local(d['session'],d['page'],'index.html',deadline=deadline())
    before=capture(d);native_before=d['port']._epochs[(d['session'],d['page'])]
    context_before=d['manager'].session(d['owner'],d['session']).browser_context_epoch
    t=begin_human(d);drive(d,human_driver,'sensitive');drive(d,human_driver,'external');time.sleep(.25);drive(d,human_driver,'done')
    proof=assert_lost_terminal_denial(d,t)
    # No public observation may exist on this branch. Preserve the absence
    # assertion on the returned metadata rather than manufacture a projection.
    leak='test-only-'in json.dumps(proof)
    (d['tmp']/'secret_boundary_check.json').write_text(json.dumps(dict(scenario='declared password + same-origin document replacement during real host takeover',humanCompletion=True,contextEpoch=d['manager'].session(d['owner'],d['session']).browser_context_epoch,credentialMarkerProjected=leak,rawValuePersistedInEvidence=False)),encoding='utf-8')
    assert before.browser_session_ref==d['session'] and before.page_ref==d['page']
    assert proof['observedSensitiveGenerationRetired'] and not proof['strongTerminalSourcePresent']
    assert not proof['agentResumed'] and not proof['freshObservationPublished']
    assert d['manager'].session(d['owner'],d['session']).browser_context_epoch==context_before
    assert not leak,'Declared human credential reached model-eligible observation after document replacement (value withheld)'
