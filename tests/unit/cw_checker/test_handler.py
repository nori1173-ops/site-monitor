"""CWログ監視 Lambda ハンドラー統合テスト（moto DynamoDB + SQS + mock Insights）"""

import json
import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws


STACK_NAME = "TestStack"
SITES_TABLE = f"{STACK_NAME}-sites"
CHECK_RESULTS_TABLE = f"{STACK_NAME}-check_results"
STATUS_CHANGES_TABLE = f"{STACK_NAME}-status_changes"
NOTIFICATION_QUEUE_URL = "https://sqs.ap-northeast-1.amazonaws.com/123456789012/test-notification-queue"


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-northeast-1")
    monkeypatch.setenv("STACK_NAME", STACK_NAME)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("SITES_TABLE_NAME", SITES_TABLE)
    monkeypatch.setenv("CHECK_RESULTS_TABLE_NAME", CHECK_RESULTS_TABLE)
    monkeypatch.setenv("STATUS_CHANGES_TABLE_NAME", STATUS_CHANGES_TABLE)
    monkeypatch.setenv("NOTIFICATION_QUEUE_URL", NOTIFICATION_QUEUE_URL)


def _create_tables(dynamodb):
    dynamodb.create_table(
        TableName=SITES_TABLE,
        KeySchema=[{"AttributeName": "site_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "site_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    dynamodb.create_table(
        TableName=CHECK_RESULTS_TABLE,
        KeySchema=[
            {"AttributeName": "site_id", "KeyType": "HASH"},
            {"AttributeName": "checked_at#target_url", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "site_id", "AttributeType": "S"},
            {"AttributeName": "checked_at#target_url", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    dynamodb.create_table(
        TableName=STATUS_CHANGES_TABLE,
        KeySchema=[
            {"AttributeName": "site_id", "KeyType": "HASH"},
            {"AttributeName": "changed_at", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "site_id", "AttributeType": "S"},
            {"AttributeName": "changed_at", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _insert_cw_site(
    dynamodb,
    site_id,
    targets,
    last_check_status=None,
    consecutive_miss_count=0,
):
    table = dynamodb.Table(SITES_TABLE)
    table.put_item(Item={
        "site_id": site_id,
        "site_name": "CWテストサイト",
        "monitor_type": "cloudwatch_log",
        "targets": targets,
        "schedule_start": "00:00",
        "schedule_interval_minutes": 60,
        "consecutive_threshold": 3,
        "enabled": True,
        "last_check_status": last_check_status,
        "last_checked_at": None,
        "consecutive_miss_count": consecutive_miss_count,
    })


def _build_sqs_event(site_id: str) -> dict:
    return {
        "Records": [
            {
                "messageId": "msg-001",
                "body": json.dumps({"site_id": site_id}),
                "receiptHandle": "handle-001",
            }
        ]
    }


class TestCwCheckerBasic:
    @mock_aws
    @patch("cw_checker.app.run_query")
    def test_log_found_status_updated(self, mock_run_query):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "cw-site-001"
        _insert_cw_site(dynamodb, site_id, [
            {
                "log_group": "TestLogGroup",
                "message_filter": "リクエストを送信します。",
                "json_search_word": '"account": "10206721"',
                "search_period_minutes": 60,
            },
        ])

        mock_run_query.return_value = {
            "status": "success",
            "hit_count": 5,
            "latest_timestamp": "2026-04-06 09:00:00.000",
        }

        from cw_checker.app import handler
        result = handler(_build_sqs_event(site_id), None)

        assert result["status"] == "completed"
        assert result["results"][0]["check_status"] == "updated"

        site = dynamodb.Table(SITES_TABLE).get_item(Key={"site_id": site_id})["Item"]
        assert site["last_check_status"] == "updated"
        assert site["consecutive_miss_count"] == 0

    @mock_aws
    @patch("cw_checker.app.run_query")
    def test_log_not_found_status_not_updated(self, mock_run_query):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "cw-site-002"
        _insert_cw_site(dynamodb, site_id, [
            {
                "log_group": "TestLogGroup",
                "message_filter": "filter",
                "json_search_word": "word",
                "search_period_minutes": 60,
            },
        ], last_check_status="updated")

        mock_run_query.return_value = {
            "status": "success",
            "hit_count": 0,
            "latest_timestamp": None,
        }

        from cw_checker.app import handler
        result = handler(_build_sqs_event(site_id), None)

        assert result["results"][0]["check_status"] == "not_updated"

        site = dynamodb.Table(SITES_TABLE).get_item(Key={"site_id": site_id})["Item"]
        assert site["last_check_status"] == "not_updated"
        assert site["consecutive_miss_count"] == 1

    @mock_aws
    @patch("cw_checker.app.run_query")
    def test_query_error_status_error(self, mock_run_query):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "cw-site-003"
        _insert_cw_site(dynamodb, site_id, [
            {
                "log_group": "TestLogGroup",
                "message_filter": "filter",
                "json_search_word": "word",
                "search_period_minutes": 60,
            },
        ])

        mock_run_query.return_value = {
            "status": "error",
            "message": "Query failed",
            "hit_count": 0,
            "latest_timestamp": None,
        }

        from cw_checker.app import handler
        result = handler(_build_sqs_event(site_id), None)

        assert result["results"][0]["check_status"] == "error"


class TestCwCheckerStateChange:
    @mock_aws
    @patch("cw_checker.app.run_query")
    def test_state_change_triggers_notification(self, mock_run_query):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs_resource = boto3.resource("sqs", region_name="ap-northeast-1")
        queue = sqs_resource.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "cw-site-004"
        _insert_cw_site(dynamodb, site_id, [
            {
                "log_group": "TestLogGroup",
                "message_filter": "filter",
                "json_search_word": "word",
                "search_period_minutes": 60,
            },
        ], last_check_status="updated")

        mock_run_query.return_value = {
            "status": "success",
            "hit_count": 0,
            "latest_timestamp": None,
        }

        from cw_checker.app import handler
        handler(_build_sqs_event(site_id), None)

        status_changes = dynamodb.Table(STATUS_CHANGES_TABLE).scan()["Items"]
        assert len(status_changes) == 1
        assert status_changes[0]["previous_status"] == "updated"
        assert status_changes[0]["new_status"] == "not_updated"

        messages = queue.receive_messages(MaxNumberOfMessages=10)
        assert len(messages) == 1
        body = json.loads(messages[0].body)
        assert body["site_id"] == site_id
        assert body["previous_status"] == "updated"
        assert body["new_status"] == "not_updated"

    @mock_aws
    @patch("cw_checker.app.run_query")
    def test_no_state_change_no_notification(self, mock_run_query):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs_resource = boto3.resource("sqs", region_name="ap-northeast-1")
        queue = sqs_resource.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "cw-site-005"
        _insert_cw_site(dynamodb, site_id, [
            {
                "log_group": "TestLogGroup",
                "message_filter": "filter",
                "json_search_word": "word",
                "search_period_minutes": 60,
            },
        ], last_check_status="updated")

        mock_run_query.return_value = {
            "status": "success",
            "hit_count": 3,
            "latest_timestamp": "2026-04-06 09:00:00.000",
        }

        from cw_checker.app import handler
        handler(_build_sqs_event(site_id), None)

        status_changes = dynamodb.Table(STATUS_CHANGES_TABLE).scan()["Items"]
        assert len(status_changes) == 0

        messages = queue.receive_messages(MaxNumberOfMessages=10)
        assert len(messages) == 0

    @mock_aws
    @patch("cw_checker.app.run_query")
    def test_recovery_from_not_updated_to_updated(self, mock_run_query):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs_resource = boto3.resource("sqs", region_name="ap-northeast-1")
        queue = sqs_resource.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "cw-site-006"
        _insert_cw_site(dynamodb, site_id, [
            {
                "log_group": "TestLogGroup",
                "message_filter": "filter",
                "json_search_word": "word",
                "search_period_minutes": 60,
            },
        ], last_check_status="not_updated", consecutive_miss_count=5)

        mock_run_query.return_value = {
            "status": "success",
            "hit_count": 2,
            "latest_timestamp": "2026-04-06 10:00:00.000",
        }

        from cw_checker.app import handler
        handler(_build_sqs_event(site_id), None)

        site = dynamodb.Table(SITES_TABLE).get_item(Key={"site_id": site_id})["Item"]
        assert site["last_check_status"] == "updated"
        assert site["consecutive_miss_count"] == 0

        status_changes = dynamodb.Table(STATUS_CHANGES_TABLE).scan()["Items"]
        assert len(status_changes) == 1
        assert status_changes[0]["new_status"] == "updated"


class TestCwCheckerCheckResults:
    @mock_aws
    @patch("cw_checker.app.run_query")
    def test_check_result_recorded_with_ttl(self, mock_run_query):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "cw-site-007"
        _insert_cw_site(dynamodb, site_id, [
            {
                "log_group": "TestLogGroup",
                "message_filter": "filter",
                "json_search_word": "word",
                "search_period_minutes": 60,
            },
        ])

        mock_run_query.return_value = {
            "status": "success",
            "hit_count": 3,
            "latest_timestamp": "2026-04-06 09:00:00.000",
        }

        from cw_checker.app import handler
        handler(_build_sqs_event(site_id), None)

        results = dynamodb.Table(CHECK_RESULTS_TABLE).query(
            KeyConditionExpression="site_id = :sid",
            ExpressionAttributeValues={":sid": site_id},
        )["Items"]

        assert len(results) == 1
        assert results[0]["status"] == "updated"
        assert "ttl" in results[0]
        assert results[0]["ttl"] > 0
        assert "TestLogGroup" in results[0]["checked_at#target_url"]


class TestCwCheckerEdgeCases:
    @mock_aws
    @patch("cw_checker.app.run_query")
    def test_site_not_found(self, mock_run_query):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        from cw_checker.app import handler
        result = handler(_build_sqs_event("nonexistent"), None)

        assert result["status"] == "error"

    @mock_aws
    @patch("cw_checker.app.run_query")
    def test_multiple_targets(self, mock_run_query):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "cw-site-008"
        _insert_cw_site(dynamodb, site_id, [
            {
                "log_group": "LogGroup1",
                "message_filter": "filter1",
                "json_search_word": "word1",
                "search_period_minutes": 60,
            },
            {
                "log_group": "LogGroup2",
                "message_filter": "filter2",
                "json_search_word": "word2",
                "search_period_minutes": 30,
            },
        ])

        mock_run_query.side_effect = [
            {"status": "success", "hit_count": 5, "latest_timestamp": "2026-04-06 09:00:00.000"},
            {"status": "success", "hit_count": 0, "latest_timestamp": None},
        ]

        from cw_checker.app import handler
        result = handler(_build_sqs_event(site_id), None)

        assert result["status"] == "completed"
        assert len(result["results"]) == 2
        assert result["overall_status"] == "not_updated"

    @mock_aws
    def test_invalid_sqs_message(self):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        from cw_checker.app import handler

        event = {
            "Records": [
                {
                    "messageId": "msg-bad",
                    "body": "not json",
                    "receiptHandle": "handle-bad",
                }
            ]
        }
        result = handler(event, None)
        assert result["status"] == "error"

    @mock_aws
    @patch("cw_checker.app.run_query")
    def test_consecutive_miss_increments(self, mock_run_query):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "cw-site-009"
        _insert_cw_site(dynamodb, site_id, [
            {
                "log_group": "TestLogGroup",
                "message_filter": "filter",
                "json_search_word": "word",
                "search_period_minutes": 60,
            },
        ], last_check_status="not_updated", consecutive_miss_count=3)

        mock_run_query.return_value = {
            "status": "success",
            "hit_count": 0,
            "latest_timestamp": None,
        }

        from cw_checker.app import handler
        handler(_build_sqs_event(site_id), None)

        site = dynamodb.Table(SITES_TABLE).get_item(Key={"site_id": site_id})["Item"]
        assert site["consecutive_miss_count"] == 4
