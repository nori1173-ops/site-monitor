"""email_sender 単体テスト — SES send_email のモック検証"""

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def env_vars(monkeypatch):
    monkeypatch.setenv("EMAIL_DOMAIN", "alive.osasi-cloud.com")
    monkeypatch.setenv("SES_REGION", "us-west-2")


class TestSendEmail:
    def test_send_email_calls_ses_with_correct_params(self):
        mock_ses = MagicMock()
        with patch("notifier.email_sender._get_ses_client", return_value=mock_ses):
            from notifier.email_sender import send_email

            send_email(
                to_address="user@example.com",
                site_name="テストダム",
                trigger_url="https://example.com/data.png",
                previous_status="updated",
                new_status="not_updated",
                last_checked_at="2026-04-06T09:00:00+00:00",
                message_template="観測データ未更新です",
            )

        mock_ses.send_email.assert_called_once()
        call_kwargs = mock_ses.send_email.call_args[1]

        assert call_kwargs["Source"] == "OSASI.NET<noreply@alive.osasi-cloud.com>"
        assert call_kwargs["Destination"] == {"ToAddresses": ["user@example.com"]}
        assert "[Web Alive] テストダム - 状態変化通知" in call_kwargs["Message"]["Subject"]["Data"]

    def test_email_body_contains_site_info(self):
        mock_ses = MagicMock()
        with patch("notifier.email_sender._get_ses_client", return_value=mock_ses):
            from notifier.email_sender import send_email

            send_email(
                to_address="user@example.com",
                site_name="○○橋梁",
                trigger_url="https://example.com/bridge.html",
                previous_status="updated",
                new_status="not_updated",
                last_checked_at="2026-04-06T10:00:00+00:00",
                message_template="確認してください",
            )

        call_kwargs = mock_ses.send_email.call_args[1]
        body = call_kwargs["Message"]["Body"]["Text"]["Data"]
        assert "○○橋梁" in body
        assert "https://example.com/bridge.html" in body
        assert "正常" in body
        assert "異常（欠測）" in body
        assert "2026-04-06T10:00:00+00:00" in body
        assert "確認してください" in body

    def test_status_label_mapping(self):
        mock_ses = MagicMock()
        with patch("notifier.email_sender._get_ses_client", return_value=mock_ses):
            from notifier.email_sender import send_email

            send_email(
                to_address="user@example.com",
                site_name="テスト",
                trigger_url="https://example.com",
                previous_status="not_updated",
                new_status="error",
                last_checked_at="2026-04-06T11:00:00+00:00",
                message_template="",
            )

        call_kwargs = mock_ses.send_email.call_args[1]
        body = call_kwargs["Message"]["Body"]["Text"]["Data"]
        assert "異常（欠測）" in body
        assert "エラー" in body

    def test_recovery_status_label(self):
        mock_ses = MagicMock()
        with patch("notifier.email_sender._get_ses_client", return_value=mock_ses):
            from notifier.email_sender import send_email

            send_email(
                to_address="user@example.com",
                site_name="テスト",
                trigger_url="https://example.com",
                previous_status="not_updated",
                new_status="updated",
                last_checked_at="2026-04-06T12:00:00+00:00",
                message_template="",
            )

        call_kwargs = mock_ses.send_email.call_args[1]
        body = call_kwargs["Message"]["Body"]["Text"]["Data"]
        assert "正常" in body

    def test_email_domain_from_env(self):
        mock_ses = MagicMock()
        with patch("notifier.email_sender._get_ses_client", return_value=mock_ses):
            from notifier.email_sender import send_email

            send_email(
                to_address="admin@example.com",
                site_name="テスト",
                trigger_url="https://example.com",
                previous_status="updated",
                new_status="not_updated",
                last_checked_at="2026-04-06T09:00:00+00:00",
                message_template="",
            )

        call_kwargs = mock_ses.send_email.call_args[1]
        assert "alive.osasi-cloud.com" in call_kwargs["Source"]

    def test_ses_region_from_env(self):
        with patch("boto3.client") as mock_boto3_client:
            mock_client = MagicMock()
            mock_boto3_client.return_value = mock_client

            import importlib
            import notifier.email_sender as mod
            mod._ses_client = None
            client = mod._get_ses_client()

            mock_boto3_client.assert_called_with("ses", region_name="us-west-2")
