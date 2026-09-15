from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, urlunparse
import ipaddress
import re
import socket

_METADATA_HOSTS = {
    '169.254.169.254',
    'metadata.google.internal',
    '100.100.100.200',
}

_SAFE_ENV_EXAMPLES = {'.env.example', '.env.sample', '.env.template'}
_SENSITIVE_NAMES = {
    '.netrc', '.pypirc', '.npmrc',
    'credentials.json', 'credential.json', 'token.json', 'tokens.json',
    'secrets.json', 'secret.json', 'secrets.yaml', 'secrets.yml',
    'id_rsa', 'id_ed25519', 'id_ecdsa', 'id_dsa',
}
_SENSITIVE_SUFFIXES = {'.pem', '.key', '.p12', '.pfx', '.jks', '.keystore'}


def is_sensitive_path(path: str | Path) -> bool:
    p = Path(path)
    name = p.name.lower()
    parts = [x.lower() for x in p.parts]

    if name in _SAFE_ENV_EXAMPLES:
        return False
    if name == '.env' or name.startswith('.env.'):
        return True
    if name in _SENSITIVE_NAMES or p.suffix.lower() in _SENSITIVE_SUFFIXES:
        return True
    if 'credentials' in name or name.startswith('secret') or name.startswith('token.'):
        return True
    joined = '/'.join(parts)
    if joined.endswith('/.aws/credentials') or joined.endswith('/.kube/config') or joined.endswith('/.docker/config.json'):
        return True
    if '/.ssh/' in f'/{joined}/' and name not in {'known_hosts', 'known_hosts.old'}:
        return True
    return False


def redact_secrets(value: object, max_chars: int | None = None) -> str:
    text = str(value)
    patterns = [
        (re.compile(r'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----', re.I | re.S), '[REDACTED PRIVATE KEY]'),
        (re.compile(r'(?i)(authorization\s*:\s*(?:bearer|basic)\s+)[^\s,;]+'), r'\1[REDACTED]'),
        (re.compile(r"(?i)([\"'](?:password|passwd|pwd|token|api[_-]?key|secret|client[_-]?secret|access[_-]?key|cookie)[\"']\s*:\s*[\"'])[^\"']*([\"'])"), r'\1[REDACTED]\2'),
        (re.compile(r'(?i)\b(password|passwd|pwd|token|api[_-]?key|secret|client[_-]?secret|access[_-]?key|cookie)\s*([=:])\s*([^\s,;]+)'), r'\1\2[REDACTED]'),
        (re.compile(r'(?i)([?&](?:token|access_token|api_key|apikey|signature|sig|x-amz-signature)=)[^&\s]+'), r'\1[REDACTED]'),
        (re.compile(r'\bAKIA[0-9A-Z]{16}\b'), '[REDACTED AWS ACCESS KEY]'),
        (re.compile(r'\bASIA[0-9A-Z]{16}\b'), '[REDACTED AWS ACCESS KEY]'),
        (re.compile(r'\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b'), '[REDACTED JWT]'),
    ]
    for pat, repl in patterns:
        text = pat.sub(repl, text)

    # Match userinfo greedily through the final '@' before the host so passwords
    # containing '@' are fully removed instead of partially leaked.
    uri_pat = re.compile(r'(?P<scheme>\b[a-zA-Z][a-zA-Z0-9+.-]*://)(?P<username>[^:/\s@]+):(?P<password>[^/\s]+)@(?P<host>[^/\s]+)')
    text = uri_pat.sub(lambda m: f"{m.group('scheme')}{m.group('username')}:[REDACTED]@{m.group('host')}", text)

    if max_chars is not None:
        text = text[:max(0, int(max_chars))]
    return text


def _resolved_ips(hostname: str) -> set[ipaddress._BaseAddress]:
    try:
        literal = ipaddress.ip_address(hostname.strip('[]'))
        return {literal}
    except ValueError:
        pass
    addresses: set[ipaddress._BaseAddress] = set()
    for _family, _socktype, _proto, _canon, sockaddr in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM):
        raw = sockaddr[0]
        try:
            addresses.add(ipaddress.ip_address(raw))
        except ValueError:
            continue
    return addresses


def _non_public_ip(ip: ipaddress._BaseAddress) -> bool:
    return any((
        ip.is_private,
        ip.is_loopback,
        ip.is_link_local,
        ip.is_multicast,
        ip.is_reserved,
        ip.is_unspecified,
    ))


def url_network_scope(url: str, resolve: bool = True) -> tuple[str, str | None]:
    """Return ('public'|'private'|'invalid', reason). Conservative on DNS failures."""
    try:
        p = urlparse(url)
    except Exception:
        return 'invalid', 'URL could not be parsed.'
    if p.scheme not in {'http', 'https'} or not p.hostname:
        return 'invalid', 'Only http/https URLs with a hostname are allowed.'
    host = p.hostname.lower().rstrip('.')
    if p.username or p.password:
        return 'invalid', 'Credentials embedded in URLs are not allowed.'
    if host in _METADATA_HOSTS:
        return 'private', 'Cloud metadata endpoints are blocked.'
    if host == 'localhost' or host.endswith('.localhost'):
        return 'private', 'Loopback/local endpoint.'
    try:
        literal = ipaddress.ip_address(host.strip('[]'))
        return ('private', 'Non-public IP address.') if _non_public_ip(literal) else ('public', None)
    except ValueError:
        pass
    if not resolve:
        return 'public', None
    try:
        ips = _resolved_ips(host)
    except OSError:
        return 'invalid', 'Hostname could not be resolved safely.'
    if not ips:
        return 'invalid', 'Hostname resolved to no usable addresses.'
    if any(_non_public_ip(ip) for ip in ips):
        return 'private', 'Hostname resolves to a non-public address.'
    return 'public', None


def is_loopback_http_url(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in {'http', 'https'} or not p.hostname or p.username or p.password:
            return False
        host = p.hostname.lower().rstrip('.')
        if host == 'localhost' or host.endswith('.localhost'):
            return True
        return ipaddress.ip_address(host.strip('[]')).is_loopback
    except Exception:
        return False


def is_local_model_endpoint(url: str) -> bool:
    return is_loopback_http_url(url)


def safe_display_url(url: str) -> str:
    """Strip URI credentials before including a URL in logs/errors."""
    try:
        p = urlparse(url)
        if not (p.username or p.password):
            return url
        host = p.hostname or ''
        if p.port:
            host = f'{host}:{p.port}'
        return urlunparse((p.scheme, host, p.path, p.params, p.query, p.fragment))
    except Exception:
        return '[invalid URL]'
