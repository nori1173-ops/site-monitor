"""HTTP GETクライアント — タイムアウト10秒、レスポンスサイズ上限10MB"""

import hashlib

import requests

try:
    from ssrf import validate_url
except ImportError:
    from checker.ssrf import validate_url

TIMEOUT_SECONDS = 10
MAX_RESPONSE_SIZE = 10 * 1024 * 1024
USER_AGENT = "WebAliveMonitoring/1.0"


class ResponseTooLargeError(Exception):
    pass


def fetch_url(url: str) -> dict:
    validate_url(url)

    response = requests.get(
        url,
        timeout=TIMEOUT_SECONDS,
        stream=True,
        headers={"User-Agent": USER_AGENT},
    )

    last_modified = response.headers.get("Last-Modified")
    etag = response.headers.get("ETag")

    sha256 = hashlib.sha256()
    total_size = 0

    for chunk in response.iter_content(chunk_size=8192):
        total_size += len(chunk)
        if total_size > MAX_RESPONSE_SIZE:
            raise ResponseTooLargeError(
                f"レスポンスサイズが上限（10MB）を超えました"
            )
        sha256.update(chunk)

    return {
        "status_code": response.status_code,
        "last_modified": last_modified,
        "etag": etag,
        "content_hash": sha256.hexdigest(),
    }
