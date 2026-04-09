import os
import json

import boto3
import pytest
from moto import mock_aws


STACK_NAME = "TestStack"


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-northeast-1")
    monkeypatch.setenv("STACK_NAME", STACK_NAME)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("SITES_TABLE_NAME", f"{STACK_NAME}-sites")
    monkeypatch.setenv("CHECK_RESULTS_TABLE_NAME", f"{STACK_NAME}-check_results")
    monkeypatch.setenv("NOTIFICATIONS_TABLE_NAME", f"{STACK_NAME}-notifications")
    monkeypatch.setenv("STATUS_CHANGES_TABLE_NAME", f"{STACK_NAME}-status_changes")
    monkeypatch.setenv("NOTIFICATION_QUEUE_URL", "https://sqs.ap-northeast-1.amazonaws.com/123456789012/test-notification-queue")
    monkeypatch.setenv("CW_LOG_QUEUE_URL", "https://sqs.ap-northeast-1.amazonaws.com/123456789012/test-cw-log-queue")
    monkeypatch.setenv("CHECKER_FUNCTION_ARN", "arn:aws:lambda:ap-northeast-1:123456789012:function:test-checker")
    monkeypatch.setenv("SCHEDULER_ROLE_ARN", "arn:aws:iam::123456789012:role/test-scheduler-role")
    monkeypatch.setenv("SCHEDULER_GROUP_NAME", "default")


def _create_sites_table(dynamodb):
    dynamodb.create_table(
        TableName=f"{STACK_NAME}-sites",
        KeySchema=[
            {"AttributeName": "site_id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "site_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _create_check_results_table(dynamodb):
    dynamodb.create_table(
        TableName=f"{STACK_NAME}-check_results",
        KeySchema=[
            {"AttributeName": "site_id", "KeyType": "HASH"},
            {"AttributeName": "checked_at#target_url", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "site_id", "AttributeType": "S"},
            {"AttributeName": "checked_at#target_url", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _create_notifications_table(dynamodb):
    dynamodb.create_table(
        TableName=f"{STACK_NAME}-notifications",
        KeySchema=[
            {"AttributeName": "site_id", "KeyType": "HASH"},
            {"AttributeName": "notification_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "site_id", "AttributeType": "S"},
            {"AttributeName": "notification_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _create_status_changes_table(dynamodb):
    dynamodb.create_table(
        TableName=f"{STACK_NAME}-status_changes",
        KeySchema=[
            {"AttributeName": "site_id", "KeyType": "HASH"},
            {"AttributeName": "changed_at", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "site_id", "AttributeType": "S"},
            {"AttributeName": "changed_at", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture
def dynamodb_tables():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        _create_sites_table(dynamodb)
        _create_check_results_table(dynamodb)
        _create_notifications_table(dynamodb)
        _create_status_changes_table(dynamodb)
        yield dynamodb


def make_api_event(
    method: str,
    path: str,
    body: dict | None = None,
    path_parameters: dict | None = None,
    query_parameters: dict | None = None,
    email: str = "user@example.com",
) -> dict:
    """API Gateway proxy event を構築"""
    event = {
        "httpMethod": method,
        "path": path,
        "headers": {
            "Content-Type": "application/json",
        },
        "pathParameters": path_parameters,
        "queryStringParameters": query_parameters,
        "requestContext": {
            "authorizer": {
                "claims": {
                    "email": email,
                    "sub": "test-user-sub",
                }
            }
        },
        "body": json.dumps(body) if body else None,
    }
    return event
