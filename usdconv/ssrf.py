"""SSRF-safe outbound HTTP. All user-supplied URLs MUST go through safe_get()."""
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

BLOCKED = [ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "169.254.0.0/16",
    "100.64.0.0/10", "0.0.0.0/8", "192.0.0.0/24", "198.18.0.0/15", "224.0.0.0/4", "240.0.0.0/4",
    "::/128", "::1/128", "fc00::/7", "fe80::/10", "ff00::/8")]


class UnsafeURL(ValueError):
    pass


def _blocked(ip) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return any(ip in n for n in BLOCKED)


def resolve_safe(url: str, allow_private: bool = False, ports=(80, 443)):
    """Validate URL, resolve host, return (ip, port, parsed). Raises UnsafeURL."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise UnsafeURL("invalid URL")
    if u.username or u.password:
        raise UnsafeURL("credentials in URL not allowed")
    port = u.port or (443 if u.scheme == "https" else 80)
    if not allow_private and port not in ports:
        raise UnsafeURL("port not allowed")
    try:
        infos = socket.getaddrinfo(u.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise UnsafeURL(f"cannot resolve host: {e}") from e
    ips = sorted({ipaddress.ip_address(i[4][0]) for i in infos}, key=str)
    if not ips:
        raise UnsafeURL("no address")
    if not allow_private and any(_blocked(ip) for ip in ips):
        raise UnsafeURL("address is in a private/internal range")
    return ips[0], port, u


def safe_get(url: str, *, timeout: float = 30, max_bytes: int = 50 * 1024 * 1024,
             max_redirects: int = 3, allow_private: bool = False, params: dict | None = None) -> bytes:
    """GET with DNS pinning, manual redirect re-validation, size and time limits."""
    if params:
        sep = "&" if urlparse(url).query else "?"
        url = url + sep + httpx.QueryParams(params).__str__()
    for _ in range(max_redirects + 1):
        ip, port, u = resolve_safe(url, allow_private)
        host_ip = f"[{ip}]" if ip.version == 6 else str(ip)
        netloc = f"{host_ip}:{port}"
        pinned = u._replace(netloc=netloc).geturl()
        headers = {"Host": u.netloc.rsplit("@", 1)[-1], "User-Agent": "usd-converter/0.1",
                   "Accept": "application/json, */*"}
        ext = {"sni_hostname": u.hostname} if u.scheme == "https" else {}
        with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as c:
            with c.stream("GET", pinned, headers=headers, extensions=ext) as r:
                if r.status_code in (301, 302, 303, 307, 308):
                    loc = r.headers.get("location")
                    if not loc:
                        raise UnsafeURL("redirect without location")
                    url = urljoin(url, loc)
                    continue
                if r.status_code >= 400:
                    raise UnsafeURL(f"remote server returned HTTP {r.status_code}")
                buf = bytearray()
                for chunk in r.iter_bytes():
                    buf += chunk
                    if len(buf) > max_bytes:
                        raise UnsafeURL("response too large")
                return bytes(buf)
    raise UnsafeURL("too many redirects")
