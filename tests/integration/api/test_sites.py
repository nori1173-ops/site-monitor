import json
from unittest.mock import patch, MagicMock

import pytest

from tests.integration.api.conftest import make_api_event


class TestSitesCRUD:
    """sites CRUD 統合テスト (moto DynamoDB)"""

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

    def _create_site(self, handler, body: dict | None = None, email: str = "user@osasi.co.jp"):
        if body is None:
            body = {
                "site_name": "テストダム",
                "monitor_type": "url_check",
                "targets": ["https://example.com/data/latest.png"],
                "schedule_start": "00:20",
                "schedule_interval_minutes": 60,
                "consecutive_threshold": 3,
                "enabled": True,
            }
        event = make_api_event("POST", "/sites", body=body, email=email)
        response = handler(event, None)
        return response

    def test_post_sites_creates_site(self):
        handler = self._import_handler()
        response = self._create_site(handler)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert body["success"] is True
        assert "site_id" in body["data"]
        assert body["data"]["site_name"] == "テストダム"
        assert body["data"]["created_by"] == "user@osasi.co.jp"

    def test_post_sites_creates_scheduler(self):
        handler = self._import_handler()
        self._create_site(handler)

        self.mock_scheduler.create_schedule.assert_called_once()

    def test_post_sites_rollback_on_scheduler_failure(self):
        handler = self._import_handler()
        self.mock_scheduler.create_schedule.side_effect = Exception("Scheduler error")

        response = self._create_site(handler)
        assert response["statusCode"] == 500

        table = self.dynamodb.Table("TestStack-sites")
        items = table.scan()["Items"]
        assert len(items) == 0

    def test_get_sites_returns_list(self):
        handler = self._import_handler()
        self._create_site(handler)
        self._create_site(handler, body={
            "site_name": "テスト橋梁",
            "monitor_type": "url_check",
            "targets": ["https://example.com/bridge.png"],
            "schedule_start": "00:05",
            "schedule_interval_minutes": 10,
            "consecutive_threshold": 3,
            "enabled": True,
        })

        event = make_api_event("GET", "/sites")
        response = handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert len(body["data"]) == 2

    def test_get_sites_filter_mine(self):
        handler = self._import_handler()
        self._create_site(handler, email="user@osasi.co.jp")
        self._create_site(handler, body={
            "site_name": "他人のサイト",
            "monitor_type": "url_check",
            "targets": ["https://other.example.com/"],
            "schedule_start": "00:00",
            "schedule_interval_minutes": 60,
            "consecutive_threshold": 3,
            "enabled": True,
        }, email="other@osasi.co.jp")

        event = make_api_event(
            "GET", "/sites",
            query_parameters={"filter": "mine"},
            email="user@osasi.co.jp",
        )
        response = handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["data"]) == 1
        assert body["data"][0]["created_by"] == "user@osasi.co.jp"

    def test_get_site_detail(self):
        handler = self._import_handler()
        create_resp = self._create_site(handler)
        site_id = json.loads(create_resp["body"])["data"]["site_id"]

        event = make_api_event(
            "GET", f"/sites/{site_id}",
            path_parameters={"site_id": site_id},
        )
        response = handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["data"]["site_id"] == site_id
        assert body["data"]["site_name"] == "テストダム"

    def test_get_site_not_found(self):
        handler = self._import_handler()
        event = make_api_event(
            "GET", "/sites/nonexistent",
            path_parameters={"site_id": "nonexistent"},
        )
        response = handler(event, None)

        assert response["statusCode"] == 404

    def test_put_site_updates(self):
        handler = self._import_handler()
        create_resp = self._create_site(handler)
        site_id = json.loads(create_resp["body"])["data"]["site_id"]

        event = make_api_event(
            "PUT", f"/sites/{site_id}",
            path_parameters={"site_id": site_id},
            body={
                "site_name": "更新後のダム",
                "monitor_type": "url_check",
                "targets": ["https://example.com/new.png"],
                "schedule_start": "01:00",
                "schedule_interval_minutes": 30,
                "consecutive_threshold": 5,
                "enabled": True,
            },
            email="user@osasi.co.jp",
        )
        response = handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["data"]["site_name"] == "更新後のダム"
        assert body["data"]["updated_by"] == "user@osasi.co.jp"

    def test_put_site_updates_scheduler_on_schedule_change(self):
        handler = self._import_handler()
        create_resp = self._create_site(handler)
        site_id = json.loads(create_resp["body"])["data"]["site_id"]

        event = make_api_event(
            "PUT", f"/sites/{site_id}",
            path_parameters={"site_id": site_id},
            body={
                "site_name": "テストダム",
                "monitor_type": "url_check",
                "targets": ["https://example.com/data/latest.png"],
                "schedule_start": "01:00",
                "schedule_interval_minutes": 30,
                "consecutive_threshold": 3,
                "enabled": True,
            },
        )
        handler(event, None)

        self.mock_scheduler.update_schedule.assert_called_once()

    def test_delete_site(self):
        handler = self._import_handler()
        create_resp = self._create_site(handler)
        site_id = json.loads(create_resp["body"])["data"]["site_id"]

        event = make_api_event(
            "DELETE", f"/sites/{site_id}",
            path_parameters={"site_id": site_id},
        )
        response = handler(event, None)

        assert response["statusCode"] == 200

        table = self.dynamodb.Table("TestStack-sites")
        result = table.get_item(Key={"site_id": site_id})
        assert "Item" not in result

    def test_delete_site_deletes_scheduler(self):
        handler = self._import_handler()
        create_resp = self._create_site(handler)
        json.loads(create_resp["body"])["data"]["site_id"]

        event = make_api_event(
            "DELETE", f"/sites/{json.loads(create_resp['body'])['data']['site_id']}",
            path_parameters={"site_id": json.loads(create_resp["body"])["data"]["site_id"]},
        )
        handler(event, None)

        self.mock_scheduler.delete_schedule.assert_called_once()

    def test_delete_site_deletes_notifications(self):
        handler = self._import_handler()
        create_resp = self._create_site(handler)
        site_id = json.loads(create_resp["body"])["data"]["site_id"]

        notif_event = make_api_event(
            "POST", f"/sites/{site_id}/notifications",
            path_parameters={"site_id": site_id},
            body={
                "type": "email",
                "destination": "alert@osasi.co.jp",
                "enabled": True,
            },
        )
        handler(notif_event, None)

        event = make_api_event(
            "DELETE", f"/sites/{site_id}",
            path_parameters={"site_id": site_id},
        )
        handler(event, None)

        notif_table = self.dynamodb.Table("TestStack-notifications")
        items = notif_table.scan(
            FilterExpression="site_id = :sid",
            ExpressionAttributeValues={":sid": site_id},
        )["Items"]
        assert len(items) == 0

    def test_get_site_results(self):
        handler = self._import_handler()
        create_resp = self._create_site(handler)
        site_id = json.loads(create_resp["body"])["data"]["site_id"]

        results_table = self.dynamodb.Table("TestStack-check_results")
        results_table.put_item(Item={
            "site_id": site_id,
            "checked_at#target_url": "2026-04-06T00:00:00Z#https://example.com/data/latest.png",
            "status": "updated",
        })

        event = make_api_event(
            "GET", f"/sites/{site_id}/results",
            path_parameters={"site_id": site_id},
        )
        response = handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["data"]) == 1
        assert body["data"][0]["status"] == "updated"

    def test_put_site_forbidden_for_other_user(self):
        handler = self._import_handler()
        create_resp = self._create_site(handler, email="owner@osasi.co.jp")
        site_id = json.loads(create_resp["body"])["data"]["site_id"]

        event = make_api_event(
            "PUT", f"/sites/{site_id}",
            path_parameters={"site_id": site_id},
            body={
                "site_name": "不正更新",
                "monitor_type": "url_check",
                "targets": ["https://example.com/x.png"],
                "schedule_start": "00:00",
                "schedule_interval_minutes": 60,
                "consecutive_threshold": 3,
                "enabled": True,
            },
            email="other@osasi.co.jp",
        )
        response = handler(event, None)
        assert response["statusCode"] == 403

    def test_delete_site_forbidden_for_other_user(self):
        handler = self._import_handler()
        create_resp = self._create_site(handler, email="owner@osasi.co.jp")
        site_id = json.loads(create_resp["body"])["data"]["site_id"]

        event = make_api_event(
            "DELETE", f"/sites/{site_id}",
            path_parameters={"site_id": site_id},
            email="other@osasi.co.jp",
        )
        response = handler(event, None)
        assert response["statusCode"] == 403

    def test_put_site_rollback_on_scheduler_failure(self):
        handler = self._import_handler()
        create_resp = self._create_site(handler)
        site_id = json.loads(create_resp["body"])["data"]["site_id"]
        original_name = json.loads(create_resp["body"])["data"]["site_name"]

        self.mock_scheduler.update_schedule.side_effect = Exception("Scheduler error")

        event = make_api_event(
            "PUT", f"/sites/{site_id}",
            path_parameters={"site_id": site_id},
            body={
                "site_name": "変更後の名前",
                "monitor_type": "url_check",
                "targets": ["https://example.com/new.png"],
                "schedule_start": "02:00",
                "schedule_interval_minutes": 30,
                "consecutive_threshold": 3,
                "enabled": True,
            },
        )
        response = handler(event, None)
        assert response["statusCode"] == 500

        table = self.dynamodb.Table("TestStack-sites")
        result = table.get_item(Key={"site_id": site_id})
        assert result["Item"]["site_name"] == original_name

    def test_post_site_validation_error(self):
        handler = self._import_handler()
        response = self._create_site(handler, body={
            "site_name": "",
            "monitor_type": "url_check",
            "targets": ["https://example.com/x.png"],
            "schedule_start": "00:00",
            "schedule_interval_minutes": 60,
        })
        assert response["statusCode"] == 400

    def test_post_site_invalid_interval(self):
        handler = self._import_handler()
        response = self._create_site(handler, body={
            "site_name": "テスト",
            "monitor_type": "url_check",
            "targets": ["https://example.com/x.png"],
            "schedule_start": "00:00",
            "schedule_interval_minutes": 7,
        })
        assert response["statusCode"] == 400
