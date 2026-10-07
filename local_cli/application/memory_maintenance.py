"""M6 Application policy/receipts. Coordinator owns scheduling and commits.

Workers compute untrusted extraction only. No second AgentLoop, new session,
grant, security policy, or retention decision. Queue data is synthetic in tests.
"""
from dataclasses import replace
from datetime import datetime, timezone
from local_cli.core.memory import (MemoryAccessScope,MemoryError,MemoryErrorCode,
    MemorySourceClass,MemoryStatus)
from local_cli.application.memory_extraction import (AutoSafeMemoryPolicy,
    MemoryConsolidator,cheap_prefilter,parse_extraction)


class MemoryMaintenanceService:
    def __init__(self,service,jobs,*,mode='off',soft_records=20000,soft_bytes=512*1024*1024):
        self.service,self.jobs=service,jobs
        self.policy=AutoSafeMemoryPolicy(service.redactor,mode=mode)
        self.consolidator=MemoryConsolidator(service)
        if type(soft_records) is not int or soft_records<1 or type(soft_bytes) is not int or soft_bytes<1:
            raise ValueError('Invalid trusted memory engineering soft limit')
        self.soft_records,self.soft_bytes=soft_records,soft_bytes
        self.pause_reason=None

    def capacity(self):
        usage=self.jobs.usage()
        observed=usage['filesBytes'];maintenance_error=None
        if usage['activeRecords']<self.soft_records and observed>=self.soft_bytes:
            try:usage=self.jobs.usage(stabilize=True)
            except MemoryError as exc:maintenance_error=exc.code
        record_limit=usage['activeRecords']>=self.soft_records
        size_limit=bool(usage.get('footprintStable') and usage['filesBytes']>=self.soft_bytes)
        busy=bool(maintenance_error or usage.get('checkpointBusy'))
        self.pause_reason=('MEMORY_CAPACITY_REACHED' if record_limit or size_limit else
            (maintenance_error or 'MEMORY_STORE_LOCKED') if busy else None)
        return dict(capturePaused=self.pause_reason is not None,errorCode=self.pause_reason,
            activeRecords=usage['activeRecords'],filesBytes=usage['filesBytes'],
            observedFootprintBytes=observed,stableFootprintBytes=usage['filesBytes'] if usage.get('footprintStable') else None,
            checkpointAttempted=usage.get('checkpointAttempted',False),maintenanceDeferred=busy,
            recordLimitReached=record_limit,sizeLimitReached=size_limit,
            softRecordLimit=self.soft_records,softSizeBytes=self.soft_bytes,limitsAreOperational=True)

    def suppressed_memory_ids(self,scope):return self.jobs.suppressed_memory_ids(scope)

    def scope(self,workspace,*,register=False):
        return MemoryAccessScope(self.service.subject,self.service.identity.resolve_workspace(workspace,register=register))

    def capture(self,input):
        if self.policy.mode=='off' or not cheap_prefilter(input.text,self.policy.base):return None
        state=self.capacity()
        if state['capturePaused']:raise MemoryError(MemoryErrorCode(state['errorCode']))
        return self.jobs.enqueue(input)

    def checkpoint(self,job,reply,scope):
        from local_cli.core.memory_maintenance import MemoryExtractionInput
        input=MemoryExtractionInput(subject_id=scope.subject_id,workspace_id=scope.workspace_id,
            evidence=self._evidence(job),text=job['text'])
        drafts=parse_extraction(reply,input,job['jobId'],self.policy.base)
        ready={**job,'revision':job['revision']+1,'state':'READY','drafts':drafts}
        self.jobs.save_job(job['jobId'],scope,expected_revision=job['revision'],payload=ready)
        return ready

    @staticmethod
    def _evidence(job):
        from local_cli.core.memory import MemoryEvidence
        data=job['source']
        return MemoryEvidence(**{**data,'source_class':MemorySourceClass(data['source_class']),
            'source_timestamp':datetime.fromisoformat(data['source_timestamp'])})

    def commit(self,job,scope,*,pre_commit=None,**options):
        payload,changes=self.consolidator.plan(job,self.policy,**options)
        created=sum(c.action=='create' for c in changes)
        if not options.get('confirmation') and created:
            capacity=self.capacity()
            if capacity['capturePaused'] or capacity['activeRecords']+created>self.soft_records:
                self.pause_reason=capacity['errorCode'] or 'MEMORY_CAPACITY_REACHED'
                raise MemoryError(MemoryErrorCode(self.pause_reason))
        if pre_commit is not None:pre_commit()
        self.jobs.commit_job(job['jobId'],scope,expected_revision=job['revision'],payload=payload,changes=changes)
        # SQLite epoch invalidates M5 projections synchronously with the write.
        # No extra embedding inference delaying/preventing a new user Turn.
        return payload['result']

    def control(self,name,args,*,workspace,session_id,operation_id):
        scope=self.scope(workspace)
        if name=='memory_proposals':
            if args:raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
            jobs=self.jobs.list_jobs(scope,states=('DONE',),limit=128,proposed_only=True)
            return {'proposals':[dict(jobId=j['jobId'],revision=j['revision'],proposal=d)
                for j in jobs for d in j['drafts'] if d['state']=='PROPOSED']}
        allowed={'jobId','proposalId','revision'}|({'resolution'} if name=='memory_confirm' else set())
        if not set(args)<=allowed or not {'jobId','proposalId','revision'}<=set(args):
            raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
        job=self.jobs.get_job(args['jobId'],scope)
        if not job:raise MemoryError(MemoryErrorCode.NOT_FOUND)
        if type(args['revision']) is not int or job['revision']!=args['revision']:
            raise MemoryError(MemoryErrorCode.CONFLICT)
        draft=next((d for d in job['drafts'] if d['proposalId']==args['proposalId'] and d['state']=='PROPOSED'),None)
        if draft is None:raise MemoryError(MemoryErrorCode.CONFLICT)
        if name=='memory_confirm':
            resolution=args.get('resolution','create')
            if resolution not in ('create','supersede','conflict'):raise MemoryError(MemoryErrorCode.UNTRUSTED_INPUT)
            return self.commit(job,scope,confirmation={'sessionId':session_id,'operationId':operation_id},
                proposal_id=draft['proposalId'],resolution=resolution)
        # Rejecting a conflicting proposal does NOT restore a fact automatically:
        # ordinary memory_correct explicitly resolves the quarantined old record.
        drafts=[{**d,'state':'REJECTED','text':'','source':{},'direct':False}
            if d['proposalId']==draft['proposalId'] else d for d in job['drafts']]
        self.jobs.save_job(job['jobId'],scope,expected_revision=job['revision'],
            payload={**job,'revision':job['revision']+1,'drafts':drafts})
        return {'rejected':True,'notice':'Conflicted records remain quarantined until explicitly corrected.'}
