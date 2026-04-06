"""EventBridge Scheduler用のCron式生成ユーティリティ"""

JST_OFFSET_HOURS = 9


def generate_cron_expression(start_time_jst: str, interval_minutes: int) -> str:
    """JST開始時刻と間隔（分）からEventBridge SchedulerのCron式を生成する。

    Args:
        start_time_jst: 開始時刻（HH:MM形式、JST）
        interval_minutes: 監視間隔（分）

    Returns:
        EventBridge Scheduler用のCron式文字列

    Raises:
        ValueError: 不正な時刻形式または間隔
    """
    if interval_minutes <= 0:
        raise ValueError(f"interval_minutes must be positive: {interval_minutes}")

    parts = start_time_jst.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {start_time_jst}")

    hour_jst = int(parts[0])
    minute = int(parts[1])

    if not (0 <= hour_jst <= 23) or not (0 <= minute <= 59):
        raise ValueError(f"Invalid time: {start_time_jst}")

    hour_utc = (hour_jst - JST_OFFSET_HOURS) % 24

    if interval_minutes < 60:
        return f"cron({minute}/{interval_minutes} * * * ? *)"

    if interval_minutes == 60:
        return f"cron({minute} * * * ? *)"

    hours = interval_minutes // 60

    if interval_minutes % 60 == 0:
        if hours == 24:
            return f"cron({minute} {hour_utc} * * ? *)"
        return f"cron({minute} {hour_utc}/{hours} * * ? *)"

    raise ValueError(
        f"interval_minutes must be < 60 or a multiple of 60: {interval_minutes}"
    )
