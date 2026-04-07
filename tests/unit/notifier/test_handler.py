"""notifier handler 統合テスト — SQSイベント → DynamoDB読み → 通知送信"""

import json
import os
from unittest.mock import MagicMock, patch, call

import boto3
import pytest
from moto import mock_aws


STACK_NAME = "TestStack"
SITES_TABLE = f"{STACK_NAME}-sites"
NOTIFICATIONS_TABLE = f"{STACK_NAME}-notifications"


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
    monkeypatch.setenv("NOTIFICATIONS_TABLE_NAME", NOTIFICATIONS_TABLE)
    monkeypatch.setenv("EMAIL_DOMAIN", "alive.osasi-cloud.com")
    monkeypatch.setenv("SES_REGION", "us-west-2")


def _create_tables(dynamodb):
    dynamodb.create_table(
        TableName=SITES_TABLE,
        KeySchema=[{"AttributeName": "site_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "site_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    dynamodb.create_table(
        TableName=NOTIFICATIONS_TABLE,
        KeySchema=[
            {"AttributeName": "site_id", "KeyType": "HASH"},
            {"AttributeName": "notification_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "site_id", "AttributeType": "S"},
            {"AttributeName": "notification_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _make_sqs_event(messages: list[dict]) -> dict:
    return {
        "Records": [
            {"body": json.dumps(msg)} for msg in messages
        ]
    }


def _seed_site(dynamodb, site_id: str = "site-001", site_name: str = "テストダム"):
    table = dynamodb.Table(SITES_TABLE)
    table.put_item(Item={
        "site_id": site_id,
        "site_name": site_name,
        "targets": [{"url": "https://example.com/data.png"}],
        "enabled": True,
    })


def _seed_notifications(dynamodb, site_id: str = "site-001"):
    table = dynamodb.Table(NOTIFICATIONS_TABLE)
    table.put_item(Item={
        "site_id": site_id,
        "notification_id": "notif-email-001",
        "type": "email",
        "destination": "admin@example.com",
        "mention": "",
        "message_template": "確認してください",
        "enabled": True,
    })
    table.put_item(Item={
        "site_id": site_id,
        "notification_id": "notif-slack-001",
        "type": "slack",
        "destination": "/web-alive/slack-webhook-url",
        "mention": "<!channel>",
        "message_template": "",
        "enabled": True,
    })


class TestHandler:
    @mock_aws
    def test_processes_sqs_event_and_sends_notifications(self):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        _create_tables(dynamodb)
        _seed_site(dynamodb)
        _seed_notifications(dynamodb)

        event = _make_sqs_event([{
            "site_id": "site-001",
            "site_name": "テストダム",
            "previous_status": "updated",
            "new_status": "not_updated",
            "trigger_url": "https://example.com/data.png",
            "checked_at": "2026-04-06T09:00:00+00:00",
        }])

        with patch("notifier.app.send_email") as mock_email, \
             patch("notifier.app.send_slack") as mock_slack:
            import notifier.app as notifier_app
            notifier_app._dynamodb = None
            notifier_app.handler(event, None)

            mock_email.assert_called_once_with(
                to_address="admin@example.com",
                site_name="テストダム",
                trigger_url="https://example.com/data.png",
                previous_status="updated",
                new_status="not_updated",
                last_checked_at="2026-04-06T09:00:00+00:00",
                message_template="確認してください",
            )
            mock_slack.assert_called_once_with(
                ssm_parameter_name="/web-alive/slack-webhook-url",
                mention="<!channel>",
                site_name="テストダム",
                trigger_url="https://example.com/data.png",
                previous_status="updated",
                new_status="not_updated",
                last_checked_at="2026-04-06T09:00:00+00:00",
            )

    @mock_aws
    def test_skips_disabled_notifications(self):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        _create_tables(dynamodb)
        _seed_site(dynamodb)

        table = dynamodb.Table(NOTIFICATIONS_TABLE)
        table.put_item(Item={
            "site_id": "site-001",
            "notification_id": "notif-disabled",
            "type": "email",
            "destination": "disabled@example.com",
            "mention": "",
            "message_template": "",
            "enabled": False,
        })

        event = _make_sqs_event([{
            "site_id": "site-001",
            "site_name": "テストダム",
            "previous_status": "updated",
            "new_status": "not_updated",
            "trigger_url": "https://example.com/data.png",
            "checked_at": "2026-04-06T09:00:00+00:00",
        }])

        with patch("notifier.app.send_email") as mock_email, \
             patch("notifier.app.send_slack") as mock_slack:
            import notifier.app as notifier_app
            notifier_app._dynamodb = None
            notifier_app.handler(event, None)

            mock_email.assert_not_called()
            mock_slack.assert_not_called()

    @mock_aws
    def test_handles_missing_site_gracefully(self):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        _create_tables(dynamodb)

        event = _make_sqs_event([{
            "site_id": "nonexistent",
            "site_name": "不明",
            "previous_status": "updated",
            "new_status": "not_updated",
            "trigger_url": "https://example.com",
            "checked_at": "2026-04-06T09:00:00+00:00",
        }])

        with patch("notifier.app.send_email") as mock_email, \
             patch("notifier.app.send_slack") as mock_slack:
            import notifier.app as notifier_app
            notifier_app._dynamodb = None
            notifier_app.handler(event, None)

            mock_email.assert_not_called()
            mock_slack.assert_not_called()

    @mock_aws
    def test_processes_multiple_sqs_records(self):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        _create_tables(dynamodb)
        _seed_site(dynamodb, "site-001", "ダムA")
        _seed_site(dynamodb, "site-002", "橋梁B")

        table = dynamodb.Table(NOTIFICATIONS_TABLE)
        table.put_item(Item={
            "site_id": "site-001",
            "notification_id": "n1",
            "type": "email",
            "destination": "a@example.com",
            "mention": "",
            "message_template": "",
            "enabled": True,
        })
        table.put_item(Item={
            "site_id": "site-002",
            "notification_id": "n2",
            "type": "email",
            "destination": "b@example.com",
            "mention": "",
            "message_template": "",
            "enabled": True,
        })

        event = _make_sqs_event([
            {
                "site_id": "site-001",
                "site_name": "ダムA",
                "previous_status": "updated",
                "new_status": "not_updated",
                "trigger_url": "https://example.com/a",
                "checked_at": "2026-04-06T09:00:00+00:00",
            },
            {
                "site_id": "site-002",
                "site_name": "橋梁B",
                "previous_status": "updated",
                "new_status": "error",
                "trigger_url": "https://example.com/b",
                "checked_at": "2026-04-06T09:00:00+00:00",
            },
        ])

        with patch("notifier.app.send_email") as mock_email, \
             patch("notifier.app.send_slack"):
            import notifier.app as notifier_app
            notifier_app._dynamodb = None
            notifier_app.handler(event, None)

            assert mock_email.call_count == 2

    @mock_aws
    def test_notification_failure_raises_for_sqs_retry(self):
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        _create_tables(dynamodb)
        _seed_site(dynamodb)
        _seed_notifications(dynamodb)

        event = _make_sqs_event([{
            "site_id": "site-001",
            "site_name": "テストダム",
            "previous_status": "updated",
            "new_status": "not_updated",
            "trigger_url": "https://example.com/data.png",
            "checked_at": "2026-04-06T09:00:00+00:00",
        }])

        with patch("notifier.app.send_email", side_effect=Exception("SES error")), \
             patch("notifier.app.send_slack"):
            import notifier.app as notifier_app
            notifier_app._dynamodb = None
            with pytest.raises(Exception, match="SES error"):
                notifier_app.handler(event, None)
