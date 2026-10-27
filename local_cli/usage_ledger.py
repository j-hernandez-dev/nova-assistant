"""Local inference metrics. Stores dates/counts only, never prompts or responses."""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from threading import RLock
from uuid import uuid4


def _instant(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError('INVALID_USAGE_RANGE')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('INVALID_USAGE_RANGE')
    return result.timestamp()


def _count(value):
    return value if type(value) is int and 0 <= value <= 2**53 - 1 else None


class UsageLedger:
    def __init__(self, path=None, *, clock=None, kind="llm"):
        state = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local' / 'state')
        if kind not in ('llm', 'embedding'):
            raise ValueError('INVALID_USAGE_KIND')
        self.path = Path(path) if path is not None else state / 'nova' / ('embedding-usage.sqlite3' if kind == 'embedding' else 'model-usage.sqlite3')
        self.clock = clock or (lambda: datetime.now(timezone.utc).timestamp())
        self._lock = RLock()
        self.gap = False

    @contextmanager
    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=.5)
        try:
            with connection:
                connection.execute('PRAGMA journal_mode=WAL')
                connection.execute('''CREATE TABLE IF NOT EXISTS requests (
                    id TEXT PRIMARY KEY, started REAL NOT NULL, model TEXT NOT NULL,
                    input_tokens INTEGER, output_tokens INTEGER, outcome TEXT NOT NULL)''')
                connection.execute('CREATE INDEX IF NOT EXISTS requests_started ON requests(started)')
                yield connection
        finally:
            connection.close()

    def begin(self, model):
        identity = str(uuid4())
        try:
            with self._lock, self._connect() as connection:
                connection.execute('INSERT INTO requests VALUES (?,?,?,NULL,NULL,?)',
                    (identity, self.clock(), str(model)[:256], 'pending'))
            return identity
        except (OSError, sqlite3.Error):
            self.gap = True
            return None

    def finish(self, identity, data, outcome):
        if identity is None:
            return
        try:
            with self._lock, self._connect() as connection:
                connection.execute('UPDATE requests SET input_tokens=?,output_tokens=?,outcome=? WHERE id=?',
                    (_count(data.get('prompt_eval_count')), _count(data.get('eval_count')),
                     outcome if outcome in ('completed', 'interrupted', 'failed') else 'failed', identity))
        except (OSError, sqlite3.Error):
            self.gap = True

    def query(self, value):
        if not isinstance(value, dict) or set(value) != {'start', 'end', 'buckets'}:
            raise ValueError('INVALID_USAGE_RANGE')
        start, end = _instant(value['start']), _instant(value['end'])
        buckets = value['buckets']
        if not (0 < end - start <= 186 * 86400) or not isinstance(buckets, list) or not 1 <= len(buckets) <= 32:
            raise ValueError('INVALID_USAGE_RANGE')
        intervals = []
        boundary = start
        for item in buckets:
            if not isinstance(item, dict) or set(item) != {'start', 'end'}:
                raise ValueError('INVALID_USAGE_RANGE')
            left, right = _instant(item['start']), _instant(item['end'])
            if left != boundary or not left < right <= end:
                raise ValueError('INVALID_USAGE_RANGE')
            intervals.append((left, right)); boundary = right
        if boundary != end:
            raise ValueError('INVALID_USAGE_RANGE')
        result = []
        with self._lock, self._connect() as connection:
            for left, right in intervals:
                row = connection.execute('''SELECT COUNT(*),COALESCE(SUM(input_tokens),0),
                    COALESCE(SUM(output_tokens),0),COALESCE(SUM(CASE WHEN input_tokens IS NULL
                    OR output_tokens IS NULL THEN 1 ELSE 0 END),0) FROM requests WHERE started>=? AND started<?''', (left, right)).fetchone()
                result.append(dict(requests=row[0], inputTokens=row[1], outputTokens=row[2], unreported=row[3]))
        return {'schemaVersion': 1, 'buckets': result, 'gap': self.gap,
                'requests': sum(item['requests'] for item in result),
                'inputTokens': sum(item['inputTokens'] for item in result),
                'outputTokens': sum(item['outputTokens'] for item in result),
                'unreported': sum(item['unreported'] for item in result)}
