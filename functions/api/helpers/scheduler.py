"""EventBridge Scheduler CRUD操作ユーティリティ"""

import json
import os

import boto3

try:
    from helpers.cron import generate_cron_expression
except ImportError:
    from api.helpers.cron import generate_cron_expression


def get_scheduler_client():
    return boto3.client("scheduler")


def _schedule_name(site_id: str) -> str:
    stack_name = os.environ.get("STACK_NAME", "")
    return f"{stack_name}-site-{site_id}"


def create_schedule(
    site_id: str,
    schedule_start: str,
    schedule_interval_minutes: int,
    monitor_type: str,
    enabled: bool = True,
) -> str:
    """EventBridge Schedulerのスケジュールを作成する。

    Returns:
        作成されたスケジュールのARN
    """
    client = get_scheduler_client()
    cron_expr = generate_cron_expression(schedule_start, schedule_interval_minutes)
    name = _schedule_name(site_id)

    target_arn = os.environ.get("CHECKER_FUNCTION_ARN", "")
    role_arn = os.environ.get("SCHEDULER_ROLE_ARN", "")
    group_name = os.environ.get("SCHEDULER_GROUP_NAME", "default")

    target = {
        "Arn": target_arn,
        "RoleArn": role_arn,
        "Input": json.dumps({"site_id": site_id}),
    }

    if monitor_type == "cloudwatch_log":
        cw_queue_url = os.environ.get("CW_LOG_QUEUE_URL", "")
        target = {
            "Arn": cw_queue_url,
            "RoleArn": role_arn,
            "Input": json.dumps({"site_id": site_id}),
        }

    response = client.create_schedule(
        Name=name,
        GroupName=group_name,
        ScheduleExpression=cron_expr,
        ScheduleExpressionTimezone="UTC",
        FlexibleTimeWindow={"Mode": "OFF"},
        State="ENABLED" if enabled else "DISABLED",
        Target=target,
    )
    return response["ScheduleArn"]


def update_schedule(
    site_id: str,
    schedule_start: str,
    schedule_interval_minutes: int,
    monitor_type: str,
    enabled: bool = True,
) -> None:
    client = get_scheduler_client()
    cron_expr = generate_cron_expression(schedule_start, schedule_interval_minutes)
    name = _schedule_name(site_id)

    target_arn = os.environ.get("CHECKER_FUNCTION_ARN", "")
    role_arn = os.environ.get("SCHEDULER_ROLE_ARN", "")
    group_name = os.environ.get("SCHEDULER_GROUP_NAME", "default")

    target = {
        "Arn": target_arn,
        "RoleArn": role_arn,
        "Input": json.dumps({"site_id": site_id}),
    }

    if monitor_type == "cloudwatch_log":
        cw_queue_url = os.environ.get("CW_LOG_QUEUE_URL", "")
        target = {
            "Arn": cw_queue_url,
            "RoleArn": role_arn,
            "Input": json.dumps({"site_id": site_id}),
        }

    client.update_schedule(
        Name=name,
        GroupName=group_name,
        ScheduleExpression=cron_expr,
        ScheduleExpressionTimezone="UTC",
        FlexibleTimeWindow={"Mode": "OFF"},
        State="ENABLED" if enabled else "DISABLED",
        Target=target,
    )


def delete_schedule(site_id: str) -> None:
    client = get_scheduler_client()
    name = _schedule_name(site_id)
    group_name = os.environ.get("SCHEDULER_GROUP_NAME", "default")

    try:
        client.delete_schedule(Name=name, GroupName=group_name)
    except client.exceptions.ResourceNotFoundException:
        pass


def disable_schedule(site_id: str) -> None:
    client = get_scheduler_client()
    name = _schedule_name(site_id)
    group_name = os.environ.get("SCHEDULER_GROUP_NAME", "default")

    existing = client.get_schedule(Name=name, GroupName=group_name)
    client.update_schedule(
        Name=name,
        GroupName=group_name,
        ScheduleExpression=existing["ScheduleExpression"],
        ScheduleExpressionTimezone="UTC",
        FlexibleTimeWindow={"Mode": "OFF"},
        State="DISABLED",
        Target=existing["Target"],
    )


def enable_schedule(site_id: str) -> None:
    client = get_scheduler_client()
    name = _schedule_name(site_id)
    group_name = os.environ.get("SCHEDULER_GROUP_NAME", "default")

    existing = client.get_schedule(Name=name, GroupName=group_name)
    client.update_schedule(
        Name=name,
        GroupName=group_name,
        ScheduleExpression=existing["ScheduleExpression"],
        ScheduleExpressionTimezone="UTC",
        FlexibleTimeWindow={"Mode": "OFF"},
        State="ENABLED",
        Target=existing["Target"],
    )
