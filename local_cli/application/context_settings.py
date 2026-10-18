"""Public numeric projection and shared limit validation for host settings."""
from local_cli.core.context import ContextSelection, ContextError, PRESET_LABELS


def resolve_context(requested, policy, runtime):
    return ContextSelection(requested, runtime.provider_revision).resolve(
        model_limit=runtime.model_context_window,
        provider_limit=runtime.provider_context_window,
        resource_limit=policy.resource_limit)


def context_settings(requested, policy, runtime):
    if isinstance(requested, str):
        requested = 0 if requested.upper() == 'AUTO' else PRESET_LABELS.get(requested.upper(), requested)
    try:
        selected, _, _ = resolve_context(requested, policy, runtime)
        error = None
    except ContextError as exc:
        selected, error = None, exc.code
    return {'requestedTokens': 0 if requested == 'AUTO' else requested,
            'selectedTokens': selected, 'errorCode': error}
