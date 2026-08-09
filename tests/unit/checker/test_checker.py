"""更新判定ロジックのテスト"""

import pytest

from checker.checker import determine_update_status


class TestLastModifiedComparison:
    def test_last_modified_changed(self):
        result = determine_update_status(
            fetch_result={
                "last_modified": "Thu, 02 Jan 2026 00:00:00 GMT",
                "etag": None,
                "content_hash": "abc123",
            },
            previous={
                "last_modified": "Thu, 01 Jan 2026 00:00:00 GMT",
                "etag": None,
                "content_hash": "abc123",
            },
        )
        assert result["status"] == "updated"
        assert result["method"] == "last_modified"

    def test_last_modified_unchanged(self):
        result = determine_update_status(
            fetch_result={
                "last_modified": "Thu, 01 Jan 2026 00:00:00 GMT",
                "etag": None,
                "content_hash": "abc123",
            },
            previous={
                "last_modified": "Thu, 01 Jan 2026 00:00:00 GMT",
                "etag": None,
                "content_hash": "abc123",
            },
        )
        assert result["status"] == "not_updated"
        assert result["method"] == "last_modified"


class TestETagComparison:
    def test_etag_changed(self):
        result = determine_update_status(
            fetch_result={
                "last_modified": None,
                "etag": '"new-etag"',
                "content_hash": "abc123",
            },
            previous={
                "last_modified": None,
                "etag": '"old-etag"',
                "content_hash": "abc123",
            },
        )
        assert result["status"] == "updated"
        assert result["method"] == "etag"

    def test_etag_unchanged(self):
        result = determine_update_status(
            fetch_result={
                "last_modified": None,
                "etag": '"same-etag"',
                "content_hash": "abc123",
            },
            previous={
                "last_modified": None,
                "etag": '"same-etag"',
                "content_hash": "abc123",
            },
        )
        assert result["status"] == "not_updated"
        assert result["method"] == "etag"


class TestSHA256Fallback:
    def test_hash_changed_when_no_headers(self):
        result = determine_update_status(
            fetch_result={
                "last_modified": None,
                "etag": None,
                "content_hash": "new_hash_value",
            },
            previous={
                "last_modified": None,
                "etag": None,
                "content_hash": "old_hash_value",
            },
        )
        assert result["status"] == "updated"
        assert result["method"] == "content_hash"

    def test_hash_unchanged_when_no_headers(self):
        result = determine_update_status(
            fetch_result={
                "last_modified": None,
                "etag": None,
                "content_hash": "same_hash",
            },
            previous={
                "last_modified": None,
                "etag": None,
                "content_hash": "same_hash",
            },
        )
        assert result["status"] == "not_updated"
        assert result["method"] == "content_hash"


class TestFirstCheck:
    def test_no_previous_record_is_updated(self):
        result = determine_update_status(
            fetch_result={
                "last_modified": "Thu, 01 Jan 2026 00:00:00 GMT",
                "etag": None,
                "content_hash": "abc123",
            },
            previous=None,
        )
        assert result["status"] == "updated"

    def test_no_previous_with_hash_only(self):
        result = determine_update_status(
            fetch_result={
                "last_modified": None,
                "etag": None,
                "content_hash": "abc123",
            },
            previous=None,
        )
        assert result["status"] == "updated"


class TestHeaderPriority:
    def test_last_modified_preferred_over_etag(self):
        result = determine_update_status(
            fetch_result={
                "last_modified": "Thu, 02 Jan 2026 00:00:00 GMT",
                "etag": '"same-etag"',
                "content_hash": "same_hash",
            },
            previous={
                "last_modified": "Thu, 01 Jan 2026 00:00:00 GMT",
                "etag": '"same-etag"',
                "content_hash": "same_hash",
            },
        )
        assert result["status"] == "updated"
        assert result["method"] == "last_modified"

    def test_etag_preferred_over_hash(self):
        result = determine_update_status(
            fetch_result={
                "last_modified": None,
                "etag": '"new-etag"',
                "content_hash": "same_hash",
            },
            previous={
                "last_modified": None,
                "etag": '"old-etag"',
                "content_hash": "same_hash",
            },
        )
        assert result["status"] == "updated"
        assert result["method"] == "etag"
