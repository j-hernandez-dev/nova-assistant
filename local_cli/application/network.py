"""S5 URL/destination decisions and finite, audited fetch-chain coordination."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import ipaddress
import re
from urllib.parse import urljoin, urlsplit

from local_cli.core.contracts import EffectState, ToolResult, ToolStatus
from local_cli.core.network import FetchBudget, FetchLimits, HttpFetchPort, NetworkError, FetchedSnapshot
from local_cli.core.security import Capability, ControlClass, Permission, ResourceScope, ScopeKind, SecurityError


def canonical_url(raw):
    try:
        # Core's URL schema denies credentials, fragments, ambiguous host syntax,
        # CR/LF and non-HTTP(S). No alternate numeric host spellings are admitted.
        result = ResourceScope(ScopeKind.URL, raw).resource
        host = urlsplit(result).hostname
        if re.fullmatch(r'[0-9.]+', host) or re.match(r'(?i)^0x', host):
            ipaddress.ip_address(host)
        return result
    except (SecurityError, ValueError, TypeError):
        raise NetworkError('NETWORK_URL_DENIED') from None


def public_address(address):
    try:
        ip = ipaddress.ip_address(address)
        if '%' in address:
            return False
        if isinstance(ip, ipaddress.IPv6Address):
            # Mapped IPs inherit IPv4 checks; transition mechanisms can embed
            # private IPv4 and are not silently treated as public destinations.
            if ip.ipv4_mapped:
                ip = ip.ipv4_mapped
            elif ip.sixtofour or ip.teredo:
                return False
            elif ip in ipaddress.ip_network('64:ff9b::/96'):
                return False  # well-known NAT64 may translate into a private IPv4
        return bool(ip.is_global and not (ip.is_multicast or ip.is_reserved
                    or ip.is_loopback or ip.is_link_local or ip.is_unspecified))
    except ValueError:
        return False


def audit_url(url):
    """No query values, credentials or fragments in the minimal S5 audit."""
    p = urlsplit(url)
    return p.scheme + '://' + p.netloc + p.path


class NetworkFetchService:
    """Application controls each hop; Infrastructure receives one pinned GET.

    The one-shot grant binds the initial URL and this finite redirect policy.
    It is not a wildcard URL grant: every hop additionally must fit the current
    host ceiling and the original parent's scope. No attenuation rule changes.
    """
    policy_name = 'PUBLIC_ONLY'

    def __init__(self, broker: HttpFetchPort, limits: FetchLimits):
        self.broker, self.limits = broker, limits
        from local_cli.application.secrets import SecretRedactor
        self.redactor = SecretRedactor()

    def binding(self, url):
        return {'requestedUrl': canonical_url(url), 'controlClass': 'BROKER_ENFORCED',
                'destinationPolicy': self.policy_name, 'redirectMediation': 'checked_each_hop',
                'redirectPolicy': 'public_http_https_no_downgrade', 'limits': asdict(self.limits)}

    def _admit(self, endpoints):
        # Reject mixed public/private answers as well, not merely the chosen IP.
        if not endpoints or len(endpoints) > 64 or not all(public_address(e.address) for e in endpoints):
            raise NetworkError('NETWORK_DESTINATION_DENIED')

    def execute(self, invocation, grant, issuer, *, parent, validate_dispatch, capture=None):
        url = canonical_url(invocation.arguments['url'])
        if dict(grant.request.network_intent) != self.binding(url):
            raise NetworkError('NETWORK_BINDING_MISMATCH')
        budget = FetchBudget(self.limits, invocation.context.cancellation_token,
                             invocation.context.deadline)
        records, dispatched, effective, contacted = [], False, url, None
        try:
            for index in range(self.limits.redirects + 1):
                budget.check()
                validate_dispatch()
                cap = Capability(Permission('network.fetch'), ResourceScope(ScopeKind.URL, effective),
                                 ControlClass.BROKER_ENFORCED)
                if not issuer.ceiling.covers(cap) or (parent is not None and not any(
                        p.covers(cap) for p in parent.request.capabilities)):
                    raise NetworkError('NETWORK_REDIRECT_AUTHORITY_DENIED')
                p = urlsplit(effective)
                # Reject literal destinations before even performing DNS.
                try:
                    literal = ipaddress.ip_address(p.hostname)
                except ValueError:
                    literal = None
                if literal is not None and not public_address(str(literal)):
                    raise NetworkError('NETWORK_DESTINATION_DENIED')
                endpoints = self.broker.resolve(p.hostname, p.port or (443 if p.scheme == 'https' else 80), budget)
                self._admit(endpoints)
                endpoint = endpoints[0]
                record = {'kind': 'http_hop', 'index': index, 'url': audit_url(effective),
                          'address': endpoint.address, 'port': endpoint.port, 'controlClass': 'BROKER_ENFORCED'}
                records.append(record)
                hop = self.broker.get(effective, endpoint, budget=budget, body_bytes=self.limits.body_bytes,
                                      validate_dispatch=validate_dispatch)
                dispatched = True
                contacted = effective
                record['status'] = hop.status
                if hop.status in (301, 302, 303, 307, 308):
                    if not hop.location:
                        raise NetworkError('NETWORK_REDIRECT_INVALID')
                    if index == self.limits.redirects:
                        raise NetworkError('NETWORK_REDIRECT_LIMIT')
                    target = canonical_url(urljoin(effective, hop.location))
                    if p.scheme == 'https' and urlsplit(target).scheme != 'https':
                        raise NetworkError('NETWORK_REDIRECT_DOWNGRADE_DENIED')
                    effective = target
                    continue
                if not 200 <= hop.status < 300:
                    raise NetworkError('NETWORK_HTTP_ERROR')
                text, truncated = self._text(hop, invocation.arguments.get('max_length', self.limits.published_chars))
                budget.check()
                if capture is not None:
                    # Only the trusted per-call Application seam receives raw
                    # bytes. No second fetch, ambient handler or ToolResult field.
                    validate_dispatch()
                    budget.check()
                    capture(FetchedSnapshot(url, effective, datetime.now(timezone.utc),
                        hop.content_type, hop.body, hop.truncated, hop.safe_headers))
                return ToolResult(ToolStatus.COMPLETED, EffectState.NONE, legacy_text=text,
                    metadata=self._metadata(url, contacted, records, truncated))
            raise NetworkError('NETWORK_REDIRECT_LIMIT')
        except NetworkError as exc:
            unknown = dispatched or exc.dispatched
            if exc.dispatched:
                contacted = effective
            records.append({'kind': 'fetch_denied_or_failed', 'attemptedUrl': audit_url(effective),
                            'errorCode': exc.code, 'httpDispatched': unknown})
            status = (ToolStatus.OUTCOME_UNKNOWN if unknown else ToolStatus.CANCELLED
                      if exc.code in ('NETWORK_CANCELLED', 'NETWORK_TIMEOUT') else ToolStatus.DENIED
                      if exc.code.endswith('DENIED') or exc.code.endswith('MISMATCH') else ToolStatus.FAILED)
            return ToolResult(status, EffectState.UNKNOWN if unknown else EffectState.NONE,
                error=exc.code, legacy_text='Error: ' + exc.code,
                metadata={**self._metadata(url, contacted, records, False), 'securityErrorCode': exc.code,
                          'httpDispatched': unknown, 'retryAllowed': False})

    @staticmethod
    def _metadata(url, effective, records, truncated):
        return {'requestedUrl': audit_url(url), 'effectiveUrl': audit_url(effective) if effective else None,
                'networkAudit': records, 'networkControlClass': 'BROKER_ENFORCED',
                'truncated': truncated, 'cached': False}

    def _text(self, hop, max_length):
        encoding = 'utf-8'
        if 'charset=' in hop.content_type.lower():
            encoding = hop.content_type.lower().split('charset=', 1)[1].split(';', 1)[0].strip().strip('"')
        try:
            text = hop.body.decode(encoding, errors='replace')
        except (LookupError, UnicodeError):
            text = hop.body.decode('utf-8', errors='replace')
        # Linear scan: malformed megabytes of '<' must not trigger quadratic
        # regex backtracking outside the HTTP budget.
        parts, start = [], 0
        while (opening := text.find('<', start)) != -1:
            closing = text.find('>', opening + 1)
            if closing == -1:
                break
            parts.append(text[start:opening])
            start = closing + 1
        parts.append(text[start:])
        text = ''.join(parts)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        text = self.redactor.text(text, partial=hop.truncated)
        limit = max(1, min(max_length, self.limits.published_chars))
        truncated = hop.truncated or len(text) > limit
        if truncated:
            suffix = '\n... [content truncated]'[:limit]
            text = text[:max(0, limit-len(suffix))] + suffix
        return text, truncated
