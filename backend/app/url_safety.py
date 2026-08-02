import ipaddress
from urllib.parse import urlparse, urlunparse

BLOCKED_SCHEMES = {"javascript", "data", "file", "vbscript", "blob", "about"}
ALLOWED_SCHEMES = {"http", "https"}
METADATA_HOSTS = {"169.254.169.254", "metadata.google.internal", "metadata"}


class UnsafeURLError(ValueError):
    pass


def _is_blocked_ip(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_destination(url: str) -> str:
    """Validate and normalize a destination URL. Raises UnsafeURLError."""
    if not url or not url.strip():
        raise UnsafeURLError("Destination URL is required")
    url = url.strip()
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme in BLOCKED_SCHEMES:
        raise UnsafeURLError(f"Scheme '{scheme}' is not allowed")
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError("Only http and https URLs are allowed")
    host = (parsed.hostname or "").lower()
    if not host:
        raise UnsafeURLError("URL must include a valid host")
    if host in METADATA_HOSTS or _is_blocked_ip(host):
        raise UnsafeURLError("Destination points to a blocked or private address")
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        raise UnsafeURLError("Destination points to a loopback address")
    # normalize
    normalized = urlunparse(
        (scheme, parsed.netloc, parsed.path or "/", parsed.params, parsed.query, parsed.fragment)
    )
    return normalized
