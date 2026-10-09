"""Non-campaign structural validation for K8 V2. Never imports product or runners."""
import hashlib, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "knowledge_inputs_v2"
FIX = Path(__file__).resolve().parent / "fixtures"
HIST = [ROOT / "docs" / "architecture" / n for n in (
    "NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md",
    "NOVA_CORE_ARQUITECTURA_V1.md",
    "NOVA_MEMORY_ARQUITECTURA_V1.md",
    "NOVA_KNOWLEDGE_CONTEXT_CAPABILITY_RESOLUTION_V1.md",
)] + list((ROOT / "docs" / "knowledge_inputs_v1").rglob("*")) + list((ROOT / "tests" / "knowledge_inputs_v1").rglob("*"))

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    corpus = json.loads((FIX / "corpus_v2.json").read_text(encoding="utf-8"))
    gold = json.loads((FIX / "gold_v2.json").read_text(encoding="utf-8"))
    docs = corpus["source_documents"]; cases = corpus["cases"]
    assert corpus["status"] == gold["status"] == "FROZEN_PENDING_HUMAN_REVIEW"
    assert len({d["id"] for d in docs}) == len(docs) == 18
    assert len({c["id"] for c in cases}) == len(cases) == 20
    assert {c["profile"] for c in cases} == {"4K", "8K"}
    assert sum(c["profile"] == "4K" for c in cases) == 14
    assert sum(c["profile"] == "8K" for c in cases) == 6
    assert "SABLE_ROUTE" not in (FIX / "corpus_v2.json").read_text(encoding="utf-8")
    historical = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in HIST if p.is_file())
    tokens = [d["id"] for d in docs] + [c["id"] for c in cases]
    collisions = sorted(t for t in tokens if t in historical)
    forbidden_references = sorted(t for t in ["SABLE_ROUTE", "REPAIR_V1", "REPAIR_V2", "REPAIR_V3", "REPAIR_V4", "REPAIR_V5", "REPAIR_V6"] if t in historical)
    assert not collisions, collisions
    assert gold["profiles"]["4K"]["denominator"] == 14 and gold["profiles"]["8K"]["denominator"] == 6
    out = {"status":"STRUCTURE_VALIDATED_ONLY", "campaigns_consumed":0, "inference":0,
           "retrieval":0, "admission":0, "collisions":collisions, "historical_reference_tokens":forbidden_references,
           "historical_inventory":[{"path":str(p.relative_to(ROOT)),"sha256":sha(p)} for p in HIST if p.is_file()],
           "v2_hashes":[{"path":str(p.relative_to(ROOT)),"sha256":sha(p)} for p in [FIX/"corpus_v2.json", FIX/"gold_v2.json"]],
           "scope":"literal token collision scan only; not semantic independence"}
    (DOC / "VALIDATION_V2.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (DOC / "NON_REUSE_V2.json").write_text(json.dumps({"status":"VALIDATED_LITERAL_NON_REUSE","collisions":collisions,"historical_reference_tokens":forbidden_references,"scope":out["scope"],"historical_inventory":out["historical_inventory"]}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status":out["status"],"cases":len(cases),"documents":len(docs),"collisions":collisions,"campaigns_consumed":0}))

if __name__ == "__main__": main()
