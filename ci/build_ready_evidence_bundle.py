"""Archive only the external raw files referenced by the accepted READY graph.

Never runs product/tests/backend, never moves originals or rewrites a manifest.
The full archive can be verified later without the original machine paths.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
READY = ROOT / "docs/knowledge_inputs_v1/ready_closure/manifest.json"
EXPECTED_READY = "2883164d13bb08e80b4d9b41674fc8d93ef4f432b5caf7bb5c1166d5d0c4f2cc"
TAG = "nova-knowledge-inputs-v1-ready"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def external_graph(repository_rows=None):
    if digest(READY) != EXPECTED_READY:
        raise ValueError("READY_MANIFEST_DRIFT")
    data = read(READY)
    files, sources, groups = {}, [], []

    def add(row, base, label):
        path = Path(row["path"])
        if not path.is_absolute():
            path = base / path
        path = path.resolve()
        expected = row.get("sha256") or row.get("expectedSha256")
        if not expected or not re.fullmatch("[0-9a-f]{64}", expected):
            raise ValueError("MISSING_EXPECTED_HASH:" + str(path))
        if path.is_relative_to(ROOT):
            if repository_rows is not None:
                repository_rows.append({"path": path.relative_to(ROOT).as_posix(),
                                        "sha256": expected, "required_by": label})
            return
        key = str(path)
        if key in files and files[key]["sha256"] != expected:
            raise ValueError("CONFLICTING_EXTERNAL_PINS:" + key)
        if key not in files:
            if not path.is_file() or digest(path) != expected:
                raise ValueError("EXTERNAL_RAW_DRIFT:" + key)
            files[key] = {"origin": path.as_posix(), "size": path.stat().st_size,
                          "sha256": expected, "required_by": []}
        if label not in files[key]["required_by"]:
            files[key]["required_by"].append(label)

    index_labels = {
        "accepted_READY_audit", "SCF_R2_delivery", "SCF_R2_raw_Turn",
        "SCF_R2_preexecution", "SCF_original_preexecution", "SCF_original_attempt",
        "K8_V2_original_35_attempts", "R1_R2_focused_harness",
    }
    for group in data["integrity"]["groups"]:
        label = group["label"]
        src = Path(group["source"])
        if not src.is_absolute():
            src = ROOT / src
        src = src.resolve()
        if not src.is_file() or digest(src) != group["source_sha256"]:
            raise ValueError("READY_SOURCE_DRIFT:" + str(src))
        sources.append({"label": label, "origin": src.as_posix(),
                        "sha256": group["source_sha256"]})
        add({"path": str(src), "sha256": group["source_sha256"]}, ROOT,
            label + ":source_manifest")
        content = read(src)
        base = ROOT
        if label in index_labels:
            rows, base = content["files"], src.parent
        elif label in {"preexisting_product_and_evidence_preservation", "original_focal_preservation"}:
            rows = [{"path": key, "sha256": sha} for key, sha in content.items()]
        elif label == "SCF_R2_699_pins":
            rows = content["pins"]
        elif label == "K8_V2_R4_629_pins":
            rows = content["pins"] + content["external_pins"]
        elif label == "current_regression_archived_11_artifacts":
            rows = content["artifacts"]
        elif label == "current_regression_116_verified_references":
            rows = content["integrityAfter"]["immutableHistoricalReferences"]
        elif label == "original_K8_campaign_closure_artifacts":
            rows = content["artifacts"]
        elif label == "original_K8_raw_inventory_identity":
            rows = [content["artifacts"]["rawInventory"]]
        elif label == "original_K8_138_raw_artifacts":
            rows = content["artifacts"]
        elif label == "accepted_identity_anchors":
            # All five exact anchors are inside the checkout and pinned by READY;
            # no additional external members are introduced by this group.
            rows = []
        else:
            raise ValueError("UNRECOGNIZED_READY_GROUP:" + label)
        if label != "accepted_identity_anchors" and len(rows) != group["checked"]:
            raise ValueError("READY_GROUP_CARDINALITY_DRIFT:" + label)
        for row in rows:
            add(row, base, label)
        groups.append({"label": label, "declared_rows": group["checked"],
                       "external_unique_references": sum(label in f["required_by"] for f in files.values())})
    for row in data["files"]:
        add(row, ROOT, "additive_READY_closure_manifest_files")
    delivery_path = READY.parent / "evidence_index.json"
    expected_delivery = "85ef997d44975d4a65a7419aa9f7a8007c60632171579b087a0813cce6857ace"
    if digest(delivery_path) != expected_delivery:
        raise ValueError("READY_DELIVERY_INDEX_DRIFT")
    for row in read(delivery_path)["files"]:
        add(row, delivery_path.parent, "READY_delivery_index")
    ordered = sorted(files.values(), key=lambda row: row["origin"].casefold())
    for i, row in enumerate(ordered, 1):
        row["archive_path"] = "raw/" + str(i).zfill(6) + "/" + Path(row["origin"]).name
        row["required_by"].sort()
    return {
        "schema": "knowledge-ready-external-bundle-index-1",
        "scope": "Exactly external members and source indices of the accepted READY manifest/verifier graph; no directory sweep",
        "ready_manifest_path": READY.relative_to(ROOT).as_posix(),
        "ready_manifest_sha256": EXPECTED_READY,
        "ready_delivery_index_sha256": expected_delivery,
        "ready_closure_id": data["closure_id"],
        "future_tag": TAG, "version_unchanged": "0.12.6",
        "publication": "NOT_PUBLISHED; candidate asset for future release or equivalent durable storage",
        "originals_unmodified": True, "files": ordered, "source_manifests": sources,
        "groups": groups, "raw_file_count": len(ordered),
        "raw_total_bytes": sum(row["size"] for row in ordered),
        "preserved_historical_states": data["preserved_historical_states"],
    }


def verify_archive(path, expected_sha=None):
    if expected_sha is not None and digest(path) != expected_sha:
        raise ValueError("BUNDLE_SHA256_DRIFT")
    with zipfile.ZipFile(path) as archive:
        index = json.loads(archive.read("INDEX.json"))
        expected_names = {"INDEX.json", "README.md"} | {row["archive_path"] for row in index["files"]}
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != expected_names:
            raise ValueError("BUNDLE_MEMBER_SET_DRIFT")
        for row in index["files"]:
            h, size = hashlib.sha256(), 0
            with archive.open(row["archive_path"]) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(block)
                    size += len(block)
            if size != row["size"] or h.hexdigest() != row["sha256"]:
                raise ValueError("BUNDLE_MEMBER_DRIFT:" + row["archive_path"])
    return {"status": "PASS", "raw_file_count": index["raw_file_count"],
            "raw_total_bytes": index["raw_total_bytes"], "bundle_sha256": digest(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--sha256")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_archive(args.verify, args.sha256)))
        return
    index = external_graph()
    if args.inventory:
        print(json.dumps({key: value for key, value in index.items() if key != "files"}))
        return
    if args.output is None:
        parser.error("new output directory required")
    output = args.output.resolve()
    if output.is_relative_to(ROOT) or output.exists():
        raise ValueError("BUNDLE_REQUIRES_FRESH_OUTPUT_OUTSIDE_CHECKOUT")
    parent = output.parent
    while not parent.exists():
        parent = parent.parent
    if subprocess.run(["git", "-C", str(parent), "rev-parse", "--show-toplevel"],
                      capture_output=True).returncode == 0:
        raise ValueError("BUNDLE_OUTPUT_INSIDE_GIT_WORKSPACE")
    output.mkdir(parents=True)
    created = datetime.now(timezone.utc).isoformat()
    index["created_at"] = created
    readme = ("# Knowledge Inputs V1 READY: external raw evidence\n\n"
              "Preserved bytes only; not a new campaign or changed certification.\n"
              "INDEX.json maps every original path to an archive entry, size and SHA-256.\n"
              "Verify the bundle SHA in the versioned receipt, then each entry.\n"
              "Restore by this mapping if needed; do not rewrite historical paths/pins.\n"
              "The archive includes personal original paths and raw evidence; review\n"
              "publication destination/access before a later human-authorized release.\n"
              "CI does not download or require this archive.\n\n"
              "READY manifest SHA: " + EXPECTED_READY + "\n"
              "Future tag: " + TAG + "; version 0.12.6 unchanged.\n"
              "Original result labels, ledgers and attempts remain immutable.\n")
    archive_path = output / (TAG + "-external-evidence.zip")
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in (("INDEX.json", json_bytes(index)), ("README.md", readme.encode("utf-8"))):
            info = zipfile.ZipInfo(name, (2026, 10, 9, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100444 << 16
            archive.writestr(info, content)
        for row in index["files"]:
            origin = Path(row["origin"])
            if digest(origin) != row["sha256"]:
                raise ValueError("ORIGINAL_DRIFT_BEFORE_ARCHIVE:" + str(origin))
            info = zipfile.ZipInfo(row["archive_path"], (2026, 10, 9, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100444 << 16
            with archive.open(info, "w", force_zip64=True) as member, origin.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    member.write(block)
            if digest(origin) != row["sha256"]:
                raise ValueError("ORIGINAL_DRIFT_AFTER_ARCHIVE:" + str(origin))
    receipt = verify_archive(archive_path)
    receipt.update(schema="knowledge-ready-durable-bundle-receipt-1", created_at=created,
                   bundle_path=archive_path.as_posix(), bundle_bytes=archive_path.stat().st_size,
                   index_sha256=hashlib.sha256(json_bytes(index)).hexdigest(),
                   ready_manifest_sha256=EXPECTED_READY, future_tag=TAG,
                   publication="NOT_PUBLISHED", originals_preserved=True,
                   product_tests_executed=0, inference=0, retrieval=0, admission=0)
    for name, value in (("index.json", index), ("receipt.json", receipt)):
        with (output / name).open("xb") as stream:
            stream.write(json_bytes(value))
    archive_path.chmod(0o444)
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
