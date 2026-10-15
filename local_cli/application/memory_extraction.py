"""M6 literal-evidence extraction, conservative policy and consolidation.

No LLM confidence authorizes a write. The extractor supplies only offsets,
kind/key and literal temporal bounds. Application binds subject/scope/provenance.
"""
from dataclasses import replace
from difflib import SequenceMatcher
from datetime import datetime, timezone
import hashlib
import re
import unicodedata

from local_cli.core.memory import (MemoryAccessScope,MemoryError,MemoryErrorCode,
    MemoryEvidence,MemoryKind,MemoryProposal,MemoryScope,MemoryScopeKind,MemorySensitivity,
    MemorySource,MemorySourceClass,MemoryStatus,MemoryValidity,MemoryRecord,MemoryQuery,
    MemoryWriteDisposition)
from local_cli.core.memory_maintenance import MemoryExtractionInput,MemoryRecordChange
from local_cli.application.memory_policy import ExplicitMemoryPolicy

AUTO_SAFE_VERSION='mem6-conservative-span-v1'
_INSTRUCTION=re.compile(r'(?i)ignore\s+(?:all\s+)?(?:previous|prior)|ignora\s+.*instrucci|'
    r'\b(?:system prompt|developer message|grant|approval|sudo|execute|run command|api.key|'
    r'contrase[ñn]a|password|bearer|token|secret|jailbreak)\b')
_INDIRECT=re.compile(r'(?i)\b(?:example|ejemplo|imagine|imagina|suppose|sup[oó]n|'
    r'quoted|citado|fiction|ficci[oó]n|hypothetical|hipot[eé]tic|if|si|maybe|quiz[aá])\b|[\"“”`]')
_PREF=re.compile(r'(?i)^(?:I (?:prefer|like)|Prefiero|Me gusta)\s+\S')
_WORK=re.compile(r'(?i)^(?:In this (?:project|workspace),? we (?:use|follow)|'
    r'This project (?:uses|follows)|En este proyecto (?:usamos|seguimos)|Este proyecto (?:usa|sigue))\s+\S')
_TRIGGER=re.compile(r'(?i)prefer|prefier|me gusta|this project|este proyecto|'
    r'work|trabaj|currently|actualmente|finished|complet|closed|cerr|remember|recuerd')
_TRANSIENT=re.compile(r'(?i)\b(?:today|tonight|temporarily|currently|for now|this turn|'
    r'ahora|hoy|temporalmente|actualmente|por ahora|este turno)\b')
_KEY_PREFIX={MemoryKind.PREFERENCE:'preference.',MemoryKind.WORKSPACE_FACT:'workspace.',
    MemoryKind.SEMANTIC_FACT:'profile.',MemoryKind.EPISODE:'episode.',MemoryKind.PROCEDURE:'procedure.'}


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())


def stable_id(*parts):
    return hashlib.sha256('\0'.join(str(p) for p in parts).encode()).hexdigest()


def cheap_prefilter(text,policy):
    # Conservative opportunity filter, NOT a claim to understand all language.
    return (isinstance(text,str) and 8<=len(text)<=4096 and '[REDACTED' not in text
        and policy.classify(text) is MemorySensitivity.NORMAL
        and not _INSTRUCTION.search(text) and bool(_TRIGGER.search(text)))


def parse_extraction(reply,evidence,job_id,policy):
    if (not isinstance(reply,dict) or set(reply)!={'schemaVersion','candidates'}
            or type(reply['schemaVersion']) is not int or reply['schemaVersion'] not in (1,2)
            or not isinstance(reply['candidates'],list) or len(reply['candidates'])>4):
        raise MemoryError(MemoryErrorCode.INVALID_PROPOSAL)
    drafts=[];seen=set()
    for row in reply['candidates']:
        if reply['schemaVersion']==2:
            if not isinstance(row,dict) or set(row)!={'kind','evidenceSpan','key','validFrom','validTo'}:
                raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
            span=row['evidenceSpan']
            if (not isinstance(span,str) or not span.strip() or len(span)>512 or
                    evidence.text.count(span)!=1):
                raise MemoryError(MemoryErrorCode.INVALID_PROPOSAL)
            start=evidence.text.index(span)
            row={k:v for k,v in row.items() if k!='evidenceSpan'}|{'start':start,'end':start+len(span)}
        if not isinstance(row,dict) or set(row)!={'kind','start','end','key','validFrom','validTo'}:
            raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
        try:kind=MemoryKind(row['kind'])
        except (ValueError,TypeError):raise MemoryError(MemoryErrorCode.INVALID_PROPOSAL) from None
        start,end=row['start'],row['end']
        if (type(start) is not int or type(end) is not int or not 0<=start<end<=len(evidence.text)
                or end-start>512):
            raise MemoryError(MemoryErrorCode.INVALID_PROPOSAL)
        literal=evidence.text[start:end].strip()
        if not literal:raise MemoryError(MemoryErrorCode.INVALID_PROPOSAL)
        key=row['key']
        if key is not None and (not isinstance(key,str) or not re.fullmatch('[a-z][a-z0-9_.-]{0,127}',key)
                or not key.startswith(_KEY_PREFIX[kind])):
            raise MemoryError(MemoryErrorCode.INVALID_PROPOSAL)
        def date(value):
            if value is None:return None
            if not isinstance(value,str) or value not in literal:
                raise MemoryError(MemoryErrorCode.INVALID_PROPOSAL)
            try:d=datetime.fromisoformat(value)
            except ValueError:raise MemoryError(MemoryErrorCode.INVALID_PROPOSAL) from None
            if d.tzinfo is None:raise MemoryError(MemoryErrorCode.INVALID_PROPOSAL)
            return d
        validity=MemoryValidity(observed_at=evidence.evidence.source_timestamp,
            valid_from=date(row['validFrom']),valid_to=date(row['validTo']))
        sensitivity=policy.classify(literal,key)
        if sensitivity is not MemorySensitivity.NORMAL or _INSTRUCTION.search(literal):
            continue  # Never escrow raw sensitive/secret data from automatic capture.
        signature=(kind.value,normalized(literal),key)
        if signature in seen:continue
        seen.add(signature)
        # Whole-input directness matters: a quoted/example span is not a user assertion.
        direct=(start==0 and end==len(evidence.text)
            and evidence.evidence.source_class is MemorySourceClass.USER_ASSERTION
            and not _INDIRECT.search(evidence.text)
            and not _TRANSIENT.search(evidence.text)
            and not _INSTRUCTION.search(evidence.text)
            and sensitivity is MemorySensitivity.NORMAL
            and policy.classify(evidence.text) is MemorySensitivity.NORMAL
            and ((kind is MemoryKind.PREFERENCE and _PREF.match(literal) and _PREF.match(evidence.text.strip()))
             or (kind is MemoryKind.WORKSPACE_FACT and _WORK.match(literal) and _WORK.match(evidence.text.strip()))))
        personal=kind is MemoryKind.PREFERENCE and direct and not re.search(r'(?i)\b(?:project|workspace|proyecto)\b',literal)
        scope=MemoryScope(MemoryScopeKind.GLOBAL_PROFILE) if personal else (
            MemoryScope(MemoryScopeKind.WORKSPACE,evidence.workspace_id))
        source=replace(evidence.evidence,source_id='m6-source-'+stable_id(job_id,start,end),
            evidence_excerpt=literal,evidence_hash=hashlib.sha256(literal.encode()).hexdigest())
        def source_dto(s):
            d=dict(vars(s));d['source_class']=s.source_class.value
            d['source_timestamp']=s.source_timestamp.isoformat();return d
        pid='m6-proposal-'+stable_id(job_id,start,end,kind.value)
        drafts.append(dict(proposalId=pid,kind=kind.value,text=literal,key=key,
            scopeKind=scope.kind.value,scopeId=scope.scope_id.value if scope.scope_id else None,
            identityVersion=scope.scope_id.identity_version if scope.scope_id else None,
            source=source_dto(source),sensitivity=sensitivity.value,direct=bool(direct),
            validFrom=validity.valid_from.isoformat() if validity.valid_from else None,
            validTo=validity.valid_to.isoformat() if validity.valid_to else None,
            state='PROPOSED',targetId=None,targetRevision=None,conflictGroupId=None,
            memoryId=None,contentHash=hashlib.sha256(normalized(literal).encode()).hexdigest()))
    return drafts


class AutoSafeMemoryPolicy:
    def __init__(self,redactor,*,mode='off'):
        if mode not in ('off','propose_only','low_risk'):raise ValueError('Invalid memory capture mode')
        self.base=ExplicitMemoryPolicy(redactor);self.mode=mode

    def evaluate(self,draft):
        if self.mode=='off':return MemoryWriteDisposition.DEFER
        if (draft['sensitivity']!='NORMAL' or self.base.classify(draft['text'],draft['key']) is not MemorySensitivity.NORMAL
                or _INSTRUCTION.search(draft['text'])):
            return MemoryWriteDisposition.REJECT
        if (self.mode=='low_risk' and draft['direct']
                and draft['source']['source_class']==MemorySourceClass.USER_ASSERTION.value
                and draft['kind'] in ('PREFERENCE','WORKSPACE_FACT')
                and draft['validFrom'] is None and draft['validTo'] is None
                and not draft['targetId']):
            return MemoryWriteDisposition.ACCEPT
        return MemoryWriteDisposition.REQUIRE_USER_CONFIRMATION


class MemoryConsolidator:
    def __init__(self,service):
        self.service=service

    def scope(self,job,draft):
        from local_cli.core.memory import WorkspaceId
        return MemoryScope(MemoryScopeKind(draft['scopeKind']),
            WorkspaceId(draft['scopeId'],draft['identityVersion']) if draft['scopeId'] else None)

    def candidates(self,job,draft):
        from local_cli.core.memory import SubjectId
        scope=self.scope(job,draft);access=MemoryAccessScope(SubjectId(job['subjectId']),scope.scope_id,
            include_global=scope.kind is MemoryScopeKind.GLOBAL_PROFILE)
        exact=self.service.store.find_exact(access,text=draft['text'],key=draft['key'])
        if draft['key']:
            keyed=tuple(r for r in exact if r.canonical_key==draft['key'])
            if keyed:return keyed
        if exact:return exact
        # Bounded near-candidates, no store scan. Ambiguity requires confirmation,
        # not an automatic semantic merge or LWW.
        words=re.findall(r'\w+',draft['text'])[:24]
        if not words:return ()
        query=MemoryQuery(text=' '.join(words),scope=access,at=datetime.now(timezone.utc),
            limit=8,match_any=True,allow_conflicted=True)
        ids=self.service.lexical.search(query)
        candidates=tuple(r for item in ids if (r:=self.service.store.get(item.memory_id,access)) is not None)
        # Only exact normalized equality is deduplicated without confirmation.
        near=tuple(r for r in candidates if r.kind.value==draft['kind'] and
            (normalized(r.canonical_text)==normalized(draft['text']) or
             (draft['key'] is not None and r.canonical_key==draft['key']) or
             SequenceMatcher(None,normalized(r.canonical_text),normalized(draft['text'])).ratio()>=.75))
        if near:return near
        # Optional M5 projection: bounded, capability-gated, never loads a model.
        semantic=self.service.semantic
        if semantic is not None and semantic.available:
            from time import perf_counter
            rows,_,_=semantic.query(query,started=perf_counter())
            return tuple(r for item in rows if item.score>=.9 and
                (r:=self.service.store.get(item.memory_id,access)) is not None and r.kind.value==draft['kind'])
        return ()

    def record(self,job,draft,*,now,confirmation=None,supersedes=None,conflict=False):
        from local_cli.core.memory import SubjectId
        source_data={**draft['source'],'source_class':MemorySourceClass(draft['source']['source_class']),
            'source_timestamp':datetime.fromisoformat(draft['source']['source_timestamp'])}
        mid='m6-memory-'+stable_id(job['jobId'],draft['proposalId'])
        sources=[MemorySource(**source_data,memory_id=mid)]
        if confirmation:
            sources.append(MemorySource(source_id='m6-confirm-'+confirmation['operationId'],memory_id=mid,
                source_class=MemorySourceClass.USER_EXPLICIT_MEMORY,source_timestamp=now,
                session_id=confirmation['sessionId'],operation_id=confirmation['operationId']))
        return MemoryRecord(memory_id=mid,subject_id=SubjectId(job['subjectId']),scope=self.scope(job,draft),
            kind=MemoryKind(draft['kind']),canonical_text=draft['text'],canonical_key=draft['key'],
            source_class=MemorySourceClass.USER_EXPLICIT_MEMORY if confirmation else MemorySourceClass.USER_ASSERTION,
            sensitivity_class=MemorySensitivity.NORMAL,created_at=now,updated_at=now,sources=tuple(sources),
            validity=MemoryValidity(observed_at=datetime.fromisoformat(draft['source']['source_timestamp']),
                valid_from=datetime.fromisoformat(draft['validFrom']) if draft['validFrom'] else None,
                valid_to=datetime.fromisoformat(draft['validTo']) if draft['validTo'] else None),
            supersedes_memory_id=supersedes,status=MemoryStatus.CONFLICTED if conflict else MemoryStatus.ACTIVE,
            conflict_group_id=draft['conflictGroupId'] if conflict else None)

    def plan(self,job,policy,*,now=None,confirmation=None,proposal_id=None,resolution='create'):
        now=now or datetime.now(timezone.utc)
        drafts=[dict(d) for d in job['drafts']];changes=[];claimed=set()
        for draft in drafts:
            if draft['state']!='PROPOSED' or proposal_id and draft['proposalId']!=proposal_id:continue
            matches=self.candidates(job,draft)
            if any(r.sensitivity_class is not MemorySensitivity.NORMAL for r in matches):
                if confirmation:raise MemoryError(MemoryErrorCode.SENSITIVE_DENIED)
                draft.update(state='REJECTED',text='',source={},direct=False)
                continue  # No sensitivity downgrade or auto-append to a sensitive record.
            duplicate=next((r for r in matches if r.kind.value==draft['kind'] and
                r.status is MemoryStatus.ACTIVE and normalized(r.canonical_text)==normalized(draft['text'])),None)
            if matches and not duplicate:
                old=matches[0]
                if draft['targetId'] and (draft['targetId']!=old.memory_id or draft['targetRevision']!=old.revision):
                    raise MemoryError(MemoryErrorCode.CONFLICT)
                draft.update(targetId=old.memory_id,targetRevision=old.revision,
                    conflictGroupId=draft['conflictGroupId'] or 'm6-conflict-'+stable_id(old.memory_id,draft['proposalId']))
                if not confirmation and old.status is MemoryStatus.ACTIVE:
                    # Quarantine metadata, NOT an automatic contradictory fact.
                    changes.append(MemoryRecordChange('update',replace(old,revision=old.revision+1,
                        updated_at=max(now,old.updated_at),status=MemoryStatus.CONFLICTED,
                        conflict_group_id=draft['conflictGroupId']),old.revision))
                    draft['targetRevision']=old.revision+1
            signature=(draft['scopeKind'],draft['scopeId'],draft['key'] or normalized(draft['text']))
            if signature in claimed:raise MemoryError(MemoryErrorCode.CONFLICT)
            claimed.add(signature)
            decision=MemoryWriteDisposition.ACCEPT if confirmation else policy.evaluate(draft)
            if draft['kind']=='PROCEDURE' and not confirmation:decision=MemoryWriteDisposition.REQUIRE_USER_CONFIRMATION
            if decision is not MemoryWriteDisposition.ACCEPT:continue
            record=self.record(job,draft,now=now,confirmation=confirmation,
                supersedes=draft['targetId'] if confirmation and resolution=='supersede' else None,
                conflict=bool(confirmation and matches and not duplicate and resolution=='conflict'))
            if duplicate:
                source=replace(record.sources[0],memory_id=duplicate.memory_id)
                if not any(s.source_id==source.source_id for s in duplicate.sources):
                    extra=tuple(replace(s,memory_id=duplicate.memory_id) for s in record.sources
                        if not any(old.source_id==s.source_id for old in duplicate.sources))
                    changes.append(MemoryRecordChange('update',replace(duplicate,revision=duplicate.revision+1,
                        updated_at=max(now,duplicate.updated_at),sources=duplicate.sources+extra,
                        source_class=MemorySourceClass.USER_EXPLICIT_MEMORY if confirmation else duplicate.source_class),duplicate.revision))
                draft.update(state='ACCEPTED',memoryId=duplicate.memory_id)
            elif matches:
                if not confirmation:continue
                if len(matches)!=1 or matches[0].kind.value!=draft['kind']:
                    raise MemoryError(MemoryErrorCode.CONFLICT)
                old=matches[0]
                if resolution=='supersede':
                    changes.append(MemoryRecordChange('supersede',record,old.revision))
                elif resolution=='conflict':
                    changes.append(MemoryRecordChange('update',replace(old,revision=old.revision+1,updated_at=now,
                        status=MemoryStatus.CONFLICTED,conflict_group_id=draft['conflictGroupId']),old.revision))
                    changes.append(MemoryRecordChange('create',record))
                else:raise MemoryError(MemoryErrorCode.CONFLICT)
                draft.update(state='ACCEPTED',memoryId=record.memory_id)
            else:
                if draft['targetId']:raise MemoryError(MemoryErrorCode.CONFLICT)  # Deleted/changed target: no resurrection.
                changes.append(MemoryRecordChange('create',record))
                draft.update(state='ACCEPTED',memoryId=record.memory_id)
        payload={**job,'revision':job['revision']+1,'state':'DONE','text':'','drafts':drafts,
            'result':{'accepted':sum(d['state']=='ACCEPTED' for d in drafts),
                'proposed':sum(d['state']=='PROPOSED' for d in drafts)}}
        # Accepted drafts retain IDs/hashes only, not a duplicate content archive.
        payload['drafts']=[{**d,'text':'','source':{},'direct':False} if d['state'] in ('ACCEPTED','REJECTED') else d for d in drafts]
        return payload,tuple(changes)

