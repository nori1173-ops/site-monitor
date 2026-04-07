"""統合テスト: test-check, test-notify, status-changes, cloudwatch/log-groups, OPTIONS

app.py のカバレッジ低下部分を重点的にテストする。
"""

import json
from unittest.mock import patch, MagicMock

import boto3
import pytest
from moto import mock_aws

from tests.integration.api.conftest import make_api_event


class TestOptionsEndpoint:
    """OPTIONS (CORS preflight) のテスト"""

    @pytest.fixture(autouse=True)
    def setup(self, dynamodb_tables):
        self.dynamodb = dynamodb_tables
        self.scheduler_patcher = patch(
            "api.helpers.scheduler.get_scheduler_client",
            return_value=MagicMock(),
        )
        self.scheduler_patcher.start()
        yield
        self.scheduler_patcher.stop()

    def _import_handler(self):
        from api.app import handler
        return handler

    def test_options_returns_200(self):
        handler = self._import_handler()
        event = {
            "httpMethod": "OPTIONS",
            "path": "/sites",
            "headers": {},
            "pathParameters": None,
            "queryStringParameters": None,
            "requestContext": {},
            "body": None,
        }
        response = handler(event, None)
        assert response["statusCode"] == 200

    def test_unknown_route_returns_404(self):
        handler = self._import_handler()
        event = {
            "httpMethod": "GET",
            "path": "/nonexistent",
            "headers": {},
            "pathParameters": None,
            "queryStringParameters": None,
            "requestContext": {
                "authorizer": {"claims": {"email": "user@osasi.co.jp"}},
            },
            "body": None,
        }
        response = handler(event, None)
        assert response["statusCode"] == 404


class TestStatusChangesEndpoint:
    """GET /sites/{site_id}/status-changes のテスト"""

    @pytest.fixture(autouse=True)
    def setup(self, dynamodb_tables):
        self.dynamodb = dynamodb_tables
        self.mock_scheduler = MagicMock()
        self.scheduler_patcher = patch(
            "api.helpers.scheduler.get_scheduler_client",
            return_value=self.mock_scheduler,
        )
        self.scheduler_patcher.start()
        self.mock_scheduler.create_schedule.return_value = {
            "ScheduleArn": "arn:aws:scheduler:ap-northeast-1:123456789012:schedule/default/test"
        }
        yield
        self.scheduler_patcher.stop()

    def _import_handler(self):
        from api.app import handler
        return handler

    def test_get_status_changes_empty(self):
        handler = self._import_handler()
        event = make_api_event(
            "GET", "/sites/some-id/status-changes",
            path_parameters={"site_id": "some-id"},
        )
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["data"] == []

    def test_get_status_changes_with_data(self):
        handler = self._import_handler()
        table = self.dynamodb.Table("TestStack-status_changes")
        table.put_item(Item={
            "site_id": "test-site",
            "changed_at": "2026-04-06T10:00:00Z",
            "previous_status": "updated",
            "new_status": "not_updated",
            "trigger_url": "https://example.com/data.png",
        })
        table.put_item(Item={
            "site_id": "test-site",
            "changed_at": "2026-04-06T11:00:00Z",
            "previous_status": "not_updated",
            "new_status": "updated",
            "trigger_url": "https://example.com/data.png",
        })

        event = make_api_event(
            "GET", "/sites/test-site/status-changes",
            path_parameters={"site_id": "test-site"},
        )
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["data"]) == 2


class TestTestCheckEndpoint:
    """POST /sites/{site_id}/test-check のテスト"""

    @pytest.fixture(autouse=True)
    def setup(self, dynamodb_tables):
        self.dynamodb = dynamodb_tables
        self.mock_scheduler = MagicMock()
        self.scheduler_patcher = patch(
            "api.helpers.scheduler.get_scheduler_client",
            return_value=self.mock_scheduler,
        )
        self.scheduler_patcher.start()
        self.mock_scheduler.create_schedule.return_value = {
            "ScheduleArn": "arn:aws:scheduler:ap-northeast-1:123456789012:schedule/default/test"
        }
        yield
        self.scheduler_patcher.stop()

    def _import_handler(self):
        from api.app import handler
        return handler

    def _create_site(self, handler) -> str:
        body = {
            "site_name": "テストダム",
            "monitor_type": "url_check",
            "targets": ["https://example.com/data/latest.png"],
            "schedule_start": "00:20",
            "schedule_interval_minutes": 60,
            "consecutive_threshold": 3,
            "enabled": True,
        }
        event = make_api_event("POST", "/sites", body=body)
        response = handler(event, None)
        return json.loads(response["body"])["data"]["site_id"]

    def test_test_check_site_not_found(self):
        handler = self._import_handler()
        event = make_api_event(
            "POST", "/sites/nonexistent/test-check",
            path_parameters={"site_id": "nonexistent"},
        )
        response = handler(event, None)
        assert response["statusCode"] == 404

    def test_test_check_no_checker_arn(self, monkeypatch):
        handler = self._import_handler()
        site_id = self._create_site(handler)
        monkeypatch.setenv("CHECKER_FUNCTION_ARN", "")

        event = make_api_event(
            "POST", f"/sites/{site_id}/test-check",
            path_parameters={"site_id": site_id},
        )
        response = handler(event, None)
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "not configured" in body["error"]

    @patch("boto3.client")
    def test_test_check_success(self, mock_boto_client):
        handler = self._import_handler()
        site_id = self._create_site(handler)

        mock_lambda = MagicMock()
        mock_payload = MagicMock()
        mock_payload.read.return_value = json.dumps({"status": "updated"}).encode()
        mock_lambda.invoke.return_value = {"Payload": mock_payload}

        def client_factory(service, **kwargs):
            if service == "lambda":
                return mock_lambda
            return MagicMock()

        mock_boto_client.side_effect = client_factory

        event = make_api_event(
            "POST", f"/sites/{site_id}/test-check",
            path_parameters={"site_id": site_id},
        )
        response = handler(event, None)
        assert response["statusCode"] == 200

    @patch("boto3.client")
    def test_test_check_lambda_invoke_failure(self, mock_boto_client):
        handler = self._import_handler()
        site_id = self._create_site(handler)

        def client_factory(service, **kwargs):
            if service == "lambda":
                mock_lambda = MagicMock()
                mock_lambda.invoke.side_effect = Exception("Lambda invocation error")
                return mock_lambda
            return MagicMock()

        mock_boto_client.side_effect = client_factory

        event = make_api_event(
            "POST", f"/sites/{site_id}/test-check",
            path_parameters={"site_id": site_id},
        )
        response = handler(event, None)
        assert response["statusCode"] == 500


class TestTestNotifyEndpoint:
    """POST /sites/{site_id}/test-notify のテスト"""

    @pytest.fixture(autouse=True)
    def setup(self, dynamodb_tables):
        self.dynamodb = dynamodb_tables
        self.mock_scheduler = MagicMock()
        self.scheduler_patcher = patch(
            "api.helpers.scheduler.get_scheduler_client",
            return_value=self.mock_scheduler,
        )
        self.scheduler_patcher.start()
        self.mock_scheduler.create_schedule.return_value = {
            "ScheduleArn": "arn:aws:scheduler:ap-northeast-1:123456789012:schedule/default/test"
        }
        yield
        self.scheduler_patcher.stop()

    def _import_handler(self):
        from api.app import handler
        return handler

    def _create_site(self, handler) -> str:
        body = {
            "site_name": "テストダム",
            "monitor_type": "url_check",
            "targets": ["https://example.com/data/latest.png"],
            "schedule_start": "00:20",
            "schedule_interval_minutes": 60,
            "consecutive_threshold": 3,
            "enabled": True,
        }
        event = make_api_event("POST", "/sites", body=body)
        response = handler(event, None)
        return json.loads(response["body"])["data"]["site_id"]

    def _add_notification(self, handler, site_id: str, notif_type: str = "email", destination: str = "test@osasi.co.jp"):
        event = make_api_event(
            "POST", f"/sites/{site_id}/notifications",
            path_parameters={"site_id": site_id},
            body={
                "type": notif_type,
                "destination": destination,
                "enabled": True,
            },
        )
        return handler(event, None)

    def test_test_notify_site_not_found(self):
        handler = self._import_handler()
        event = make_api_event(
            "POST", "/sites/nonexistent/test-notify",
            path_parameters={"site_id": "nonexistent"},
        )
        response = handler(event, None)
        assert response["statusCode"] == 404

    def test_test_notify_no_notifications(self):
        handler = self._import_handler()
        site_id = self._create_site(handler)

        event = make_api_event(
            "POST", f"/sites/{site_id}/test-notify",
            path_parameters={"site_id": site_id},
        )
        response = handler(event, None)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "通知先が設定されていません" in body["error"]

    @patch("boto3.client")
    def test_test_notify_email_success(self, mock_boto_client):
        handler = self._import_handler()
        site_id = self._create_site(handler)
        self._add_notification(handler, site_id, "email", "alert@osasi.co.jp")

        mock_ses = MagicMock()

        def client_factory(service, **kwargs):
            if service == "ses":
                return mock_ses
            return MagicMock()

        mock_boto_client.side_effect = client_factory

        event = make_api_event(
            "POST", f"/sites/{site_id}/test-notify",
            path_parameters={"site_id": site_id},
        )
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["data"]["results"][0]["status"] == "sent"

    @patch("boto3.client")
    def test_test_notify_email_failure(self, mock_boto_client):
        handler = self._import_handler()
        site_id = self._create_site(handler)
        self._add_notification(handler, site_id, "email", "alert@osasi.co.jp")

        mock_ses = MagicMock()
        mock_ses.send_email.side_effect = Exception("SES error")

        def client_factory(service, **kwargs):
            if service == "ses":
                return mock_ses
            return MagicMock()

        mock_boto_client.side_effect = client_factory

        event = make_api_event(
            "POST", f"/sites/{site_id}/test-notify",
            path_parameters={"site_id": site_id},
        )
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["data"]["results"][0]["status"] == "failed"

    @patch("boto3.client")
    def test_test_notify_slack_success(self, mock_boto_client):
        handler = self._import_handler()
        site_id = self._create_site(handler)
        self._add_notification(handler, site_id, "slack", "/web-alive/webhook-url")

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://hooks.slack.com/test"}
        }

        def client_factory(service, **kwargs):
            if service == "ssm":
                return mock_ssm
            return MagicMock()

        mock_boto_client.side_effect = client_factory

        import requests as req_module
        with patch.object(req_module, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            event = make_api_event(
                "POST", f"/sites/{site_id}/test-notify",
                path_parameters={"site_id": site_id},
            )
            response = handler(event, None)
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["data"]["results"][0]["status"] == "sent"

    def test_test_notify_disabled_notification_skipped(self):
        handler = self._import_handler()
        site_id = self._create_site(handler)

        notif_table = self.dynamodb.Table("TestStack-notifications")
        notif_table.put_item(Item={
            "site_id": site_id,
            "notification_id": "notif-disabled",
            "type": "email",
            "destination": "alert@osasi.co.jp",
            "enabled": False,
        })

        event = make_api_event(
            "POST", f"/sites/{site_id}/test-notify",
            path_parameters={"site_id": site_id},
        )
        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["data"]["results"] == []


class TestCloudWatchLogGroupsEndpoint:
    """GET /cloudwatch/log-groups のテスト"""

    @pytest.fixture(autouse=True)
    def setup(self, dynamodb_tables):
        self.dynamodb = dynamodb_tables
        self.scheduler_patcher = patch(
            "api.helpers.scheduler.get_scheduler_client",
            return_value=MagicMock(),
        )
        self.scheduler_patcher.start()
        yield
        self.scheduler_patcher.stop()

    def _import_handler(self):
        from api.app import handler
        return handler

    @patch("boto3.client")
    def test_get_log_groups_success(self, mock_boto_client):
        handler = self._import_handler()

        mock_logs = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"logGroups": [
                {"logGroupName": "/aws/lambda/test-function", "storedBytes": 1024},
                {"logGroupName": "/aws/lambda/other-function", "storedBytes": 2048},
            ]}
        ]
        mock_logs.get_paginator.return_value = mock_paginator

        def client_factory(service, **kwargs):
            if service == "logs":
                return mock_logs
            return MagicMock()

        mock_boto_client.side_effect = client_factory

        event = make_api_event("GET", "/cloudwatch/log-groups")
        response = handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["data"]) == 2
        assert body["data"][0]["logGroupName"] == "/aws/lambda/test-function"

    @patch("boto3.client")
    def test_get_log_groups_failure(self, mock_boto_client):
        handler = self._import_handler()

        def client_factory(service, **kwargs):
            if service == "logs":
                mock_logs = MagicMock()
                mock_logs.get_paginator.side_effect = Exception("CloudWatch error")
                return mock_logs
            return MagicMock()

        mock_boto_client.side_effect = client_factory

        event = make_api_event("GET", "/cloudwatch/log-groups")
        response = handler(event, None)

        assert response["statusCode"] == 500


class TestHandlerEdgeCases:
    """handler 関数のエッジケーステスト"""

    @pytest.fixture(autouse=True)
    def setup(self, dynamodb_tables):
        self.dynamodb = dynamodb_tables
        self.scheduler_patcher = patch(
            "api.helpers.scheduler.get_scheduler_client",
            return_value=MagicMock(),
        )
        self.scheduler_patcher.start()
        yield
        self.scheduler_patcher.stop()

    def _import_handler(self):
        from api.app import handler
        return handler

    def test_handler_with_null_path_parameters(self):
        handler = self._import_handler()
        event = {
            "httpMethod": "GET",
            "path": "/sites",
            "headers": {},
            "pathParameters": None,
            "queryStringParameters": None,
            "requestContext": {
                "authorizer": {"claims": {"email": "user@osasi.co.jp"}},
            },
            "body": None,
        }
        response = handler(event, None)
        assert response["statusCode"] == 200

    def test_handler_put_notification_not_found(self):
        handler = self._import_handler()
        event = make_api_event(
            "PUT", "/sites/some-site/notifications/nonexistent",
            path_parameters={"site_id": "some-site", "notification_id": "nonexistent"},
            body={"type": "email", "destination": "a@osasi.co.jp"},
        )
        response = handler(event, None)
        assert response["statusCode"] == 404
