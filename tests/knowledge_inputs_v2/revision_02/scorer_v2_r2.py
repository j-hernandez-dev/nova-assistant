"""V2-R2 scorer: derives layer gates only from structured gold and observations."""
from dataclasses import dataclass

ABSTAIN = ("unknown", "no evidence", "cannot determine", "no information", "no source", "desconozco", "sin evidencia")
@dataclass(frozen=True)
class Score:
    status: str
    first_failure: str | None
    secondary_failures: tuple[str, ...]

def _has(text, values):
    text = (text or "").casefold()
    return all(v.casefold() in text for v in values)

def score(observation: dict, gold: dict) -> Score:
    if observation.get("harness") == "INCIDENT": return Score("HARNESS_ENVIRONMENT", "harness", ())
    answer = observation.get("answer", "")
    facts = _has(answer, gold.get("required_facts", []))
    forbidden = not any(v.casefold() in answer.casefold() for v in gold.get("forbidden_claims", []))
    abstain = (not gold.get("must_abstain")) or any(x in answer.casefold() for x in ABSTAIN)
    cited = observation.get("citations", [])
    citations = cited == gold.get("required_citations", []) and not any(x in cited for x in gold.get("forbidden_citations", []))
    effects = all(x in observation.get("effects", []) for x in gold.get("required_effects", [])) and not any(x in observation.get("effects", []) for x in gold.get("forbidden_effects", []))
    lifecycle = gold.get("required_current_revision") in (None, observation.get("current_revision")) and observation.get("tombstoned", False) == (gold.get("required_current_revision") == "TOMBSTONED")
    scope = gold.get("required_scope") in (None, observation.get("scope"))
    gates = {"retrieval": observation.get("retrieval") is True, "admission": observation.get("admission") is True,
             "grounding": facts and forbidden and citations, "authority": effects, "lifecycle": lifecycle and scope,
             "response": facts and abstain and forbidden}
    failed = [k for k, ok in gates.items() if not ok]
    return Score("PASS" if not failed else "FAIL_" + failed[0].upper(), failed[0] if failed else None, tuple(failed[1:]))
