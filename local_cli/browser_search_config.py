"""Explicit browser search preference; never migrates legacy SearXNG settings."""
import json
import os
from pathlib import Path
import tempfile

from local_cli.core.browser_search import BrowserSearchSettings

FILENAME = 'browser-search.json'


def load_settings(state_dir):
    path = Path(state_dir).expanduser() / FILENAME
    try:
        if path.is_symlink() or path.stat().st_size > 1024: return BrowserSearchSettings()
        data = json.loads(path.read_bytes()[:1025])
        if set(data) != {'schema', 'engine'} or data['schema'] != 'NOVA_BROWSER_SEARCH_V1':
            return BrowserSearchSettings()
        return BrowserSearchSettings(data['engine'])
    except (OSError, ValueError, TypeError):
        return BrowserSearchSettings()


def save_settings(state_dir, engine):
    BrowserSearchSettings(engine)
    root = Path(state_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    path, temporary = root / FILENAME, None
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise OSError('Invalid browser search settings file')
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=root,
                prefix='.browser-search-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({'schema': 'NOVA_BROWSER_SEARCH_V1', 'engine': engine}, stream)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)
