"""Small explicit user preference for the optional fetch tool.

No Active Web configuration, engine, search provider or certificate manifest is
required. Reading settings never writes or migrates the user's configuration.
"""
import json
import os
from pathlib import Path
import tempfile


CONFIG_FILENAME = 'fetch-preference.json'


def load_fetch_enabled(state_dir) -> bool:
    from local_cli.web_config import has_web_settings, load_web_settings
    if has_web_settings(state_dir):
        return load_web_settings(state_dir)['fetchEnabled']
    """Fetch is enabled on a fresh installation; an explicit saved off wins."""
    path = Path(state_dir).expanduser() / CONFIG_FILENAME
    try:
        if path.is_symlink():
            return False
        if not path.exists():
            return True
        if not path.is_file() or path.stat().st_size > 1024:
            return False
        with path.open('rb') as stream:
            payload = stream.read(1025)
        if len(payload) > 1024:
            return False
        value = json.loads(payload.decode('utf-8'))
        if (type(value) is not dict or set(value) != {'schema', 'enabled'}
                or value['schema'] != 'NOVA_FETCH_PREFERENCE_V1' or type(value['enabled']) is not bool):
            return False
        return value['enabled']
    except (OSError, ValueError, TypeError, UnicodeError):
        return False


def save_fetch_enabled(state_dir, enabled: bool) -> None:
    if type(enabled) is not bool:
        raise ValueError('Fetch enabled must be true or false.')
    from local_cli.web_config import has_web_settings, update_web_settings
    if has_web_settings(state_dir):
        update_web_settings(state_dir, fetchEnabled=enabled)
        return
    root = Path(state_dir).expanduser()
    temporary = None
    try:
        root.mkdir(parents=True, exist_ok=True)
        path = root / CONFIG_FILENAME
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise OSError('Invalid fetch settings file')
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=root,
                prefix='.fetch-preference-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(dict(schema='NOVA_FETCH_PREFERENCE_V1', enabled=enabled), stream)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
