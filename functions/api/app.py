"""Web Alive Monitoring API Lambda Handler

全13エンドポイントを単一Lambdaで処理する。
"""

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3

try:
    from osasi_powertools.logging import LambdaLogger

    logger = LambdaLogger()
except ImportError:
    import logging

    logger = logging.getLogger(__name__)
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

    class _FakeDecorator:
        @staticmethod
        def contextualize(func):
            return func

    if not hasattr(logger, "contextualize"):
        LambdaLogger = _FakeDecorator
    else:
        LambdaLogger = type(logger)

from botocore.exceptions import ClientError

from api.utils.auth import get_email_from_claims
from api.utils.response import error_response, success_response
from api.utils.validator import validate_notification_body, validate_site_body
from api.utils import scheduler as sched_util


SITES_TABLE = os.environ.get("SITES_TABLE_NAME", "")
CHECK_RESULTS_TABLE = os.environ.get("CHECK_RESULTS_TABLE_NAME", "")
NOTIFICATIONS_TABLE = os.environ.get("NOTIFICATIONS_TABLE_NAME", "")
STATUS_CHANGES_TABLE = os.environ.get("STATUS_CHANGES_TABLE_NAME", "")

dynamodb = None


def _get_dynamodb():
    global dynamodb
    if dynamodb is None:
        dynamodb = boto3.resource("dynamodb")
    return dynamodb


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decimal_to_native(obj):
    """DynamoDB Decimal をPythonネイティブ型に変換"""
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_native(i) for i in obj]
    return obj


ROUTES = {}


def route(method: str, path: str):
    def decorator(func):
        ROUTES[(method, path)] = func
        return func
    return decorator


def _match_route(method: str, path: str):
    """パスパターンマッチング"""
    for (route_method, route_path), func in ROUTES.items():
        if route_method != method:
            continue
        route_parts = route_path.split("/")
        path_parts = path.rstrip("/").split("/")
        if len(route_parts) != len(path_parts):
            continue
        params = {}
        matched = True
        for rp, pp in zip(route_parts, path_parts):
            if rp.startswith("{") and rp.endswith("}"):
                params[rp[1:-1]] = pp
            elif rp != pp:
                matched = False
                break
        if matched:
            return func, params
    return None, {}


def handler(event, context):
    try:
        if hasattr(LambdaLogger, "contextualize"):
            pass

        method = event.get("httpMethod", "")
        path = event.get("path", "")

        if method == "OPTIONS":
            return success_response(None)

        func, path_params = _match_route(method, path)
        if func is None:
            return error_response("Not found", status_code=404)

        if event.get("pathParameters") is None:
            event["pathParameters"] = {}
        event["pathParameters"].update(path_params)

        return func(event)
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        return error_response("Internal server error", status_code=500)


# --- Sites endpoints ---

@route("GET", "/sites")
def get_sites(event: dict) -> dict:
    email = get_email_from_claims(event)
    query_params = event.get("queryStringParameters") or {}
    filter_mode = query_params.get("filter", "")

    table = _get_dynamodb().Table(SITES_TABLE)
    result = table.scan()
    items = result.get("Items", [])

    if filter_mode == "mine" and email:
        items = [item for item in items if item.get("created_by") == email]

    return success_response(_decimal_to_native(items))


@route("POST", "/sites")
def post_sites(event: dict) -> dict:
    email = get_email_from_claims(event)
    body = json.loads(event.get("body") or "{}")

    validation_error = validate_site_body(body)
    if validation_error:
        return error_response(validation_error, status_code=400)

    site_id = str(uuid.uuid4())
    now = _now_iso()

    item = {
        "site_id": site_id,
        "site_name": body.get("site_name", ""),
        "monitor_type": body.get("monitor_type", "url_check"),
        "targets": body.get("targets", []),
        "schedule_start": body.get("schedule_start", "00:00"),
        "schedule_interval_minutes": body.get("schedule_interval_minutes", 60),
        "consecutive_threshold": body.get("consecutive_threshold", 3),
        "enabled": body.get("enabled", True),
        "last_check_status": None,
        "last_checked_at": None,
        "consecutive_miss_count": 0,
        "created_by": email,
        "updated_by": email,
        "created_at": now,
        "updated_at": now,
    }

    table = _get_dynamodb().Table(SITES_TABLE)
    table.put_item(Item=item)

    try:
        scheduler_arn = sched_util.create_schedule(
            site_id=site_id,
            schedule_start=item["schedule_start"],
            schedule_interval_minutes=item["schedule_interval_minutes"],
            monitor_type=item["monitor_type"],
            enabled=item["enabled"],
        )
        item["scheduler_arn"] = scheduler_arn
        table.update_item(
            Key={"site_id": site_id},
            UpdateExpression="SET scheduler_arn = :arn",
            ExpressionAttributeValues={":arn": scheduler_arn},
        )
    except Exception as e:
        logger.error("Scheduler creation failed, rolling back", {"error": str(e)})
        table.delete_item(Key={"site_id": site_id})
        return error_response("スケジュール作成に失敗しました", status_code=500)

    return success_response(_decimal_to_native(item), status_code=201)


@route("GET", "/sites/{site_id}")
def get_site(event: dict) -> dict:
    site_id = event["pathParameters"]["site_id"]
    table = _get_dynamodb().Table(SITES_TABLE)
    result = table.get_item(Key={"site_id": site_id})

    if "Item" not in result:
        return error_response("Site not found", status_code=404)

    return success_response(_decimal_to_native(result["Item"]))


@route("PUT", "/sites/{site_id}")
def put_site(event: dict) -> dict:
    site_id = event["pathParameters"]["site_id"]
    email = get_email_from_claims(event)
    body = json.loads(event.get("body") or "{}")

    validation_error = validate_site_body(body)
    if validation_error:
        return error_response(validation_error, status_code=400)

    table = _get_dynamodb().Table(SITES_TABLE)
    existing = table.get_item(Key={"site_id": site_id})

    if "Item" not in existing:
        return error_response("Site not found", status_code=404)

    old_item = existing["Item"]

    if old_item.get("created_by") != email:
        return error_response("この操作は作成者のみ実行できます", status_code=403)

    now = _now_iso()

    schedule_changed = (
        body.get("schedule_start") != old_item.get("schedule_start")
        or body.get("schedule_interval_minutes") != old_item.get("schedule_interval_minutes")
        or body.get("enabled") != old_item.get("enabled")
        or body.get("monitor_type") != old_item.get("monitor_type")
    )

    updated_item = {
        **old_item,
        "site_name": body.get("site_name", old_item.get("site_name")),
        "monitor_type": body.get("monitor_type", old_item.get("monitor_type")),
        "targets": body.get("targets", old_item.get("targets")),
        "schedule_start": body.get("schedule_start", old_item.get("schedule_start")),
        "schedule_interval_minutes": body.get("schedule_interval_minutes", old_item.get("schedule_interval_minutes")),
        "consecutive_threshold": body.get("consecutive_threshold", old_item.get("consecutive_threshold")),
        "enabled": body.get("enabled", old_item.get("enabled")),
        "updated_by": email,
        "updated_at": now,
    }

    table.put_item(Item=updated_item)

    if schedule_changed:
        try:
            sched_util.update_schedule(
                site_id=site_id,
                schedule_start=updated_item["schedule_start"],
                schedule_interval_minutes=updated_item["schedule_interval_minutes"],
                monitor_type=updated_item["monitor_type"],
                enabled=updated_item["enabled"],
            )
        except Exception as e:
            logger.error("Scheduler update failed, rolling back", {"error": str(e)})
            table.put_item(Item=old_item)
            return error_response("スケジュール更新に失敗しました", status_code=500)

    return success_response(_decimal_to_native(updated_item))


@route("DELETE", "/sites/{site_id}")
def delete_site(event: dict) -> dict:
    site_id = event["pathParameters"]["site_id"]
    email = get_email_from_claims(event)
    table = _get_dynamodb().Table(SITES_TABLE)

    existing = table.get_item(Key={"site_id": site_id})
    if "Item" not in existing:
        return error_response("Site not found", status_code=404)

    if existing["Item"].get("created_by") != email:
        return error_response("この操作は作成者のみ実行できます", status_code=403)

    try:
        sched_util.delete_schedule(site_id)
    except Exception as e:
        logger.error("Scheduler deletion failed", {"error": str(e)})

    notif_table = _get_dynamodb().Table(NOTIFICATIONS_TABLE)
    notif_result = notif_table.query(
        KeyConditionExpression="site_id = :sid",
        ExpressionAttributeValues={":sid": site_id},
    )
    for item in notif_result.get("Items", []):
        notif_table.delete_item(
            Key={"site_id": site_id, "notification_id": item["notification_id"]}
        )

    table.delete_item(Key={"site_id": site_id})

    return success_response({"message": "Site deleted"})


@route("GET", "/sites/{site_id}/results")
def get_site_results(event: dict) -> dict:
    site_id = event["pathParameters"]["site_id"]
    table = _get_dynamodb().Table(CHECK_RESULTS_TABLE)

    result = table.query(
        KeyConditionExpression="site_id = :sid",
        ExpressionAttributeValues={":sid": site_id},
        ScanIndexForward=False,
    )

    return success_response(_decimal_to_native(result.get("Items", [])))


# --- Notifications endpoints ---

@route("GET", "/sites/{site_id}/notifications")
def get_notifications(event: dict) -> dict:
    site_id = event["pathParameters"]["site_id"]
    table = _get_dynamodb().Table(NOTIFICATIONS_TABLE)

    result = table.query(
        KeyConditionExpression="site_id = :sid",
        ExpressionAttributeValues={":sid": site_id},
    )

    return success_response(_decimal_to_native(result.get("Items", [])))


@route("POST", "/sites/{site_id}/notifications")
def post_notification(event: dict) -> dict:
    site_id = event["pathParameters"]["site_id"]
    body = json.loads(event.get("body") or "{}")

    validation_error = validate_notification_body(body)
    if validation_error:
        return error_response(validation_error, status_code=400)

    sites_table = _get_dynamodb().Table(SITES_TABLE)
    site_result = sites_table.get_item(Key={"site_id": site_id})
    if "Item" not in site_result:
        return error_response("Site not found", status_code=404)

    notification_id = str(uuid.uuid4())

    item = {
        "site_id": site_id,
        "notification_id": notification_id,
        "type": body.get("type", "email"),
        "destination": body.get("destination", ""),
        "mention": body.get("mention", ""),
        "message_template": body.get("message_template", ""),
        "enabled": body.get("enabled", True),
    }

    table = _get_dynamodb().Table(NOTIFICATIONS_TABLE)
    table.put_item(Item=item)

    return success_response(_decimal_to_native(item), status_code=201)


@route("PUT", "/sites/{site_id}/notifications/{notification_id}")
def put_notification(event: dict) -> dict:
    site_id = event["pathParameters"]["site_id"]
    notification_id = event["pathParameters"]["notification_id"]
    body = json.loads(event.get("body") or "{}")

    table = _get_dynamodb().Table(NOTIFICATIONS_TABLE)
    existing = table.get_item(
        Key={"site_id": site_id, "notification_id": notification_id}
    )

    if "Item" not in existing:
        return error_response("Notification not found", status_code=404)

    old_item = existing["Item"]
    updated_item = {
        **old_item,
        "type": body.get("type", old_item.get("type")),
        "destination": body.get("destination", old_item.get("destination")),
        "mention": body.get("mention", old_item.get("mention", "")),
        "message_template": body.get("message_template", old_item.get("message_template", "")),
        "enabled": body.get("enabled", old_item.get("enabled")),
    }

    table.put_item(Item=updated_item)

    return success_response(_decimal_to_native(updated_item))


@route("DELETE", "/sites/{site_id}/notifications/{notification_id}")
def delete_notification(event: dict) -> dict:
    site_id = event["pathParameters"]["site_id"]
    notification_id = event["pathParameters"]["notification_id"]

    table = _get_dynamodb().Table(NOTIFICATIONS_TABLE)
    try:
        table.delete_item(
            Key={"site_id": site_id, "notification_id": notification_id},
            ConditionExpression="attribute_exists(notification_id)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return error_response("Notification not found", status_code=404)
        raise

    return success_response({"message": "Notification deleted"})


# --- Test endpoints ---

@route("POST", "/sites/{site_id}/test-check")
def test_check(event: dict) -> dict:
    """手動チェック実行 — checker Lambdaを同期Invokeする"""
    site_id = event["pathParameters"]["site_id"]

    sites_table = _get_dynamodb().Table(SITES_TABLE)
    site_result = sites_table.get_item(Key={"site_id": site_id})
    if "Item" not in site_result:
        return error_response("Site not found", status_code=404)

    checker_arn = os.environ.get("CHECKER_FUNCTION_ARN", "")
    if not checker_arn:
        return error_response("Checker function not configured", status_code=500)

    try:
        lambda_client = boto3.client("lambda")
        response = lambda_client.invoke(
            FunctionName=checker_arn,
            InvocationType="RequestResponse",
            Payload=json.dumps({"site_id": site_id}),
        )
        payload = json.loads(response["Payload"].read())
        return success_response(payload)
    except Exception as e:
        logger.error("Test check failed", {"error": str(e)})
        return error_response("チェック実行に失敗しました", status_code=500)


@route("POST", "/sites/{site_id}/test-notify")
def test_notify(event: dict) -> dict:
    """テスト通知。Phase 4で本格実装。"""
    return success_response({
        "message": "Test notify stub - will be implemented in Phase 4",
    })


# --- CloudWatch endpoints ---

@route("GET", "/cloudwatch/log-groups")
def get_cloudwatch_log_groups(event: dict) -> dict:
    """CWロググループ一覧を取得する。"""
    try:
        client = boto3.client("logs")
        log_groups = []
        paginator = client.get_paginator("describe_log_groups")
        for page in paginator.paginate():
            for lg in page.get("logGroups", []):
                log_groups.append({
                    "logGroupName": lg["logGroupName"],
                    "storedBytes": lg.get("storedBytes", 0),
                })
        return success_response(log_groups)
    except Exception as e:
        logger.error("Failed to get log groups", {"error": str(e)})
        return error_response("ロググループの取得に失敗しました", status_code=500)
