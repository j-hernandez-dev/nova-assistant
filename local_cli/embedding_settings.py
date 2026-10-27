"""Local embedding preferences and validation, separate from chat and Memory switches."""
from copy import deepcopy
import json
import os
from pathlib import Path
from threading import RLock
from uuid import uuid4

PRESETS = (512, 1024, 2048, 4096, 8192, 16384, 32768)
EMPTY_SELECTION = {'modelId': '', 'requestedTokens': 0, 'enabledModels': []}
STORE_DEFAULTS = {'modelId': '', 'requestedTokens': 0, 'hiddenModels': []}


class EmbeddingSettingsError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def validate_settings(value):
    if (not isinstance(value, dict) or set(value) != set(EMPTY_SELECTION)
            or not isinstance(value['modelId'], str) or len(value['modelId']) > 512
            or type(value['requestedTokens']) is not int or value['requestedTokens'] not in (0, *PRESETS)
            or not isinstance(value['enabledModels'], list) or len(value['enabledModels']) > 1024
            or any(not isinstance(n, str) or not n.strip() or len(n) > 512 for n in value['enabledModels'])
            or len(set(value['enabledModels'])) != len(value['enabledModels'])):
        raise ValueError('INVALID_EMBEDDING_SETTINGS')
    return deepcopy(value)


def validate_stored_settings(value):
    if (not isinstance(value, dict) or set(value) != set(STORE_DEFAULTS)
            or not isinstance(value['hiddenModels'], list) or len(value['hiddenModels']) > 4096):
        raise ValueError('INVALID_EMBEDDING_PREFERENCES')
    validate_settings({k:v for k,v in value.items() if k != 'hiddenModels'} | {'enabledModels':[]})
    if (any(not isinstance(n,str) or not n.strip() or len(n)>512 for n in value['hiddenModels'])
            or len(set(value['hiddenModels'])) != len(value['hiddenModels'])):
        raise ValueError('INVALID_EMBEDDING_PREFERENCES')
    return deepcopy(value)


class EmbeddingPreferences:
    def __init__(self, state_dir):
        self.path = Path(state_dir).expanduser() / 'embedding-preferences.json'

    def load(self):
        try:
            if self.path.is_symlink() or self.path.stat().st_size > 2_500_000:
                return deepcopy(STORE_DEFAULTS)
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            version = raw.pop('schemaVersion')
            if type(version) is not int:
                return deepcopy(STORE_DEFAULTS)
            if version == 1:
                # The previous version started disabled. Adopt the corrected
                # default while keeping the selected model and context.
                old = validate_settings(raw)
                return {'modelId':old['modelId'], 'requestedTokens':old['requestedTokens'], 'hiddenModels':[]}
            return validate_stored_settings(raw) if version == 2 else deepcopy(STORE_DEFAULTS)
        except (OSError, ValueError, TypeError, AttributeError, KeyError, UnicodeError):
            return deepcopy(STORE_DEFAULTS)

    def save(self, value):
        value = validate_stored_settings(value)
        if self.path.is_symlink():
            raise OSError('Invalid preferences target')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name('.embedding-' + uuid4().hex + '.tmp')
        try:
            with temporary.open('x', encoding='utf-8') as stream:
                json.dump({'schemaVersion': 2, **value}, stream, ensure_ascii=False)
                stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)


class EmbeddingSettings:
    def __init__(self, preferences, *, inventory, usage=None):
        self.preferences, self.inventory, self.usage = preferences, inventory, usage
        self._value = preferences.load()
        self._models = []
        self._connected = False
        self._error = None
        self._lock = RLock()

    def observe(self, models, connected=True):
        with self._lock:
            self._connected = bool(connected)
            self._models = deepcopy(models) if connected else []

    def _selected(self):
        models = [m for m in self._models if m.get('kind') == 'embedding' and m['name'] not in self._value['hiddenModels']]
        return next((m for m in models if m['name'] == self._value['modelId']), models[0] if models else None)

    def snapshot(self):
        with self._lock:
            selected = self._selected()
            limit = selected.get('contextLength') if selected else None
            requested = self._value['requestedTokens']
            effective = (requested or min(8192, limit)) if limit else requested or None
            error = self._error
            if requested and limit and requested > limit:
                effective, error = None, 'EMBEDDING_CONTEXT_LIMIT_EXCEEDED'
            return {'modelId':self._value['modelId'], 'requestedTokens':requested,
                    'enabledModels':[m['name'] for m in self._models if m.get('kind') == 'embedding' and m['name'] not in self._value['hiddenModels']],
                    'selectedModel': selected['name'] if selected else '',
                    'connected': self._connected, 'selectedTokens': effective,
                    'contextLimit': limit, 'errorCode': error}

    def update(self, value):
        value = validate_settings(value)
        with self._lock:
            try:
                self.observe(self.inventory())
            except Exception:
                raise EmbeddingSettingsError('EMBEDDING_CONNECTION_FAILED') from None
            available = {m['name']:m for m in self._models if m.get('kind') == 'embedding'}
            if any(n not in available for n in value['enabledModels']):
                raise EmbeddingSettingsError('EMBEDDING_MODEL_UNAVAILABLE')
            selected = value['modelId']
            if selected and selected not in value['enabledModels']:
                raise EmbeddingSettingsError('EMBEDDING_MODEL_UNAVAILABLE')
            candidate = selected or next((n for n in available if n in value['enabledModels']), '')
            limit = available.get(candidate, {}).get('contextLength')
            changed_context = value['requestedTokens'] != self._value['requestedTokens']
            visibility_only = set(value['enabledModels']) != set(self.snapshot()['enabledModels']) and not changed_context
            if value['requestedTokens'] and limit and value['requestedTokens'] > limit and not visibility_only:
                raise EmbeddingSettingsError('EMBEDDING_CONTEXT_LIMIT_EXCEEDED')
            # Store exclusions so future installs start active. Retain explicit
            # exclusions for temporarily uninstalled models.
            hidden = (set(self._value['hiddenModels']) - set(available)) | (set(available) - set(value['enabledModels']))
            stored = {'modelId':selected, 'requestedTokens':value['requestedTokens'], 'hiddenModels':sorted(hidden)}
            try:
                self.preferences.save(stored)
            except (OSError, ValueError):
                raise EmbeddingSettingsError('EMBEDDING_PREFERENCES_SAVE_FAILED') from None
            self._value, self._error = stored, None
            return self.snapshot()

    def reset(self):
        with self._lock:
            try:
                self.preferences.save(STORE_DEFAULTS)
            except (OSError, ValueError):
                raise EmbeddingSettingsError('EMBEDDING_PREFERENCES_SAVE_FAILED') from None
            self._value, self._error = deepcopy(STORE_DEFAULTS), None
            return self.snapshot()

    def report_error(self, code):
        with self._lock:
            self._error = code

    def runtime_options(self, model):
        state = self.snapshot()
        if state['selectedModel'] != model:
            raise EmbeddingSettingsError('EMBEDDING_MODEL_UNAVAILABLE')
        if state['requestedTokens'] and state['contextLimit'] and state['requestedTokens'] > state['contextLimit']:
            raise EmbeddingSettingsError(state['errorCode'])
        return {'num_ctx': state['selectedTokens']} if state['selectedTokens'] else {}
