import pytest
from cognito_trigger.app import handler


class TestCognitoPreSignupTrigger:
    """Cognito Pre Sign-up トリガーのドメイン制限テスト"""

    def _make_event(self, email: str) -> dict:
        return {
            "request": {
                "userAttributes": {
                    "email": email,
                }
            },
            "response": {},
        }

    def test_example-company_domain_allowed(self):
        event = self._make_event("user@example.com")
        result = handler(event, None)
        assert result == event

    def test_gmail_rejected(self):
        event = self._make_event("user@gmail.com")
        with pytest.raises(Exception, match="example.com"):
            handler(event, None)

    def test_subdomain_rejected(self):
        event = self._make_event("user@fake-example.com")
        with pytest.raises(Exception, match="example.com"):
            handler(event, None)

    def test_uppercase_allowed(self):
        event = self._make_event("USER@OSASI.CO.JP")
        result = handler(event, None)
        assert result == event

    def test_missing_email_rejected(self):
        event = {"request": {"userAttributes": {}}, "response": {}}
        with pytest.raises(Exception):
            handler(event, None)
