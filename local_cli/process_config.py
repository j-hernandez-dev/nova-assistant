"""Host composition defaults approved for SECURITY V1.2 S4 on 2026-10-03.

SEC12-OD-02 Equilibrado; SEC12-OD-03 S4 Compatible minimo. Operational
admission/capture limits, never preventive OS quotas or process isolation.
No project-variable pass/UX or full S6 secret model is defined here.
"""
from local_cli.core.process import ProcessLimits

DEFAULT_PROCESS_LIMITS = ProcessLimits(
    stdout_bytes=100 * 1024, stderr_bytes=100 * 1024, published_bytes=100 * 1024,
    default_timeout=120, max_timeout=600, cleanup_seconds=5, max_concurrent=2)

COMPATIBLE_ENVIRONMENT_NAMES = frozenset({
    'PATH', 'SystemRoot', 'WINDIR', 'COMSPEC', 'PATHEXT', 'SystemDrive',
    'TEMP', 'TMP', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'APPDATA',
    'LOCALAPPDATA', 'LANG', 'LANGUAGE', 'LC_ALL', 'LC_CTYPE', 'TERM', 'NO_COLOR',
})
