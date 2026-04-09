"""SES メール送信モジュール"""

import os

import boto3


STATUS_LABELS = {
    "updated": "正常",
    "not_updated": "異常（欠測）",
    "error": "エラー",
}

_ses_client = None


def _get_ses_client():
    global _ses_client
    if _ses_client is None:
        region = os.environ.get("SES_REGION", "us-west-2")
        _ses_client = boto3.client("ses", region_name=region)
    return _ses_client


def send_email(
    *,
    to_address: str,
    site_name: str,
    trigger_url: str,
    previous_status: str,
    new_status: str,
    last_checked_at: str,
    message_template: str,
) -> None:
    domain = os.environ.get("EMAIL_DOMAIN", "alive.osasi-cloud.com")
    source = f"OSASI.NET<noreply@{domain}>"
    subject = f"[Web Alive] {site_name} - 状態変化通知"

    prev_label = STATUS_LABELS.get(previous_status, previous_status)
    new_label = STATUS_LABELS.get(new_status, new_status)

    body = (
        f"⚠️ データ欠測検知\n"
        f"【現場名】{site_name}\n"
        f"【対象URL】{trigger_url}\n"
        f"【状態変化】{prev_label} → {new_label}\n"
        f"【最終更新】{last_checked_at}\n"
        f"【メッセージ】{message_template}"
    )

    client = _get_ses_client()
    client.send_email(
        Source=source,
        Destination={"ToAddresses": [to_address]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
        },
    )
