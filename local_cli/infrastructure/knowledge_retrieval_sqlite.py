"""K4 bounded SQLite projections on the existing versioned Knowledge store.

Scope/current-publication filters precede both scoring and candidate limits.
No legacy RAG DB is opened here. Projection metadata is immutable by space ID;
document vectors are rebuildable derived data, not source authority.
"""
from dataclasses import replace
import hashlib
import heapq
import json
import math
import struct
from time import perf_counter
import unicodedata

from local_cli.core.knowledge import (KnowledgeError, KnowledgeErrorCode,
    SourceRevision, _require, _uuid)
from local_cli.core.knowledge_store import (DocumentBlock, DocumentChunk,
    KnowledgeAccess, KnowledgeStorageError, StorageFailure)
from local_cli.core.knowledge_retrieval import (DocumentCandidate, DocumentEmbeddingSpace,
    DocumentRetrievalFilter, LEXICAL_CAP, SEMANTIC_CAP, LEXICAL_FLOOR,
    SEMANTIC_FLOOR, lexical_text, terms, vector)
from local_cli.infrastructure.knowledge_lexical import documentary_terms, identifier_terms
from local_cli.infrastructure.knowledge_query import plan_query


class DocumentRetrievalStorage:
    """Infrastructure mixin; transaction/containment ownership stays in K1."""

    def _retrieval_where(self, access, filters):
        _require(isinstance(access, KnowledgeAccess) and isinstance(filters, DocumentRetrievalFilter))
        where = ["s.workspace_id=?", "(s.scope_kind='WORKSPACE' OR s.session_id=?)",
            "s.current_revision_id=r.revision_id", "s.state IN ('READY','PARTIAL')",
            "p.state=s.state", "NOT EXISTS (SELECT 1 FROM source_tombstones t WHERE t.source_id=s.source_id)"]
        args = [access.workspace_id, access.session_id]
        for column, values in [('s.source_id', filters.source_ids), ('r.revision_id', filters.revision_ids),
            ('s.state', tuple(v.value for v in filters.states)),
            ("json_extract(r.revision_json,'$.mediaType')", filters.media_types),
            ("json_extract(s.source_json,'$.kind')", tuple(v.value for v in filters.kinds))]:
            if values:
                where.append(column + ' IN (' + ','.join('?' for _ in values) + ')'); args.extend(values)
            elif column == 's.state': where.append('0')
        if filters.scope:
            where.append('s.scope_kind=?'); args.append(filters.scope.value)
        return ' AND '.join(where), args

    @staticmethod
    def _joins():
        return '''JOIN source_revisions r ON r.revision_id=ch.revision_id
            JOIN sources s ON s.source_id=r.source_id
            JOIN revision_publication p ON p.revision_id=r.revision_id'''

    def _candidate(self, row, access, score, exact=False):
        # Verify selected metadata/lineage, not paths or mutable origin strings.
        source = self._source(row['source_id'], access)
        revision = SourceRevision.from_dict(json.loads(row['revision_json']))
        chunk = DocumentChunk.from_dict(json.loads(row['chunk_json']))
        if (source.current_revision_id != row['revision_id'] or revision.source_id != source.source_id
                or revision.revision_id != row['revision_id'] or chunk.revision_id != row['revision_id']
                or chunk.chunk_id != row['chunk_id'] or chunk.ordinal != row['ordinal']):
            raise KnowledgeStorageError(StorageFailure.CORRUPT)
        if chunk.block_spans:
            texts, locators = [], []
            for span in chunk.block_spans:
                block_row = self._connection.execute('SELECT block_json FROM document_blocks WHERE block_id=? AND revision_id=?',
                    (span.block_id, chunk.revision_id)).fetchone()
                if block_row is None: raise KnowledgeStorageError(StorageFailure.CORRUPT)
                block = DocumentBlock.from_dict(json.loads(block_row[0]))
                if block.block_id != span.block_id or span.end > len(block.text):
                    raise KnowledgeStorageError(StorageFailure.CORRUPT)
                texts.append(block.text[span.start:span.end]); locators.append(block.locator)
            expected = hashlib.sha256(unicodedata.normalize('NFKC', chunk.text).encode()).hexdigest()
            if (chunk.text != '\n'.join(texts) or chunk.locator_start != locators[0]
                    or chunk.locator_end != locators[-1] or chunk.normalized_text_hash != expected):
                raise KnowledgeStorageError(StorageFailure.CORRUPT)
        return DocumentCandidate(source.source_id, revision.revision_id, chunk, score, exact)

    def lexical_candidates(self, query, access, filters=DocumentRetrievalFilter()):
        diversity = plan_query(query).source_diversity
        query_terms = documentary_terms(query)
        if not query_terms: return ()
        where, args = self._retrieval_where(access, filters)
        # Literal FTS tokens; no user-supplied MATCH operators/SQL interpolation.
        match = ' OR '.join('"'+t+'"' for t in query_terms)
        with self._transaction(write=False):
            # DF is scoped/current, never influenced by inaccessible revisions.
            frequencies = {}
            df_sql = f'''SELECT count(DISTINCT ch.revision_id) FROM chunk_fts
                JOIN chunks ch ON ch.chunk_id=chunk_fts.chunk_id {self._joins()}
                WHERE {where} AND chunk_fts.revision_id=ch.revision_id AND chunk_fts MATCH ?'''
            for term in query_terms:
                frequencies[term] = self._connection.execute(df_sql,[*args,'"'+term+'"']).fetchone()[0]
            identifiers = identifier_terms(query_terms)
            # Near-miss identifiers may not be substituted by matching common
            # topic words. All requested keys must exist in the permitted view.
            if any(not frequencies[t] for t in identifiers): return ()
            sql = f'''SELECT ch.*,r.source_id,r.revision_json,
                chunk_fts.text AS projection,bm25(chunk_fts) AS bm25
                FROM chunk_fts JOIN chunks ch ON ch.chunk_id=chunk_fts.chunk_id
                {self._joins()} WHERE {where} AND chunk_fts.revision_id=ch.revision_id
                AND chunk_fts MATCH ? ORDER BY bm25 ASC,ch.revision_id,ch.ordinal,ch.chunk_id LIMIT ?'''
            phrase = ' '.join(query_terms)
            # Exact phase precedes the shared candidate cap. Shorter partial
            # matches must not crowd out a complete identifier/text phrase.
            if diversity:
                # Same scoped FTS/BM25 and strict coverage floor, before the same
                # 32-candidate cap. Round-robin by provenance keeps one source's
                # many chunks from crowding out another relevant source. The
                # materialized FTS score is needed for SQLite window ordering.
                coverage = '+'.join("(instr(' '||projection||' ',?)>0)" for t in query_terms)
                key_gate = (' AND ('+' OR '.join("instr(' '||projection||' ',?)>0" for t in identifiers)+')') if identifiers else ''
                diverse_sql = f'''WITH matches AS MATERIALIZED (
                    SELECT ch.*,r.source_id,r.revision_json,
                        chunk_fts.text AS projection,bm25(chunk_fts) AS bm25
                    FROM chunk_fts JOIN chunks ch ON ch.chunk_id=chunk_fts.chunk_id
                    {self._joins()} WHERE {where} AND chunk_fts.revision_id=ch.revision_id
                        AND chunk_fts MATCH ?),
                    eligible AS (SELECT *,instr(' '||projection||' ',?)>0 AS literal_exact
                        FROM matches WHERE bm25<0 AND ({coverage})>? {key_gate})
                    SELECT * FROM eligible ORDER BY
                        row_number() OVER (PARTITION BY source_id ORDER BY literal_exact DESC,bm25,revision_id,ordinal,chunk_id),
                        literal_exact DESC,bm25,revision_id,ordinal,chunk_id LIMIT ?'''
                rows = self._connection.execute(diverse_sql, [*args, match, ' '+phrase+' ',
                    *(' '+t+' ' for t in query_terms), LEXICAL_FLOOR*len(query_terms),
                    *(' '+t+' ' for t in identifiers), LEXICAL_CAP]).fetchall()
            else:
                exact_rows = self._connection.execute(sql, [*args, '"'+phrase+'"', LEXICAL_CAP]).fetchall()
                rows = list(exact_rows)
                selected = {row['chunk_id'] for row in rows}
                if len(rows) < LEXICAL_CAP:
                    for row in self._connection.execute(sql, [*args, match, LEXICAL_CAP]):
                        if row['chunk_id'] not in selected:
                            rows.append(row); selected.add(row['chunk_id'])
                        if len(rows) == LEXICAL_CAP: break
            candidates = []
            for row in rows:
                candidate = self._candidate(row, access, -row['bm25'])
                if candidate.chunk.lexical_projection != row['projection']:
                    raise KnowledgeStorageError(StorageFailure.CORRUPT)
                normalized = lexical_text(candidate.chunk.text)
                content_terms = set(normalized.split())
                matched = tuple(t for t in query_terms if t in content_terms)
                if identifiers and not any(t in content_terms for t in identifiers): continue
                coverage = len(matched)/len(query_terms)
                exact = (' '+phrase+' ') in (' '+normalized+' ')
                # Strictly above the frozen floor; equality is not sufficient.
                if candidate.score > 0 and matched and (exact or coverage > LEXICAL_FLOOR):
                    candidates.append(replace(candidate, exact=exact))
            ranked = sorted(candidates, key=lambda c: (not c.exact, -c.score,
                c.revision_id, c.chunk.ordinal, c.chunk.chunk_id))
            if diversity:
                first, rest, seen = [], [], set()
                for candidate in ranked:
                    (rest if candidate.source_id in seen else first).append(candidate)
                    seen.add(candidate.source_id)
                ranked = first + rest
            return tuple(ranked)

    def validate_candidates(self, candidates, access, filters=DocumentRetrievalFilter()):
        _require(len(candidates) <= 24)
        where, args = self._retrieval_where(access, filters)
        result = []
        with self._transaction(write=False):
            for candidate in candidates:
                row = self._connection.execute(f'''SELECT ch.*,r.source_id,r.revision_json FROM chunks ch
                    {self._joins()} WHERE {where} AND ch.chunk_id=?''', [*args, candidate.chunk.chunk_id]).fetchone()
                if row is not None:
                    fresh = self._candidate(row, access, candidate.score, candidate.exact)
                    if fresh.chunk != candidate.chunk or fresh.source_id != candidate.source_id:
                        raise KnowledgeStorageError(StorageFailure.CORRUPT)
                    result.append(fresh)
        return tuple(result)

    def _space(self, space):
        _require(isinstance(space, DocumentEmbeddingSpace))
        row = self._connection.execute('SELECT metadata_json FROM semantic_spaces WHERE space_id=?', (space.space_id,)).fetchone()
        if row is None: raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_UNAVAILABLE)
        stored = DocumentEmbeddingSpace.from_dict(json.loads(row[0]))
        if stored != space or stored.space_id != space.space_id:
            raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)

    def put_document_vectors(self, revision_id, space, vectors, access):
        """Explicit bounded idle projection, complete for one current revision.

        A failure rolls back the whole projection. Existing vectors in another
        space are never compared, converted or overwritten in that space.
        """
        _require(isinstance(space, DocumentEmbeddingSpace) and isinstance(vectors, dict))
        with self._transaction():
            revision = self._revision(revision_id, access)
            source = self._source(revision.source_id, access)
            if source.current_revision_id != revision_id: raise KnowledgeError(KnowledgeErrorCode.STALE_SOURCE)
            chunks = tuple(DocumentChunk.from_dict(json.loads(row[0])) for row in self._connection.execute(
                'SELECT chunk_json FROM chunks WHERE revision_id=?', (revision_id,)))
            if set(vectors) != {c.chunk_id for c in chunks} or any(c.chunking_profile != space.chunking_profile for c in chunks):
                raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
            normalized = {key: vector(value, space) for key, value in vectors.items()}
            # Optional projections consume the same workspace operational cap,
            # including retained spaces. A rejected projection leaves FTS intact.
            if source.scope.kind.value == 'WORKSPACE':
                blob_bytes = self._connection.execute('''SELECT COALESCE(sum(r.byte_length),0)
                    FROM source_revisions r JOIN sources s USING(source_id)
                    WHERE s.workspace_id=? AND s.scope_kind='WORKSPACE' AND s.state!='DELETED' ''',
                    (access.workspace_id,)).fetchone()[0]
                vector_bytes = self._connection.execute('''SELECT COALESCE(sum(length(v.vector)),0)
                    FROM semantic_vectors v JOIN chunks ch USING(chunk_id)
                    JOIN source_revisions r USING(revision_id) JOIN sources s USING(source_id)
                    WHERE s.workspace_id=? AND s.scope_kind='WORKSPACE' AND NOT
                    (ch.revision_id=? AND v.space_id=?)''', (access.workspace_id, revision_id, space.space_id)).fetchone()[0]
                if blob_bytes + vector_bytes + 8*space.dimension*len(normalized) > self.limits.workspace_bytes:
                    raise KnowledgeError(KnowledgeErrorCode.SOURCE_CAPACITY_EXCEEDED)
            row = self._connection.execute('SELECT 1 FROM semantic_spaces WHERE space_id=?', (space.space_id,)).fetchone()
            if row: self._space(space)
            else: self._connection.execute('INSERT INTO semantic_spaces VALUES (?,?)',
                (space.space_id, json.dumps(space.to_dict(), sort_keys=True, separators=(',', ':'))))
            for chunk_id, value in normalized.items():
                self._connection.execute('INSERT OR REPLACE INTO semantic_vectors VALUES (?,?,?)',
                    (chunk_id, space.space_id, struct.pack('<'+'d'*space.dimension, *value)))

    def semantic_candidates(self, query_vector, space, access, filters=DocumentRetrievalFilter()):
        query_vector = vector(query_vector, space)
        where, args = self._retrieval_where(access, filters)
        started, best = perf_counter(), []
        with self._transaction(write=False):
            self._space(space)
            rows = self._connection.execute(f'''SELECT ch.*,r.source_id,r.revision_json,v.vector FROM chunks ch
                {self._joins()} JOIN semantic_vectors v ON v.chunk_id=ch.chunk_id
                WHERE {where} AND v.space_id=?''', [*args, space.space_id])
            # Streaming dense scan, bounded RAM. Not advertised as ANN/quality
            # certification. Work exceeding the optional search budget degrades.
            for row in rows:
                if perf_counter()-started > .5: raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_UNAVAILABLE)
                data = row['vector']
                if len(data) != 8*space.dimension: raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
                values = vector(struct.unpack('<'+'d'*space.dimension, data), space)
                score = sum(a*b for a, b in zip(values, query_vector))
                if not math.isfinite(score): raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
                if score >= SEMANTIC_FLOOR:
                    rank = (-score, row['revision_id'], row['ordinal'], row['chunk_id'])
                    best.append((rank, dict(row)))
                    best = heapq.nsmallest(SEMANTIC_CAP, best, key=lambda item: item[0])
            result = tuple(self._candidate(row, access, -rank[0]) for rank, row in sorted(best, key=lambda item:item[0]))
            if any(c.chunk.chunking_profile != space.chunking_profile for c in result):
                raise KnowledgeError(KnowledgeErrorCode.SEMANTIC_SPACE_MISMATCH)
            return result

    def reserve_legacy_source(self, legacy_key, scope, access):
        """Random Nova ID bound to an explicit host rebuild key, including tombstones.

        Reserve before import so interruption/rebuild cannot create a duplicate
        identity and delete cannot be bypassed by repeating the same rebuild.
        """
        from local_cli.core.knowledge import Source, SourceKind, SourceTrustClass, new_source_id
        from datetime import datetime, timezone
        _require(access.permits(scope) and isinstance(legacy_key, str) and bool(legacy_key))
        key = 'legacy-rebuild-v1:' + hashlib.sha256(json.dumps([scope.to_dict(),legacy_key], sort_keys=True).encode()).hexdigest()
        with self._transaction():
            row = self._connection.execute('SELECT value FROM knowledge_meta WHERE key=?', (key,)).fetchone()
            if row: return self._source(row[0], access)
            source = Source(new_source_id(), SourceKind.PROJECT_SOURCE, scope,
                'legacy-rebuild:'+hashlib.sha256(legacy_key.encode()).hexdigest(),
                'Explicit legacy source rebuild', SourceTrustClass.LEGACY_IMPORTED, datetime.now(timezone.utc))
            from local_cli.infrastructure.knowledge_sqlite import encode
            self._connection.execute('INSERT INTO sources VALUES (?,?,?,?,?,?,?)', (source.source_id,
                scope.workspace_id, scope.session_id, scope.kind.value, encode(source), None, source.lifecycle_state.value))
            self._capacity(source)
            self._connection.execute('INSERT INTO knowledge_meta VALUES (?,?)', (key, source.source_id))
            return source
