"""URL更新チェック Lambda ハンドラー

EventBridge Scheduler -> Lambda(event: {"site_id": "xxx"})
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

from checker.http_client import fetch_url
from checker.checker import determine_update_status

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


def _get_previous_result(site_id: str, target_url: str) -> dict | None:
    table = _get_dynamodb().Table(CHECK_RESULTS_TABLE)
    result = table.query(
        KeyConditionExpression="site_id = :sid",
        ExpressionAttributeValues={":sid": site_id},
        ScanIndexForward=False,
    )

    for item in result.get("Items", []):
        sk = item.get("checked_at#target_url", "")
        if sk.endswith(f"#{target_url}"):
            return item

    return None


def _record_check_result(
    site_id: str,
    target_url: str,
    checked_at: str,
    status: str,
    last_modified: str | None = None,
    etag: str | None = None,
    content_hash: str | None = None,
    error_message: str | None = None,
) -> None:
    table = _get_dynamodb().Table(CHECK_RESULTS_TABLE)
    item = {
        "site_id": site_id,
        "checked_at#target_url": f"{checked_at}#{target_url}",
        "status": status,
        "last_modified": last_modified,
        "etag": etag,
        "content_hash": content_hash,
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


def _determine_overall_status(url_results: list[dict]) -> str:
    statuses = [r["status"] for r in url_results]
    if "error" in statuses:
        return "error"
    if "not_updated" in statuses:
        return "not_updated"
    return "updated"


def _find_trigger_url(url_results: list[dict], overall_status: str) -> str:
    if overall_status == "error":
        for r in url_results:
            if r["status"] == "error":
                return r["url"]
    if overall_status == "not_updated":
        for r in url_results:
            if r["status"] == "not_updated":
                return r["url"]
    return url_results[0]["url"] if url_results else ""


@LambdaLogger.contextualize
def handler(event, context):
    site_id = event.get("site_id")
    if not site_id:
        return {"status": "error", "message": "site_id is required"}

    # reset module-level clients for moto compatibility in tests
    global _dynamodb, _sqs
    _dynamodb = None
    _sqs = None

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
    url_results = []

    for target in targets:
        target_url = target.get("url", "")
        try:
            fetch_result = fetch_url(target_url)
            previous_record = _get_previous_result(site_id, target_url)
            judgment = determine_update_status(fetch_result, previous_record)

            _record_check_result(
                site_id=site_id,
                target_url=target_url,
                checked_at=checked_at,
                status=judgment["status"],
                last_modified=fetch_result.get("last_modified"),
                etag=fetch_result.get("etag"),
                content_hash=fetch_result.get("content_hash"),
            )

            url_results.append({
                "url": target_url,
                "status": judgment["status"],
                "method": judgment["method"],
            })

        except Exception as e:
            logger.error(f"URL check failed: {target_url}", {"error": str(e)})

            _record_check_result(
                site_id=site_id,
                target_url=target_url,
                checked_at=checked_at,
                status="error",
                error_message=str(e),
            )

            url_results.append({
                "url": target_url,
                "status": "error",
                "error": str(e),
            })

    overall_status = _determine_overall_status(url_results)

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
        trigger_url = _find_trigger_url(url_results, overall_status)

        _record_status_change(
            site_id=site_id,
            changed_at=checked_at,
            previous_status=previous_status,
            new_status=overall_status,
            trigger_url=trigger_url,
        )

        _send_notification(
            site_id=site_id,
            site_name=site_name,
            previous_status=previous_status,
            new_status=overall_status,
            trigger_url=trigger_url,
            checked_at=checked_at,
        )

    return {
        "status": "completed",
        "site_id": site_id,
        "overall_status": overall_status,
        "results": url_results,
    }
