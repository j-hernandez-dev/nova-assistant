"""M6 synthetic evidence helpers. Scripted extractor is CONTRACT evidence only."""
import hashlib
from dataclasses import replace
from local_cli.core.memory import MemorySourceClass
from local_cli.core.memory_maintenance import MemoryExtractionInput
from tests.memory_v1.m1_fixtures import AT,SUBJECT_A,WORKSPACE_A,evidence


def extraction_input(text='I prefer concise answers.',*,source_class=MemorySourceClass.USER_ASSERTION,source_id=None,**kw):
    source_id=source_id or hashlib.sha256(text.encode()).hexdigest()
    return MemoryExtractionInput(subject_id=kw.pop('subject_id',SUBJECT_A),
        workspace_id=kw.pop('workspace_id',WORKSPACE_A),text=text,
        evidence=evidence(source_id,source_class=source_class,turn_id='synthetic-turn',
            evidence_hash=hashlib.sha256(text.encode()).hexdigest(),**kw))


def reply(text,kind='PREFERENCE',key='preference.answer_style',**fields):
    return dict(schemaVersion=1,candidates=[{**dict(kind=kind,start=0,end=len(text),key=key,
        validFrom=None,validTo=None),**fields}])

