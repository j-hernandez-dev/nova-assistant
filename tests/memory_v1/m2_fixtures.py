"""Private synthetic filesystem/SQLite fixtures, never Nova user data."""

import json
from pathlib import Path
import sqlite3

from local_cli.application.secrets import SecretRedactor
from local_cli.core.memory import MemoryContentLimits
from local_cli.infrastructure.memory_codec import encode
from local_cli.infrastructure.memory_migrations import APPLICATION_ID, FORMAT_V0
from local_cli.infrastructure.memory_sqlite import SQLiteMemoryLexicalIndex, SQLiteMemoryStore
from tests.memory_v1.m1_fixtures import ACCESS_A, AT


LIMITS = MemoryContentLimits(4096, 512)  # Fixture bounds, not final product quotas.


def open_store(state, **kwargs):
    return SQLiteMemoryStore(Path(state).resolve(),content_limits=kwargs.pop('content_limits',LIMITS),
        redactor=kwargs.pop('redactor',SecretRedactor(source={})),**kwargs)


def index(store):
    return SQLiteMemoryLexicalIndex(store)


def make_v0(state, records, *, active_subject=None):
    path = Path(state)/'memory/v1/memory.db'
    path.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(f'PRAGMA application_id={APPLICATION_ID}')
        connection.execute('CREATE TABLE memory_meta (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        connection.execute('CREATE TABLE memories (memory_id TEXT PRIMARY KEY,record_json TEXT NOT NULL)')
        connection.execute('INSERT INTO memory_meta VALUES (?,?)',('format',FORMAT_V0))
        if active_subject:
            connection.execute('INSERT INTO memory_meta VALUES (?,?)',('active_subject',active_subject.value))
        connection.executemany('INSERT INTO memories VALUES (?,?)',
            [(r.memory_id,json.dumps(encode(r),ensure_ascii=False)) for r in records])
    return path
