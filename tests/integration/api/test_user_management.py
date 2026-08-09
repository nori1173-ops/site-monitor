"""ユーザー管理機能の統合テスト

テスト対象:
- DELETE /users/me (自ユーザー削除)
- GET /admin/users (ユーザー一覧)
- POST /admin/users/{email}/toggle-status (有効/無効切替)
- POST /admin/users/{email}/reset-password (パスワードリセット)
- DELETE /admin/users/{email} (管理者によるユーザー削除)
- PUT /sites/{site_id} 管理者オーバーライド
- DELETE /sites/{site_id} 管理者オーバーライド
"""

import base64
import json
from unittest.mock import patch, MagicMock

import boto3
import pytest
from moto import mock_aws

from tests.integration.api.conftest import make_api_event


ADMIN_CREDENTIALS = base64.b64encode(b"admin:SecurePassword123").decode()


def make_admin_api_event(
    method: str,
    path: str,
    body: dict | None = None,
    path_parameters: dict | None = None,
    query_parameters: dict | None = None,
    email: str = "admin@example.com",
) -> dict:
    """管理者認証ヘッダー付きAPI Gateway proxy event を構築"""
    event = make_api_event(
        method=method,
        path=path,
        body=body,
        path_parameters=path_parameters,
        query_parameters=query_parameters,
        email=email,
    )
    event["headers"]["X-Admin-Auth"] = ADMIN_CREDENTIALS
    return event


class TestDeleteUserMe:
    """DELETE /users/me 自ユーザー削除テスト"""

    @pytest.fixture(autouse=True)
    def setup(self, dynamodb_tables, monkeypatch):
        self.dynamodb = dynamodb_tables
        self.mock_scheduler = MagicMock()
        self.scheduler_patcher = patch(
            "api.helpers.scheduler.get_scheduler_client",
            return_value=self.mock_scheduler,
        )
        self.scheduler_patcher.start()
        self.mock_scheduler.create_schedule.return_value = {
            "ScheduleArn": "arn:aws:scheduler:ap-northeast-1:123456789012:schedule/default/test-schedule"
        }
        monkeypatch.setenv("USER_POOL_ID", "ap-northeast-1_TestPool")
        yield
        self.scheduler_patcher.stop()

    def _import_handler(self):
        from api.app import handler
        return handler

    def _create_site(self, handler, email: str = "user@example.com"):
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
        return handler(event, None)

    def test_delete_user_me_with_sites_returns_400(self):
        handler = self._import_handler()
        self._create_site(handler, email="user@example.com")

        event = make_api_event("DELETE", "/users/me", email="user@example.com")
        response = handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "サイト" in body["error"]

    @patch("api.app._get_cognito_client")
    def test_delete_user_me_without_sites_returns_200(self, mock_cognito):
        mock_client = MagicMock()
        mock_cognito.return_value = mock_client

        handler = self._import_handler()

        event = make_api_event("DELETE", "/users/me", email="user@example.com")
        response = handler(event, None)

        assert response["statusCode"] == 200
        mock_client.admin_delete_user.assert_called_once()


class TestAdminUsers:
    """管理者ユーザー管理テスト"""

    @pytest.fixture(autouse=True)
    def setup(self, dynamodb_tables, monkeypatch):
        self.dynamodb = dynamodb_tables
        self.mock_scheduler = MagicMock()
        self.scheduler_patcher = patch(
            "api.helpers.scheduler.get_scheduler_client",
            return_value=self.mock_scheduler,
        )
        self.scheduler_patcher.start()
        self.mock_scheduler.create_schedule.return_value = {
            "ScheduleArn": "arn:aws:scheduler:ap-northeast-1:123456789012:schedule/default/test-schedule"
        }
        monkeypatch.setenv("USER_POOL_ID", "ap-northeast-1_TestPool")
        yield
        self.scheduler_patcher.stop()

    def _import_handler(self):
        from api.app import handler
        return handler

    @patch("api.app._get_cognito_client")
    def test_get_admin_users(self, mock_cognito):
        mock_client = MagicMock()
        mock_cognito.return_value = mock_client
        mock_client.list_users.return_value = {
            "Users": [
                {
                    "Username": "user1@example.com",
                    "Attributes": [
                        {"Name": "email", "Value": "user1@example.com"},
                    ],
                    "Enabled": True,
                    "UserCreateDate": "2026-01-01T00:00:00Z",
                    "UserStatus": "CONFIRMED",
                },
            ]
        }

        handler = self._import_handler()
        event = make_admin_api_event("GET", "/admin/users")
        response = handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["success"] is True
        assert len(body["data"]) == 1
        assert body["data"][0]["email"] == "user1@example.com"

    @patch("api.app._get_cognito_client")
    def test_toggle_user_status(self, mock_cognito):
        mock_client = MagicMock()
        mock_cognito.return_value = mock_client
        mock_client.admin_get_user.return_value = {"Enabled": True}

        handler = self._import_handler()
        event = make_admin_api_event(
            "POST",
            "/admin/users/user1@example.com/toggle-status",
        )
        response = handler(event, None)

        assert response["statusCode"] == 200
        mock_client.admin_disable_user.assert_called_once()

    @patch("api.app._get_cognito_client")
    def test_admin_reset_password(self, mock_cognito):
        mock_client = MagicMock()
        mock_cognito.return_value = mock_client

        handler = self._import_handler()
        event = make_admin_api_event(
            "POST",
            "/admin/users/user1@example.com/reset-password",
        )
        response = handler(event, None)

        assert response["statusCode"] == 200
        mock_client.admin_reset_user_password.assert_called_once()

    @patch("api.app._get_cognito_client")
    def test_admin_delete_user(self, mock_cognito):
        mock_client = MagicMock()
        mock_cognito.return_value = mock_client

        handler = self._import_handler()
        event = make_admin_api_event(
            "DELETE",
            "/admin/users/user1@example.com",
        )
        response = handler(event, None)

        assert response["statusCode"] == 200
        mock_client.admin_delete_user.assert_called_once()

    def test_admin_endpoints_require_admin_auth(self):
        handler = self._import_handler()
        event = make_api_event("GET", "/admin/users")
        response = handler(event, None)

        assert response["statusCode"] == 403


class TestAdminOverride:
    """管理者オーバーライドテスト（サイト操作権限）"""

    @pytest.fixture(autouse=True)
    def setup(self, dynamodb_tables, monkeypatch):
        self.dynamodb = dynamodb_tables
        self.mock_scheduler = MagicMock()
        self.scheduler_patcher = patch(
            "api.helpers.scheduler.get_scheduler_client",
            return_value=self.mock_scheduler,
        )
        self.scheduler_patcher.start()
        self.mock_scheduler.create_schedule.return_value = {
            "ScheduleArn": "arn:aws:scheduler:ap-northeast-1:123456789012:schedule/default/test-schedule"
        }
        monkeypatch.setenv("USER_POOL_ID", "ap-northeast-1_TestPool")
        yield
        self.scheduler_patcher.stop()

    def _import_handler(self):
        from api.app import handler
        return handler

    def _create_site(self, handler, email: str = "owner@example.com"):
        body = {
            "site_name": "オーナーのサイト",
            "monitor_type": "url_check",
            "targets": ["https://example.com/data/latest.png"],
            "schedule_start": "00:20",
            "schedule_interval_minutes": 60,
            "consecutive_threshold": 3,
            "enabled": True,
        }
        event = make_api_event("POST", "/sites", body=body, email=email)
        return handler(event, None)

    def test_admin_can_update_others_site(self):
        handler = self._import_handler()
        create_resp = self._create_site(handler, email="owner@example.com")
        site_id = json.loads(create_resp["body"])["data"]["site_id"]

        event = make_admin_api_event(
            "PUT",
            f"/sites/{site_id}",
            body={
                "site_name": "管理者が更新",
                "monitor_type": "url_check",
                "targets": ["https://example.com/new.png"],
                "schedule_start": "01:00",
                "schedule_interval_minutes": 30,
                "consecutive_threshold": 3,
                "enabled": True,
            },
            email="admin@example.com",
        )
        response = handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["data"]["site_name"] == "管理者が更新"

    def test_admin_can_delete_others_site(self):
        handler = self._import_handler()
        create_resp = self._create_site(handler, email="owner@example.com")
        site_id = json.loads(create_resp["body"])["data"]["site_id"]

        event = make_admin_api_event(
            "DELETE",
            f"/sites/{site_id}",
            email="admin@example.com",
        )
        response = handler(event, None)

        assert response["statusCode"] == 200

    def test_non_admin_cannot_update_others_site(self):
        handler = self._import_handler()
        create_resp = self._create_site(handler, email="owner@example.com")
        site_id = json.loads(create_resp["body"])["data"]["site_id"]

        event = make_api_event(
            "PUT",
            f"/sites/{site_id}",
            body={
                "site_name": "不正更新",
                "monitor_type": "url_check",
                "targets": ["https://example.com/x.png"],
                "schedule_start": "00:00",
                "schedule_interval_minutes": 60,
                "consecutive_threshold": 3,
                "enabled": True,
            },
            email="other@example.com",
        )
        response = handler(event, None)
        assert response["statusCode"] == 403
