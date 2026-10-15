"""Small public Browser results. Recovery hints are data, never permissions."""
from local_cli.core.contracts import EffectState, ToolStatus

UNAVAILABLE = frozenset({'HOST_NOT_FOUND', 'RUNTIME_NOT_FOUND', 'PLAYWRIGHT_NOT_AVAILABLE',
    'UNSUPPORTED_PLATFORM', 'BROWSER_NOT_INSTALLED', 'BROWSER_START_FAILED',
    'PLAYWRIGHT_DRIVER_INCOMPATIBLE', 'PLAYWRIGHT_PACKAGE_CONFLICT'})
PROGRESS = {
    'web_search': 'Searching the web…', 'browser_navigate': 'Opening page…',
    'browser_observe': 'Reading page…', 'browser_click': 'Interacting with page…',
    'browser_type': 'Entering text…', 'browser_press_key': 'Interacting with page…',
    'browser_back': 'Going back…', 'browser_forward': 'Going forward…',
    'browser_reload': 'Reloading page…', 'browser_close': 'Closing browser…',
    'browser_request_takeover': 'Opening browser for human control…',
    'browser_upload': 'Preparing file attachment…', 'browser_download': 'Preparing download…',
}


def failure(code, message, status, effect):
    unknown = status is ToolStatus.OUTCOME_UNKNOWN or effect is EffectState.UNKNOWN
    next_actions = []
    if code == 'SEARCH_HUMAN_REQUIRED':
        hint = 'Use browser_request_takeover for human verification, or let the human choose another engine with /search engine. No search results were accepted.'
        next_actions = ['browser_request_takeover']
    elif code.startswith('SEARCH_'):
        hint = 'You can read another requested page or let the human choose another engine with /search engine. No source was read by this failed search.'
        next_actions = ['browser_navigate']
    elif code == 'BROWSER_CLEANUP_UNCONFIRMED':
        hint = 'The previous browser resources are not confirmed closed. No new browser was started. Other tools remain available.'
    elif unknown and code in ('BROWSER_TIMEOUT', 'BROWSER_CANCELLED'):
        hint = 'The operation may have started. Do not repeat it automatically. Close the browser before a new session; other tools remain available.'
        next_actions = ['browser_close']
    elif unknown:
        hint = 'The outcome is unconfirmed. Do not repeat the action automatically. Read the current state or ask the human before another mutation.'
        next_actions = ['browser_observe']
    elif code in ('BROWSER_REF_STALE', 'BROWSER_BINDING_CHANGED', 'BROWSER_PAGE_MISMATCH', 'APPROVAL_STALE'):
        hint = 'Observe the current page and use its new refs. Approval is still required where applicable.'
        next_actions = ['browser_observe']
    elif code in ('BROWSER_PAGE_CLOSED', 'BROWSER_CONNECTION_LOST', 'BROWSER_OBSERVATION_UNAVAILABLE'):
        hint = 'Open the requested URL in a new browser session, or close the browser. Do not reuse old refs.'
        next_actions = ['browser_navigate', 'browser_close']
    elif code in ('BROWSER_HUMAN_ACTIVE', 'SECRET_BOUNDARY_UNCONFIRMED'):
        hint = 'Wait for human control. Use /browser resume when safe, or /browser close.'
    elif code == 'BROWSER_MUTATION_UNCERTAIN':
        hint = 'Do not retry the mutation. A new human turn and fresh observation are required.'
        next_actions = ['browser_observe']
    elif code in UNAVAILABLE:
        hint = 'Check /browser status or explicitly choose an installed browser with /browser use. No browser was installed or selected automatically.'
    elif code == 'BROWSER_UNRESPONSIVE':
        hint = 'Close the browser before starting a new browser session. Other tools remain available.'
        next_actions = ['browser_close']
    elif status is ToolStatus.CANCELLED:
        hint = 'The operation was cancelled. Do not claim it completed.'
    elif status is ToolStatus.DENIED:
        hint = 'Explain the denial. A different tool or wording does not approve this action.'
    else:
        hint = 'Check the arguments or explain the failure. Do not claim the action succeeded.'
    state = ('unknown' if unknown else 'unavailable' if code in UNAVAILABLE else
             'cancelled' if status is ToolStatus.CANCELLED else 'denied' if status is ToolStatus.DENIED else 'failed')
    return {'status': state, 'code': code, 'message': message, 'effect': effect.value,
            'recovery': hint, 'allowedNextTools': next_actions, 'retrySameAction': False}


def status_lines(state):
    """English CLI projection of the same shared snapshot, without raw JSON."""
    selected = state.get('selected', 'webview2')
    ready = state.get('available', False)
    lines = [f"Browser: {selected} ({'available' if ready else 'unavailable'})",
             'Control: ' + state.get('controlState', 'agentActive'),
             'Page: ' + ('open' if state.get('hasPage') else 'not open')]
    if not ready:
        lines.append('Select an installed browser with /browser use webview2|chrome|edge.')
    if state.get('controlState') in ('humanActive', 'resumePending', 'blocked'):
        lines.append('Agent control is paused. Use /browser resume or /browser close.')
    elif state.get('sessionState') == 'unresponsive':
        lines.append('The browser did not respond. Close it before opening a new session.')
    elif state.get('sessionState') == 'lost':
        lines.append('The page or connection was lost. Open a requested URL again or close the browser.')
    elif state.get('sessionState') == 'cleanupUnconfirmed':
        lines.append('Previous browser cleanup remains unconfirmed. A new session has not been started.')
    if state.get('runtimeCheckedOnUse') and not state.get('hasPage'):
        lines.append('Runtime availability is checked when the browser starts.')
    return lines
