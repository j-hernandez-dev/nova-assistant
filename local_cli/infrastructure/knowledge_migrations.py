"""Explicit empty-format 0 -> Knowledge V1 migration; never a legacy importer."""
APPLICATION_ID = 0x4E4B5631
FORMAT = 'nova-knowledge-v1'
VERSION = 1

SCHEMA = (
    'CREATE TABLE knowledge_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)',
    '''CREATE TABLE sources(source_id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,
       session_id TEXT,scope_kind TEXT NOT NULL CHECK(scope_kind IN ('SESSION','WORKSPACE')),
       source_json TEXT NOT NULL,current_revision_id TEXT,state TEXT NOT NULL,
       CHECK((scope_kind='SESSION' AND session_id IS NOT NULL) OR
             (scope_kind='WORKSPACE' AND session_id IS NULL)))''',
    '''CREATE TABLE source_revisions(revision_id TEXT PRIMARY KEY,source_id TEXT NOT NULL
       REFERENCES sources(source_id),revision_json TEXT NOT NULL,blob_key TEXT NOT NULL UNIQUE,
       byte_length INTEGER NOT NULL CHECK(byte_length>=0))''',
    '''CREATE TABLE revision_publication(revision_id TEXT PRIMARY KEY REFERENCES
       source_revisions(revision_id) ON DELETE CASCADE,state TEXT NOT NULL)''',
    '''CREATE TABLE documents(revision_id TEXT PRIMARY KEY REFERENCES source_revisions(revision_id)
       ON DELETE CASCADE,document_json TEXT NOT NULL)''',
    '''CREATE TABLE document_blocks(block_id TEXT PRIMARY KEY,revision_id TEXT NOT NULL
       REFERENCES documents(revision_id) ON DELETE CASCADE,ordinal INTEGER NOT NULL,
       block_json TEXT NOT NULL,UNIQUE(revision_id,ordinal))''',
    '''CREATE TABLE chunks(chunk_id TEXT PRIMARY KEY,revision_id TEXT NOT NULL REFERENCES
       documents(revision_id) ON DELETE CASCADE,ordinal INTEGER NOT NULL,chunk_json TEXT NOT NULL,
       UNIQUE(revision_id,ordinal))''',
    # Publication needs an actual committed lexical projection, not a boolean
    # "indexed" receipt. No search/scoring or chunking algorithm is exposed in K1.
    'CREATE VIRTUAL TABLE chunk_fts USING fts5(chunk_id UNINDEXED,revision_id UNINDEXED,text)',
    '''CREATE TABLE semantic_spaces(space_id TEXT PRIMARY KEY,metadata_json TEXT NOT NULL)''',
    '''CREATE TABLE semantic_vectors(chunk_id TEXT NOT NULL REFERENCES chunks(chunk_id)
       ON DELETE CASCADE,space_id TEXT NOT NULL REFERENCES semantic_spaces(space_id),
       vector BLOB NOT NULL,PRIMARY KEY(chunk_id,space_id))''',
    '''CREATE TABLE source_tombstones(source_id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,
       session_id TEXT,deleted_at TEXT NOT NULL)''',
    '''CREATE TABLE import_operations(operation_id TEXT PRIMARY KEY,source_id TEXT NOT NULL
       REFERENCES sources(source_id),revision_id TEXT NOT NULL UNIQUE,previous_revision_id TEXT,
       workspace_id TEXT NOT NULL,session_id TEXT NOT NULL,status TEXT NOT NULL,
       phase TEXT NOT NULL,error_code TEXT,digest TEXT,byte_length INTEGER)''',
    'CREATE INDEX source_scope ON sources(workspace_id,scope_kind,session_id,state)',
    'CREATE INDEX revision_source ON source_revisions(source_id)',
    'CREATE INDEX operation_scope ON import_operations(workspace_id,session_id,status)',
    '''CREATE TRIGGER immutable_revision BEFORE UPDATE ON source_revisions
       BEGIN SELECT RAISE(ABORT,'immutable revision'); END''',
    '''CREATE TRIGGER immutable_document BEFORE UPDATE ON documents
       BEGIN SELECT RAISE(ABORT,'immutable document'); END''',
    '''CREATE TRIGGER immutable_block BEFORE UPDATE ON document_blocks
       BEGIN SELECT RAISE(ABORT,'immutable block'); END''',
    '''CREATE TRIGGER immutable_chunk BEFORE UPDATE ON chunks
       BEGIN SELECT RAISE(ABORT,'immutable chunk'); END''',
    '''CREATE TRIGGER chunk_delete AFTER DELETE ON chunks
       BEGIN DELETE FROM chunk_fts WHERE chunk_id=old.chunk_id; END''',
    '''CREATE TRIGGER no_resurrection BEFORE INSERT ON sources WHEN EXISTS
       (SELECT 1 FROM source_tombstones WHERE source_id=new.source_id)
       BEGIN SELECT RAISE(ABORT,'deleted source'); END''',
    '''CREATE TRIGGER no_deleted_revision BEFORE INSERT ON source_revisions WHEN EXISTS
       (SELECT 1 FROM source_tombstones WHERE source_id=new.source_id)
       BEGIN SELECT RAISE(ABORT,'deleted source'); END''',
)


def create_v1(connection):
    for statement in SCHEMA:
        connection.execute(statement)
    connection.execute('INSERT INTO knowledge_meta VALUES (?,?)', ('format', FORMAT))
    connection.execute(f'PRAGMA application_id={APPLICATION_ID}')
    connection.execute(f'PRAGMA user_version={VERSION}')


MIGRATIONS = {0: create_v1}
