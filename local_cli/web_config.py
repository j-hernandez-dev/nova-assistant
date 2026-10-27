"""Atomic, host-owned web preferences shared by Desktop and CLI.

Existing individual preferences are read only until the first unified save.
Permission changes never grant approval for a browser action.
"""
import json
import os
from pathlib import Path
import tempfile

FILENAME = 'web-preferences.json'
SCHEMA = 'NOVA_WEB_PREFERENCES_V1'
DEFAULTS = dict(fetchEnabled=True, searchEnabled=True, browserEnabled=True,
                engine='google', browser='webview2')


def validate_web_settings(value):
    if (type(value) is not dict or set(value) != set(DEFAULTS)
            or any(type(value[key]) is not bool for key in ('fetchEnabled', 'searchEnabled', 'browserEnabled'))
            or value['engine'] not in ('google', 'bing', 'duckduckgo')
            or value['browser'] not in ('webview2', 'chrome', 'edge')):
        raise ValueError('Invalid web settings')
    return dict(value)


def has_web_settings(state_dir):
    path = Path(state_dir).expanduser() / FILENAME
    return path.exists() or path.is_symlink()


def load_web_settings(state_dir):
    path = Path(state_dir).expanduser() / FILENAME
    if not has_web_settings(state_dir):
        from local_cli.fetch_config import load_fetch_enabled
        from local_cli.browser_config import load_browser
        from local_cli.browser_search_config import load_settings
        return {**DEFAULTS, 'fetchEnabled': load_fetch_enabled(state_dir),
                'engine': load_settings(state_dir).engine, 'browser': load_browser(state_dir)}
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2048:
            raise ValueError('Invalid web preferences file')
        data = json.loads(path.read_bytes()[:2049])
        if type(data) is not dict or data.pop('schema', None) != SCHEMA:
            raise ValueError('Invalid web preferences schema')
        return validate_web_settings(data)
    except (OSError, ValueError, TypeError):
        return {**DEFAULTS, 'fetchEnabled': False, 'searchEnabled': False, 'browserEnabled': False}


def save_web_settings(state_dir, value):
    value = validate_web_settings(value)
    root = Path(state_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    path, temporary = root / FILENAME, None
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise OSError('Invalid web preferences file')
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=root,
                prefix='.web-preferences-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({'schema': SCHEMA, **value}, stream)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)


def update_web_settings(state_dir, **patch):
    save_web_settings(state_dir, {**load_web_settings(state_dir), **patch})
