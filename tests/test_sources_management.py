"""Sources inventory, URL ownership and original-copy export use the real store."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from local_cli.core.knowledge import KnowledgeError,SourceKind,SourceTrustClass
from local_cli.core.knowledge_store import KnowledgeAccess
from local_cli.infrastructure.knowledge_sqlite import SQLiteKnowledgeStore
from local_cli.infrastructure.knowledge_storage import workspace_identity
from tests.knowledge_inputs_v1.k1_helpers import published,source,PAYLOAD


class SourcesManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.a=self.root/'A';self.a.mkdir()
        self.b=self.root/'B';self.b.mkdir()
        self.projects=[dict(path=str(self.a),name='A'),dict(path=str(self.b),name='B')]
        self.access_a=KnowledgeAccess(workspace_identity(self.a),'test-a')
        self.access_b=KnowledgeAccess(workspace_identity(self.b),'test-b')
        self.store=SQLiteKnowledgeStore(self.root/'owned-state')
        self.addCleanup(self.store.close)
        self.store.register_storage_workspace(self.a,self.access_a.workspace_id)
        self.store.register_storage_workspace(self.b,self.access_b.workspace_id)

    def web(self):
        return published(self.store,replace(source(access=self.access_a),kind=SourceKind.URL_SNAPSHOT,
            trust_class=SourceTrustClass.PUBLIC_WEB_FETCH,origin='https://example.com/source'),self.access_a)[0]

    def run_action(self,name,**args):
        return self.store.manage_storage(name,dict(projects=self.projects,**args))

    def test_sources_include_web_copies_while_storage_keeps_its_file_only_inventory(self):
        local=published(self.store,source(access=self.access_a),self.access_a)[0]
        web=self.web()
        report=self.run_action('source_report')
        self.assertEqual({row['id'] for row in report['sources']},{local.source_id,web.source_id})
        self.assertEqual([row['id'] for row in report['files']],[local.source_id])
        row=next(row for row in report['sources'] if row['id']==web.source_id)
        self.assertEqual((row['kind'],row['url'],row['projectPath']),('url','https://example.com/source',str(self.a)))
        self.assertTrue(row['downloadable'])
        self.run_action('delete_all')
        self.assertEqual(self.store.read_storage_file(web.source_id,include_web=True),PAYLOAD)

    def test_web_rebind_and_unlink_change_project_access_and_preserve_original_bytes(self):
        web=self.web()
        with self.assertRaises(KnowledgeError):self.store.read_storage_file(web.source_id)
        self.run_action('source_move',ids=[web.source_id],projectPath=str(self.b))
        with self.assertRaises(KnowledgeError):self.store.get_source(web.source_id,self.access_a)
        self.assertEqual(self.store.get_source(web.source_id,self.access_b).current_revision_id,web.current_revision_id)
        self.assertEqual(self.store.read_storage_file(web.source_id,include_web=True),PAYLOAD)
        self.run_action('source_move',ids=[web.source_id],projectPath=None)
        with self.assertRaises(KnowledgeError):self.store.get_source(web.source_id,self.access_b)
        self.assertIsNone(self.run_action('source_report')['sources'][0]['projectPath'])

    def test_mixed_source_delete_is_atomic_and_removes_owned_web_blob(self):
        local=published(self.store,source(access=self.access_a),self.access_a)[0]
        web=self.web()
        with self.assertRaises(KnowledgeError):self.run_action('source_delete',ids=[local.source_id,str(uuid4()),web.source_id])
        self.assertEqual(len(self.run_action('source_report')['sources']),2)
        self.run_action('source_delete',ids=[local.source_id,web.source_id])
        self.assertEqual(self.run_action('source_report')['sources'],[])
        self.assertFalse(self.store.files.path('blobs',web.current_revision_id+'.bin').exists())

    def test_source_ownership_survives_reopening_the_store(self):
        web=self.web()
        self.run_action('source_move',ids=[web.source_id],projectPath=str(self.b))
        self.store.close()
        self.store=SQLiteKnowledgeStore(self.root/'owned-state');self.addCleanup(self.store.close)
        self.assertEqual(self.run_action('source_report')['sources'][0]['projectPath'],str(self.b))
        self.assertEqual(self.store.read_storage_file(web.source_id,include_web=True),PAYLOAD)

    def test_preview_uses_the_saved_copy_after_the_original_is_removed(self):
        original=self.a/'original.txt';original.write_text('Original',encoding='utf-8')
        local=published(self.store,replace(source(access=self.access_a),origin=str(original)),
            self.access_a,payload='Recuerdo de prueba.\nSegunda línea.'.encode())[0]
        original.unlink()
        preview=self.store.preview_storage_source(local.source_id)
        self.assertEqual(preview['content'],'Recuerdo de prueba.\nSegunda línea.')
        self.assertIsNone(preview['reason'])

    def test_preview_keeps_html_literal_and_handles_bom(self):
        web=published(self.store,replace(source(access=self.access_a),kind=SourceKind.URL_SNAPSHOT,
            trust_class=SourceTrustClass.PUBLIC_WEB_FETCH,origin='https://example.com/source'),
            self.access_a,payload=b'\xef\xbb\xbf<script>window.untrusted=true</script>')[0]
        self.assertEqual(self.store.preview_storage_source(web.source_id)['content'],
            '<script>window.untrusted=true</script>')

    def test_preview_refuses_binary_oversized_and_unpublished_content(self):
        from tests.knowledge_inputs_v1.k1_helpers import begin,projection
        for payload,reason in ((b'a\x00b','BINARY'),(b'a'*1_000_001,'TOO_LARGE'),(b'\xff\xfe','BINARY')):
            operation=begin(self.store,source(access=self.access_a),self.access_a)
            digest,size=self.store.stage(operation.operation_id,self.access_a,[payload],lambda:False)
            record=self.store.publish(operation.operation_id,self.access_a,projection(operation,digest,size,'safe projection'),lambda:False)
            preview=self.store.preview_storage_source(record.source_id)
            self.assertEqual(preview['reason'],reason);self.assertIsNone(preview['content'])
        operation=begin(self.store,source(access=self.access_a),self.access_a)
        self.assertEqual(self.store.preview_storage_source(operation.source_id)['reason'],'NO_CONTENT')
