"""JWT claims からユーザー情報を取得するユーティリティ"""


def get_email_from_claims(event: dict) -> str | None:
    """API Gateway Cognito Authorizer の claims から email を取得する。

    Args:
        event: API Gateway proxy event

    Returns:
        メールアドレス、取得できない場合は None
    """
    try:
        return event["requestContext"]["authorizer"]["claims"]["email"]
    except (KeyError, TypeError):
        return None
