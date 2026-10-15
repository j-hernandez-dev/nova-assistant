"""User-data namespaces are isolated; explicit custom paths remain supported."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from local_cli.application.persistence import create_persistence_service
from local_cli.config import CONFIG_DEFAULTS, ENV_VAR_MAP, Config
from local_cli.conversation_store import ConversationStore

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    for name in ENV_VAR_MAP:
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def test_default_config_does_not_import_legacy_profile(isolated_home):
    old = isolated_home / ".config/local-cli/config"
    old.parent.mkdir(parents=True)
    old.write_text("model=legacy-profile-model\n", encoding="utf-8")

    config = Config()

    assert Path(config.config_file) == isolated_home / ".config/nova/config"
    assert config.model == CONFIG_DEFAULTS["model"]
    assert old.read_text(encoding="utf-8") == "model=legacy-profile-model\n"


def test_nova_config_loads_and_preserves_custom_state_dir(isolated_home):
    config_file = isolated_home / ".config/nova/config"
    config_file.parent.mkdir(parents=True)
    custom_state = isolated_home / "custom-state"
    config_file.write_text(f"model=nova-profile-model\nstate_dir={custom_state}\n",
                           encoding="utf-8")

    config = Config()

    assert config.model == "nova-profile-model"
    assert Path(config.state_dir) == custom_state


def test_explicit_config_path_still_accepts_legacy_location(isolated_home):
    config_file = isolated_home / ".config/local-cli/config"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("model=explicit-profile-model\n", encoding="utf-8")

    config = Config(config_file=str(config_file))

    assert Path(config.config_file) == config_file
    assert config.model == "explicit-profile-model"


@pytest.mark.parametrize("custom", [False, True])
def test_persistence_writes_selected_profile_without_migrating_old_data(isolated_home, custom):
    workspace = isolated_home / "workspace"
    workspace.mkdir()
    old = ConversationStore(str(isolated_home / ".local/state/local-cli"), cwd=str(workspace))
    old.save_checked([{"role": "user", "content": "old conversation"}])
    original = old.path.read_bytes()
    selected = isolated_home / ("custom-state" if custom else ".local/state/nova")
    config = Config(cli_args=SimpleNamespace(state_dir=str(selected)) if custom else None)
    persistence = create_persistence_service(config=config, workspace=workspace)

    assert persistence.load() == []
    messages = [{"role": "user", "content": "new conversation: ¡Nova!"}]
    persistence.save(messages)
    snapshot_id = persistence.save_session(messages)

    assert persistence.last_error is None
    assert ConversationStore(str(selected), cwd=str(workspace)).load() == messages
    assert (selected / "sessions" / f"{snapshot_id}.jsonl").is_file()
    assert old.path.read_bytes() == original


@pytest.mark.parametrize("xdg", [False, True])
def test_catalog_cache_uses_nova_and_preserves_xdg_override(isolated_home, xdg):
    cache_root = isolated_home / ("custom-cache" if xdg else ".cache")
    legacy = cache_root / "local-cli/model_catalog.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps({"updated_at": int(time.time()),
        "models": [{"name": "legacy-cache-only"}]}), encoding="utf-8")
    original = legacy.read_bytes()
    env = dict(os.environ)
    env.pop("XDG_CACHE_HOME", None)
    if xdg:
        env["XDG_CACHE_HOME"] = str(cache_root)
    # A subprocess isolates module-level cache paths from the rest of the suite.
    result = subprocess.run([sys.executable, "-c", """
import json
from local_cli import model_catalog, model_search
before = model_catalog.get_cached_catalog()
model_search.search_models = lambda **kwargs: [{"name": "nova-cache-only"}]
model_catalog.update_catalog()
print(json.dumps({"before": before, "path": str(model_catalog._CACHE_FILE),
                  "after": model_catalog.get_cached_catalog()}))
"""], cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True, timeout=15)

    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data["before"] is None
    assert Path(data["path"]) == cache_root / "nova/model_catalog.json"
    names = {entry["name"] for entry in data["after"]}
    assert "nova-cache-only" in names
    assert "legacy-cache-only" not in names
    assert legacy.read_bytes() == original
