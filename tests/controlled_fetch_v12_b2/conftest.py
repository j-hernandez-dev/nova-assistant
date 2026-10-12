"""Explicit native profile; fixtures use existing assigned GLOBAL IPv6, never a fake IP."""
import json
import os
from pathlib import Path

import pytest

from tests.controlled_fetch_v12_b2.native_harness import Environment


@pytest.fixture(scope='session')
def native_env():
    if os.environ.get('NOVA_CF_B2_NATIVE')!='1':pytest.skip('Native fixture profile opt-in; not certification evidence')
    env=Environment(os.environ['NOVA_CF_B2_PUBLIC_IPV6'],os.environ['NOVA_CF_B2_OPENSSL'])
    try:yield env
    finally:
        Path(os.environ['NOVA_CF_B2_NATIVE_OUTPUT']).write_text(json.dumps(env.rows,indent=2)+'\n',encoding='utf-8')
        env.close()
