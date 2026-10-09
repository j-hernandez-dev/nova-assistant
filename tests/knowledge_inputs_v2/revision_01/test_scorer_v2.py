from scorer_v2 import score

BASE = {k: True for k in ("retrieval", "admission", "grounding", "authority", "lifecycle", "response")}

def test_pass():
    assert score(BASE).status == "PASS"

def test_first_failure_is_retrieval():
    r = dict(BASE, retrieval=False, response=False)
    got = score(r)
    assert got.status == "FAIL_RETRIEVAL" and got.secondary_failures == ("response",)

def test_layer_order_and_harness():
    assert score(dict(BASE, admission=False, lifecycle=False)).status == "FAIL_ADMISSION"
    assert score(dict(BASE, harness="INCIDENT")).status == "HARNESS_ENVIRONMENT"
