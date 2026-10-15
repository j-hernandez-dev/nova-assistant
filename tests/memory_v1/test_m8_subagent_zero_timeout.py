"""Deterministic Core timeout edge, independent of monotonic tick resolution."""
from unittest.mock import patch

import pytest

from local_cli.sub_agent import SubAgent,_SubAgentTimeout
from tests.test_sub_agent import _make_mock_provider,_setup_provider_simple_response


@pytest.mark.parametrize('response',['fast','empty'])
def test_zero_timeout_on_nonadvancing_clock_starts_no_inference(response):
    provider=_make_mock_provider()
    if response=='fast':_setup_provider_simple_response(provider)
    else:provider.chat_stream.return_value=iter(())
    agent=SubAgent(provider=provider,model='synthetic-local-model',tools=[],prompt='Synthetic task',timeout=0.)
    with patch('local_cli.sub_agent.time.monotonic',return_value=123.):result=agent.run()
    assert result.status=='timeout' and result.content=='' and 'timed out' in result.error_message
    provider.chat_stream.assert_not_called()


def test_positive_timeout_equal_deadline_is_expired_not_success():
    agent=SubAgent(provider=_make_mock_provider(),model='synthetic',tools=[],prompt='Synthetic',timeout=1.)
    with patch('local_cli.sub_agent.time.monotonic',return_value=124.):
        with pytest.raises(_SubAgentTimeout):agent._check_timeout(123.)


def test_positive_timeout_before_deadline_and_cancel_precedence_preserved():
    agent=SubAgent(provider=_make_mock_provider(),model='synthetic',tools=[],prompt='Synthetic',timeout=1.)
    with patch('local_cli.sub_agent.time.monotonic',return_value=123.5):agent._check_timeout(123.)
    agent.request_cancel()
    with patch('local_cli.sub_agent.time.monotonic',return_value=125.):result=agent.run()
    assert result.status=='cancelled'
