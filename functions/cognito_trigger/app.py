ALLOWED_DOMAIN = "osasi.co.jp"


def handler(event, context):
    email = event.get("request", {}).get("userAttributes", {}).get("email", "")
    if not email:
        raise Exception("email attribute is required")

    domain = email.split("@")[-1].lower()
    if domain != ALLOWED_DOMAIN:
        raise Exception(
            f"Signup is restricted to @{ALLOWED_DOMAIN} domain only"
        )

    return event
