"""CloudWatchログ監視 Lambda ハンドラー

SQS (CWログ監視キュー) -> Lambda(同時実行数=1)
"""

import json
import os
from datetime import datetime, timezone, timedelta

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

try:
    from insights import run_query
except ImportError:
    from cw_checker.insights import run_query

SITES_TABLE = os.environ.get("SITES_TABLE_NAME", "")
CHECK_RESULTS_TABLE = os.environ.get("CHECK_RESULTS_TABLE_NAME", "")
STATUS_CHANGES_TABLE = os.environ.get("STATUS_CHANGES_TABLE_NAME", "")
NOTIFICATION_QUEUE_URL = os.environ.get("NOTIFICATION_QUEUE_URL", "")

CHECK_RESULTS_TTL_DAYS = 90
STATUS_CHANGES_TTL_DAYS = 365

_dynamodb = None
_sqs = None


def _get_dynamodb():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb


def _get_sqs():
    global _sqs
    if _sqs is None:
        _sqs = boto3.client("sqs")
    return _sqs


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ttl_epoch(days: int) -> int:
    return int((datetime.now(timezone.utc) + timedelta(days=days)).timestamp())


def _record_check_result(
    site_id: str,
    target_identifier: str,
    checked_at: str,
    status: str,
    hit_count: int = 0,
    latest_timestamp: str | None = None,
    error_message: str | None = None,
) -> None:
    table = _get_dynamodb().Table(CHECK_RESULTS_TABLE)
    item = {
        "site_id": site_id,
        "checked_at#target_url": f"{checked_at}#{target_identifier}",
        "status": status,
        "hit_count": hit_count,
        "latest_timestamp": latest_timestamp,
        "ttl": _ttl_epoch(CHECK_RESULTS_TTL_DAYS),
    }
    if error_message:
        item["error_message"] = error_message
    table.put_item(Item=item)


def _update_site_status(
    site_id: str,
    new_status: str,
    checked_at: str,
    consecutive_miss_count: int,
) -> None:
    table = _get_dynamodb().Table(SITES_TABLE)
    table.update_item(
        Key={"site_id": site_id},
        UpdateExpression="SET last_check_status = :status, last_checked_at = :at, consecutive_miss_count = :cnt",
        ExpressionAttributeValues={
            ":status": new_status,
            ":at": checked_at,
            ":cnt": consecutive_miss_count,
        },
    )


def _record_status_change(
    site_id: str,
    changed_at: str,
    previous_status: str,
    new_status: str,
    trigger_url: str,
) -> None:
    table = _get_dynamodb().Table(STATUS_CHANGES_TABLE)
    table.put_item(Item={
        "site_id": site_id,
        "changed_at": changed_at,
        "previous_status": previous_status,
        "new_status": new_status,
        "trigger_url": trigger_url,
        "ttl": _ttl_epoch(STATUS_CHANGES_TTL_DAYS),
    })


def _send_notification(
    site_id: str,
    site_name: str,
    previous_status: str,
    new_status: str,
    trigger_url: str,
    checked_at: str,
) -> None:
    sqs = _get_sqs()
    message = {
        "site_id": site_id,
        "site_name": site_name,
        "previous_status": previous_status,
        "new_status": new_status,
        "trigger_url": trigger_url,
        "checked_at": checked_at,
    }
    sqs.send_message(
        QueueUrl=NOTIFICATION_QUEUE_URL,
        MessageBody=json.dumps(message),
    )


def _determine_overall_status(target_results: list[dict]) -> str:
    statuses = [r["check_status"] for r in target_results]
    if "error" in statuses:
        return "error"
    if "not_updated" in statuses:
        return "not_updated"
    return "updated"


def _find_trigger_identifier(target_results: list[dict], overall_status: str) -> str:
    if overall_status in ("error", "not_updated"):
        for r in target_results:
            if r["check_status"] == overall_status:
                return r["log_group"]
    return target_results[0]["log_group"] if target_results else ""


@LambdaLogger.contextualize
def handler(event, context):
    global _dynamodb, _sqs
    _dynamodb = None
    _sqs = None

    try:
        record = event.get("Records", [{}])[0]
        body = json.loads(record.get("body", "{}"))
        site_id = body.get("site_id")
    except (json.JSONDecodeError, IndexError, KeyError) as e:
        logger.error(f"Invalid SQS message: {e}")
        return {"status": "error", "message": f"Invalid SQS message: {e}"}

    if not site_id:
        return {"status": "error", "message": "site_id is required"}

    sites_table = _get_dynamodb().Table(SITES_TABLE)
    site_result = sites_table.get_item(Key={"site_id": site_id})

    if "Item" not in site_result:
        return {"status": "error", "message": "Site not found"}

    site = site_result["Item"]
    targets = site.get("targets", [])
    previous_status = site.get("last_check_status")
    consecutive_miss_count = int(site.get("consecutive_miss_count", 0))
    site_name = site.get("site_name", "")

    checked_at = _now_iso()
    target_results = []

    for target in targets:
        log_group = target.get("log_group", "")
        message_filter = target.get("message_filter", "")
        json_search_word = target.get("json_search_word", "")
        search_period_minutes = int(target.get("search_period_minutes", 60))

        query_result = run_query(
            log_group=log_group,
            message_filter=message_filter,
            json_search_word=json_search_word,
            search_period_minutes=search_period_minutes,
        )

        if query_result["status"] == "error":
            check_status = "error"
        elif query_result["hit_count"] == 0:
            check_status = "not_updated"
        else:
            check_status = "updated"

        _record_check_result(
            site_id=site_id,
            target_identifier=log_group,
            checked_at=checked_at,
            status=check_status,
            hit_count=query_result.get("hit_count", 0),
            latest_timestamp=query_result.get("latest_timestamp"),
            error_message=query_result.get("message") if query_result["status"] == "error" else None,
        )

        target_results.append({
            "log_group": log_group,
            "check_status": check_status,
            "hit_count": query_result.get("hit_count", 0),
            "latest_timestamp": query_result.get("latest_timestamp"),
        })

    overall_status = _determine_overall_status(target_results)

    if overall_status == "updated":
        consecutive_miss_count = 0
    else:
        consecutive_miss_count += 1

    _update_site_status(
        site_id=site_id,
        new_status=overall_status,
        checked_at=checked_at,
        consecutive_miss_count=consecutive_miss_count,
    )

    if previous_status is not None and overall_status != previous_status:
        trigger_identifier = _find_trigger_identifier(target_results, overall_status)

        _record_status_change(
            site_id=site_id,
            changed_at=checked_at,
            previous_status=previous_status,
            new_status=overall_status,
            trigger_url=trigger_identifier,
        )

        _send_notification(
            site_id=site_id,
            site_name=site_name,
            previous_status=previous_status,
            new_status=overall_status,
            trigger_url=trigger_identifier,
            checked_at=checked_at,
        )

    return {
        "status": "completed",
        "site_id": site_id,
        "overall_status": overall_status,
        "results": target_results,
    }
