"""ハンドラー統合テスト（moto DynamoDB + mock HTTP）"""

import json
import os
from datetime import datetime, timezone
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


def _insert_site(dynamodb, site_id, targets, last_check_status=None, consecutive_miss_count=0, consecutive_threshold=3):
    table = dynamodb.Table(SITES_TABLE)
    table.put_item(Item={
        "site_id": site_id,
        "site_name": "テストサイト",
        "monitor_type": "url_check",
        "targets": targets,
        "schedule_start": "00:00",
        "schedule_interval_minutes": 60,
        "consecutive_threshold": consecutive_threshold,
        "enabled": True,
        "last_check_status": last_check_status,
        "last_checked_at": None,
        "consecutive_miss_count": consecutive_miss_count,
    })


class TestHandlerBasic:
    @mock_aws
    @patch("checker.app.fetch_url")
    def test_all_urls_updated(self, mock_fetch):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "site-001"
        _insert_site(dynamodb, site_id, [
            {"url": "http://example.com/page1.html"},
            {"url": "http://example.com/page2.html"},
        ], last_check_status="updated")

        mock_fetch.return_value = {
            "status_code": 200,
            "last_modified": "Thu, 02 Jan 2026 00:00:00 GMT",
            "etag": None,
            "content_hash": "newhash123",
        }

        from checker.app import handler
        result = handler({"site_id": site_id}, None)

        assert result["status"] == "completed"
        assert len(result["results"]) == 2
        for r in result["results"]:
            assert r["status"] == "updated"

        site = dynamodb.Table(SITES_TABLE).get_item(Key={"site_id": site_id})["Item"]
        assert site["last_check_status"] == "updated"
        assert site["consecutive_miss_count"] == 0

    @mock_aws
    @patch("checker.app.fetch_url")
    def test_url_not_updated(self, mock_fetch):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "site-002"
        _insert_site(dynamodb, site_id, [
            {"url": "http://example.com/page.html"},
        ], last_check_status="updated")

        check_results_table = dynamodb.Table(CHECK_RESULTS_TABLE)
        check_results_table.put_item(Item={
            "site_id": site_id,
            "checked_at#target_url": "2026-01-01T00:00:00+00:00#http://example.com/page.html",
            "status": "updated",
            "last_modified": "Thu, 01 Jan 2026 00:00:00 GMT",
            "etag": None,
            "content_hash": "samehash",
        })

        mock_fetch.return_value = {
            "status_code": 200,
            "last_modified": "Thu, 01 Jan 2026 00:00:00 GMT",
            "etag": None,
            "content_hash": "samehash",
        }

        from checker.app import handler
        result = handler({"site_id": site_id}, None)

        assert result["results"][0]["status"] == "not_updated"

        site = dynamodb.Table(SITES_TABLE).get_item(Key={"site_id": site_id})["Item"]
        assert site["last_check_status"] == "not_updated"
        assert site["consecutive_miss_count"] == 1


class TestStateChange:
    @mock_aws
    @patch("checker.app.fetch_url")
    def test_state_change_normal_to_abnormal(self, mock_fetch):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "site-003"
        _insert_site(dynamodb, site_id, [
            {"url": "http://example.com/page.html"},
        ], last_check_status="updated")

        check_results_table = dynamodb.Table(CHECK_RESULTS_TABLE)
        check_results_table.put_item(Item={
            "site_id": site_id,
            "checked_at#target_url": "2026-01-01T00:00:00+00:00#http://example.com/page.html",
            "status": "updated",
            "last_modified": "Thu, 01 Jan 2026 00:00:00 GMT",
            "etag": None,
            "content_hash": "samehash",
        })

        mock_fetch.return_value = {
            "status_code": 200,
            "last_modified": "Thu, 01 Jan 2026 00:00:00 GMT",
            "etag": None,
            "content_hash": "samehash",
        }

        from checker.app import handler
        result = handler({"site_id": site_id}, None)

        status_changes = dynamodb.Table(STATUS_CHANGES_TABLE).scan()["Items"]
        assert len(status_changes) == 1
        assert status_changes[0]["previous_status"] == "updated"
        assert status_changes[0]["new_status"] == "not_updated"

    @mock_aws
    @patch("checker.app.fetch_url")
    def test_state_change_abnormal_to_normal(self, mock_fetch):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "site-004"
        _insert_site(dynamodb, site_id, [
            {"url": "http://example.com/page.html"},
        ], last_check_status="not_updated", consecutive_miss_count=2)

        mock_fetch.return_value = {
            "status_code": 200,
            "last_modified": "Thu, 02 Jan 2026 00:00:00 GMT",
            "etag": None,
            "content_hash": "newhash",
        }

        from checker.app import handler
        result = handler({"site_id": site_id}, None)

        status_changes = dynamodb.Table(STATUS_CHANGES_TABLE).scan()["Items"]
        assert len(status_changes) == 1
        assert status_changes[0]["previous_status"] == "not_updated"
        assert status_changes[0]["new_status"] == "updated"

        site = dynamodb.Table(SITES_TABLE).get_item(Key={"site_id": site_id})["Item"]
        assert site["consecutive_miss_count"] == 0

    @mock_aws
    @patch("checker.app.fetch_url")
    def test_no_state_change_no_notification(self, mock_fetch):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "site-005"
        _insert_site(dynamodb, site_id, [
            {"url": "http://example.com/page.html"},
        ], last_check_status="updated")

        mock_fetch.return_value = {
            "status_code": 200,
            "last_modified": "Thu, 02 Jan 2026 00:00:00 GMT",
            "etag": None,
            "content_hash": "newhash",
        }

        from checker.app import handler
        result = handler({"site_id": site_id}, None)

        status_changes = dynamodb.Table(STATUS_CHANGES_TABLE).scan()["Items"]
        assert len(status_changes) == 0


class TestSqsNotification:
    @mock_aws
    @patch("checker.app.fetch_url")
    def test_sqs_message_sent_on_state_change(self, mock_fetch):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs_resource = boto3.resource("sqs", region_name="ap-northeast-1")
        queue = sqs_resource.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "site-006"
        _insert_site(dynamodb, site_id, [
            {"url": "http://example.com/page.html"},
        ], last_check_status="updated")

        check_results_table = dynamodb.Table(CHECK_RESULTS_TABLE)
        check_results_table.put_item(Item={
            "site_id": site_id,
            "checked_at#target_url": "2026-01-01T00:00:00+00:00#http://example.com/page.html",
            "status": "updated",
            "last_modified": "Thu, 01 Jan 2026 00:00:00 GMT",
            "etag": None,
            "content_hash": "samehash",
        })

        mock_fetch.return_value = {
            "status_code": 200,
            "last_modified": "Thu, 01 Jan 2026 00:00:00 GMT",
            "etag": None,
            "content_hash": "samehash",
        }

        from checker.app import handler
        handler({"site_id": site_id}, None)

        messages = queue.receive_messages(MaxNumberOfMessages=10)
        assert len(messages) == 1

        body = json.loads(messages[0].body)
        assert body["site_id"] == site_id
        assert body["previous_status"] == "updated"
        assert body["new_status"] == "not_updated"

    @mock_aws
    @patch("checker.app.fetch_url")
    def test_no_sqs_message_when_no_state_change(self, mock_fetch):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs_resource = boto3.resource("sqs", region_name="ap-northeast-1")
        queue = sqs_resource.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "site-007"
        _insert_site(dynamodb, site_id, [
            {"url": "http://example.com/page.html"},
        ], last_check_status="updated")

        mock_fetch.return_value = {
            "status_code": 200,
            "last_modified": "Thu, 02 Jan 2026 00:00:00 GMT",
            "etag": None,
            "content_hash": "newhash",
        }

        from checker.app import handler
        handler({"site_id": site_id}, None)

        messages = queue.receive_messages(MaxNumberOfMessages=10)
        assert len(messages) == 0


class TestErrorHandling:
    @mock_aws
    @patch("checker.app.fetch_url")
    def test_individual_url_error_does_not_affect_others(self, mock_fetch):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "site-008"
        _insert_site(dynamodb, site_id, [
            {"url": "http://example.com/good.html"},
            {"url": "http://example.com/bad.html"},
        ])

        def side_effect(url):
            if "bad" in url:
                raise ConnectionError("Connection refused")
            return {
                "status_code": 200,
                "last_modified": "Thu, 02 Jan 2026 00:00:00 GMT",
                "etag": None,
                "content_hash": "newhash",
            }

        mock_fetch.side_effect = side_effect

        from checker.app import handler
        result = handler({"site_id": site_id}, None)

        assert result["status"] == "completed"
        assert len(result["results"]) == 2

        good_result = [r for r in result["results"] if r["url"] == "http://example.com/good.html"][0]
        bad_result = [r for r in result["results"] if r["url"] == "http://example.com/bad.html"][0]

        assert good_result["status"] == "updated"
        assert bad_result["status"] == "error"

    @mock_aws
    @patch("checker.app.fetch_url")
    def test_error_status_recorded_in_check_results(self, mock_fetch):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "site-009"
        _insert_site(dynamodb, site_id, [
            {"url": "http://example.com/error.html"},
        ])

        mock_fetch.side_effect = ConnectionError("Timeout")

        from checker.app import handler
        result = handler({"site_id": site_id}, None)

        check_results = dynamodb.Table(CHECK_RESULTS_TABLE).query(
            KeyConditionExpression="site_id = :sid",
            ExpressionAttributeValues={":sid": site_id},
        )["Items"]

        assert len(check_results) == 1
        assert check_results[0]["status"] == "error"

    @mock_aws
    def test_site_not_found(self):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        from checker.app import handler
        result = handler({"site_id": "nonexistent"}, None)

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()


class TestOverallStatus:
    @mock_aws
    @patch("checker.app.fetch_url")
    def test_one_error_makes_overall_error(self, mock_fetch):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "site-010"
        _insert_site(dynamodb, site_id, [
            {"url": "http://example.com/good.html"},
            {"url": "http://example.com/bad.html"},
        ], last_check_status="updated")

        def side_effect(url):
            if "bad" in url:
                raise ConnectionError("fail")
            return {
                "status_code": 200,
                "last_modified": "Thu, 02 Jan 2026 00:00:00 GMT",
                "etag": None,
                "content_hash": "newhash",
            }

        mock_fetch.side_effect = side_effect

        from checker.app import handler
        handler({"site_id": site_id}, None)

        site = dynamodb.Table(SITES_TABLE).get_item(Key={"site_id": site_id})["Item"]
        assert site["last_check_status"] == "error"

    @mock_aws
    @patch("checker.app.fetch_url")
    def test_one_not_updated_makes_overall_not_updated(self, mock_fetch):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "site-011"
        _insert_site(dynamodb, site_id, [
            {"url": "http://example.com/page1.html"},
            {"url": "http://example.com/page2.html"},
        ], last_check_status="updated")

        check_results_table = dynamodb.Table(CHECK_RESULTS_TABLE)
        check_results_table.put_item(Item={
            "site_id": site_id,
            "checked_at#target_url": "2026-01-01T00:00:00+00:00#http://example.com/page2.html",
            "status": "updated",
            "last_modified": "Thu, 01 Jan 2026 00:00:00 GMT",
            "etag": None,
            "content_hash": "samehash",
        })

        call_count = 0

        def side_effect(url):
            nonlocal call_count
            call_count += 1
            if "page1" in url:
                return {
                    "status_code": 200,
                    "last_modified": "Thu, 02 Jan 2026 00:00:00 GMT",
                    "etag": None,
                    "content_hash": "newhash",
                }
            return {
                "status_code": 200,
                "last_modified": "Thu, 01 Jan 2026 00:00:00 GMT",
                "etag": None,
                "content_hash": "samehash",
            }

        mock_fetch.side_effect = side_effect

        from checker.app import handler
        handler({"site_id": site_id}, None)

        site = dynamodb.Table(SITES_TABLE).get_item(Key={"site_id": site_id})["Item"]
        assert site["last_check_status"] == "not_updated"


class TestCheckResultsRecording:
    @mock_aws
    @patch("checker.app.fetch_url")
    def test_check_result_has_ttl(self, mock_fetch):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "site-012"
        _insert_site(dynamodb, site_id, [
            {"url": "http://example.com/page.html"},
        ])

        mock_fetch.return_value = {
            "status_code": 200,
            "last_modified": "Thu, 02 Jan 2026 00:00:00 GMT",
            "etag": None,
            "content_hash": "hash123",
        }

        from checker.app import handler
        handler({"site_id": site_id}, None)

        results = dynamodb.Table(CHECK_RESULTS_TABLE).query(
            KeyConditionExpression="site_id = :sid",
            ExpressionAttributeValues={":sid": site_id},
        )["Items"]

        assert len(results) == 1
        assert "ttl" in results[0]
        assert results[0]["ttl"] > 0

    @mock_aws
    @patch("checker.app.fetch_url")
    def test_status_change_has_ttl(self, mock_fetch):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        sqs = boto3.resource("sqs", region_name="ap-northeast-1")
        sqs.create_queue(QueueName="test-notification-queue")
        _create_tables(dynamodb)

        site_id = "site-013"
        _insert_site(dynamodb, site_id, [
            {"url": "http://example.com/page.html"},
        ], last_check_status="updated")

        check_results_table = dynamodb.Table(CHECK_RESULTS_TABLE)
        check_results_table.put_item(Item={
            "site_id": site_id,
            "checked_at#target_url": "2026-01-01T00:00:00+00:00#http://example.com/page.html",
            "status": "updated",
            "last_modified": "Thu, 01 Jan 2026 00:00:00 GMT",
            "etag": None,
            "content_hash": "samehash",
        })

        mock_fetch.return_value = {
            "status_code": 200,
            "last_modified": "Thu, 01 Jan 2026 00:00:00 GMT",
            "etag": None,
            "content_hash": "samehash",
        }

        from checker.app import handler
        handler({"site_id": site_id}, None)

        changes = dynamodb.Table(STATUS_CHANGES_TABLE).scan()["Items"]
        assert len(changes) == 1
        assert "ttl" in changes[0]
        assert changes[0]["ttl"] > 0
