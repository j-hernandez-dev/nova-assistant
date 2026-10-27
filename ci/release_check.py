"""Check source-release metadata without inference, packaging or Git mutations."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/j-hernandez-dev/nova-assistant"


def check(tag=None):
    package = json.loads((ROOT / "desktop/package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "desktop/package-lock.json").read_text(encoding="utf-8"))
    python = ast.parse((ROOT / "local_cli/__init__.py").read_text(encoding="utf-8"))
    python_version = next(ast.literal_eval(node.value) for node in python.body
                          if isinstance(node, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets))
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_version = re.search(r'^version\s*=\s*"([^"]+)"', project, re.M).group(1)
    versions = {"desktop": package["version"], "lock": lock["version"],
                "lock_package": lock["packages"][""]["version"],
                "python": python_version, "pyproject": project_version}
    version = package["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version) or len(set(versions.values())) != 1:
        raise ValueError("RELEASE_VERSION_MISMATCH: " + json.dumps(versions))
    if tag is not None and tag != "v" + version:
        raise ValueError("RELEASE_TAG_MISMATCH")
    for section in ("dependencies", "devDependencies"):
        if package.get(section, {}) != lock["packages"][""].get(section, {}):
            raise ValueError("RELEASE_DEPENDENCY_LOCK_MISMATCH: " + section)
    for name in ("electron", "esbuild"):
        dependency_version = lock["packages"]["node_modules/" + name]["version"]
        if package.get("allowScripts", {}).get(name + "@" + dependency_version) is not True:
            raise ValueError("RELEASE_DEPENDENCY_SCRIPT_NOT_APPROVED: " + name)
    if package["repository"]["url"] != REPOSITORY + ".git" or package["homepage"] != REPOSITORY:
        raise ValueError("RELEASE_REPOSITORY_MISMATCH")
    if package["build"]["publish"] != dict(provider="github", owner="j-hernandez-dev", repo="nova-assistant"):
        raise ValueError("RELEASE_PUBLISH_TARGET_MISMATCH")
    main = (ROOT / "desktop/electron/main.ts").read_text(encoding="utf-8")
    about = (ROOT / "desktop/src/components/AboutSettings.tsx").read_text(encoding="utf-8")
    if "const APP_VERSION = app.getVersion()" not in main or "'get-app-version', () => APP_VERSION" not in main:
        raise ValueError("RELEASE_DESKTOP_VERSION_NOT_OBSERVED")
    if "value={version===null?" not in about or "'v'+version" not in about:
        raise ValueError("RELEASE_ABOUT_VERSION_NOT_OBSERVED")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if version not in readme or not (ROOT / "docs/releases" / (version + ".md")).is_file():
        raise ValueError("RELEASE_DOCUMENTATION_MISSING")
    broken = []
    for target in re.findall(r'\]\(([^)]+)\)', readme):
        if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
            continue
        if not (ROOT / target.split("#", 1)[0]).exists():
            broken.append(target)
    if broken:
        raise ValueError("README_BROKEN_LOCAL_LINKS: " + json.dumps(broken))
    for path in ("desktop/build/icon.ico", "desktop/build/icon.icns", "desktop/build/icon.png", "desktop/public/icon.svg"):
        if not (ROOT / path).is_file():
            raise ValueError("RELEASE_ICON_MISSING: " + path)
    return dict(status="PASS", version=version, proposed_tag="v" + version,
                about="Electron package version", metadata=versions,
                scope="source metadata only; regression results are separate")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    args = parser.parse_args()
    print(json.dumps(check(args.tag)))
