"""slack_sender 単体テスト — SSM取得 + Webhook POST のモック検証"""

from unittest.mock import MagicMock, patch

import pytest


class TestSendSlack:
    def test_sends_webhook_with_correct_payload(self):
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://hooks.slack.com/services/T00/B00/xxx"}
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("notifier.slack_sender._get_ssm_client", return_value=mock_ssm), \
             patch("requests.post", return_value=mock_response) as mock_post:
            from notifier.slack_sender import send_slack

            send_slack(
                ssm_parameter_name="/site-monitor/slack-webhook-url",
                mention="<!channel>",
                site_name="テストダム",
                trigger_url="https://example.com/data.png",
                previous_status="updated",
                new_status="not_updated",
                last_checked_at="2026-04-06T09:00:00+00:00",
            )

        mock_ssm.get_parameter.assert_called_once_with(
            Name="/site-monitor/slack-webhook-url",
            WithDecryption=True,
        )
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[0][0] == "https://hooks.slack.com/services/T00/B00/xxx"
        payload = call_kwargs[1]["json"]
        assert "<!channel>" in payload["text"]
        assert "テストダム" in payload["text"]
        assert "https://example.com/data.png" in payload["text"]

    def test_message_contains_status_labels(self):
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://hooks.slack.com/services/T00/B00/xxx"}
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("notifier.slack_sender._get_ssm_client", return_value=mock_ssm), \
             patch("requests.post", return_value=mock_response) as mock_post:
            from notifier.slack_sender import send_slack

            send_slack(
                ssm_parameter_name="/site-monitor/slack-webhook-url",
                mention="<@U12345>",
                site_name="テスト橋梁",
                trigger_url="https://example.com",
                previous_status="not_updated",
                new_status="updated",
                last_checked_at="2026-04-06T10:00:00+00:00",
            )

        payload = mock_post.call_args[1]["json"]
        text = payload["text"]
        assert "<@U12345>" in text
        assert "異常（欠測）" in text
        assert "正常" in text

    def test_empty_mention_not_in_message(self):
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://hooks.slack.com/services/T00/B00/xxx"}
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("notifier.slack_sender._get_ssm_client", return_value=mock_ssm), \
             patch("requests.post", return_value=mock_response) as mock_post:
            from notifier.slack_sender import send_slack

            send_slack(
                ssm_parameter_name="/site-monitor/slack-webhook-url",
                mention="",
                site_name="テスト",
                trigger_url="https://example.com",
                previous_status="updated",
                new_status="error",
                last_checked_at="2026-04-06T11:00:00+00:00",
            )

        payload = mock_post.call_args[1]["json"]
        text = payload["text"]
        assert not text.startswith("\n")
        assert "データ欠測検知" in text

    def test_raises_on_http_error(self):
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "https://hooks.slack.com/services/T00/B00/xxx"}
        }
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")

        with patch("notifier.slack_sender._get_ssm_client", return_value=mock_ssm), \
             patch("requests.post", return_value=mock_response):
            from notifier.slack_sender import send_slack

            with pytest.raises(Exception, match="HTTP 500"):
                send_slack(
                    ssm_parameter_name="/site-monitor/slack-webhook-url",
                    mention="",
                    site_name="テスト",
                    trigger_url="https://example.com",
                    previous_status="updated",
                    new_status="not_updated",
                    last_checked_at="2026-04-06T09:00:00+00:00",
                )
