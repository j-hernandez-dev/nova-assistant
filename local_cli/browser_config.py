"""Only an explicit human choice persists; WebView2 remains the default."""
import json
import os
from pathlib import Path
import tempfile

BROWSERS = ('webview2', 'chrome', 'edge')
FILENAME = 'browser-preference.json'


def load_browser(state_dir):
    path = Path(state_dir).expanduser() / FILENAME
    try:
        if path.is_symlink() or path.stat().st_size > 1024: return 'webview2'
        data = json.loads(path.read_bytes()[:1025])
        if (set(data) == {'schema', 'browser'} and data['schema'] == 'NOVA_BROWSER_PREFERENCE_V1'
                and data['browser'] in BROWSERS): return data['browser']
    except (OSError, ValueError, TypeError): pass
    return 'webview2'


def save_browser(state_dir, browser):
    if browser not in BROWSERS: raise ValueError('Choose webview2, chrome, or edge.')
    root = Path(state_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    path, temporary = root / FILENAME, None
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise OSError('Invalid browser preference file')
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=root,
                prefix='.browser-preference-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({'schema': 'NOVA_BROWSER_PREFERENCE_V1', 'browser': browser}, stream)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)
