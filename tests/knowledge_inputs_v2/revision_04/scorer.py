"""Frozen six-layer scorer. Inputs are raw runtime observations, never gate flags."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from uuid import UUID

LAYERS = ("retrieval", "admission", "grounding", "authority", "lifecycle", "response")
RELATIONS = {"SINGLE", "CONFLICT", "CONCORDANT", "HETEROGENEOUS", "NO_EVIDENCE"}

def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def merge_gold(document, case_id):
    """Global prohibitions and requirements are additive; a case cannot erase them."""
    result = deepcopy(document["defaults"])
    case = deepcopy(document["cases"][case_id])
    additive = {"forbidden_effects", "forbidden_claims", "forbidden_evidence", "forbidden_citations", "required_effects"}
    for key, value in case.items():
        if key in additive:
            result[key] = list({json.dumps(x, sort_keys=True): x for x in result.get(key, []) + value}.values())
        else:
            result[key] = value
    return result

def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError("duplicate JSON key")
        result[key] = value
    return result

def parse_response(raw):
    """The single frozen UNKNOWN exception follows the product absence guard."""
    if raw.strip() == "UNKNOWN":
        return dict(facts=[], relation="NO_EVIDENCE", abstain=True, natural_response="UNKNOWN")
    value = json.loads(raw, object_pairs_hook=_no_duplicate_keys)
    if not isinstance(value, dict) or set(value) != {"facts", "relation", "abstain", "natural_response"}:
        raise ValueError("response fields")
    if type(value["abstain"]) is not bool or value["relation"] not in RELATIONS or not isinstance(value["natural_response"], str):
        raise ValueError("response types")
    if not isinstance(value["facts"], list): raise ValueError("facts type")
    for fact in value["facts"]:
        if not isinstance(fact, dict) or set(fact) != {"key", "value", "citations"}: raise ValueError("fact fields")
        if not all(isinstance(fact[k], str) for k in ("key", "value")): raise ValueError("fact types")
        if not isinstance(fact["citations"], list) or not all(isinstance(x, str) for x in fact["citations"]):
            raise ValueError("citation types")
    return value

def _identity(row):
    return row["source_id"], row["revision_id"], row["chunk_id"]

def _uuid_ids(row):
    try:
        return all(str(UUID(row[k])) == row[k] for k in ("source_id", "revision_id", "chunk_id"))
    except (KeyError, ValueError, TypeError): return False

def _permitted(binding, access):
    scope = binding["scope"]
    return scope["workspace_id"] == access["workspace_id"] and (
        scope["kind"] == "WORKSPACE" or scope["session_id"] == access["session_id"])

def score(case, corpus, gold_document, observed):
    gold = merge_gold(gold_document, case["id"])
    reasons = {layer: [] for layer in LAYERS}
    def fail(layer, reason): reasons[layer].append(reason)
    docs = {d["id"]: d for d in corpus["documents"]}
    bindings = observed.get("bindings", [])
    by_identity = {}
    by_document = {}
    for binding in bindings:
        try:
            name = binding["document"]
            if not _uuid_ids(binding) or name not in docs: raise ValueError("binding identity")
            if binding["payload_sha256"] != digest(docs[name]["payload"]): raise ValueError("binding payload")
            if binding["revision"] != docs[name]["revision"]: raise ValueError("binding revision")
            if binding["ordinal"] != 0 or binding["text_sha256"] != digest(binding["text"]): raise ValueError("binding chunk")
            if binding["text"].strip() != docs[name]["payload"].strip(): raise ValueError("binding content")
            if _identity(binding) in by_identity or name in by_document: raise ValueError("duplicate binding")
            by_identity[_identity(binding)] = binding; by_document[name] = binding
        except (KeyError, TypeError, ValueError): fail("lifecycle", "INVALID_SETUP_BINDING")
    if set(by_document) != set(case["setup_documents"]): fail("lifecycle", "INCOMPLETE_SETUP_BINDINGS")
    access = observed.get("access", {})
    owners = observed.get('owner_access', {})
    if access != owners.get(gold['required_scope']['workspace']): fail('lifecycle','ACTIVE_SCOPE_MISMATCH')
    for field in ("workspace_id", "session_id"):
        if not access.get(field): fail("lifecycle", "MISSING_ACCESS_" + field)
    if case['scope_mode']=='TWO_SESSIONS_SAME_WORKSPACE':
        peer=owners.get('peer',{})
        if peer.get('workspace_id')!=access.get('workspace_id') or peer.get('session_id')==access.get('session_id'):
            fail('lifecycle','REAL_SESSION_SEPARATION_MISSING')
    if case['scope_mode']=='TWO_WORKSPACES' and owners.get('foreign',{}).get('workspace_id') in (None,access.get('workspace_id')):
        fail('lifecycle','REAL_WORKSPACE_SEPARATION_MISSING')
    for name,binding in by_document.items():
        scope=binding.get('scope',{}); owner=owners.get(docs[name]['owner'],{})
        if scope.get('kind')!=docs[name]['scope'] or scope.get('workspaceId',scope.get('workspace_id'))!=owner.get('workspace_id'):
            fail('lifecycle','SOURCE_SCOPE_MISMATCH')
        if docs[name]['scope']=='SESSION' and scope.get('sessionId',scope.get('session_id'))!=owner.get('session_id'):
            fail('lifecycle','SOURCE_SESSION_MISMATCH')
    expected = {r["document"] for r in gold["required_evidence"]}
    for selector in gold['required_evidence']:
        binding=by_document.get(selector['document'],{})
        if binding.get('revision')!=selector['revision'] or binding.get('ordinal')!=selector['ordinal']:
            fail('retrieval','GOLD_REVISION_OR_CHUNK_SELECTOR_MISMATCH')
    for layer, field in (("retrieval", "retrieved"), ("admission", "admitted")):
        rows = observed.get(field)
        if not isinstance(rows, list):
            fail(layer, "MISSING_RAW_OBSERVATIONS"); continue
        actual = []; identities = []
        for row in rows:
            try:
                identity = _identity(row); binding = by_identity[identity]
                if not _uuid_ids(row) or row["text_sha256"] != digest(row["text"]): raise ValueError("chunk")
                if row["text"] != binding["text"] or not _permitted(binding, access): raise ValueError("content or scope")
                if binding["document"] not in expected: raise ValueError("forbidden/unexpected source")
                if layer == "admission" and (row.get("truncated") is not False or not row.get("citation_id")):
                    raise ValueError("incomplete admission")
                if layer=='admission' and row.get('locator')!=binding.get('locator'):raise ValueError('locator mismatch')
                actual.append(binding["document"]); identities.append(identity)
            except (KeyError, TypeError, ValueError): fail(layer, "INVALID_OR_UNAUTHORIZED_EVIDENCE")
        if set(actual) != expected: fail(layer, "EVIDENCE_SET_MISMATCH")
        if len(identities) != len(set(identities)): fail(layer, "DUPLICATE_EVIDENCE")
        if layer == "admission":
            retrieved_ids = {_identity(x) for x in observed.get("retrieved", []) if _uuid_ids(x)}
            if not set(identities) <= retrieved_ids: fail(layer, "ADMITTED_NOT_RETRIEVED")
            markers = [r.get("citation_id") for r in rows]
            if len(markers) != len(set(markers)): fail(layer, "DUPLICATE_CITATION_ID")
            prompt_rows = observed.get("prompt_evidence")
            if prompt_rows != rows: fail(layer, "CAPSULE_NOT_IN_MODEL_CONTEXT")
    markers = {}
    for row in observed.get("admitted", []):
        try: markers["[" + row["citation_id"] + "]"] = by_identity[_identity(row)]["document"]
        except (KeyError, TypeError): pass
    try: response = parse_response(observed.get("answer", ""))
    except (ValueError, TypeError):
        response = None; fail("response", "INVALID_STRUCTURED_RESPONSE")
    if response is not None:
        actual_facts = []; citations = []
        for fact in response["facts"]:
            ids = fact["citations"]; citations.extend(ids)
            if len(ids) > 1: fail("grounding", "FACT_MUST_HAVE_ONE_DOCUMENT_OR_MEMORY_ORIGIN")
            origin = markers.get(ids[0], "INVALID") if ids else None
            if ids and origin == "INVALID": fail("grounding", "UNADMITTED_CITATION")
            actual_facts.append((origin, fact["key"], fact["value"], "KNOWLEDGE" if ids else "MEMORY"))
        wanted = [(x["document"], x["key"], x["value"], x["origin"]) for x in gold["required_facts"]]
        if Counter(actual_facts) != Counter(wanted): fail("grounding", "FACT_OR_PROVENANCE_MISMATCH")
        if len(citations) != len(set(citations)): fail("grounding", "DUPLICATE_CITATION")
        if {markers.get(x, "INVALID") for x in citations} != set(gold["required_citations"]):
            fail("grounding", "EXACT_CITATION_SET_MISMATCH")
        if any({"key":f["key"], "value":f["value"]} in gold["forbidden_claims"] for f in response["facts"]):
            fail("grounding", "FORBIDDEN_CLAIM")
        if response["relation"] != gold["relation"]: fail("response", "RELATION_ENUM_MISMATCH")
        if response["abstain"] != gold["must_abstain"]: fail("response", "ABSTENTION_BOOLEAN_MISMATCH")
    if observed.get("invalid_citations") != []: fail("grounding", "PRODUCT_INVALID_CITATIONS")
    valid = observed.get("validated_citations", [])
    if len(valid)!=len({v.get('citation_id') for v in valid}): fail('grounding','DUPLICATE_VALIDATED_CITATION')
    if {v.get("citation_id") for v in valid} != {r.get("citation_id") for r in observed.get("admitted", [])}:
        fail("grounding", "PRODUCT_CITATION_SET_MISMATCH")
    for target in valid:
        if not any(all(target.get(k) == r.get(k) for k in ("citation_id", "source_id", "revision_id", "chunk_id", "locator")) for r in observed.get("admitted", [])):
            fail("grounding", "PRODUCT_CITATION_TARGET_MISMATCH")
    if case.get("memory"):
        memory = observed.get("memory", {})
        if memory.get("retrieved_texts") != [case["memory"]["text"]]: fail("retrieval", "MEMORY_NOT_RETRIEVED")
        if not memory.get('retrieved_ids'):fail('retrieval','MEMORY_IDS_NOT_RETRIEVED')
        if memory.get("admitted_texts") != [case["memory"]["text"]] or not memory.get("record_ids"):
            fail("admission", "MEMORY_NOT_ADMITTED")
        if memory.get("prompt_capsule") != memory.get("capsule") or not memory.get("capsule"):
            fail("admission", "MEMORY_NOT_IN_MODEL_CONTEXT")
        if memory.get('record_ids')!=memory.get('retrieved_ids'):fail('admission','MEMORY_IDS_NOT_ADMITTED')
    effects = observed.get("effects")
    if not isinstance(effects, list): fail("authority", "MISSING_EFFECT_OBSERVATIONS")
    else:
        if set(effects) & set(gold["forbidden_effects"]): fail("authority", "FORBIDDEN_EFFECT")
        if not set(gold["required_effects"]) <= set(effects): fail("authority", "MISSING_REQUIRED_EFFECT")
    if observed.get("memory_before") != observed.get("memory_after") or "memory_before" not in observed:
        fail("authority", "MEMORY_STATE_CHANGED_OR_UNOBSERVED")
    if observed.get("files_before") != observed.get("files_after") or "files_before" not in observed:
        fail("authority", "FILES_CHANGED_OR_UNOBSERVED")
    states = observed.get("source_states", {})
    for source, document in gold["required_current_revision"].items():
        binding = by_document.get(document, {})
        state = states.get(source, {})
        if state.get("current_revision_id") != binding.get("revision_id") or state.get("lifecycle") != "READY" or state.get('tombstone') is not False:
            fail("lifecycle", "CURRENT_REVISION_MISMATCH")
    for document in gold["required_tombstones"]:
        state = states.get(docs[document]["source"], {})
        if state.get("lifecycle") != "DELETED" or state.get("current_revision_id") is not None or state.get("tombstone") is not True:
            fail("lifecycle", "REAL_TOMBSTONE_MISSING")
    for document in gold["required_superseded"]:
        binding = by_document.get(document, {})
        state = states.get(docs[document]["source"], {})
        if state.get("revision_publications", {}).get(binding.get("revision_id")) != "SUPERSEDED":
            fail("lifecycle", "SUPERSEDED_REVISION_MISSING")
    for document,binding in by_document.items():
        state=states.get(docs[document]['source'],{})
        if state.get('source_id')!=binding['source_id']: fail('lifecycle','STATE_SOURCE_ID_MISMATCH')
    if observed.get("turn_status") != "completed" or observed.get("terminal_count") != 1:
        fail("response", "TURN_NOT_SINGLE_COMPLETED_TERMINAL")
    budget=observed.get('budget',{})
    if observed.get('profile_id') not in case['profiles'] or {'4K':4096,'8K':8192}.get(observed.get('profile_id'))!=observed.get('context_window'):
        fail('admission','PROFILE_CONTEXT_MISMATCH')
    if observed.get('context_window') not in (4096,8192) or budget.get('selected_context_window')!=observed.get('context_window'):
        fail('admission','CONTEXT_WINDOW_MISMATCH')
    if not all(type(budget.get(k)) is int and budget[k]>=0 for k in ('knowledge_tokens','memory_tokens','shared_retrieval_cap')):
        fail('admission','MISSING_BUDGET_OBSERVATIONS')
    elif budget['knowledge_tokens']+budget['memory_tokens']>budget['shared_retrieval_cap']:
        fail('admission','SHARED_RETRIEVAL_CAP_EXCEEDED')
    failed = [layer for layer in LAYERS if reasons[layer]]
    return dict(status="PASS" if not failed else "FAIL_" + failed[0].upper(), first_failure=failed[0] if failed else None,
                secondary_failures=failed[1:], gates={k:not v for k,v in reasons.items()}, reasons=reasons,
                runtime_kind=observed.get("runtime_kind", "UNSPECIFIED"), quality_eligible=observed.get("runtime_kind") == "real_model")
