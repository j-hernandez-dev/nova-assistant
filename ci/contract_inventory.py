"""Static, fail-closed inventory of pytest contracts; never imports product/tests."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "ci/pytest_contracts.json"
CATEGORIES = {
    "CURRENT_PORTABLE_CI", "CURRENT_LOCAL_EVIDENCE_ONLY",
    "HISTORICAL_CERTIFICATION_ARTIFACT", "SPECIAL_INFRASTRUCTURE_ONLY",
    "CURRENT_WINDOWS_CI", "CURRENT_WINDOWS_NATIVE_CI", "CURRENT_NATIVE_CERTIFICATION",
}
ORDINARY_CATEGORIES = {"CURRENT_PORTABLE_CI", "CURRENT_WINDOWS_CI", "CURRENT_WINDOWS_NATIVE_CI"}
SPECIAL_CATEGORIES = {"SPECIAL_INFRASTRUCTURE_ONLY", "CURRENT_NATIVE_CERTIFICATION"}
DISCOVERY_ROOTS = ("tests", "native/nova-browser-host/tests", "ci/tests")


def discover(root=ROOT):
    records = []
    paths = {path for relative in DISCOVERY_ROOTS for path in (root / relative).rglob("*.py")}
    for path in sorted(paths):
        if not (path.name.startswith("test_") or path.name.endswith("_test.py")):
            continue
        relative = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=relative)

        def visit(body, classes=()):
            for node in body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("test"):
                        records.append({
                            "nodeid": relative + "::" + "::".join((*classes, node.name)),
                            "line": node.lineno,
                        })
                elif isinstance(node, ast.ClassDef):
                    visit(node.body, (*classes, node.name))
                elif isinstance(node, (ast.For, ast.If, ast.With, ast.Try)):
                    for field in ("body", "orelse", "finalbody"):
                        visit(getattr(node, field, ()), classes)
                    if isinstance(node, ast.Try):
                        for handler in node.handlers:
                            visit(handler.body, classes)
        visit(tree.body)
    counts = Counter(row["nodeid"] for row in records)
    if any(count != 1 for count in counts.values()):
        raise ValueError("DUPLICATE_STATIC_CONTRACT_NODE")
    return records


def base_nodeid(nodeid):
    # Parameterized function/class cases remain one declared contract; every
    # collected parameter instance is selected, never filtered by its outcome.
    # Only the selector prefix is structural. A parameter ID can itself contain
    # brackets, IPv6 '::', URLs or query text; never parse that payload as nodes.
    return nodeid.replace("\\", "/").split("[", 1)[0]


def validate(manifest=None, discovered=None):
    data = manifest if manifest is not None else json.loads(MANIFEST.read_text(encoding="utf-8"))
    found = discovered if discovered is not None else discover()
    declared = data["contracts"]
    nodes = [row["nodeid"] for row in declared]
    if len(nodes) != len(set(nodes)):
        raise ValueError("DUPLICATE_CLASSIFICATION")
    actual = {row["nodeid"] for row in found}
    expected = set(nodes)
    if actual != expected:
        raise ValueError("CONTRACT_CLASSIFICATION_DRIFT: " + json.dumps({
            "unclassified": sorted(actual - expected), "removed": sorted(expected - actual)
        }))
    for row in declared:
        category = row["classification"]
        if category not in CATEGORIES or row["rule"] not in data["rules"]:
            raise ValueError("INVALID_CLASSIFICATION: " + row["nodeid"])
        rule = data["rules"][row["rule"]]
        if any(job not in data['jobs'] for job in row.get('additional_jobs', ())):
            raise ValueError('UNDECLARED_ADDITIONAL_JOB: ' + row['nodeid'])
        if any(job not in data['jobs']or data['jobs'][job]['ordinary']or data['jobs'][job]['platforms']!=['Windows']
               for job in row.get('native_jobs',())):
            raise ValueError('INVALID_EXPLICIT_NATIVE_JOB: '+row['nodeid'])
        if row.get('additional_jobs') and (category not in ORDINARY_CATEGORIES or
                any(not data['jobs'][job]['ordinary'] for job in row['additional_jobs'])):
            raise ValueError('INVALID_ADDITIONAL_ORDINARY_SCOPE: ' + row['nodeid'])
        if rule["classification"] != category or not rule["reason"] or not rule["references"]:
            raise ValueError("UNSUPPORTED_CLASSIFICATION: " + row["nodeid"])
        if category in ORDINARY_CATEGORIES | {'CURRENT_NATIVE_CERTIFICATION'} and (not rule["job"] or not rule["platforms"]):
            raise ValueError("UNCOVERED_CURRENT_CONTRACT: " + row["nodeid"])
        if category not in ORDINARY_CATEGORIES and rule.get("ordinary_ci"):
            raise ValueError("NONPORTABLE_ORDINARY_CI: " + row["nodeid"])
        if rule.get('job') is not None and rule['job'] not in data['jobs']:
            raise ValueError('UNDECLARED_RULE_JOB: ' + row['nodeid'])
        if category in ('CURRENT_WINDOWS_CI','CURRENT_WINDOWS_NATIVE_CI','CURRENT_NATIVE_CERTIFICATION') and rule['platforms']!=['Windows']:
            raise ValueError('INVALID_WINDOWS_SCOPE: ' + row['nodeid'])
        if category in ORDINARY_CATEGORIES and not data['jobs'][rule['job']]['ordinary']:
            raise ValueError('ORDINARY_CONTRACT_WITHOUT_ORDINARY_JOB: ' + row['nodeid'])
        if category in SPECIAL_CATEGORIES and rule.get('job')and data['jobs'][rule['job']]['ordinary']:
            raise ValueError('NATIVE_CERTIFICATION_IN_ORDINARY_JOB: ' + row['nodeid'])
        for reference in rule["references"]:
            if not (ROOT / reference["path"]).is_file():
                raise ValueError("CLASSIFICATION_REFERENCE_MISSING: " + reference["path"])
            if reference.get("sha256"):
                actual_hash = hashlib.sha256((ROOT / reference["path"]).read_bytes()).hexdigest()
                if actual_hash != reference["sha256"]:
                    raise ValueError("CLASSIFICATION_REFERENCE_DRIFT: " + reference["path"])
    return data


def select(data, job, platform, *, special=False):
    rows = []
    for row in data["contracts"]:
        rule = data["rules"][row["rule"]]
        if special and job in row.get('native_jobs',())and platform in data['jobs'][job]['platforms']:
            rows.append(row['nodeid']);continue
        if (rule["job"] != job and job not in row.get('additional_jobs', ())) or platform not in rule["platforms"]:
            continue
        permitted = row["classification"] in ORDINARY_CATEGORIES
        permitted |= special and row["classification"] in SPECIAL_CATEGORIES
        if permitted:
            rows.append(row["nodeid"])
    if not rows:
        raise ValueError("EMPTY_POSITIVE_SELECTION: " + job + "/" + platform)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    if args.inventory:
        records = discover()
        end = args.offset + args.limit if args.limit else len(records)
        print(json.dumps(records[args.offset:end], separators=(",", ":")))
    else:
        data = validate()
        print(json.dumps({
            "status": "PASS", "static_contracts": len(data["contracts"]),
            "categories": dict(Counter(row["classification"] for row in data["contracts"])),
            "discovery_roots": DISCOVERY_ROOTS, "unclassified": [], "stale": [], "duplicates": [],
            "product_tests_executed": 0, "inference": 0,
        }, separators=(",", ":")))


if __name__ == "__main__":
    main()

