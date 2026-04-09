"""通知Lambda ハンドラー

SQS（通知キュー）→ Lambda
  - メッセージからsite_id取得
  - DynamoDBからnotifications設定を読込
  - 各通知先に送信
  - 失敗時は例外raise → SQS自動リトライ → DLQ
"""

import json
import os

import boto3

try:
    from example-company_powertools.logging import LambdaLogger

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

try:
    from email_sender import send_email
    from slack_sender import send_slack
except ImportError:
    from notifier.email_sender import send_email
    from notifier.slack_sender import send_slack


SITES_TABLE = os.environ.get("SITES_TABLE_NAME", "")
NOTIFICATIONS_TABLE = os.environ.get("NOTIFICATIONS_TABLE_NAME", "")

_dynamodb = None


def _get_dynamodb():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb


def _process_record(record: dict) -> None:
    body = json.loads(record["body"])
    site_id = body["site_id"]
    site_name = body.get("site_name", "")
    previous_status = body.get("previous_status", "")
    new_status = body.get("new_status", "")
    trigger_url = body.get("trigger_url", "")
    checked_at = body.get("checked_at", "")

    notif_table = _get_dynamodb().Table(NOTIFICATIONS_TABLE)
    result = notif_table.query(
        KeyConditionExpression="site_id = :sid",
        ExpressionAttributeValues={":sid": site_id},
    )
    notifications = result.get("Items", [])

    if not notifications:
        logger.info("No notifications configured", {"site_id": site_id})
        return

    for notif in notifications:
        if not notif.get("enabled", True):
            continue

        notif_type = notif.get("type", "")

        if notif_type == "email":
            send_email(
                to_address=notif["destination"],
                site_name=site_name,
                trigger_url=trigger_url,
                previous_status=previous_status,
                new_status=new_status,
                last_checked_at=checked_at,
                message_template=notif.get("message_template", ""),
            )
        elif notif_type == "slack":
            send_slack(
                ssm_parameter_name=notif["destination"],
                mention=notif.get("mention", ""),
                site_name=site_name,
                trigger_url=trigger_url,
                previous_status=previous_status,
                new_status=new_status,
                last_checked_at=checked_at,
            )
        else:
            logger.warning("Unknown notification type", {"type": notif_type})


@LambdaLogger.contextualize
def handler(event, context):
    records = event.get("Records", [])
    logger.info("Processing notification records", {"count": len(records)})

    for record in records:
        _process_record(record)
