"""Server/Desktop context preference; never changes CLI configuration."""
import json
import os
from pathlib import Path
from uuid import uuid4
from local_cli.core.context import PRESETS


def valid_context_tokens(value):
    return type(value) is int and value in (0, *PRESETS)


class DesktopContextPreferences:
    def __init__(self, state_dir):
        self.path = Path(state_dir).expanduser() / 'desktop-context.json'

    def load(self, default=0):
        try:
            if self.path.stat().st_size > 4096:
                return default
            value = json.loads(self.path.read_text(encoding='utf-8'))
            if (isinstance(value, dict) and set(value) == {'schemaVersion', 'requestedTokens'}
                    and type(value['schemaVersion']) is int and value['schemaVersion'] == 1
                    and valid_context_tokens(value['requestedTokens'])):
                return value['requestedTokens']
        except (OSError, ValueError, UnicodeError):
            pass
        return default

    def save(self, requested):
        if not valid_context_tokens(requested):
            raise ValueError('Invalid Desktop context preset')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name('.desktop-context-' + uuid4().hex + '.tmp')
        try:
            with temporary.open('x', encoding='utf-8') as stream:
                json.dump({'schemaVersion': 1, 'requestedTokens': requested}, stream)
                stream.write('\n')
            os.replace(temporary, self.path)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
