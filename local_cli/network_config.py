"""Host composition defaults authorized for SEC12-OD-04 on 2026-10-03.

These are HTTP-client operational bounds, not OS quotas or shell networking
restrictions. Provider/Ollama networking does not use this configuration.
"""
from local_cli.core.network import FetchLimits

DEFAULT_FETCH_LIMITS = FetchLimits(30, 2 * 1024 * 1024, 5, 50000)
