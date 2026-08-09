"""Slack Webhook 送信モジュール"""

import boto3
import requests


STATUS_LABELS = {
    "updated": "正常",
    "not_updated": "異常（欠測）",
    "error": "エラー",
}

_ssm_client = None


def _convert_slack_mention(mention: str) -> str:
    if not mention:
        return ""
    if mention in ("@channel", "@here", "@everyone"):
        return f"<!{mention[1:]}>"
    return mention


def _get_ssm_client():
    global _ssm_client
    if _ssm_client is None:
        _ssm_client = boto3.client("ssm")
    return _ssm_client


def send_slack(
    *,
    ssm_parameter_name: str,
    mention: str,
    site_name: str,
    trigger_url: str,
    previous_status: str,
    new_status: str,
    last_checked_at: str,
) -> None:
    ssm = _get_ssm_client()
    if not ssm_parameter_name.startswith("/"):
        ssm_parameter_name = "/" + ssm_parameter_name
    result = ssm.get_parameter(Name=ssm_parameter_name, WithDecryption=True)
    webhook_url = result["Parameter"]["Value"]

    prev_label = STATUS_LABELS.get(previous_status, previous_status)
    new_label = STATUS_LABELS.get(new_status, new_status)

    mention = _convert_slack_mention(mention)
    lines = []
    if mention:
        lines.append(mention)
    lines.append(
        f"⚠️ *データ欠測検知*\n"
        f"*現場名:* {site_name}\n"
        f"*対象:* {trigger_url}\n"
        f"*状態変化:* {prev_label} → {new_label}\n"
        f"*最終更新:* {last_checked_at}"
    )

    text = "\n".join(lines)
    response = requests.post(webhook_url, json={"text": text}, timeout=10)
    response.raise_for_status()
