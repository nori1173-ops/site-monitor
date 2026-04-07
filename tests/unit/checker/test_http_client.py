"""HTTP GETクライアントのテスト"""

from unittest.mock import MagicMock, patch

import pytest

from checker.http_client import fetch_url, ResponseTooLargeError


class TestFetchUrl:
    @patch("checker.http_client.validate_url")
    @patch("checker.http_client.requests.get")
    def test_successful_fetch(self, mock_get, mock_validate):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {
            "Last-Modified": "Thu, 01 Jan 2026 00:00:00 GMT",
            "ETag": '"abc123"',
        }
        mock_response.iter_content = MagicMock(return_value=[b"hello world"])
        mock_get.return_value = mock_response

        result = fetch_url("http://example.com/page.html")

        assert result["status_code"] == 200
        assert result["last_modified"] == "Thu, 01 Jan 2026 00:00:00 GMT"
        assert result["etag"] == '"abc123"'
        assert result["content_hash"] is not None
        assert len(result["content_hash"]) == 64

    @patch("checker.http_client.validate_url")
    @patch("checker.http_client.requests.get")
    def test_timeout_setting(self, mock_get, mock_validate):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.iter_content = MagicMock(return_value=[b"data"])
        mock_get.return_value = mock_response

        fetch_url("http://example.com/")

        mock_get.assert_called_once_with(
            "http://example.com/",
            timeout=10,
            stream=True,
            headers={"User-Agent": "WebAliveMonitoring/1.0"},
        )

    @patch("checker.http_client.validate_url")
    @patch("checker.http_client.requests.get")
    def test_response_size_limit_exceeded(self, mock_get, mock_validate):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        chunk = b"x" * (1024 * 1024)
        mock_response.iter_content = MagicMock(return_value=[chunk] * 11)
        mock_get.return_value = mock_response

        with pytest.raises(ResponseTooLargeError, match="10MB"):
            fetch_url("http://example.com/large-file")

    @patch("checker.http_client.validate_url")
    @patch("checker.http_client.requests.get")
    def test_no_headers_returns_none(self, mock_get, mock_validate):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.iter_content = MagicMock(return_value=[b"content"])
        mock_get.return_value = mock_response

        result = fetch_url("http://example.com/")

        assert result["last_modified"] is None
        assert result["etag"] is None
        assert result["content_hash"] is not None

    @patch("checker.http_client.validate_url")
    @patch("checker.http_client.requests.get")
    def test_user_agent_header(self, mock_get, mock_validate):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.iter_content = MagicMock(return_value=[b"data"])
        mock_get.return_value = mock_response

        fetch_url("http://example.com/")

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["headers"]["User-Agent"] == "WebAliveMonitoring/1.0"

    @patch("checker.http_client.validate_url")
    @patch("checker.http_client.requests.get")
    def test_streaming_hash_consistency(self, mock_get, mock_validate):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.iter_content = MagicMock(return_value=[b"chunk1", b"chunk2"])
        mock_get.return_value = mock_response

        result1 = fetch_url("http://example.com/")

        mock_response.iter_content = MagicMock(return_value=[b"chunk1", b"chunk2"])
        mock_get.return_value = mock_response

        result2 = fetch_url("http://example.com/")

        assert result1["content_hash"] == result2["content_hash"]

    @patch("checker.http_client.validate_url")
    @patch("checker.http_client.requests.get")
    def test_different_content_different_hash(self, mock_get, mock_validate):
        mock_response1 = MagicMock()
        mock_response1.status_code = 200
        mock_response1.headers = {}
        mock_response1.iter_content = MagicMock(return_value=[b"content_v1"])
        mock_get.return_value = mock_response1
        result1 = fetch_url("http://example.com/")

        mock_response2 = MagicMock()
        mock_response2.status_code = 200
        mock_response2.headers = {}
        mock_response2.iter_content = MagicMock(return_value=[b"content_v2"])
        mock_get.return_value = mock_response2
        result2 = fetch_url("http://example.com/")

        assert result1["content_hash"] != result2["content_hash"]
