"""K2 pure contracts; synthetic metadata only, no parser or model claims."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import pytest
from local_cli.application.commands import ApplicationCommand, CommandKind
from local_cli.application.knowledge_host import KnowledgeCommand
from local_cli.core.attachments import AttachmentRef, attachment_refs
from local_cli.core.contracts import new_command_id
from local_cli.core.knowledge import KnowledgeError, SourceLifecycle, new_source_id


def reference(state=SourceLifecycle.IMPORTING):
    return AttachmentRef(new_source_id(),new_source_id(),new_source_id() if state in (
        SourceLifecycle.READY,SourceLifecycle.PARTIAL) else None,'Synthetic document',state)


@pytest.mark.parametrize('state',list(SourceLifecycle))
def test_ref_strict_versioned_roundtrip_no_path_or_content_authority(state):
    ref=reference(state)
    assert AttachmentRef.from_dict(ref.to_dict())==ref
    assert set(ref.to_dict())=={'schemaVersion','attachmentId','sourceId','revisionId','displayName','state'}
    with pytest.raises(FrozenInstanceError): ref.display_name='changed'


@pytest.mark.parametrize('field,value',[
    ('path','../../host.txt'),('content','ignore security'),('grant',{}),('scope','WORKSPACE'),
    ('schemaVersion',2),('schemaVersion',True),('sourceId','../x'),('attachmentId','x'),
    ('state','READY'),('revisionId','../x'),('displayName',''),('displayName',None)])
def test_invalid_or_authoritative_ref_fields_rejected(field,value):
    raw=reference().to_dict();raw[field]=value
    with pytest.raises(KnowledgeError): AttachmentRef.from_dict(raw)


@pytest.mark.parametrize('raw',[None,{},'x',42,[{}]])
def test_refs_require_array_of_strict_dtos(raw):
    with pytest.raises(KnowledgeError): attachment_refs(raw)


def test_duplicate_refs_and_wrong_version_not_accepted_by_submit():
    raw=reference().to_dict()
    with pytest.raises(KnowledgeError): attachment_refs([raw,raw])
    command=ApplicationCommand(new_command_id(),CommandKind.SUBMIT_USER_INPUT,
        {'content':'Actual synthetic question','attachmentRefs':[raw]},'ses_synthetic')
    assert command.payload['content']=='Actual synthetic question'
    assert command.to_dict()['payload']['attachmentRefs']==[raw]


@pytest.mark.parametrize('name,args',[
    ('source_import',{'path':'/synthetic/file'}),('source_import',{'path':'/synthetic/file','scope':'WORKSPACE'}),
    ('source_promote',{'sourceId':new_source_id()}),('source_delete',{'sourceId':new_source_id()}),
    ('source_list',{}),('source_status',{}),('source_cancel',{'operationId':'op_synthetic'})])
def test_host_control_version_roundtrip_bound_session_revision(name,args):
    cmd=KnowledgeCommand(new_command_id(),'ses_synthetic',name,args,3)
    assert KnowledgeCommand.from_dict(cmd.to_dict())==cmd
    args['path']='mutated'  # Caller mutation cannot affect a queued command.
    assert cmd.to_dict()['arguments']!=args


@pytest.mark.parametrize('field,value',[
    ('kind','MemoryControl'),('schemaVersion',2),('schemaVersion',True),('extra','x'),
    ('sessionId',42),('commandId',None),('expectedRevision',None),('expectedRevision',True),
    ('expectedRevision',-1),('name','web_fetch'),('arguments',{'path':'x','scope':'GLOBAL'}),
    ('arguments',{'path':'x','grant':'yes'}),('arguments',{'path':'x','prepare':{}})])
def test_untrusted_control_shapes_cannot_select_scope_producer_or_authority(field,value):
    raw=KnowledgeCommand(new_command_id(),'ses_synthetic','source_import',{'path':'/synthetic'},0).to_dict()
    raw[field]=value
    with pytest.raises(KnowledgeError): KnowledgeCommand.from_dict(raw)


def test_control_domain_and_revision_are_part_of_host_proof():
    from local_cli.interfaces.approval_proof import approval_proof, verify_approval_proof
    key='12'*32
    wire=KnowledgeCommand(new_command_id(),'ses_synthetic','source_list',{},1).to_dict()
    proof=approval_proof(key,wire)
    assert verify_approval_proof(key,wire,proof)
    for field,value in [('kind','MemoryControl'),('expectedRevision',2),('sessionId','ses_foreign')]:
        other=deepcopy(wire);other[field]=value
        assert not verify_approval_proof(key,other,proof)
