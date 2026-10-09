"""Preserve read-only Ollama metadata after the frozen backend gate rejected it."""
import datetime
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(r"C:/Users/joseh/Downloads/nova-local-cli/nova-assistant")
CONTROL = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests/knowledge_inputs_v2/revision_03"))
import runner
profile = runner.read(runner.DOCS / "execution_profile_v2_r3.json")
llm = profile["llm"]
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
def api(path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(llm["endpoint"] + "/api/" + path,
        data=body, headers={"Content-Type": "application/json"})
    with opener.open(request, timeout=15) as response:
        return json.load(response)

metadata = {"captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "expected": llm, "read_only_endpoints": ["tags", "ps", "show", "version"]}
for path in ("tags", "ps", "show", "version"):
    try:
        metadata[path] = api(path, {"model": llm["model"]} if path == "show" else None)
    except Exception as exc:
        metadata[path + "_error"] = {"type": type(exc).__name__, "message": str(exc)}
runner.write(CONTROL / "backend_metadata_after_rejection.json", metadata)
matches = [row for row in metadata.get("tags", {}).get("models", [])
    if row.get("name") == llm["model"]]
resident = [row for row in metadata.get("ps", {}).get("models", [])
    if row.get("name") == llm["model"]]
post = runner.preflight(runner.read(CONTROL / "AUTHORIZED"))
post["verified_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
runner.write(CONTROL / "post_stop_integrity.json", post)
summary = {
    "status": "BLOCKED_BEFORE_CAMPAIGNS", "error": "BACKEND_RUNNER_MISMATCH",
    "freeze_sha256": post["freeze_sha256"], "integrity_errors": post["integrity_errors"],
    "execution_errors_offline": post["execution_errors"],
    "expected_runner": llm["runner"], "installed_matching_models": matches,
    "resident_matching_models": resident,
    "ollama_version": metadata.get("version"),
    "campaigns_consumed": 0, "inference": 0, "retrieval": 0, "admission": 0,
    "campaign_output_exists": (CONTROL / "campaigns").exists(),
    "freeze_ledger_exists": (pathlib.Path(r"C:/Users/joseh/AppData/Local/Temp/nova-k8-v2-certification-ledger") / (post["freeze_sha256"] + ".json")).exists(),
}
runner.write(CONTROL / "execution_stopped_summary.json", summary)
print(json.dumps(summary, indent=2))
