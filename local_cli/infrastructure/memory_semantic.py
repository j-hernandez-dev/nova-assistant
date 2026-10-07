"""M5 optional exact NumPy projection. SQLite records remain authoritative.

Rebuild is explicit/idle work, not a hidden O(N) step in interactive search.
It reads paged vectors+metadata (never canonical text/sources). Search filters
cached metadata in native arrays BEFORE cosine scoring. A changed store/space
invalidates the cache and degrades until rebuilt; it never serves stale data.
"""
from datetime import datetime
import math
import struct
import sqlite3
from threading import RLock

from local_cli.core.memory import (EmbeddingSpace, MemoryError, MemoryErrorCode,
    MemoryQuery, RankedMemoryId)
from local_cli.infrastructure.memory_codec import timestamp

FORMAT = 'nova-f32le-revision-v1'
HEADER = struct.Struct('<8sQI')
MAGIC = b'NVEC0001'


def vector_checked(vector, dimension):
    if (not isinstance(vector, tuple) or len(vector) != dimension or dimension > 8192 or
            any(type(v) not in (float, int) or not math.isfinite(v) for v in vector)):
        raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
    norm = math.sqrt(sum(float(v)*float(v) for v in vector))
    if not math.isfinite(norm) or norm <= 0:
        raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
    return tuple(float(v)/norm for v in vector)


class NumpySemanticIndex:
    def __init__(self, store, space: EmbeddingSpace, *, minimum_similarity=.45,
                 matrix_limit_bytes=512*1024*1024):
        try:
            import numpy as np  # Optional capability; no install/fallback Python scan.
        except (ImportError,OSError):
            raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE) from None
        if (not isinstance(space, EmbeddingSpace) or space.storage_format != FORMAT or
                space.normalization != 'l2' or not 0 <= minimum_similarity <= 1 or
                type(matrix_limit_bytes) is not int or matrix_limit_bytes < 1):
            raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
        self.np, self.store, self.space = np, store, space
        self.minimum_similarity, self.matrix_limit_bytes = minimum_similarity, matrix_limit_bytes
        self._lock, self._signature, self._matrix, self._fields = RLock(), None, None, {}
        with store._transaction(write=True):
            c = store._connection
            row = c.execute('SELECT * FROM embedding_spaces WHERE embedding_space_id=?',
                            (space.embedding_space_id,)).fetchone()
            values = (space.embedding_space_id, space.provider_kind, space.model_id,
                space.model_revision, space.dimension, space.normalization, space.storage_format,
                timestamp(space.created_at))
            if row and tuple(row)[:-1] != values[:-1]:
                raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
            if not row:
                c.execute('INSERT INTO embedding_spaces VALUES (?,?,?,?,?,?,?,?)', values)

    def capabilities(self):
        return self.space

    def ready(self):
        return self._signature is not None

    def _check_space(self, space_id):
        if space_id != self.space.embedding_space_id:
            raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)

    def _stamp(self):
        c = self.store._connection
        row = c.execute("SELECT value FROM memory_meta WHERE key='semantic_epoch'").fetchone()
        return (row[0] if row else '0', c.execute('PRAGMA data_version').fetchone()[0])

    def upsert(self, memory_id, vector, embedding_space_id, *, expected_revision=None):
        self.upsert_batch(((memory_id,vector,expected_revision),),embedding_space_id)

    def upsert_batch(self, batch, embedding_space_id):
        self._check_space(embedding_space_id)
        if not isinstance(batch,tuple) or not 1<=len(batch)<=32:
            raise MemoryError(MemoryErrorCode.CAPACITY_REACHED)
        checked_batch=[]
        for memory_id,vector,expected_revision in batch:
            if expected_revision is not None and (type(expected_revision) is not int or expected_revision<1):
                raise MemoryError(MemoryErrorCode.INVALID_RECORD)
            checked_batch.append((memory_id,vector_checked(vector,self.space.dimension),expected_revision))
        with self._lock, self.store._transaction(write=True):
            c = self.store._connection
            for memory_id,checked,expected_revision in checked_batch:
                row = c.execute('SELECT revision,status,sensitivity_class FROM memories WHERE memory_id=?',
                                (memory_id,)).fetchone()
                if row is None:
                    raise MemoryError(MemoryErrorCode.NOT_FOUND)
                if expected_revision is not None and row['revision'] != expected_revision:
                    raise MemoryError(MemoryErrorCode.CONFLICT)
                if row['status'] != 'ACTIVE' or row['sensitivity_class'] != 'NORMAL':
                    raise MemoryError(MemoryErrorCode.SENSITIVE_DENIED)
                blob = HEADER.pack(MAGIC, row['revision'], self.space.dimension) + struct.pack(
                    '<'+'f'*self.space.dimension, *checked)
                c.execute('INSERT INTO memory_embeddings VALUES (?,?,?) ON CONFLICT(memory_id,embedding_space_id) '
                    'DO UPDATE SET vector=excluded.vector', (memory_id, embedding_space_id, blob))
            self.store._bump_semantic_epoch()
            self._signature = None

    def remove(self, memory_id):
        with self._lock, self.store._transaction(write=True):
            self.store._connection.execute('DELETE FROM memory_embeddings WHERE memory_id=?', (memory_id,))
            self.store._bump_semantic_epoch()
            self._signature = None

    def has_revision(self, memory_id, revision):
        with self.store._transaction():
            row=self.store._connection.execute('SELECT vector FROM memory_embeddings WHERE memory_id=? '
                'AND embedding_space_id=?',(memory_id,self.space.embedding_space_id)).fetchone()
            if not row: return False
            blob=row[0]
            if (len(blob)!=HEADER.size+self.space.dimension*4 or
                    HEADER.unpack_from(blob)!=(MAGIC,revision,self.space.dimension)):
                return False
            vector=self.np.frombuffer(blob,dtype='<f4',offset=HEADER.size)
            return bool(self.np.isfinite(vector).all() and abs(float(self.np.linalg.norm(vector))-1)<.001)

    def rebuild(self, embedding_space_id):
        self._check_space(embedding_space_id)
        np = self.np
        with self._lock:
            self._signature = None  # Failed/corrupt rebuild cannot keep an old cache live.
            with self.store._transaction():
                before=self._stamp()
            # A separate read-only WAL snapshot avoids holding the interactive
            # store RLock while rebuilding thousands of vectors in the background.
            reader=sqlite3.connect(self.store.path.as_uri()+'?mode=ro',uri=True,timeout=0,isolation_level=None)
            reader.row_factory=sqlite3.Row
            try:
                reader.execute('BEGIN')
                row=reader.execute("SELECT value FROM memory_meta WHERE key='semantic_epoch'").fetchone()
                epoch=row[0] if row else '0'
                matrix,fields=self._read_projection(reader,np,embedding_space_id)
            except (sqlite3.Error,ValueError,struct.error):
                raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH) from None
            finally:
                reader.close()
            with self.store._transaction():
                if before!=self._stamp() or epoch!=before[0]:
                    raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
                self._matrix,self._fields,self._signature=matrix,fields,before

    def _read_projection(self, reader, np, embedding_space_id):
            cursor = reader.execute('''SELECT m.memory_id,m.revision,m.subject_id,
                m.scope_kind,m.scope_id,m.identity_version,m.kind,m.status,m.sensitivity_class,
                m.valid_from,m.valid_to,e.vector FROM memory_embeddings e JOIN memories m
                ON m.memory_id=e.memory_id WHERE e.embedding_space_id=? AND NOT EXISTS
                (SELECT 1 FROM memory_tombstones t WHERE t.memory_id=m.memory_id) ORDER BY m.memory_id''',
                (embedding_space_id,))
            vectors, columns = [], {k: [] for k in ('memory_id','subject_id','scope_kind','scope_id',
                'identity_version','kind','status','sensitivity_class','valid_from','valid_to')}
            count = 0
            while batch := cursor.fetchmany(256):
                for row in batch:
                    blob = row['vector']
                    if len(blob) != HEADER.size + self.space.dimension*4:
                        raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
                    magic, revision, dimension = HEADER.unpack_from(blob)
                    if magic != MAGIC or revision != row['revision'] or dimension != self.space.dimension:
                        raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
                    vector = np.frombuffer(blob, dtype='<f4', offset=HEADER.size)
                    if not np.isfinite(vector).all() or abs(float(np.linalg.norm(vector))-1) > .001:
                        raise MemoryError(MemoryErrorCode.EMBEDDING_SPACE_MISMATCH)
                    vectors.append(vector)
                    count += 1
                    if count*self.space.dimension*4 > self.matrix_limit_bytes:
                        raise MemoryError(MemoryErrorCode.CAPACITY_REACHED)
                    for key in columns:
                        value = row[key]
                        if key in ('valid_from','valid_to'):
                            value = datetime.fromisoformat(value).timestamp() if value else (
                                -math.inf if key == 'valid_from' else math.inf)
                        elif key == 'identity_version':
                            value = value or 0
                        else:
                            value = value or ''
                        columns[key].append(value)
            matrix = np.stack(vectors) if vectors else np.empty((0,self.space.dimension),dtype=np.float32)
            fields = {k: np.asarray(v, dtype=float if k.startswith('valid_') else
                int if k == 'identity_version' else str) for k,v in columns.items()}
            return matrix,fields

    def search(self, query_vector, query: MemoryQuery, embedding_space_id):
        self._check_space(embedding_space_id)
        vector = self.np.asarray(vector_checked(query_vector, self.space.dimension), dtype=self.np.float32)
        if not isinstance(query, MemoryQuery):
            raise MemoryError(MemoryErrorCode.INVALID_RECORD)
        np = self.np
        with self._lock, self.store._transaction():
            if self._signature is None or self._signature != self._stamp():
                raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
            f=self._fields
            positions=self._eligible_positions(query)
            # Native vectorized O(N*d), not Python cosine/deserialization per query.
            scores = np.einsum('ij,j->i', self._matrix[positions], vector, optimize=False)
            keep = scores >= self.minimum_similarity
            positions, scores = positions[keep], scores[keep]
            order = np.lexsort((f['memory_id'][positions], -scores))[:min(query.limit,24)]
            return tuple(RankedMemoryId(str(f['memory_id'][positions[i]]), rank+1) for rank,i in enumerate(order))

    def has_candidates(self, query):
        with self._lock, self.store._transaction():
            if self._signature is None or self._signature!=self._stamp():
                raise MemoryError(MemoryErrorCode.EMBEDDING_UNAVAILABLE)
            return bool(self._eligible_positions(query).size)

    def _eligible_positions(self, query):
            if not isinstance(query,MemoryQuery): raise MemoryError(MemoryErrorCode.INVALID_RECORD)
            np=self.np;f, scope = self._fields, query.scope
            allowed_scope = (f['scope_kind'] == 'GLOBAL_PROFILE') & scope.include_global
            if scope.workspace_id:
                allowed_scope |= ((f['scope_kind']=='WORKSPACE') & (f['scope_id']==scope.workspace_id.value) &
                    (f['identity_version']==scope.workspace_id.identity_version))
            at = query.at.timestamp()
            mask = ((f['subject_id']==scope.subject_id.value) & allowed_scope &
                np.isin(f['status'], ('ACTIVE','CONFLICTED') if query.allow_conflicted else ('ACTIVE',)) &
                ((f['sensitivity_class']=='NORMAL') | query.allow_sensitive) &
                np.isin(f['kind'], tuple(k.value for k in query.kinds)) & (f['valid_from']<=at) & (f['valid_to']>at))
            if query.exclude_ids:
                mask &= ~np.isin(f['memory_id'],query.exclude_ids)
            return np.flatnonzero(mask)

    def cache_stats(self):
        return dict(backend='numpy-exact-v1', matrixBytes=0 if self._matrix is None else self._matrix.nbytes,
            vectors=0 if self._matrix is None else len(self._matrix), projectionFormat=FORMAT,
            ready=self._signature is not None)
