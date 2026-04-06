"""SSRF対策モジュールのテスト"""

import socket
from unittest.mock import patch

import pytest

from checker.ssrf import validate_url


class TestSchemeValidation:
    def test_http_scheme_allowed(self):
        with patch("checker.ssrf._resolve_host", return_value="203.0.113.1"):
            validate_url("http://example.com/page.html")

    def test_https_scheme_allowed(self):
        with patch("checker.ssrf._resolve_host", return_value="203.0.113.1"):
            validate_url("https://example.com/page.html")

    def test_ftp_scheme_rejected(self):
        with pytest.raises(ValueError, match="許可されていないスキーム"):
            validate_url("ftp://example.com/file.txt")

    def test_file_scheme_rejected(self):
        with pytest.raises(ValueError, match="許可されていないスキーム"):
            validate_url("file:///etc/passwd")

    def test_javascript_scheme_rejected(self):
        with pytest.raises(ValueError, match="許可されていないスキーム"):
            validate_url("javascript:alert(1)")

    def test_empty_url_rejected(self):
        with pytest.raises(ValueError):
            validate_url("")

    def test_no_scheme_rejected(self):
        with pytest.raises(ValueError):
            validate_url("example.com/page.html")


class TestPrivateIpBlocking:
    @pytest.mark.parametrize("ip", [
        "10.0.0.1",
        "10.255.255.255",
        "172.16.0.1",
        "172.31.255.255",
        "192.168.0.1",
        "192.168.255.255",
        "127.0.0.1",
        "127.255.255.255",
    ])
    def test_private_ip_blocked(self, ip):
        with patch("checker.ssrf._resolve_host", return_value=ip):
            with pytest.raises(ValueError, match="プライベートIPアドレス"):
                validate_url(f"http://example.com/")

    def test_public_ip_allowed(self):
        with patch("checker.ssrf._resolve_host", return_value="203.0.113.1"):
            validate_url("http://example.com/page.html")

    def test_another_public_ip_allowed(self):
        with patch("checker.ssrf._resolve_host", return_value="8.8.8.8"):
            validate_url("http://dns.google/")


class TestLinkLocalBlocking:
    def test_link_local_blocked(self):
        with patch("checker.ssrf._resolve_host", return_value="169.254.1.1"):
            with pytest.raises(ValueError, match="プライベートIPアドレス"):
                validate_url("http://example.com/")

    def test_metadata_endpoint_blocked(self):
        with patch("checker.ssrf._resolve_host", return_value="169.254.169.254"):
            with pytest.raises(ValueError, match="プライベートIPアドレス"):
                validate_url("http://169.254.169.254/latest/meta-data/")


class TestDnsResolution:
    def test_dns_resolution_failure(self):
        with patch("checker.ssrf._resolve_host", side_effect=socket.gaierror("DNS resolution failed")):
            with pytest.raises(ValueError, match="DNS解決に失敗"):
                validate_url("http://nonexistent.invalid/")

    def test_hostname_resolved_to_private_ip_blocked(self):
        with patch("checker.ssrf._resolve_host", return_value="127.0.0.1"):
            with pytest.raises(ValueError, match="プライベートIPアドレス"):
                validate_url("http://evil.example.com/")
