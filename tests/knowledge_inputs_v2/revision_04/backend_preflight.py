"""Post-freeze read-only R4 identity evidence; never runs an exam case."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runner
from nova_adapter import verify_backend
from prepare import allowed_delta, fresh_write

def main():
    evidence = runner.DOCS / "evidence/post-freeze"
    check = runner.preflight()
    fresh_write(evidence / "preflight-offline.json", check)
    if check["integrity_errors"] or check["execution_errors"] != ["JOINT_AUTHORIZATION_ABSENT"]:
        raise runner.FrozenAbort("R4_PREFLIGHT_REJECTED:" + repr(check))
    profile = runner.read(runner.DOCS / "execution_profile_v2_r3.json")
    try:
        identity = verify_backend(profile)
    except Exception as exc:
        fresh_write(evidence / "backend-identity-incident.json", dict(type=type(exc).__name__, error=str(exc),
            campaigns_consumed=0, inference=0, retrieval=0, admission=0))
        raise
    fresh_write(evidence / "backend-identity-real.json", identity)
    prior_auth = runner.read(runner.ROOT / "docs/knowledge_inputs_v2/revision_03/evidence/k8-v2-r3-20261009T015855Z-108ce53c53974a84927b8b3952d8ac5d/AUTHORIZED")
    prior_auth_errors = runner.authorization_errors(prior_auth, check["freeze_sha256"])
    if prior_auth_errors != ["AUTHORIZATION_FREEZE_MISMATCH"]:
        raise runner.FrozenAbort("R3_AUTHORIZATION_NOT_REJECTED:" + repr(prior_auth_errors))
    changes = allowed_delta()
    post = runner.preflight()
    fresh_write(evidence / "post-identity-integrity.json", post)
    if post["integrity_errors"]:
        raise runner.FrozenAbort("DRIFT_AFTER_IDENTITY_CHECK")
    if any(name.startswith("local_cli") for name in sys.modules):
        raise runner.FrozenAbort("PRODUCT_IMPORT_DURING_READ_ONLY_PREFLIGHT")
    exact = [row for row in identity["tags"].get("models", [])
             if row.get("name") == profile["llm"]["model"] and row.get("digest") == profile["llm"]["digest"]]
    homonyms = [row for row in identity["tags"].get("models", [])
                if row.get("name") == profile["llm"]["model"] and row.get("digest") != profile["llm"]["digest"]]
    summary = dict(status="READ_ONLY_IDENTITY_PREFLIGHT_PASS", revision="V2-R4",
        verified_at=datetime.now(timezone.utc).isoformat(), freeze_sha256=check["freeze_sha256"],
        integrity_errors=post["integrity_errors"], execution_errors=post["execution_errors"],
        llm=profile["llm"], profiles=profile["profiles"], exact_installed=exact,
        exact_resident=[row for row in identity["resident"].get("models", [])
                        if row.get("name") == profile["llm"]["model"] and row.get("digest") == profile["llm"]["digest"]],
        other_digest_homonyms_retained=homonyms, r3_authorization_errors=prior_auth_errors,
        preparation_changes=changes, product_modules_imported=[], campaigns_consumed=0, inference=0, retrieval=0, admission=0,
        campaign_authorization_created=False, quality_measured=False)
    fresh_write(evidence / "preflight-summary.json", summary)
    print(json.dumps({key: summary[key] for key in ("status", "freeze_sha256", "r3_authorization_errors", "campaigns_consumed", "inference", "retrieval", "admission")}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
