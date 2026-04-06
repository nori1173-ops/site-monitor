from api.utils.auth import get_email_from_claims


class TestGetEmailFromClaims:
    """API Gateway Cognito Authorizer のclaimsからemail取得"""

    def test_extract_email(self):
        event = {
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "email": "user@osasi.co.jp",
                        "sub": "12345",
                    }
                }
            }
        }
        assert get_email_from_claims(event) == "user@osasi.co.jp"

    def test_missing_email(self):
        event = {
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "sub": "12345",
                    }
                }
            }
        }
        assert get_email_from_claims(event) is None

    def test_missing_claims(self):
        event = {
            "requestContext": {
                "authorizer": {}
            }
        }
        assert get_email_from_claims(event) is None

    def test_missing_authorizer(self):
        event = {
            "requestContext": {}
        }
        assert get_email_from_claims(event) is None

    def test_empty_event(self):
        event = {}
        assert get_email_from_claims(event) is None
