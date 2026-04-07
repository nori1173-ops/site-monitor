"""統一レスポンスエンベロープ"""

import json
from typing import Any


CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
}


def success_response(data: Any, status_code: int = 200) -> dict:
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(
            {"success": True, "data": data, "error": None},
            ensure_ascii=False,
            default=str,
        ),
    }


def error_response(message: str, status_code: int = 400) -> dict:
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(
            {"success": False, "data": None, "error": message},
            ensure_ascii=False,
        ),
    }
