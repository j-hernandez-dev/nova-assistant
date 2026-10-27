"""Read-only capability classification. Unknown models never become chat/embedding models by name."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import RLock
from time import monotonic


class ModelInventory:
    def __init__(self):
        self._cache = {}
        self._lock = RLock()

    def read(self, provider, models=None, known_info=None):
        models = provider.list_models() if models is None else models
        if not isinstance(models, list) or len(models) > 1024:
            raise ValueError('INVALID_MODEL_INVENTORY')

        deadline = monotonic() + 5

        def classify(row):
            if (not isinstance(row, dict) or not isinstance(row.get('name'), str)
                    or not row['name'].strip() or len(row['name']) > 512
                    or type(row.get('size', 0)) is not int or row.get('size', 0) < 0):
                raise ValueError('INVALID_MODEL_INVENTORY')
            result = {'name': row['name'], 'size': row.get('size', 0), 'kind': 'unknown', 'contextLength': None}
            digest = row.get('digest')
            key = (id(provider), row['name'], digest) if isinstance(digest, str) and digest else None
            with self._lock:
                cached = self._cache.get(key) if key else None
            if cached is not None:
                return {**result, **deepcopy(cached)}
            try:
                info = (known_info or {}).get(row['name'])
                if info is None:
                    if monotonic() >= deadline:
                        return result
                    inspect = getattr(provider, 'get_inventory_info', provider.get_model_info)
                    info = inspect(row['name'])
                caps = info.get('capabilities')
                if not isinstance(caps, list) or any(not isinstance(c, str) for c in caps):
                    return result
                result['kind'] = 'embedding' if 'embedding' in caps else 'llm' if 'completion' in caps or 'tools' in caps else 'unknown'
                metadata = info.get('model_info')
                limits = [v for k, v in metadata.items() if k.endswith('.context_length') and type(v) is int and v > 0] if isinstance(metadata, dict) else []
                result['contextLength'] = min(limits) if limits else None
                if key and result['kind'] != 'unknown':
                    with self._lock:
                        if len(self._cache) >= 2048:
                            self._cache.clear()
                        self._cache[key] = {'kind': result['kind'], 'contextLength': result['contextLength']}
            except Exception:
                pass  # Retry failed metadata on the next inventory refresh.
            return result

        with ThreadPoolExecutor(max_workers=4) as pool:
            return list(pool.map(classify, models))
