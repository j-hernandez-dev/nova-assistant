"""AW4 PUBLIC_ONLY admission. Reuses S5; does not alter passive web or grants."""
from urllib.parse import urlsplit
import ipaddress
import socket

from local_cli.application.network import canonical_url, public_address
from local_cli.core.active_web_network import BrowserConnectionPlan, BrowserEgressError
from local_cli.core.network import NetworkError


class BrowserNetworkPolicy:
    policy_id = 'ACTIVE_WEB_PUBLIC_ONLY_V1'

    def __init__(self, resolver, *, validate_session,
                 http_ports=(80,), connect_ports=(443,), allowed_hosts=None):
        if not callable(validate_session):
            raise BrowserEgressError('BROWSER_EGRESS_SESSION_REQUIRED')
        self.resolver, self._validate_session = resolver, validate_session
        # Optional trusted host reduction (e.g. a probe's numeric canaries).
        # Checked before DNS. None preserves normal PUBLIC_ONLY unchanged;
        # this can only reduce admission, never admit a private address.
        if allowed_hosts is not None and (not isinstance(allowed_hosts,tuple) or
                len(allowed_hosts)>64 or
                any(not isinstance(h,str) or not h or h!=h.lower() for h in allowed_hosts) or
                len(set(allowed_hosts))!=len(allowed_hosts)):
            raise BrowserEgressError('BROWSER_EGRESS_SCOPE_INVALID')
        self.allowed_hosts=allowed_hosts
        for ports in (http_ports, connect_ports):
            if (not isinstance(ports, tuple) or not ports or len(ports) > 16
                    or len(set(ports)) != len(ports)
                    or any(type(p) is not int or not 1 <= p <= 65535 for p in ports)):
                raise BrowserEgressError('BROWSER_EGRESS_PORT_POLICY_INVALID')
        self.http_ports, self.connect_ports = http_ports, connect_ports

    def validate_current(self):
        try:
            # Trusted Application checks owner/lifetime/cancel/grant context.
            # An explicit successful proof is required, not a truthy page value.
            if self._validate_session() is not True:
                raise BrowserEgressError('BROWSER_EGRESS_SESSION_DENIED')
        except BrowserEgressError:
            raise
        except Exception:
            raise BrowserEgressError('BROWSER_EGRESS_SESSION_DENIED') from None

    def authorize(self, method, target, host_header, budget):
        self.validate_current(); budget.check()
        try:
            if method == 'CONNECT':
                # CONNECT authority form only; explicit port, no path/query.
                u = urlsplit('https://' + target)
                if (u.port is None or u.path or u.query or u.fragment or u.netloc != target
                        or u.port not in self.connect_ports):
                    raise BrowserEgressError('BROWSER_EGRESS_PROTOCOL_DENIED')
                url = canonical_url('https://' + target + '/')
            else:
                url = canonical_url(target)
                if method not in ('GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'):
                    raise BrowserEgressError('BROWSER_EGRESS_METHOD_DENIED')
                if urlsplit(url).scheme != 'http':
                    raise BrowserEgressError('BROWSER_EGRESS_PROTOCOL_DENIED')
            u = urlsplit(url)
            port = u.port or (443 if method == 'CONNECT' else 80)
            if port not in (self.connect_ports if method == 'CONNECT' else self.http_ports):
                raise BrowserEgressError('BROWSER_EGRESS_PORT_DENIED')
            # No authority confusion between absolute target and Host header.
            if any(c in host_header for c in '/?#@\\'):
                raise BrowserEgressError('BROWSER_EGRESS_HOST_MISMATCH')
            supplied = urlsplit(canonical_url(u.scheme + '://' + host_header + '/'))
            raw_host = urlsplit(u.scheme + '://' + host_header)
            if raw_host.path or raw_host.query or raw_host.fragment:
                raise BrowserEgressError('BROWSER_EGRESS_HOST_MISMATCH')
            if (supplied.hostname, supplied.port or (443 if method == 'CONNECT' else 80)) != (u.hostname, port):
                raise BrowserEgressError('BROWSER_EGRESS_HOST_MISMATCH')
            if self.allowed_hosts is not None and u.hostname not in self.allowed_hosts:
                raise BrowserEgressError('BROWSER_EGRESS_SCOPE_DENIED')
            try:
                literal = ipaddress.ip_address(u.hostname)
            except ValueError:
                literal = None
            if literal is not None and not public_address(str(literal)):
                raise BrowserEgressError('BROWSER_EGRESS_DESTINATION_DENIED')
            endpoints = self.resolver.resolve(u.hostname, port, budget)
            if not endpoints or len(endpoints) > 64:
                raise BrowserEgressError('BROWSER_EGRESS_DNS_DENIED')
            # All answers, not just a conveniently public first answer.
            for endpoint in endpoints:
                ip = ipaddress.ip_address(endpoint.address)
                if (not public_address(endpoint.address) or endpoint.port != port
                        or endpoint.family != (socket.AF_INET6 if ip.version == 6 else socket.AF_INET)):
                    raise BrowserEgressError('BROWSER_EGRESS_DESTINATION_DENIED')
            self.validate_current(); budget.check()
            origin = u.scheme + '://' + u.netloc
            return BrowserConnectionPlan(method, url, origin, u.hostname, port, endpoints[0])
        except BrowserEgressError:
            raise
        except NetworkError as exc:
            raise BrowserEgressError(exc.code, dispatched=exc.dispatched) from None
        except (ValueError, TypeError, AttributeError):
            raise BrowserEgressError('BROWSER_EGRESS_PROTOCOL_DENIED') from None
