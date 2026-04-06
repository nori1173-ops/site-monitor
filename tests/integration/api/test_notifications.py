import json
from unittest.mock import patch, MagicMock

import pytest

from tests.integration.api.conftest import make_api_event


class TestNotificationsCRUD:
    """notifications CRUD 統合テスト (moto DynamoDB)"""

    @pytest.fixture(autouse=True)
    def setup(self, dynamodb_tables):
        self.dynamodb = dynamodb_tables
        self.mock_scheduler = MagicMock()
        self.scheduler_patcher = patch(
            "api.utils.scheduler.get_scheduler_client",
            return_value=self.mock_scheduler,
        )
        self.scheduler_patcher.start()
        self.mock_scheduler.create_schedule.return_value = {
            "ScheduleArn": "arn:aws:scheduler:ap-northeast-1:123456789012:schedule/default/test-schedule"
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

    def test_post_notification(self):
        handler = self._import_handler()
        site_id = self._create_site(handler)

        event = make_api_event(
            "POST", f"/sites/{site_id}/notifications",
            path_parameters={"site_id": site_id},
            body={
                "type": "email",
                "destination": "alert@osasi.co.jp",
                "message_template": "欠測検知: {site_name}",
                "enabled": True,
            },
        )
        response = handler(event, None)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert body["success"] is True
        assert "notification_id" in body["data"]
        assert body["data"]["type"] == "email"
        assert body["data"]["destination"] == "alert@osasi.co.jp"

    def test_get_notifications(self):
        handler = self._import_handler()
        site_id = self._create_site(handler)

        for dest in ["a@osasi.co.jp", "b@osasi.co.jp"]:
            event = make_api_event(
                "POST", f"/sites/{site_id}/notifications",
                path_parameters={"site_id": site_id},
                body={
                    "type": "email",
                    "destination": dest,
                    "enabled": True,
                },
            )
            handler(event, None)

        event = make_api_event(
            "GET", f"/sites/{site_id}/notifications",
            path_parameters={"site_id": site_id},
        )
        response = handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["data"]) == 2

    def test_put_notification(self):
        handler = self._import_handler()
        site_id = self._create_site(handler)

        create_event = make_api_event(
            "POST", f"/sites/{site_id}/notifications",
            path_parameters={"site_id": site_id},
            body={
                "type": "email",
                "destination": "old@osasi.co.jp",
                "enabled": True,
            },
        )
        create_resp = handler(create_event, None)
        nid = json.loads(create_resp["body"])["data"]["notification_id"]

        update_event = make_api_event(
            "PUT", f"/sites/{site_id}/notifications/{nid}",
            path_parameters={"site_id": site_id, "notification_id": nid},
            body={
                "type": "email",
                "destination": "new@osasi.co.jp",
                "enabled": False,
            },
        )
        response = handler(update_event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["data"]["destination"] == "new@osasi.co.jp"
        assert body["data"]["enabled"] is False

    def test_delete_notification(self):
        handler = self._import_handler()
        site_id = self._create_site(handler)

        create_event = make_api_event(
            "POST", f"/sites/{site_id}/notifications",
            path_parameters={"site_id": site_id},
            body={
                "type": "slack",
                "destination": "/web-alive-monitoring/slack-webhook",
                "mention": "@channel",
                "enabled": True,
            },
        )
        create_resp = handler(create_event, None)
        nid = json.loads(create_resp["body"])["data"]["notification_id"]

        delete_event = make_api_event(
            "DELETE", f"/sites/{site_id}/notifications/{nid}",
            path_parameters={"site_id": site_id, "notification_id": nid},
        )
        response = handler(delete_event, None)

        assert response["statusCode"] == 200

        table = self.dynamodb.Table("TestStack-notifications")
        result = table.get_item(Key={"site_id": site_id, "notification_id": nid})
        assert "Item" not in result

    def test_post_notification_for_nonexistent_site(self):
        handler = self._import_handler()

        event = make_api_event(
            "POST", "/sites/nonexistent/notifications",
            path_parameters={"site_id": "nonexistent"},
            body={
                "type": "email",
                "destination": "alert@osasi.co.jp",
                "enabled": True,
            },
        )
        response = handler(event, None)

        assert response["statusCode"] == 404

    def test_slack_notification_with_mention(self):
        handler = self._import_handler()
        site_id = self._create_site(handler)

        event = make_api_event(
            "POST", f"/sites/{site_id}/notifications",
            path_parameters={"site_id": site_id},
            body={
                "type": "slack",
                "destination": "/web-alive-monitoring/slack-webhook",
                "mention": "@here",
                "message_template": "通知テスト",
                "enabled": True,
            },
        )
        response = handler(event, None)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert body["data"]["mention"] == "@here"

    def test_delete_nonexistent_notification_returns_404(self):
        handler = self._import_handler()
        site_id = self._create_site(handler)

        event = make_api_event(
            "DELETE", f"/sites/{site_id}/notifications/nonexistent",
            path_parameters={"site_id": site_id, "notification_id": "nonexistent"},
        )
        response = handler(event, None)
        assert response["statusCode"] == 404

    def test_post_notification_validation_missing_type(self):
        handler = self._import_handler()
        site_id = self._create_site(handler)

        event = make_api_event(
            "POST", f"/sites/{site_id}/notifications",
            path_parameters={"site_id": site_id},
            body={
                "destination": "alert@osasi.co.jp",
                "enabled": True,
            },
        )
        response = handler(event, None)
        assert response["statusCode"] == 400

    def test_post_notification_validation_invalid_type(self):
        handler = self._import_handler()
        site_id = self._create_site(handler)

        event = make_api_event(
            "POST", f"/sites/{site_id}/notifications",
            path_parameters={"site_id": site_id},
            body={
                "type": "sms",
                "destination": "123",
                "enabled": True,
            },
        )
        response = handler(event, None)
        assert response["statusCode"] == 400

    def test_post_notification_validation_empty_destination(self):
        handler = self._import_handler()
        site_id = self._create_site(handler)

        event = make_api_event(
            "POST", f"/sites/{site_id}/notifications",
            path_parameters={"site_id": site_id},
            body={
                "type": "email",
                "destination": "",
                "enabled": True,
            },
        )
        response = handler(event, None)
        assert response["statusCode"] == 400
