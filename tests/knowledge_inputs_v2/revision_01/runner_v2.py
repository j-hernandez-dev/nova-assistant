"""Campaign runner guarded by preflight. It cannot run until human pins execution."""
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROFILE = ROOT / "docs/knowledge_inputs_v2/revision_01/execution_profile_v2.json"
FREEZE = ROOT / "docs/knowledge_inputs_v2/revision_01/freeze_final_v2.json"

def preflight() -> list[str]:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    errors = []
    for rel, expected in freeze.get("pins", {}).items():
        path = ROOT / rel
        actual = hashlib.sha256(path.read_bytes()).hexdigest().upper() if path.is_file() else "MISSING"
        if actual != expected.upper():
            errors.append("drift: " + rel)
    for field in ("model_id", "backend_id", "parameters", "seed"):
        if profile["llm"].get(field) in (None, "", "NOT_SELECTED_BY_HUMAN"):
            errors.append("missing exact llm field: " + field)
    if profile["joint_authorization"] != {"4K": True, "8K": True}:
        errors.append("joint authorization for both campaigns is absent")
    if profile["tuning"] is not False:
        errors.append("tuning must be false")
    if freeze.get("status") != "FROZEN_PENDING_HUMAN_REVIEW":
        errors.append("freeze status is not FROZEN_PENDING_HUMAN_REVIEW")
    if freeze.get("campaigns_consumed") != 0:
        errors.append("campaign already consumed")
    return errors

def main() -> int:
    errors = preflight()
    print(json.dumps({"executable": not errors, "campaigns_started": 0, "errors": errors}))
    return 0 if not errors else 2

if __name__ == "__main__": raise SystemExit(main())
