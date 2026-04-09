"""入力バリデーションユーティリティ"""

import re
from typing import Any

VALID_MONITOR_TYPES = {"url_check", "cloudwatch_log"}
VALID_INTERVAL_MINUTES = {5, 10, 15, 30, 60, 180, 360, 720, 1440}
VALID_NOTIFICATION_TYPES = {"email", "slack"}
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


def validate_site_body(body: dict[str, Any]) -> str | None:
    """サイト登録/更新のリクエストボディをバリデーションする。

    Returns:
        エラーメッセージ。問題なければ None
    """
    site_name = body.get("site_name")
    if not site_name or not isinstance(site_name, str):
        return "site_name is required and must be a non-empty string"
    if len(site_name) > 200:
        return "site_name must be 200 characters or less"

    monitor_type = body.get("monitor_type")
    if not monitor_type or monitor_type not in VALID_MONITOR_TYPES:
        return f"monitor_type is required and must be one of {sorted(VALID_MONITOR_TYPES)}"

    targets = body.get("targets")
    if not isinstance(targets, list) or len(targets) < 1:
        return "targets is required and must be a non-empty list"

    schedule_start = body.get("schedule_start")
    if not schedule_start or not TIME_PATTERN.match(str(schedule_start)):
        return "schedule_start is required and must be in HH:MM format"

    schedule_interval_minutes = body.get("schedule_interval_minutes")
    if schedule_interval_minutes not in VALID_INTERVAL_MINUTES:
        return f"schedule_interval_minutes is required and must be one of {sorted(VALID_INTERVAL_MINUTES)}"

    consecutive_threshold = body.get("consecutive_threshold")
    if consecutive_threshold is not None:
        if not isinstance(consecutive_threshold, int) or consecutive_threshold < 1:
            return "consecutive_threshold must be a positive integer"

    return None


def validate_notification_body(body: dict[str, Any]) -> str | None:
    """通知登録のリクエストボディをバリデーションする。

    Returns:
        エラーメッセージ。問題なければ None
    """
    notif_type = body.get("type")
    if not notif_type or notif_type not in VALID_NOTIFICATION_TYPES:
        return f"type is required and must be one of {sorted(VALID_NOTIFICATION_TYPES)}"

    destination = body.get("destination")
    if not destination or not isinstance(destination, str) or not destination.strip():
        return "destination is required and must be a non-empty string"

    return None
