"""S6 explicit adapter; compatible base chosen in S4 and SEC12-OD-03."""
from local_cli.security import SANITIZED_ENV_VARS
from local_cli.process_config import COMPATIBLE_ENVIRONMENT_NAMES
from local_cli.core.environment import EnvironmentError, validate_variables
import os


_INJECTION = frozenset({'BASH_ENV', 'ENV', 'ZDOTDIR', 'NODE_OPTIONS', 'NODE_PATH',
    'PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP', 'LD_PRELOAD', 'LD_LIBRARY_PATH',
    'DYLD_INSERT_LIBRARIES', 'DYLD_LIBRARY_PATH', 'GIT_SSH', 'GIT_SSH_COMMAND',
    'GIT_ASKPASS', 'SSH_ASKPASS', 'GIT_EXEC_PATH', 'PSMODULEPATH', 'PERL5OPT',
    'PERL5LIB', 'RUBYOPT', 'JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS'})


def forbidden_additional_name(name):
    upper = name.upper()
    return (name.casefold().startswith(('nova_', 'ollama_', 'codex_'))
        or upper in _INJECTION or upper.startswith(('GIT_CONFIG', 'DYLD_'))
        or upper in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY'))


class EnvironmentBuilder:
    """Explicit base + private host selection; never inherit os.environ here."""
    def __init__(self, *, windows=None, allowed_names=COMPATIBLE_ENVIRONMENT_NAMES,
                 protected_value=lambda _: False):
        self.windows = os.name == 'nt' if windows is None else windows
        self.allowed_names = frozenset(allowed_names)
        self.protected_value = protected_value

    def identity(self, name):
        return name.casefold() if self.windows else name

    def build(self, source, *, additional):
        validate_variables(additional)
        allowed = {self.identity(n) for n in self.allowed_names}
        blocked = {n.casefold() for n in SANITIZED_ENV_VARS}
        result = {}
        for name, value in source.items():
            if (self.identity(name) in allowed and name.casefold() not in blocked
                    and not forbidden_additional_name(name) and not self.protected_value(value)):
                result[name] = value
        seen = set()
        for name, value in additional.items():
            identity = self.identity(name)
            if identity in seen or forbidden_additional_name(name) or self.protected_value(value):
                raise EnvironmentError('ENVIRONMENT_PASS_DENIED')
            seen.add(identity)
            for old in tuple(result):
                if self.identity(old) == identity:
                    del result[old]
            result[name] = value
        validate_variables(result)
        return result


def minimum_process_environment(source, allowed_names=COMPATIBLE_ENVIRONMENT_NAMES):
    """Compatibility entry point; additional variables never bypass S6 policy."""
    return EnvironmentBuilder(allowed_names=allowed_names).build(source, additional={})
