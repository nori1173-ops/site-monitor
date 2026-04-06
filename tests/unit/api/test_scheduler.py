"""scheduler.py のユニットテスト"""

import json
from unittest.mock import patch, MagicMock

import pytest


class TestSchedulerFunctions:

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        monkeypatch.setenv("STACK_NAME", "TestStack")
        monkeypatch.setenv("CHECKER_FUNCTION_ARN", "arn:aws:lambda:ap-northeast-1:123456789012:function:checker")
        monkeypatch.setenv("SCHEDULER_ROLE_ARN", "arn:aws:iam::123456789012:role/scheduler-role")
        monkeypatch.setenv("SCHEDULER_GROUP_NAME", "default")
        monkeypatch.setenv("CW_LOG_QUEUE_URL", "https://sqs.ap-northeast-1.amazonaws.com/123456789012/cw-queue")

    @patch("api.utils.scheduler.get_scheduler_client")
    def test_create_schedule_url_check(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.create_schedule.return_value = {
            "ScheduleArn": "arn:aws:scheduler:ap-northeast-1:123456789012:schedule/default/TestStack-site-abc"
        }
        mock_get_client.return_value = mock_client

        from api.utils.scheduler import create_schedule
        arn = create_schedule(
            site_id="abc",
            schedule_start="00:20",
            schedule_interval_minutes=60,
            monitor_type="url_check",
            enabled=True,
        )

        assert "arn:aws:scheduler" in arn
        mock_client.create_schedule.assert_called_once()
        call_kwargs = mock_client.create_schedule.call_args[1]
        assert call_kwargs["Name"] == "TestStack-site-abc"
        assert call_kwargs["State"] == "ENABLED"
        target = call_kwargs["Target"]
        assert target["Arn"] == "arn:aws:lambda:ap-northeast-1:123456789012:function:checker"

    @patch("api.utils.scheduler.get_scheduler_client")
    def test_create_schedule_cloudwatch_log(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.create_schedule.return_value = {
            "ScheduleArn": "arn:aws:scheduler:ap-northeast-1:123456789012:schedule/default/TestStack-site-xyz"
        }
        mock_get_client.return_value = mock_client

        from api.utils.scheduler import create_schedule
        create_schedule(
            site_id="xyz",
            schedule_start="00:50",
            schedule_interval_minutes=60,
            monitor_type="cloudwatch_log",
            enabled=False,
        )

        call_kwargs = mock_client.create_schedule.call_args[1]
        assert call_kwargs["State"] == "DISABLED"
        target = call_kwargs["Target"]
        assert "sqs" in target["Arn"]

    @patch("api.utils.scheduler.get_scheduler_client")
    def test_update_schedule_url_check(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        from api.utils.scheduler import update_schedule
        update_schedule(
            site_id="abc",
            schedule_start="01:00",
            schedule_interval_minutes=30,
            monitor_type="url_check",
            enabled=True,
        )

        mock_client.update_schedule.assert_called_once()

    @patch("api.utils.scheduler.get_scheduler_client")
    def test_update_schedule_cloudwatch_log(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        from api.utils.scheduler import update_schedule
        update_schedule(
            site_id="xyz",
            schedule_start="00:50",
            schedule_interval_minutes=60,
            monitor_type="cloudwatch_log",
            enabled=False,
        )

        call_kwargs = mock_client.update_schedule.call_args[1]
        assert call_kwargs["State"] == "DISABLED"
        target = call_kwargs["Target"]
        assert "sqs" in target["Arn"]

    @patch("api.utils.scheduler.get_scheduler_client")
    def test_delete_schedule(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        from api.utils.scheduler import delete_schedule
        delete_schedule("abc")

        mock_client.delete_schedule.assert_called_once_with(
            Name="TestStack-site-abc",
            GroupName="default",
        )

    @patch("api.utils.scheduler.get_scheduler_client")
    def test_delete_schedule_not_found(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.delete_schedule.side_effect = mock_client.exceptions.ResourceNotFoundException
        mock_client.exceptions.ResourceNotFoundException = type("ResourceNotFoundException", (Exception,), {})
        mock_client.delete_schedule.side_effect = mock_client.exceptions.ResourceNotFoundException()
        mock_get_client.return_value = mock_client

        from api.utils.scheduler import delete_schedule
        delete_schedule("nonexistent")

    @patch("api.utils.scheduler.get_scheduler_client")
    def test_disable_schedule(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_schedule.return_value = {
            "ScheduleExpression": "cron(20 * * * ? *)",
            "Target": {
                "Arn": "arn:aws:lambda:ap-northeast-1:123456789012:function:checker",
                "RoleArn": "arn:aws:iam::123456789012:role/scheduler-role",
                "Input": json.dumps({"site_id": "abc"}),
            },
        }
        mock_get_client.return_value = mock_client

        from api.utils.scheduler import disable_schedule
        disable_schedule("abc")

        mock_client.update_schedule.assert_called_once()
        call_kwargs = mock_client.update_schedule.call_args[1]
        assert call_kwargs["State"] == "DISABLED"

    @patch("api.utils.scheduler.get_scheduler_client")
    def test_enable_schedule(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_schedule.return_value = {
            "ScheduleExpression": "cron(20 * * * ? *)",
            "Target": {
                "Arn": "arn:aws:lambda:ap-northeast-1:123456789012:function:checker",
                "RoleArn": "arn:aws:iam::123456789012:role/scheduler-role",
                "Input": json.dumps({"site_id": "abc"}),
            },
        }
        mock_get_client.return_value = mock_client

        from api.utils.scheduler import enable_schedule
        enable_schedule("abc")

        mock_client.update_schedule.assert_called_once()
        call_kwargs = mock_client.update_schedule.call_args[1]
        assert call_kwargs["State"] == "ENABLED"
