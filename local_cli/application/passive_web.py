"""K6 search coordination. Provider data is never execution authority."""
from dataclasses import replace
import json

from local_cli.core.contracts import ToolResult, ToolStatus, EffectState
from local_cli.core.passive_web import SearchOptions, WebSearchError, WebSearchState
from local_cli.core.network import NetworkError
from local_cli.core.knowledge import KnowledgeError


class WebSearchService:
    def __init__(self, provider):
        self.provider = provider

    def options(self, arguments):
        try:
            return SearchOptions(arguments.get('max_results',5))
        except KnowledgeError:
            raise WebSearchError('INVALID_TOOL_ARGUMENTS') from None

    def request_url(self, arguments):
        return self.provider.request_url(arguments.get('query'), self.options(arguments))

    def execute(self, invocation, grant, issuer, network, *, parent, validate_dispatch):
        expected = self.request_url(invocation.arguments)
        failure, fetched_results, attempted = [], [], []
        def acquire(url):
            if url != expected or attempted:
                raise WebSearchError('NETWORK_BINDING_MISMATCH')
            attempted.append(True)  # Exactly one finite S5 chain, never retries.
            fetched = []
            result = network.execute(replace(invocation,arguments={'url':url}), grant, issuer,
                parent=parent, validate_dispatch=validate_dispatch, capture=fetched.append)
            if result.status is not ToolStatus.COMPLETED or not fetched:
                failure.append(result)
                raise WebSearchError(result.metadata.get('securityErrorCode','WEB_SEARCH_UNAVAILABLE'))
            fetched_results.append(result)
            return fetched[0]
        try:
            response = self.provider.search(invocation.arguments['query'],self.options(invocation.arguments),
                invocation.context.cancellation_token,acquire)
            validate_dispatch()
            if invocation.context.cancellation_token.is_cancel_requested():
                raise WebSearchError('NETWORK_CANCELLED')
            body = dict(response.to_dict(), fetchedPage=False, trustClass='WEB_SEARCH_SNIPPET')
            text = json.dumps(body,ensure_ascii=True,separators=(',',':'))
            # Publish complete JSON rows; never cut a result/provenance halfway.
            while len(text) > network.limits.published_chars and body['results']:
                body['results'].pop();body['truncated']=True
                text = json.dumps(body,ensure_ascii=True,separators=(',',':'))
            if len(text) > network.limits.published_chars:
                raise WebSearchError('WEB_SEARCH_RESPONSE_INVALID')
            self.provider.state = WebSearchState.AVAILABLE
            return ToolResult(ToolStatus.COMPLETED,EffectState.NONE,legacy_text=text,
                metadata={**fetched_results[-1].metadata,'providerId':response.provider_id,
                    'queryFingerprint':response.query_fingerprint,'acquiredAt':response.acquired_at.isoformat(),
                    'resultCount':len(body['results']),'truncated':body['truncated'],
                    'provenance':'SEARCH_PROVIDER_SNIPPET','fetchedPage':False})
        except (WebSearchError,NetworkError) as exc:
            self.provider.state = WebSearchState.DEGRADED
            if failure:
                return failure[0]  # Preserve S5 dispatch/outcome, never retry.
            return ToolResult(ToolStatus.CANCELLED if exc.code=='NETWORK_CANCELLED' else ToolStatus.FAILED,
                EffectState.NONE,error=exc.code,legacy_text='Error: '+exc.code,
                metadata={**(fetched_results[-1].metadata if fetched_results else {}),
                    'securityErrorCode':exc.code,'retryAllowed':False,'cached':False})
