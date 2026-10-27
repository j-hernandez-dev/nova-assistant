"""Persistent host preferences; importing sources never imports settings."""
from copy import deepcopy
import json
import os
from pathlib import Path
from threading import RLock
from uuid import uuid4

DEFAULTS = dict(lexicalRecall=True, semanticRecall=False, autoIndex=True, autoRebuild=True)


def validate_settings(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULTS) or any(type(v) is not bool for v in value.values()):
        raise ValueError('INVALID_KNOWLEDGE_SETTINGS')
    return deepcopy(value)


class KnowledgePreferences:
    def __init__(self, state_dir):
        self.path = Path(state_dir).expanduser() / 'knowledge-preferences.json'
        self._lock, self._value = RLock(), deepcopy(DEFAULTS)
        try:
            if self.path.is_symlink() or self.path.stat().st_size > 10000: raise ValueError()
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            version = raw.pop('schemaVersion')
            if type(version) is not int or version != 1: raise ValueError()
            self._value = validate_settings(raw)
        except (OSError, ValueError, KeyError, TypeError, UnicodeError): pass

    def snapshot(self):
        with self._lock: return deepcopy(self._value)

    def update(self, value):
        value = validate_settings(value)
        with self._lock:
            if self.path.is_symlink(): raise OSError('Invalid preferences target')
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name('.knowledge-preferences-' + uuid4().hex + '.tmp')
            try:
                with temporary.open('x', encoding='utf-8') as stream:
                    json.dump(dict(schemaVersion=1, **value), stream)
                    stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally: temporary.unlink(missing_ok=True)
            self._value = value
        return self.snapshot()

    def reset(self): return self.update(DEFAULTS)
