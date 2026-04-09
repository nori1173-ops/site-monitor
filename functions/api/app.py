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

try:
    from helpers.auth import get_email_from_claims
    from helpers.response import error_response, success_response
    from helpers.validator import validate_notification_body, validate_site_body
    from helpers import scheduler as sched_util
except ImportError:
    from api.helpers.auth import get_email_from_claims
    from api.helpers.response import error_response, success_response
    from api.helpers.validator import validate_notification_body, validate_site_body
    from api.helpers import scheduler as sched_util


SITES_TABLE = os.environ.get("SITES_TABLE_NAME", "")
CHECK_RESULTS_TABLE = os.environ.get("CHECK_RESULTS_TABLE_NAME", "")
NOTIFICATIONS_TABLE = os.environ.get("NOTIFICATIONS_TABLE_NAME", "")
STATUS_CHANGES_TABLE = os.environ.get("STATUS_CHANGES_TABLE_NAME", "")
USER_POOL_ID = os.environ.get("USER_POOL_ID", "")

ADMIN_CREDENTIALS = os.environ.get("ADMIN_CREDENTIALS", "admin:osasi034")

dynamodb = None
cognito_client = None


def _get_dynamodb():
    global dynamodb
    if dynamodb is None:
        dynamodb = boto3.resource("dynamodb")
    return dynamodb


def _get_cognito_client():
    global cognito_client
    if cognito_client is None:
        cognito_client = boto3.client("cognito-idp")
    return cognito_client


def _is_admin(event: dict) -> bool:
    """リクエストヘッダーの X-Admin-Auth を検証して管理者かどうか判定"""
    import base64
    headers = event.get("headers") or {}
    auth_value = headers.get("X-Admin-Auth") or headers.get("x-admin-auth") or ""
    if not auth_value:
        return False
    try:
        decoded = base64.b64decode(auth_value).decode("utf-8")
        if decoded == ADMIN_CREDENTIALS:
            return True
        logger.info("Admin auth failed", {"headers": "X-Admin-Auth present but invalid"})
        return False
    except Exception:
        logger.info("Admin auth failed", {"headers": "X-Admin-Auth present but invalid"})
        return False


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

    if old_item.get("created_by") != email and not _is_admin(event):
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

    if existing["Item"].get("created_by") != email and not _is_admin(event):
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


@route("GET", "/sites/{site_id}/status-changes")
def get_site_status_changes(event: dict) -> dict:
    site_id = event["pathParameters"]["site_id"]
    table = _get_dynamodb().Table(STATUS_CHANGES_TABLE)

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
    """テスト通知 — 全通知先にテストメッセージを送信する"""
    site_id = event["pathParameters"]["site_id"]

    sites_table = _get_dynamodb().Table(SITES_TABLE)
    site_result = sites_table.get_item(Key={"site_id": site_id})
    if "Item" not in site_result:
        return error_response("Site not found", status_code=404)

    site = site_result["Item"]
    site_name = site.get("site_name", "")

    notif_table = _get_dynamodb().Table(NOTIFICATIONS_TABLE)
    notif_result = notif_table.query(
        KeyConditionExpression="site_id = :sid",
        ExpressionAttributeValues={":sid": site_id},
    )
    notifications = notif_result.get("Items", [])

    if not notifications:
        return error_response("通知先が設定されていません", status_code=400)

    email_domain = os.environ.get("EMAIL_DOMAIN", "alive.osasi-cloud.com")
    ses_region = os.environ.get("SES_REGION", "us-west-2")
    results = []

    for notif in notifications:
        if not notif.get("enabled", True):
            continue

        notif_type = notif.get("type", "")
        try:
            if notif_type == "email":
                ses_client = boto3.client("ses", region_name=ses_region)
                ses_client.send_email(
                    Source=f"OSASI.NET<noreply@{email_domain}>",
                    Destination={"ToAddresses": [notif["destination"]]},
                    Message={
                        "Subject": {
                            "Data": f"[Web Alive] {site_name} - テスト通知",
                            "Charset": "UTF-8",
                        },
                        "Body": {
                            "Text": {
                                "Data": f"これはテスト通知です。\n【現場名】{site_name}\n通知設定が正しく動作しています。",
                                "Charset": "UTF-8",
                            },
                        },
                    },
                )
                results.append({"type": "email", "destination": notif["destination"], "status": "sent"})
            elif notif_type == "slack":
                import requests as req

                ssm_client = boto3.client("ssm")
                ssm_result = ssm_client.get_parameter(
                    Name=notif["destination"], WithDecryption=True
                )
                webhook_url = ssm_result["Parameter"]["Value"]
                mention = notif.get("mention", "")
                lines = []
                if mention:
                    lines.append(mention)
                lines.append(f"これはテスト通知です。\n*現場名:* {site_name}\n通知設定が正しく動作しています。")
                resp = req.post(webhook_url, json={"text": "\n".join(lines)}, timeout=10)
                resp.raise_for_status()
                results.append({"type": "slack", "destination": notif["destination"], "status": "sent"})
        except Exception as e:
            logger.error("Test notify failed", {"type": notif_type, "error": str(e)})
            results.append({"type": notif_type, "destination": notif.get("destination", ""), "status": "failed", "error": str(e)})

    return success_response({"results": results})


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


# --- User management endpoints ---

@route("DELETE", "/users/me")
def delete_user_me(event: dict) -> dict:
    """自ユーザー削除: サイト登録がなければCognitoユーザーを削除"""
    email = get_email_from_claims(event)
    if not email:
        return error_response("認証情報が取得できません", status_code=401)

    table = _get_dynamodb().Table(SITES_TABLE)
    result = table.scan(
        FilterExpression="created_by = :email",
        ExpressionAttributeValues={":email": email},
        Select="COUNT",
    )
    if result.get("Count", 0) > 0:
        return error_response("登録済みサイトを先に削除してください", status_code=400)

    try:
        client = _get_cognito_client()
        client.admin_delete_user(
            UserPoolId=USER_POOL_ID,
            Username=email,
        )
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "UserNotFoundException":
            return error_response("ユーザーが存在しません", status_code=404)
        logger.error("User deletion failed", {"error": str(e)})
        return error_response("ユーザー削除に失敗しました", status_code=500)
    except Exception as e:
        logger.error("User deletion failed", {"error": str(e)})
        return error_response("ユーザー削除に失敗しました", status_code=500)

    return success_response({"message": "ユーザーを削除しました"})


# --- Admin endpoints ---

def _require_admin(event: dict) -> dict | None:
    """管理者認証チェック。失敗時はエラーレスポンスを返す"""
    if not _is_admin(event):
        return error_response("管理者権限が必要です", status_code=403)
    return None


@route("GET", "/admin/users")
def get_admin_users(event: dict) -> dict:
    """Cognitoユーザー一覧を取得"""
    auth_error = _require_admin(event)
    if auth_error:
        return auth_error

    try:
        client = _get_cognito_client()
        response = client.list_users(UserPoolId=USER_POOL_ID)
        users = []
        for user in response.get("Users", []):
            attrs = {a["Name"]: a["Value"] for a in user.get("Attributes", [])}
            users.append({
                "email": attrs.get("email", user.get("Username", "")),
                "enabled": user.get("Enabled", True),
                "status": user.get("UserStatus", ""),
                "created_at": str(user.get("UserCreateDate", "")),
            })
        return success_response(users)
    except Exception as e:
        logger.error("Failed to list users", {"error": str(e)})
        return error_response("ユーザー一覧の取得に失敗しました", status_code=500)


@route("POST", "/admin/users/{email}/toggle-status")
def toggle_user_status(event: dict) -> dict:
    """ユーザーの有効/無効を切り替える"""
    auth_error = _require_admin(event)
    if auth_error:
        return auth_error

    target_email = event["pathParameters"]["email"]

    try:
        client = _get_cognito_client()
        user_info = client.admin_get_user(
            UserPoolId=USER_POOL_ID,
            Username=target_email,
        )
        if user_info.get("Enabled", True):
            client.admin_disable_user(
                UserPoolId=USER_POOL_ID,
                Username=target_email,
            )
            new_status = False
        else:
            client.admin_enable_user(
                UserPoolId=USER_POOL_ID,
                Username=target_email,
            )
            new_status = True
        return success_response({"email": target_email, "enabled": new_status})
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "UserNotFoundException":
            return error_response("ユーザーが存在しません", status_code=404)
        logger.error("Failed to toggle user status", {"error": str(e)})
        return error_response("ユーザーステータスの変更に失敗しました", status_code=500)
    except Exception as e:
        logger.error("Failed to toggle user status", {"error": str(e)})
        return error_response("ユーザーステータスの変更に失敗しました", status_code=500)


@route("POST", "/admin/users/{email}/reset-password")
def admin_reset_password(event: dict) -> dict:
    """管理者によるパスワードリセット"""
    auth_error = _require_admin(event)
    if auth_error:
        return auth_error

    target_email = event["pathParameters"]["email"]

    try:
        client = _get_cognito_client()
        client.admin_reset_user_password(
            UserPoolId=USER_POOL_ID,
            Username=target_email,
        )
        return success_response({"message": "パスワードリセットメールを送信しました"})
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "UserNotFoundException":
            return error_response("ユーザーが存在しません", status_code=404)
        logger.error("Failed to reset password", {"error": str(e)})
        return error_response("パスワードリセットに失敗しました", status_code=500)
    except Exception as e:
        logger.error("Failed to reset password", {"error": str(e)})
        return error_response("パスワードリセットに失敗しました", status_code=500)


@route("DELETE", "/admin/users/{email}")
def admin_delete_user(event: dict) -> dict:
    """管理者によるユーザー削除"""
    auth_error = _require_admin(event)
    if auth_error:
        return auth_error

    target_email = event["pathParameters"]["email"]

    try:
        client = _get_cognito_client()
        client.admin_delete_user(
            UserPoolId=USER_POOL_ID,
            Username=target_email,
        )
        return success_response({"message": "ユーザーを削除しました"})
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "UserNotFoundException":
            return error_response("ユーザーが存在しません", status_code=404)
        logger.error("Failed to delete user", {"error": str(e)})
        return error_response("ユーザー削除に失敗しました", status_code=500)
    except Exception as e:
        logger.error("Failed to delete user", {"error": str(e)})
        return error_response("ユーザー削除に失敗しました", status_code=500)
