"""CloudWatch Logs Insights クエリ実行モジュール"""

import time
from datetime import datetime, timezone, timedelta

import boto3

POLL_INTERVAL_SEC = 1
MAX_POLL_ATTEMPTS = 60


def run_query(
    log_group: str,
    message_filter: str,
    json_search_word: str,
    search_period_minutes: int,
) -> dict:
    """Insights クエリを実行し、ヒット件数と最終ヒット日時を返す。

    Returns:
        dict with keys:
            status: "success" | "error"
            hit_count: int
            latest_timestamp: str | None
            message: str (error時のみ)
    """
    try:
        client = boto3.client("logs")
        now = datetime.now(timezone.utc)
        start_time = int((now - timedelta(minutes=search_period_minutes)).timestamp())
        end_time = int(now.timestamp())

        query_string = (
            "fields @timestamp, @message"
            f" | filter @message like /{message_filter}/"
            f" | filter @message like /{json_search_word}/"
            " | sort @timestamp desc"
        )

        response = client.start_query(
            logGroupName=log_group,
            startTime=start_time,
            endTime=end_time,
            queryString=query_string,
        )
        query_id = response["queryId"]

        for _ in range(MAX_POLL_ATTEMPTS):
            result = client.get_query_results(queryId=query_id)
            status = result["status"]

            if status == "Complete":
                results = result.get("results", [])
                hit_count = len(results)
                latest_timestamp = None
                if results:
                    for field in results[0]:
                        if field["field"] == "@timestamp":
                            latest_timestamp = field["value"]
                            break

                return {
                    "status": "success",
                    "hit_count": hit_count,
                    "latest_timestamp": latest_timestamp,
                }

            if status in ("Failed", "Cancelled"):
                return {
                    "status": "error",
                    "message": f"Query {status}",
                    "hit_count": 0,
                    "latest_timestamp": None,
                }

            time.sleep(POLL_INTERVAL_SEC)

        return {
            "status": "error",
            "message": "Query timed out",
            "hit_count": 0,
            "latest_timestamp": None,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "hit_count": 0,
            "latest_timestamp": None,
        }
