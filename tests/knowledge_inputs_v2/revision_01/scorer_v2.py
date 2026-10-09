"""Deterministic V2 scorer; no product, retrieval, admission, or model calls."""
from dataclasses import dataclass

LAYERS = ("retrieval", "admission", "grounding", "authority", "lifecycle", "response")

@dataclass(frozen=True)
class Score:
    status: str
    first_failure: str | None
    secondary_failures: tuple[str, ...]

def score(record: dict) -> Score:
    if record.get("harness") == "INCIDENT":
        return Score("HARNESS_ENVIRONMENT", "harness", tuple())
    failed = [layer for layer in LAYERS if record.get(layer) is not True]
    if not failed:
        return Score("PASS", None, tuple())
    return Score("FAIL_" + failed[0].upper(), failed[0], tuple(failed[1:]))

def score_profile(records: list[dict], denominator: int) -> dict:
    results = [score(r) for r in records]
    passed = sum(r.status == "PASS" for r in results)
    return {"passed": passed, "denominator": denominator,
            "profile_pass": passed == denominator and len(results) == denominator,
            "results": [r.__dict__ for r in results]}
