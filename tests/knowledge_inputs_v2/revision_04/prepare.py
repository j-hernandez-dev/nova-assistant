"""R4 preparation-only validation/sealing; never starts product or campaigns."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOCS = ROOT / "docs/knowledge_inputs_v2/revision_04"
PRIOR_DOCS = ROOT / "docs/knowledge_inputs_v2/revision_03"
PRIOR_TESTS = ROOT / "tests/knowledge_inputs_v2/revision_03"
sys.path.insert(0, str(HERE))
import runner
import validate as inherited_validation

DOC_COPIES = ("authorization_schema.json", "DESIGN_V2_R3.md", "execution_profile_v2_r3.json",
              "profiles.json", "protocol.json", "response_contract.json", "retry_rules.json",
              "runtime.json", "SCORER_V2_R3.md")
TEST_COPIES = ("corpus_v2_r3.json", "gold_v2_r3.json", "scorer.py", "checks.py", "validate.py")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def fresh_write(path, value):
    if path.exists():
        raise ValueError("REFUSING_EVIDENCE_OVERWRITE:" + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")

def allowed_delta():
    inventory = read(DOCS / "preserved_inventory.json")
    drift = [entry["path"] for entry in inventory["files"]
             if not (ROOT / entry["path"]).is_file() or sha(ROOT / entry["path"]) != entry["sha256"]]
    if drift:
        raise ValueError("HISTORICAL_DRIFT:" + repr(drift))
    pairs = [(PRIOR_DOCS / name, DOCS / name) for name in DOC_COPIES]
    pairs += [(PRIOR_TESTS / name, HERE / name) for name in TEST_COPIES]
    differences = [str(new) for old, new in pairs if old.read_bytes() != new.read_bytes()]
    if differences:
        raise ValueError("NORMATIVE_COPY_DRIFT:" + repr(differences))
    old_adapter = (PRIOR_TESTS / "nova_adapter.py").read_text(encoding="utf-8")
    old_filter = 'if x.get("name")==model["model"]]'
    new_filter = 'if x.get("name")==model["model"] and x.get("digest")==model["digest"]]'
    if old_adapter.count(old_filter) != 1:
        raise ValueError("UNEXPECTED_R3_ADAPTER")
    if (HERE / "nova_adapter.py").read_text(encoding="utf-8") != old_adapter.replace(old_filter, new_filter):
        raise ValueError("ADAPTER_CHANGE_OUTSIDE_AUTHORIZED_FILTER")
    old_runner = (PRIOR_TESTS / "runner.py").read_text(encoding="utf-8")
    expected_runner = old_runner.replace('DOCS = ROOT / "docs/knowledge_inputs_v2/revision_03"',
                                         'DOCS = ROOT / "docs/knowledge_inputs_v2/revision_04"')
    expected_runner = expected_runner.replace('"freeze_final_v2_r3.json"', '"freeze_final_v2_r4.json"')
    if (HERE / "runner.py").read_text(encoding="utf-8") != expected_runner:
        raise ValueError("RUNNER_CHANGE_OUTSIDE_REVISION_ROUTING")
    baseline_errors = runner.pin_errors(read(PRIOR_DOCS / "freeze_final_v2_r3.json"))
    if baseline_errors:
        raise ValueError("R3_PIN_DRIFT:" + repr(baseline_errors))
    return dict(preserved_files=len(inventory["files"]), preservation_drift=drift,
                byte_identical_normative_copies=[new.relative_to(ROOT).as_posix() for _, new in pairs],
                adapter_delta="one filter: name AND digest", runner_delta="DOCS path and two freeze filename references only")

def validation():
    unchanged = allowed_delta()
    inherited = inherited_validation.validate()
    if any(name.startswith("local_cli") for name in sys.modules):
        raise ValueError("PRODUCT_IMPORTED_DURING_PREPARATION")
    return dict(status="OFFLINE_VALIDATION_PASS", revision="V2-R4",
        recorded_at=datetime.now(timezone.utc).isoformat(), changes=unchanged,
        inherited_exam_validation=inherited, campaigns_consumed=0, inference=0, retrieval=0, admission=0,
        quality_measured=False, methodology_changed=False)

def seal():
    allowed_delta()
    validation_record = read(DOCS / "evidence/validation-r4.json")
    checks = read(DOCS / "evidence/backend-identity-synthetic.json")
    if validation_record["status"] != "OFFLINE_VALIDATION_PASS" or checks["status"] != "PASS" or checks["tests_run"] != 9:
        raise ValueError("PRE_FREEZE_CHECKS_REQUIRED")
    baseline = read(DOCS / "preserved_inventory.json")
    pins = {entry["path"]: entry["sha256"] for entry in baseline["files"]}
    for directory in (DOCS, HERE):
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.name in ("freeze_final_v2_r4.json", "evidence_index.json", "human_authorization.pending.json"):
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            if path.is_relative_to(DOCS / "evidence/post-freeze"):
                continue
            pins[path.relative_to(ROOT).as_posix()] = sha(path)
    freeze = dict(schema="k8-v2-freeze-4", revision="V2-R4", status="FROZEN_PENDING_HUMAN_REVIEW",
        head=baseline["baseline_head"], baseline_revision="V2-R3", baseline_freeze_sha256=baseline["baseline_freeze_sha256"],
        allowed_revision_reason="execution-blocking BACKEND_RUNNER_MISMATCH only; no quality/methodology changes",
        knowledge_specific_minimum_context_window="NOT_DEFINED",
        profiles_file="docs/knowledge_inputs_v2/revision_04/profiles.json",
        retry_rules_file="docs/knowledge_inputs_v2/revision_04/retry_rules.json",
        authorization="separate additive joint authorization bound to this exact freeze SHA; R3 authorization invalid for R4",
        campaigns_consumed=0, inference=0, retrieval=0, admission=0, quality_measured=False, ready=False,
        pins=[dict(path=path, sha256=value) for path, value in sorted(pins.items())],
        external_pins=read(DOCS / "runtime.json")["external_pins"])
    path = DOCS / "freeze_final_v2_r4.json"
    fresh_write(path, freeze)
    return dict(freeze_sha256=sha(path), pins=len(freeze["pins"]), external_pins=len(freeze["external_pins"]))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("validate", "seal"))
    args = parser.parse_args()
    if args.phase == "validate":
        record = validation()
        fresh_write(DOCS / "evidence/validation-r4.json", record)
        print(json.dumps({"status": record["status"], **record["changes"], "collisions": record["inherited_exam_validation"]["collisions"]}, indent=2))
    else:
        print(json.dumps(seal(), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
