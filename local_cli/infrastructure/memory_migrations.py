"""Owned MEMORY formats only. Never migrate Core JSONL, RAG or Audit databases.

v0 is an explicitly identified pre-v1 fixture format (record_json aggregates),
not a claim that a legacy MEMORY database was previously shipped. Upgrades
require opt-in, run in the caller's transaction and never skip invalid rows.
"""

APPLICATION_ID = 0x4e564d31  # NVM1; local file-format identifier.
FORMAT_V0 = 'nova-memory-v0'
FORMAT_V1 = 'nova-memory-v1'

SCHEMA = (
    'CREATE TABLE memory_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)',
    'CREATE TABLE subjects (subject_id TEXT PRIMARY KEY, created_at TEXT NOT NULL)',
    '''CREATE TABLE workspaces (workspace_id TEXT NOT NULL, identity_version INTEGER NOT NULL CHECK(identity_version>0),
        canonical_path TEXT, PRIMARY KEY(workspace_id,identity_version))''',
    '''CREATE TABLE memories (
        memory_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL CHECK(schema_version=1),
        revision INTEGER NOT NULL CHECK(revision>0), subject_id TEXT NOT NULL REFERENCES subjects(subject_id),
        scope_kind TEXT NOT NULL CHECK(scope_kind IN ('GLOBAL_PROFILE','WORKSPACE')),
        scope_id TEXT, identity_version INTEGER,
        kind TEXT NOT NULL CHECK(kind IN ('PREFERENCE','SEMANTIC_FACT','WORKSPACE_FACT','EPISODE','PROCEDURE')),
        canonical_text TEXT NOT NULL, canonical_key TEXT,
        status TEXT NOT NULL CHECK(status IN ('ACTIVE','SUPERSEDED','CONFLICTED','RETRACTED','EXPIRED','DELETED')),
        source_class TEXT NOT NULL, sensitivity_class TEXT NOT NULL CHECK(sensitivity_class IN ('NORMAL','SENSITIVE')),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, observed_at TEXT, valid_from TEXT, valid_to TEXT,
        supersedes_memory_id TEXT, conflict_group_id TEXT, importance_class TEXT NOT NULL, content_hash TEXT NOT NULL,
        FOREIGN KEY(scope_id,identity_version) REFERENCES workspaces(workspace_id,identity_version),
        CHECK((scope_kind='GLOBAL_PROFILE' AND scope_id IS NULL AND identity_version IS NULL) OR
              (scope_kind='WORKSPACE' AND scope_id IS NOT NULL AND identity_version IS NOT NULL)),
        CHECK(kind!='WORKSPACE_FACT' OR scope_kind='WORKSPACE'),
        CHECK(status!='CONFLICTED' OR conflict_group_id IS NOT NULL))''',
    '''CREATE TABLE memory_sources (memory_id TEXT NOT NULL REFERENCES memories(memory_id) ON DELETE CASCADE,
        source_id TEXT NOT NULL, source_class TEXT NOT NULL, session_id TEXT, turn_id TEXT, message_id TEXT,
        operation_id TEXT, tool_call_id TEXT, source_timestamp TEXT NOT NULL, evidence_excerpt TEXT, evidence_hash TEXT,
        source_order INTEGER NOT NULL CHECK(source_order>=0),
        PRIMARY KEY(memory_id,source_id), UNIQUE(memory_id,source_order))''',
    '''CREATE TABLE memory_relations (memory_id TEXT PRIMARY KEY REFERENCES memories(memory_id) ON DELETE CASCADE,
        supersedes_memory_id TEXT UNIQUE NOT NULL, CHECK(memory_id!=supersedes_memory_id))''',
    '''CREATE TABLE memory_tombstones (memory_id TEXT PRIMARY KEY, subject_id TEXT NOT NULL REFERENCES subjects(subject_id),
        scope_kind TEXT NOT NULL, scope_id TEXT, identity_version INTEGER, content_hash TEXT NOT NULL,
        revision INTEGER NOT NULL, deleted_at TEXT NOT NULL)''',
    '''CREATE TABLE embedding_spaces (embedding_space_id TEXT PRIMARY KEY, provider_kind TEXT NOT NULL,
        model_id TEXT NOT NULL, model_revision TEXT, dimension INTEGER NOT NULL CHECK(dimension>0),
        normalization TEXT NOT NULL, storage_format TEXT NOT NULL, created_at TEXT NOT NULL)''',
    '''CREATE TABLE memory_embeddings (memory_id TEXT NOT NULL REFERENCES memories(memory_id) ON DELETE CASCADE,
        embedding_space_id TEXT NOT NULL REFERENCES embedding_spaces(embedding_space_id), vector BLOB NOT NULL,
        PRIMARY KEY(memory_id,embedding_space_id))''',
    'CREATE TABLE maintenance_jobs (job_id TEXT PRIMARY KEY, state TEXT NOT NULL, payload TEXT NOT NULL)',
    'CREATE INDEX memory_scope_idx ON memories(subject_id,scope_kind,scope_id,identity_version,status,kind,memory_id)',
    'CREATE INDEX memory_key_idx ON memories(subject_id,canonical_key,scope_kind,scope_id,identity_version)',
    'CREATE INDEX memory_text_idx ON memories(subject_id,canonical_text)',
    'CREATE INDEX tombstone_scope_idx ON memory_tombstones(subject_id,scope_kind,scope_id,identity_version,memory_id)',
)

FTS_SCHEMA = "CREATE VIRTUAL TABLE memory_fts USING fts5(memory_id UNINDEXED, canonical_text, canonical_key, tokenize='unicode61')"


def create_v1(connection):
    # executescript() would implicitly commit a pending transaction. Do not use.
    for statement in SCHEMA:
        connection.execute(statement)
    connection.execute(FTS_SCHEMA)
    connection.execute('INSERT INTO memory_meta VALUES (?,?)', ('format', FORMAT_V1))
    connection.execute(f'PRAGMA application_id={APPLICATION_ID}')
    connection.execute('PRAGMA user_version=1')
