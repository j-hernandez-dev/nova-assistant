"""Positive CI entry point. Collection never runs a contract/fixture or model."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from contract_inventory import ROOT, MANIFEST, base_nodeid, select, validate

sys.path.insert(0, str(ROOT))


def private_environment(output, *, special):
    # Process-local fixture profiles, not an OS sandbox. Never load a user .env.
    permitted = ("SystemRoot", "WINDIR", "PATH", "PATHEXT", "COMSPEC",
                 "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS",
                 "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA",
                 "LANG", "LC_ALL")
    child_env = {key: os.environ[key] for key in permitted if key in os.environ}
    child_env.update(PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                     PYTHONIOENCODING="utf-8", PYTHONPATH=str(ROOT),
                     NOVA_MEMORY_SEMANTIC_PROFILE="NOT_CERTIFIED")
    if output is not None:
        for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
                    "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "TEMP", "TMP"):
            folder = output / "private" / key.lower()
            folder.mkdir(parents=True, exist_ok=True)
            child_env[key] = str(folder)
    if special:
        child_env.update({key: "1" for key in (
            "NOVA_S3_HOST_REAL", "NOVA_S4_HOST_REAL",
            "NOVA_S5_HOST_REAL", "NOVA_S6_HOST_REAL")})
    return child_env


def new_output(path):
    if path is None:
        return None
    output = path.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("CI_OUTPUT_INSIDE_CHECKOUT")
    if output.exists():
        raise ValueError("CI_OUTPUT_ALREADY_EXISTS")
    ancestor = output.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    probe = subprocess.run(["git", "-C", str(ancestor), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
    if probe.returncode == 0:
        raise ValueError("CI_OUTPUT_INSIDE_GIT_WORKSPACE")
    output.mkdir(parents=True)
    return output


class CollectionGuard:
    def __init__(self, data, selected, job, host, special):
        self.data = data
        self.selected = set(selected)
        self.job, self.host, self.special = job, host, special
        self.items = []
        self.tests_executed = 0
        self.passed = False

    def pytest_configure(self, config):
        import pytest
        # Positive selection must not be narrowed by config/environment filters.
        for name in ("keyword", "markexpr", "ignore", "ignore_glob", "deselect", "lf"):
            if config.getoption(name, default=None):
                raise pytest.UsageError("UNAUTHORIZED_CI_SELECTION_FILTER:" + name)

    def pytest_collection_modifyitems(self, session, config, items):
        import pytest
        declared = {row["nodeid"]: row for row in self.data["contracts"]}
        collected = {base_nodeid(item.nodeid) for item in items}
        errors = []
        for item in items:
            base = base_nodeid(item.nodeid)
            row = declared.get(base)
            if base not in self.selected or row is None:
                errors.append("UNCLASSIFIED_OR_UNSELECTED:" + item.nodeid)
                continue
            rule = self.data["rules"][row["rule"]]
            ordinary = row["classification"] == "CURRENT_PORTABLE_CI"
            native = self.special and row["classification"] == "SPECIAL_INFRASTRUCTURE_ONLY"
            if not (ordinary or native) or rule["job"] != self.job or self.host not in rule["platforms"]:
                errors.append("WRONG_CI_SCOPE:" + item.nodeid)
        errors.extend("UNCOLLECTED_POSITIVE_SELECTOR:" + node for node in sorted(self.selected - collected))
        if errors:
            # Fail before any test setup/execution; never remove or skip items.
            raise pytest.UsageError("\n".join(errors))
        self.items = [item.nodeid for item in items]
        self.passed = True

    def pytest_runtest_logstart(self, nodeid, location):
        self.tests_executed += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", choices=("core", "security", "memory", "knowledge", "security-native"), required=True)
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--special", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    actual_host = {"Windows": "Windows", "Linux": "Linux", "Darwin": "macOS"}[platform.system()]
    if args.special != (args.job == "security-native"):
        parser.error("SPECIAL_INFRASTRUCTURE_REQUIRES_EXPLICIT_SECURITY_NATIVE_SCOPE")
    if args.special and actual_host != "Windows":
        parser.error("NATIVE_SECURITY_REQUIRES_WINDOWS")
    if not args.collect_only and args.output is None:
        parser.error("execution requires fresh private output outside checkout")
    data = validate()
    selected = select(data, args.job, actual_host, special=args.special)
    output = new_output(args.output)
    # Preserve explicitly supplied import search paths for the already-installed
    # validation runtime; this is not inherited product config or model settings.
    old_env = dict(os.environ)
    ci_env = private_environment(output, special=args.special)
    os.environ.clear()
    os.environ.update(ci_env)
    import pytest
    guard = CollectionGuard(data, selected, args.job, actual_host, args.special)
    arguments = ["-q", "-p", "no:cacheprovider", "--rootdir", str(ROOT)]
    # pytest 9 provides subtests itself; older versions require the installed
    # pytest-subtests plugin. Explicit loading avoids unrelated host plugins.
    if int(pytest.__version__.split(".", 1)[0]) < 9:
        arguments += ["-p", "pytest_subtests"]
    if args.collect_only:
        arguments += ["--collect-only"]
    elif output is not None:
        arguments += ["--basetemp", str(output / "pytest-private"),
                      "--junitxml", str(output / "tests.xml")]
    arguments += selected
    stream = io.StringIO()
    try:
        with redirect_stdout(stream), redirect_stderr(stream):
            exit_code = int(pytest.main(arguments, plugins=[guard]))
    finally:
        os.environ.clear()
        os.environ.update(old_env)
    transcript = stream.getvalue()
    receipt = {
        "schema": "positive-contract-ci-run-1",
        "scope": "COLLECTION_ONLY" if args.collect_only else "CURRENT_REGRESSION_CONTRACT",
        "job": args.job, "host": actual_host, "python": sys.version,
        "pytest": pytest.__version__, "selection_manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "positive_base_contracts": len(selected), "collected_parameter_instances": len(guard.items),
        "collected_nodeids_sha256": hashlib.sha256(json.dumps(guard.items, ensure_ascii=False).encode()).hexdigest(),
        "collection_guard": "PASS" if guard.passed else "FAIL",
        "tests_executed": guard.tests_executed,
        "quality_attempts": 0, "model_campaigns": 0,
        "exit_code": exit_code, "special_infrastructure": args.special,
        "new_skips_xfails_or_deselection": False,
    }
    if output is not None:
        (output / "selection.json").write_text(json.dumps(selected, indent=2) + "\n", encoding="utf-8")
        (output / "collected_nodeids.json").write_text(json.dumps(guard.items, indent=2) + "\n", encoding="utf-8")
        (output / "pytest.log").write_text(transcript, encoding="utf-8")
        (output / "run.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if exit_code:
        print(transcript, file=sys.stderr)
    print(json.dumps(receipt))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

