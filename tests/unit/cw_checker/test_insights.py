"""CloudWatch Logs Insights クエリ実行テスト"""

import time
from unittest.mock import MagicMock, patch, call

import pytest


class TestRunInsightsQuery:
    """insights.run_query のテスト"""

    @patch("cw_checker.insights.boto3")
    def test_query_returns_hit_count_and_latest_timestamp(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        mock_client.start_query.return_value = {"queryId": "q-123"}
        mock_client.get_query_results.return_value = {
            "status": "Complete",
            "results": [
                [
                    {"field": "@timestamp", "value": "2026-04-06 09:00:00.000"},
                    {"field": "@message", "value": "test message"},
                ],
                [
                    {"field": "@timestamp", "value": "2026-04-06 08:00:00.000"},
                    {"field": "@message", "value": "test message 2"},
                ],
            ],
            "statistics": {"recordsMatched": 2.0},
        }

        from cw_checker.insights import run_query

        result = run_query(
            log_group="TestLogGroup",
            message_filter="リクエストを送信します。",
            json_search_word='"account": "10206721"',
            search_period_minutes=60,
        )

        assert result["status"] == "success"
        assert result["hit_count"] == 2
        assert result["latest_timestamp"] == "2026-04-06 09:00:00.000"

    @patch("cw_checker.insights.boto3")
    def test_query_returns_zero_hits(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        mock_client.start_query.return_value = {"queryId": "q-456"}
        mock_client.get_query_results.return_value = {
            "status": "Complete",
            "results": [],
            "statistics": {"recordsMatched": 0.0},
        }

        from cw_checker.insights import run_query

        result = run_query(
            log_group="TestLogGroup",
            message_filter="some filter",
            json_search_word="some word",
            search_period_minutes=60,
        )

        assert result["status"] == "success"
        assert result["hit_count"] == 0
        assert result["latest_timestamp"] is None

    @patch("cw_checker.insights.boto3")
    def test_query_polls_until_complete(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        mock_client.start_query.return_value = {"queryId": "q-789"}
        mock_client.get_query_results.side_effect = [
            {"status": "Running", "results": [], "statistics": {}},
            {"status": "Running", "results": [], "statistics": {}},
            {
                "status": "Complete",
                "results": [
                    [{"field": "@timestamp", "value": "2026-04-06 10:00:00.000"}],
                ],
                "statistics": {"recordsMatched": 1.0},
            },
        ]

        from cw_checker.insights import run_query

        with patch("cw_checker.insights.time.sleep"):
            result = run_query(
                log_group="TestLogGroup",
                message_filter="filter",
                json_search_word="word",
                search_period_minutes=30,
            )

        assert result["status"] == "success"
        assert result["hit_count"] == 1
        assert mock_client.get_query_results.call_count == 3

    @patch("cw_checker.insights.boto3")
    def test_query_failed_returns_error(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        mock_client.start_query.return_value = {"queryId": "q-fail"}
        mock_client.get_query_results.return_value = {
            "status": "Failed",
            "results": [],
            "statistics": {},
        }

        from cw_checker.insights import run_query

        result = run_query(
            log_group="TestLogGroup",
            message_filter="filter",
            json_search_word="word",
            search_period_minutes=60,
        )

        assert result["status"] == "error"
        assert "Failed" in result["message"]

    @patch("cw_checker.insights.boto3")
    def test_query_cancelled_returns_error(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        mock_client.start_query.return_value = {"queryId": "q-cancel"}
        mock_client.get_query_results.return_value = {
            "status": "Cancelled",
            "results": [],
            "statistics": {},
        }

        from cw_checker.insights import run_query

        result = run_query(
            log_group="TestLogGroup",
            message_filter="filter",
            json_search_word="word",
            search_period_minutes=60,
        )

        assert result["status"] == "error"

    @patch("cw_checker.insights.boto3")
    def test_query_builds_correct_insights_query_string(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        mock_client.start_query.return_value = {"queryId": "q-build"}
        mock_client.get_query_results.return_value = {
            "status": "Complete",
            "results": [],
            "statistics": {"recordsMatched": 0.0},
        }

        from cw_checker.insights import run_query

        run_query(
            log_group="/aws/lambda/MyFunction",
            message_filter="リクエストを送信します。",
            json_search_word='"account": "10206721","note": "LONG"',
            search_period_minutes=60,
        )

        start_query_call = mock_client.start_query.call_args
        query_string = start_query_call.kwargs.get("queryString") or start_query_call[1].get("queryString")

        assert "filter @message like" in query_string
        assert "リクエストを送信します。" in query_string
        assert '"account": "10206721","note": "LONG"' in query_string

    @patch("cw_checker.insights.boto3")
    def test_query_exception_returns_error(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        mock_client.start_query.side_effect = Exception("AccessDenied")

        from cw_checker.insights import run_query

        result = run_query(
            log_group="TestLogGroup",
            message_filter="filter",
            json_search_word="word",
            search_period_minutes=60,
        )

        assert result["status"] == "error"
        assert "AccessDenied" in result["message"]
