"""AW3 pure effect and outcome contracts. No engine, IO or authority issuer."""
from dataclasses import dataclass
import re
from typing import Protocol

from local_cli.core.active_web import (
    BrowserActionKind as Action, BrowserEffectClass as Effect,
    BrowserOutcomeState as Outcome,
)
from local_cli.core.contracts import EffectState


READ_EFFECTS = frozenset((Effect.OBSERVE_ONLY, Effect.NAVIGATION_READ))


def high_impact_hint(label):
    """Untrusted text can only INCREASE restriction, never authorize an action.

    Conservative hints supplement host risk facts, not a universal classifier.
    Unknown targets still require exact approval, never read authority.
    """
    return bool(re.search(r'(?i)\b(?:purchase|checkout|buy|payment|transfer|trade|'
        r'comprar|compra|pagar|pago|transferir|publicar|publish|post|'
        r'password|contraseña|cvv|credit.card|delete.account|eliminar.cuenta|'
        r'accept.(?:terms|agreement)|aceptar.(?:términos|contrato)|'
        r'send.(?:message|email)|enviar.(?:mensaje|correo))\b', label))


@dataclass(frozen=True)
class BrowserRiskFacts:
    # Trusted host assessment, never an assertion supplied by a model/page.
    high_impact_possible: bool = False
    auth_session_change: bool = False

    def __post_init__(self):
        if type(self.high_impact_possible) is not bool or type(self.auth_session_change) is not bool:
            raise ValueError('INVALID_BROWSER_RISK_FACTS')


def classify_browser_effects(action: Action, facts: BrowserRiskFacts = BrowserRiskFacts()):
    if not isinstance(action, Action) or not isinstance(facts, BrowserRiskFacts):
        raise ValueError('INVALID_BROWSER_EFFECT_INPUT')
    if action in (Action.OBSERVE, Action.SCROLL, Action.WAIT, Action.CLOSE):
        effects = [Effect.OBSERVE_ONLY]
    elif action in (Action.OPEN, Action.NAVIGATE, Action.BACK, Action.FORWARD):
        effects = [Effect.NAVIGATION_READ]
    elif action in (Action.INPUT_TEXT, Action.SELECT_OPTION):
        # JS may observe input immediately, without a submit.
        effects = [Effect.DATA_DISCLOSURE, Effect.UNKNOWN_REMOTE_EFFECT]
    elif action is Action.FORM_SUBMIT:
        effects = [Effect.REMOTE_MUTATION]
    elif action is Action.UPLOAD_FILE:
        effects = [Effect.FILE_UPLOAD, Effect.DATA_DISCLOSURE, Effect.REMOTE_MUTATION]
    elif action is Action.DOWNLOAD:
        effects = [Effect.FILE_DOWNLOAD]
    elif action is Action.HUMAN_TAKEOVER:
        effects = [Effect.AUTH_SESSION_CHANGE]
    else:
        # A click/key name or accessible label is NOT proof of read-only effect.
        effects = [Effect.UNKNOWN_REMOTE_EFFECT]
    if facts.auth_session_change and Effect.AUTH_SESSION_CHANGE not in effects:
        effects.append(Effect.AUTH_SESSION_CHANGE)
    if facts.high_impact_possible:
        effects.append(Effect.HIGH_IMPACT)
    return tuple(effects)


@dataclass(frozen=True)
class BrowserDispatchReport:
    outcome: Outcome
    effect_state: EffectState
    no_effect_confirmed: bool = False

    def __post_init__(self):
        if not isinstance(self.outcome, Outcome) or not isinstance(self.effect_state, EffectState):
            raise ValueError('INVALID_BROWSER_DISPATCH_REPORT')
        if type(self.no_effect_confirmed) is not bool:
            raise ValueError('INVALID_BROWSER_DISPATCH_REPORT')
        if self.no_effect_confirmed and self.effect_state is not EffectState.NONE:
            raise ValueError('UNPROVEN_BROWSER_NO_EFFECT')
        if self.outcome in (Outcome.NOT_STARTED, Outcome.FAILED_NO_EFFECT_CONFIRMED):
            if not self.no_effect_confirmed or self.effect_state is not EffectState.NONE:
                raise ValueError('UNPROVEN_BROWSER_NO_EFFECT')
        if self.outcome in (Outcome.STARTED, Outcome.UNKNOWN) and self.effect_state is not EffectState.UNKNOWN:
            raise ValueError('INVALID_BROWSER_DISPATCH_REPORT')
        if self.outcome is Outcome.PARTIAL and self.effect_state not in (EffectState.PARTIAL, EffectState.UNKNOWN):
            raise ValueError('INVALID_BROWSER_DISPATCH_REPORT')
        if self.outcome is Outcome.SUCCEEDED_OBSERVED and self.effect_state not in (EffectState.NONE, EffectState.APPLIED):
            raise ValueError('INVALID_BROWSER_DISPATCH_REPORT')


class BrowserActionPort(Protocol):
    """Future adapter boundary; AW3 supplies only a deterministic test double.

    started() acknowledges engine receipt of the action, NOT its success.
    No retry is permitted by this interface. A disconnect can be ambiguous
    even before its acknowledgement reaches the host.
    """
    def dispatch(self, request, engine_binding, *, payload, deadline, cancellation, started) -> BrowserDispatchReport: ...
