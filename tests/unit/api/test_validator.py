"""validate_site_body / validate_notification_body のユニットテスト"""

import pytest

from api.utils.validator import validate_notification_body, validate_site_body


class TestValidateSiteBody:

    def _valid_body(self, **overrides):
        body = {
            "site_name": "テストダム",
            "monitor_type": "url_check",
            "targets": ["https://example.com/data/latest.png"],
            "schedule_start": "00:20",
            "schedule_interval_minutes": 60,
            "consecutive_threshold": 3,
        }
        body.update(overrides)
        return body

    def test_valid_body_returns_none(self):
        assert validate_site_body(self._valid_body()) is None

    def test_missing_site_name(self):
        body = self._valid_body()
        del body["site_name"]
        assert validate_site_body(body) is not None

    def test_empty_site_name(self):
        assert validate_site_body(self._valid_body(site_name="")) is not None

    def test_site_name_too_long(self):
        assert validate_site_body(self._valid_body(site_name="a" * 201)) is not None

    def test_site_name_max_length(self):
        assert validate_site_body(self._valid_body(site_name="a" * 200)) is None

    def test_invalid_monitor_type(self):
        assert validate_site_body(self._valid_body(monitor_type="invalid")) is not None

    def test_valid_cloudwatch_log_type(self):
        assert validate_site_body(self._valid_body(monitor_type="cloudwatch_log")) is None

    def test_missing_targets(self):
        body = self._valid_body()
        del body["targets"]
        assert validate_site_body(body) is not None

    def test_empty_targets(self):
        assert validate_site_body(self._valid_body(targets=[])) is not None

    def test_targets_not_list(self):
        assert validate_site_body(self._valid_body(targets="not-a-list")) is not None

    def test_invalid_schedule_start(self):
        assert validate_site_body(self._valid_body(schedule_start="25:00")) is None  # HH:MM format check only
        assert validate_site_body(self._valid_body(schedule_start="abc")) is not None

    def test_missing_schedule_start(self):
        body = self._valid_body()
        del body["schedule_start"]
        assert validate_site_body(body) is not None

    def test_invalid_interval(self):
        assert validate_site_body(self._valid_body(schedule_interval_minutes=7)) is not None

    @pytest.mark.parametrize("interval", [5, 10, 15, 30, 60, 180, 360, 720, 1440])
    def test_valid_intervals(self, interval):
        assert validate_site_body(self._valid_body(schedule_interval_minutes=interval)) is None

    def test_consecutive_threshold_zero(self):
        assert validate_site_body(self._valid_body(consecutive_threshold=0)) is not None

    def test_consecutive_threshold_negative(self):
        assert validate_site_body(self._valid_body(consecutive_threshold=-1)) is not None

    def test_consecutive_threshold_none_is_ok(self):
        body = self._valid_body()
        del body["consecutive_threshold"]
        assert validate_site_body(body) is None


class TestValidateNotificationBody:

    def test_valid_email(self):
        assert validate_notification_body({"type": "email", "destination": "a@b.com"}) is None

    def test_valid_slack(self):
        assert validate_notification_body({"type": "slack", "destination": "/webhook"}) is None

    def test_missing_type(self):
        assert validate_notification_body({"destination": "a@b.com"}) is not None

    def test_invalid_type(self):
        assert validate_notification_body({"type": "sms", "destination": "123"}) is not None

    def test_missing_destination(self):
        assert validate_notification_body({"type": "email"}) is not None

    def test_empty_destination(self):
        assert validate_notification_body({"type": "email", "destination": ""}) is not None

    def test_whitespace_only_destination(self):
        assert validate_notification_body({"type": "email", "destination": "   "}) is not None
