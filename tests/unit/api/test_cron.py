import pytest
from api.helpers.cron import generate_cron_expression


class TestGenerateCronExpression:
    """Cron式生成のテスト

    EventBridge Schedulerで使用するCron式を生成する。
    入力はJST（日本標準時）で、出力はUTC変換済みのCron式。
    """

    def test_60min_interval_start_0020(self):
        """60分間隔、0:20始まり → 毎時20分"""
        result = generate_cron_expression("00:20", 60)
        # JST 00:20 → UTC 15:20 (前日)、毎時なので分だけ固定
        assert result == "cron(20 * * * ? *)"

    def test_10min_interval_start_0005(self):
        """10分間隔、0:05始まり → 5分から10分刻み"""
        result = generate_cron_expression("00:05", 10)
        assert result == "cron(5/10 * * * ? *)"

    def test_360min_interval_start_0230(self):
        """360分(6h)間隔、2:30始まり → UTC 17:30、6時間刻み"""
        result = generate_cron_expression("02:30", 360)
        assert result == "cron(30 17/6 * * ? *)"

    def test_boundary_2300_jst(self):
        """23:00 JST → 14:00 UTC"""
        result = generate_cron_expression("23:00", 60)
        assert result == "cron(0 * * * ? *)"

    def test_5min_interval(self):
        """5分間隔、0:00始まり"""
        result = generate_cron_expression("00:00", 5)
        assert result == "cron(0/5 * * * ? *)"

    def test_30min_interval_start_0015(self):
        """30分間隔、0:15始まり"""
        result = generate_cron_expression("00:15", 30)
        assert result == "cron(15/30 * * * ? *)"

    def test_120min_interval_start_0100(self):
        """120分(2h)間隔、1:00始まり → UTC 16:00、2時間刻み"""
        result = generate_cron_expression("01:00", 120)
        assert result == "cron(0 16/2 * * ? *)"

    def test_1440min_interval_start_0900(self):
        """1440分(24h=1日)間隔、9:00始まり → UTC 0:00、毎日"""
        result = generate_cron_expression("09:00", 1440)
        assert result == "cron(0 0 * * ? *)"

    def test_invalid_time_format(self):
        """不正な時刻形式"""
        with pytest.raises(ValueError):
            generate_cron_expression("25:00", 60)

    def test_invalid_interval(self):
        """不正な間隔（0以下）"""
        with pytest.raises(ValueError):
            generate_cron_expression("00:00", 0)
