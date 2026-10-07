"""M8 regression: optional child proposal hint must not displace delegated4K data."""
from copy import deepcopy
from datetime import datetime,timezone
from local_cli.application.context import bind_context
from local_cli.application.providers import ProviderManager
from local_cli.application.memory_recall import TurnMemorySnapshot,MemoryCapsule
from local_cli.application.secrets import SecretRedactor
from local_cli.core.context import ContextPolicy
from local_cli.sub_agent import SubAgent
from tests.memory_v1.m1_fixtures import record
from tests.memory_v1.test_m4_application import CapturingProvider


def test_actual_child_system_unmodified_optional_hint_and_memory_fit_4k(tmp_path):
    p=CapturingProvider();m=ProviderManager(p,'old',clone_factory=lambda _:lambda:p)
    m.redactor=SecretRedactor(source={})
    bound=bind_context(m.snapshot(),workspace=tmp_path,requested=4096,policy=ContextPolicy(resource_limit=4096))
    task='Use only delegated memory to find the synthetic interface accent preference. Respond with just the value or UNKNOWN.'
    child=SubAgent(bound,'old',[],task,cwd=tmp_path,environment={},redactor=m.redactor)
    r=record(canonical_text='The synthetic interface accent preference is COBALT_UI.')
    snapshot=TurnMemorySnapshot(records=(r,),capsule=MemoryCapsule.render((r,),m.redactor))
    child.bind_memory_delegate(lambda:snapshot)
    result=child.run()
    assert result.status=='success'
    prompt=p.captured[0]
    assert any(x['role']=='user' and 'MEMORY CONTEXT' in x['content'] and 'COBALT_UI' in x['content'] for x in prompt)
    assert not any(x['role']=='system' and 'Optional: propose a memory' in x['content'] for x in prompt)
    assert {'role':'user','content':task} in prompt
    assert not any('_context_kind' in x for x in prompt)
