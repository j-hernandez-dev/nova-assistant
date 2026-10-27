"""Real SQLite/file lifecycle and authenticated host storage regressions."""
import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from uuid import uuid4

from local_cli.bootstrap_knowledge import knowledge_factory
from local_cli.core.knowledge import KnowledgeError, KnowledgeScopeKind, SourceKind, SourceTrustClass
from local_cli.core.knowledge_store import KnowledgeAccess
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from local_cli.infrastructure.knowledge_storage import workspace_identity, UNLINKED_WORKSPACE
from local_cli.infrastructure.security_audit_jsonl import JsonlSecurityAudit
from local_cli.application.storage import StorageCommand
from local_cli.application.session import AgentSessionCoordinator
from local_cli.application.events import EventBufferConfig
from local_cli.application.commands import ApplicationCommand,CommandKind
from local_cli.application.knowledge_host import KnowledgeCommand
from local_cli.core.contracts import new_command_id
from local_cli.interfaces.approval_proof import approval_proof
from local_cli.interfaces.jsonl_application import JsonlApplicationAdapter
from tests.knowledge_inputs_v1.k1_helpers import published, source, projection, execution, PAYLOAD


class StorageManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.state=self.root/'state'
        self.a=self.root/'project a';self.a.mkdir()
        self.b=self.root/'project b';self.b.mkdir()
        self.projects=[dict(path=str(self.a),name='A'),dict(path=str(self.b),name='B')]
        self.access_a=KnowledgeAccess(workspace_identity(self.a),'session-a')
        self.access_b=KnowledgeAccess(workspace_identity(self.b),'session-b')

    def store(self):
        value=SQLiteKnowledgeStore(self.state)
        value.register_storage_workspace(self.a,self.access_a.workspace_id)
        value.register_storage_workspace(self.b,self.access_b.workspace_id)
        self.addCleanup(value.close)
        return value

    def report(self,store,projects=None):
        return store.manage_storage('report',dict(projects=self.projects if projects is None else projects))

    def test_download_original_bytes_after_unlink_and_atomic_save_as(self):
        from local_cli.infrastructure.knowledge_export import export_copy
        store=self.store()
        payload=b'\x00\xffOriginal binary\r\n'
        from tests.knowledge_inputs_v1.k1_helpers import begin
        operation=begin(store,source(access=self.access_a),self.access_a)
        digest,size=store.stage(operation.operation_id,self.access_a,[payload],lambda:False)
        item=store.publish(operation.operation_id,self.access_a,projection(operation,digest,size,'Extracted summary'),lambda:False)
        store.manage_storage('detach_project',dict(projectPath=str(self.a),projects=self.projects))
        self.assertEqual(store.read_storage_file(item.source_id),payload)
        target=self.root/'Recovered.bin';target.write_bytes(b'previous destination')
        export_copy(store.read_storage_file(item.source_id),str(target),store.files.root)
        self.assertEqual(target.read_bytes(),payload)
        self.assertEqual(store.read_storage_file(item.source_id),payload)
        self.assertEqual(list(self.root.glob('.nova-download-*')),[])
        for blocked in [store.files.root/'overwrite.bin',self.root]:
            with self.assertRaises(KnowledgeError):export_copy(payload,str(blocked),store.files.root)

    def test_legacy_session_migration_before_recovery_and_close(self):
        store=self.store()
        item,_,_=published(store,source(KnowledgeScopeKind.SESSION,self.access_a),self.access_a)
        store.close_session(self.access_a)
        recovered=store.get_source(item.source_id,KnowledgeAccess(self.access_a.workspace_id,'next-session'))
        self.assertEqual(recovered.scope.kind,KnowledgeScopeKind.WORKSPACE)
        store.close()
        reopened=self.store()
        reopened.recover(KnowledgeAccess(self.access_a.workspace_id,'third-session'))
        self.assertEqual(reopened.read_blob(recovered.current_revision_id,self.access_a),PAYLOAD)

    def test_constructor_preserves_abandoned_session_before_startup_recover(self):
        store=self.store()
        item,_,_=published(store,source(KnowledgeScopeKind.SESSION,self.access_a),self.access_a)
        store.close() # simulate old process exiting without new migration hook
        reopened=self.store()
        reopened.recover(KnowledgeAccess(self.access_a.workspace_id,'different-session'))
        self.assertEqual(self.report(reopened)['files'][0]['id'],item.source_id)

    def test_rebind_preserves_ids_revisions_and_changes_access_after_restart(self):
        store=self.store()
        item,prepared,_=published(store,source(access=self.access_a),self.access_a)
        store.manage_storage('move',dict(ids=[item.source_id],projectPath=str(self.b),projects=self.projects))
        with self.assertRaises(KnowledgeError):store.get_source(item.source_id,self.access_a)
        self.assertEqual(store.get_source(item.source_id,self.access_b).current_revision_id,prepared.revision.revision_id)
        store.close()
        reopened=self.store()
        self.assertEqual(self.report(reopened)['files'][0]['projectPath'],str(self.b))
        self.assertEqual(reopened.read_blob(prepared.revision.revision_id,self.access_b),PAYLOAD)

    def test_detach_and_missing_registration_do_not_auto_relink(self):
        store=self.store()
        item,_,_=published(store,source(access=self.access_a),self.access_a)
        self.assertIsNone(self.report(store,projects=[self.projects[1]])['files'][0]['projectPath'])
        self.assertIsNone(self.report(store)['files'][0]['projectPath'])
        with self.assertRaises(KnowledgeError):store.get_source(item.source_id,self.access_a)
        store.manage_storage('move',dict(ids=[item.source_id],projectPath=str(self.a),projects=self.projects))
        store.manage_storage('detach_project',dict(projectPath=str(self.a),projects=self.projects))
        self.assertIsNone(self.report(store)['files'][0]['projectPath'])

    def test_batch_validation_is_atomic(self):
        store=self.store()
        item,_,_=published(store,source(access=self.access_a),self.access_a)
        for name,args in [('delete',dict(ids=[item.source_id,str(uuid4())])),
                          ('move',dict(ids=[item.source_id],projectPath=str(self.root/'not registered')))]:
            with self.assertRaises(KnowledgeError):store.manage_storage(name,dict(projects=self.projects,**args))
            self.assertEqual(self.report(store)['files'][0]['projectPath'],str(self.a))
            self.assertEqual(store.read_blob(item.current_revision_id,self.access_a),PAYLOAD)

    def test_removed_project_batch_still_works_after_registry_removal(self):
        store=self.store()
        item,_,_=published(store,source(access=self.access_a),self.access_a)
        store.manage_storage('detach_project',dict(projectPath=str(self.a),projects=[self.projects[1]]))
        self.assertIsNone(self.report(store)['files'][0]['projectPath'])
        store.manage_storage('move',dict(ids=[item.source_id],projectPath=str(self.a),projects=self.projects))
        store.manage_storage('delete_project',dict(projectPath=str(self.a),projects=[self.projects[1]]))
        self.assertEqual(self.report(store)['files'],[])

    def test_report_racing_removed_project_deletion_preserves_intended_batch(self):
        store=self.store()
        item,_,_=published(store,source(access=self.access_a),self.access_a)
        retained,_,_=published(store,source(access=self.access_b),self.access_b)
        without_old=[self.projects[1]]
        # UI refresh may run after registry removal but before the authorized
        # deletion IPC. It must not erase the information required by that IPC.
        inventory=self.report(store,projects=without_old)['files']
        self.assertIsNone(next(row for row in inventory if row['id']==item.source_id)['projectPath'])
        result=store.manage_storage('delete_project',dict(projectPath=str(self.a),projects=without_old))
        self.assertEqual(result['removedIds'],[item.source_id])
        self.assertEqual({item['id'] for item in result['files']},{retained.source_id})

    def test_explicit_reassignment_clears_automatic_detachment_provenance(self):
        store=self.store()
        item,_,_=published(store,source(access=self.access_a),self.access_a)
        self.report(store,projects=[self.projects[1]])
        store.manage_storage('move',dict(ids=[item.source_id],projectPath=str(self.b),projects=self.projects))
        result=store.manage_storage('delete_project',dict(projectPath=str(self.a),projects=[self.projects[1]]))
        self.assertEqual(result['removedIds'],[])
        self.assertEqual(result['files'][0]['projectPath'],str(self.b))

    def test_interrupted_delete_cleanup_is_retried_after_restart(self):
        store=self.store()
        item,_,_=published(store,source(access=self.access_a),self.access_a)
        cleanup=store._cleanup_source
        def failed(source_id):raise OSError('simulated power loss before owned blob cleanup')
        store._cleanup_source=failed
        with self.assertRaises(OSError):store.manage_storage('delete',dict(ids=[item.source_id],projects=self.projects))
        self.assertTrue(store.files.path('blobs',item.current_revision_id+'.bin').exists())
        store._cleanup_source=cleanup
        store.close()
        reopened=self.store()
        self.assertFalse(reopened.files.path('blobs',item.current_revision_id+'.bin').exists())
        self.assertEqual(self.report(reopened)['files'],[])

    def test_legacy_promoted_web_document_is_not_a_local_attachment(self):
        store=self.store()
        item,_,_=published(store,replace(source(access=self.access_a),kind=SourceKind.WORKSPACE_IMPORT,
            trust_class=SourceTrustClass.PUBLIC_WEB_FETCH),self.access_a)
        self.assertEqual(self.report(store)['files'],[])
        store.manage_storage('delete_all',dict(projects=self.projects))
        self.assertEqual(store.read_blob(item.current_revision_id,self.access_a),PAYLOAD)

    def test_delete_all_removes_historical_blobs_and_derivatives_but_not_urls(self):
        store=self.store()
        item,first,_=published(store,source(access=self.access_a),self.access_a)
        refreshed,second,_=published(store,item,self.access_a,payload=b'New bytes')
        url,_,_=published(store,replace(source(access=self.access_a),kind=SourceKind.URL_SNAPSHOT),self.access_a)
        key=first.revision.revision_id+'.'+'a'*64+'.cache'
        with store.files.open('cache',key,write=True) as stream:stream.write(b'cache')
        before=self.report(store)
        self.assertEqual(len(before['files']),1)
        self.assertEqual(before['files'][0]['bytes'],len(PAYLOAD)+len(b'New bytes'))
        self.assertEqual(before['webSnapshotBytes'],len(PAYLOAD))
        store.manage_storage('delete_all',dict(projects=self.projects))
        self.assertEqual(self.report(store)['files'],[])
        self.assertFalse(store.files.path('blobs',first.revision.revision_id+'.bin').exists())
        self.assertFalse(store.files.path('blobs',second.revision.revision_id+'.bin').exists())
        self.assertFalse(store.files.path('cache',key).exists())
        self.assertEqual(store.read_blob(url.current_revision_id,self.access_a),PAYLOAD)
        self.assertEqual(store._connection.execute('SELECT count(*) FROM source_revisions WHERE source_id=?',(item.source_id,)).fetchone()[0],0)

    def test_import_default_and_legacy_session_are_persistent_original_untouched(self):
        original=self.root/'original.txt';original.write_bytes(PAYLOAD)
        factory=knowledge_factory(self.state,prepare=projection)
        service=factory(self.a,'session-a',lambda kind,payload:None)
        outcome=service.import_file(context=execution(self.a,access=self.access_a),selected_path=str(original),
            acquisition=service.acquisition,prepare=projection,scope_kind=KnowledgeScopeKind.SESSION)
        self.assertEqual(outcome.source.scope.kind,KnowledgeScopeKind.WORKSPACE)
        service.close()
        original.rename(self.root/'renamed.txt')
        reopened=factory(self.a,'new-session',lambda kind,payload:None)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.store.read_blob(outcome.source.current_revision_id,reopened.access),PAYLOAD)

    def test_authenticated_host_gate_and_catalog_refresh(self):
        class Provider:
            def chat_stream(self,*args,**kwargs):return iter([{'message':{'role':'assistant','content':'test'},'done':True}])
        audit=JsonlSecurityAudit(self.root/'audit',workspace=self.a)
        self.addCleanup(audit.close)
        app=AgentSessionCoordinator(provider=Provider(),model='local',tool_factory=lambda work:[],
            event_config=EventBufferConfig(),
            security_audit_port=audit,
            knowledge_factory=knowledge_factory(self.state,prepare=projection))
        sid=app.handle(ApplicationCommand(new_command_id(),CommandKind.START_SESSION,{'workspace':str(self.a)})).session_id
        self.addCleanup(app.close_knowledge)
        actor=app.register_knowledge_actor('desktop_host',lambda:True)
        original=self.root/'original.txt';original.write_bytes(PAYLOAD)
        receipt=app.execute_knowledge(KnowledgeCommand(new_command_id(),sid,'source_import',{'path':str(original)},app.get_snapshot(sid).state_revision),actor=actor)
        self.assertTrue(receipt['accepted'],receipt)
        self.assertTrue(app._service_operations[receipt['createdIds']['operationId']].done.wait(5))
        old=app.get_snapshot(sid).services['knowledge']['attachmentRefs'][0]
        projects=[dict(path=str(self.a),name='Case')]
        key='ab'*32
        messages=[]
        adapter=JsonlApplicationAdapter(app,sid,messages.append,host_approval_key=key)
        initial_revision=app.get_snapshot(sid).state_revision
        command=StorageCommand('report-test',sid,'report',dict(projects=projects),initial_revision).to_dict()
        adapter.handle(dict(type='storage_command',id=1,command=command))
        self.assertFalse(messages[-1]['success'])
        adapter.handle(dict(type='storage_command',id=2,command=command,hostStorageProof=approval_proof(key,command)))
        self.assertTrue(messages[-1]['success'],messages[-1])
        original_result={key:value for key,value in messages[-1].items() if key!='id'}
        completed_revision=app.get_snapshot(sid).state_revision
        self.assertGreater(completed_revision,initial_revision)
        adapter.handle(dict(type='storage_command',id='retry',command=command,hostStorageProof=approval_proof(key,command)))
        self.assertEqual({key:value for key,value in messages[-1].items() if key!='id'},original_result)
        self.assertEqual(app.get_snapshot(sid).state_revision,completed_revision)
        stale=StorageCommand('stale-report',sid,'report',dict(projects=projects),initial_revision).to_dict()
        adapter.handle(dict(type='storage_command',id='stale',command=stale,hostStorageProof=approval_proof(key,stale)))
        self.assertFalse(messages[-1]['success'])
        self.assertEqual(messages[-1]['error']['code'],'REVISION_CONFLICT')
        self.assertEqual(messages[-1]['stateRevision'],completed_revision)
        conflicting=StorageCommand('report-test',sid,'move',dict(projects=projects,ids=[old['sourceId']],projectPath=None),initial_revision).to_dict()
        adapter.handle(dict(type='storage_command',id='conflict',command=conflicting,hostStorageProof=approval_proof(key,conflicting)))
        self.assertEqual(messages[-1]['error']['code'],'IDEMPOTENCY_CONFLICT')
        self.assertEqual(messages[-1]['stateRevision'],completed_revision)
        move=StorageCommand('move-test',sid,'move',dict(projects=projects,ids=[old['sourceId']],projectPath=None)).to_dict()
        adapter.handle(dict(type='storage_command',id=3,command=move,hostStorageProof=approval_proof(key,move)))
        self.assertTrue(messages[-1]['success'],messages[-1])
        self.assertEqual(app.get_snapshot(sid).services['knowledge']['attachmentRefs'],[])
        with self.assertRaises(KnowledgeError):app._knowledge.validate([old])
        rebound=StorageCommand('rebound-test',sid,'move',dict(projects=projects,ids=[old['sourceId']],projectPath=str(self.a))).to_dict()
        adapter.handle(dict(type='storage_command',id=4,command=rebound,hostStorageProof=approval_proof(key,rebound)))
        self.assertTrue(messages[-1]['success'],messages[-1])
        store=app._knowledge.service.store
        cleanup=store._cleanup_source
        def failed(source_id):raise OSError('simulated interrupted unlink')
        store._cleanup_source=failed
        try:
            deletion=StorageCommand('delete-test',sid,'delete',dict(projects=projects,ids=[old['sourceId']])).to_dict()
            adapter.handle(dict(type='storage_command',id=5,command=deletion,hostStorageProof=approval_proof(key,deletion)))
            self.assertFalse(messages[-1]['success'])
            self.assertTrue(messages[-1]['error']['outcomeUnknown'])
            self.assertEqual(app.get_snapshot(sid).services['knowledge']['attachmentRefs'],[])
        finally:store._cleanup_source=cleanup


if __name__=='__main__':unittest.main()
