"""S6 logical environment.read/pass policy and exact host-only selection."""
from dataclasses import replace

from local_cli.core.environment import EnvironmentError, EnvironmentSelection, EnvironmentBuilderPort
from local_cli.core.security import Capability, ControlClass, Permission, ResourceScope, ScopeKind, PathStyle
from local_cli.application.policy import ToolPolicyAction, ToolPolicyDecision


class EnvironmentService:
    def __init__(self, builder: EnvironmentBuilderPort, redactor, *, source=None):
        self.builder, self.redactor = builder, redactor
        self.source = dict(source or {})  # private host configuration, no ambient read at execution
        self.redactor.observe_environment(self.source)

    def select(self, selection):
        if not isinstance(selection, EnvironmentSelection):
            raise EnvironmentError('INVALID_ENVIRONMENT_SELECTION')
        values = dict(selection.values)
        for name in selection.read_names:
            candidates = [key for key in self.source if self.builder.identity(key) == self.builder.identity(name)]
            if len(candidates) != 1 or any(self.builder.identity(key) == self.builder.identity(name) for key in values):
                raise EnvironmentError('ENVIRONMENT_READ_DENIED')
            values[name] = self.source[candidates[0]]
        # Validate before registering values (otherwise a forbidden value could
        # corrupt public messages). Provider/internal aliases are also rejected.
        self.builder.build({}, additional=values)
        for value in values.values():
            self.redactor.register(value)
        return EnvironmentSelection(values, selection.read_names)

    def capabilities(self, selection):
        style = PathStyle.WINDOWS if self.builder.windows else PathStyle.POSIX
        return tuple(Capability(Permission(permission), ResourceScope(
            ScopeKind.ENVIRONMENT_VARIABLE, name, style), ControlClass.APPLICATION_ENFORCED)
            for permission, names in [('environment.pass', selection.values),
                                     ('environment.read', selection.read_names)] for name in names)

    def build(self, source, selection):
        return self.builder.build(source, additional=selection.values if selection else {})

    def evaluate(self, selection, ceiling, parent, revision):
        caps = self.capabilities(selection)
        if not all(ceiling.covers(c) for c in caps) or (parent is not None and not all(
                any(p.covers(c) for p in parent.request.capabilities) for c in caps)):
            raise EnvironmentError('ENVIRONMENT_AUTHORITY_EXCEEDED')
        return ToolPolicyDecision(ToolPolicyAction.REQUIRE_APPROVAL,
                                  'ENVIRONMENT_PASS_APPROVAL_REQUIRED', revision)

    @staticmethod
    def presentation(selection):
        return {'names': sorted(selection.values), 'readNames': list(selection.read_names),
                'values': {name: '[REDACTED]' for name in selection.values},
                'risk': 'HOST_UNISOLATED: root and OS children may inherit selected variables; '
                        'Nova does not reuse this pass in later operations or subagents.'}
