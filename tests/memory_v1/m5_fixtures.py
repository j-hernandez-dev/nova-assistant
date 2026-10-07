"""Deterministic vectors are CONTRACT fixtures, never semantic model evidence."""
from local_cli.core.memory import EmbeddingSpace
from local_cli.infrastructure.memory_semantic import FORMAT
from tests.memory_v1.m1_fixtures import AT


def space(name='synthetic-v1', dimension=3):
    return EmbeddingSpace(embedding_space_id=name,provider_kind='SYNTHETIC_CONTRACT_ONLY',model_id=name,
        model_revision=name,dimension=dimension,normalization='l2',storage_format=FORMAT,created_at=AT)


class SyntheticEmbeddings:
    def __init__(self, embedding_space=None):
        self.space=embedding_space or space()
        self.query_calls=0; self.record_calls=0

    def status(self): return self.space
    def embed_query(self,text):
        self.query_calls+=1
        return (1.,0.,0.)
    def embed_records(self, batch):
        self.record_calls+=1
        return tuple((1.,0.,0.) for _ in batch)
