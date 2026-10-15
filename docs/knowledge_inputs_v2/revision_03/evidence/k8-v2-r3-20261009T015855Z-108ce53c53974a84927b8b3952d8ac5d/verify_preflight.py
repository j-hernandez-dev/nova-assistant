"""Read-only verifier invoking the frozen preflight and backend identity check.

This external evidence wrapper does not implement or modify any campaign step.
"""
import datetime
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(r"C:/Users/joseh/Downloads/nova-local-cli/nova-assistant")
CONTROL = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests/knowledge_inputs_v2/revision_03"))
sys.path.insert(0, str(ROOT))
import runner

def timestamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

auth = runner.read(CONTROL / "AUTHORIZED")
report = runner.preflight(auth)
report["verified_at"] = timestamp()
runner.write(CONTROL / "preflight_final.json", report)
if report["execution_errors"]:
    print(json.dumps(report, indent=2))
    raise SystemExit(2)
expected_sha = "3cfc31e908a8a16a07893ac89a357cbad0227f0e8c4b31aa664cefb8666f40a0"
if report["freeze_sha256"] != expected_sha:
    raise SystemExit("UNEXPECTED_FREEZE_SHA")
profile = runner.read(runner.DOCS / "execution_profile_v2_r3.json")
expected = {
    "model": "qwen3.5:9b",
    "digest": "c97eb11d70b1acdc88af01eef566c1fe4f7fbe93eb1afc06871132f293ff425a",
    "backend": "Ollama", "endpoint": "http://127.0.0.1:11434",
    "runner": "llamacpp", "temperature": 0, "think": False,
    "maxIterations": 6, "seed": "NOT_SUPPORTED",
}
errors = [key for key, value in expected.items() if profile["llm"].get(key) != value]
if profile["profiles"] != {"4K": {"contextWindow": 4096}, "8K": {"contextWindow": 8192}}:
    errors.append("context_windows")
if errors:
    raise SystemExit("EXECUTION_PROFILE_MISMATCH:" + repr(errors))
from nova_adapter import verify_backend
try:
    identity = verify_backend(profile)
except Exception as exc:
    runner.write(CONTROL / "preflight_backend_incident.json", {
        "verified_at": timestamp(), "type": type(exc).__name__, "error": str(exc),
        "campaigns_consumed": 0, "inference": 0, "retrieval": 0, "admission": 0,
        "no_product_or_case_preparation": True,
    })
    raise
runner.write(CONTROL / "preflight_model_identity.json", identity)
freeze = runner.read(runner.DOCS / "freeze_final_v2_r3.json")
runner.write(CONTROL / "preflight_summary.json", {
    "verified_at": timestamp(), "status": "PASS",
    "freeze_sha256": expected_sha, "execution_id": auth["execution_id"],
    "authorization_sha256": hashlib.sha256((CONTROL / "AUTHORIZED").read_bytes()).hexdigest(),
    "execution_errors": report["execution_errors"], "runtime": sys.version,
    "llm": profile["llm"], "profiles": profile["profiles"],
    "campaigns_consumed": 0, "inference": 0, "retrieval": 0, "admission": 0,
})
print(json.dumps(runner.read(CONTROL / "preflight_summary.json"), indent=2))
