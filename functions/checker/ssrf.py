"""SSRF対策モジュール — プライベートIP・メタデータURLブロック"""

import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}

PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
]


def _resolve_host(hostname: str) -> str:
    return socket.gethostbyname(hostname)


def _is_private_ip(ip_str: str) -> bool:
    addr = ipaddress.ip_address(ip_str)
    return any(addr in network for network in PRIVATE_NETWORKS)


def validate_url(url: str) -> None:
    if not url:
        raise ValueError("URLが空です")

    parsed = urlparse(url)

    if not parsed.scheme:
        raise ValueError("スキームがありません")

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"許可されていないスキーム: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("ホスト名がありません")

    try:
        resolved_ip = _resolve_host(hostname)
    except socket.gaierror as e:
        raise ValueError(f"DNS解決に失敗: {hostname} ({e})")

    if _is_private_ip(resolved_ip):
        raise ValueError(f"プライベートIPアドレスへのアクセスは禁止されています: {resolved_ip}")
