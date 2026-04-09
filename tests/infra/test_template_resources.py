"""CloudFormation テンプレートのリソース定義テスト"""

import pytest


def _get_resources_by_type(template: dict, resource_type: str) -> dict:
    return {
        k: v
        for k, v in template.get("Resources", {}).items()
        if v.get("Type") == resource_type
    }


def _assert_tags(properties: dict, project_tag: bool = True, name_tag: bool = True):
    tags = properties.get("Tags", [])
    tag_keys = [t["Key"] for t in tags]
    if project_tag:
        assert "Project" in tag_keys, "Project タグが必要"
    if name_tag:
        assert "Name" in tag_keys, "Name タグが必要"


# =============================================================================
# DynamoDB テスト
# =============================================================================


class TestDynamoDBTables:
    EXPECTED_TABLES = {
        "sites": {"pk": "site_id", "sk": None},
        "check_results": {"pk": "site_id", "sk": "checked_at#target_url"},
        "notifications": {"pk": "site_id", "sk": "notification_id"},
        "status_changes": {"pk": "site_id", "sk": "changed_at"},
    }

    def _find_table(self, template, table_suffix):
        tables = _get_resources_by_type(template, "AWS::DynamoDB::Table")
        for name, res in tables.items():
            props = res["Properties"]
            table_name = props.get("TableName", "")
            if isinstance(table_name, dict):
                parts = []
                if "Fn::Sub" in table_name:
                    parts = [table_name["Fn::Sub"]]
                elif "Fn::Join" in table_name:
                    parts = table_name["Fn::Join"][1]
            else:
                parts = [table_name]
            for p in parts:
                if isinstance(p, str) and table_suffix in p:
                    return name, res
        return None, None

    def test_four_tables_exist(self, database_template):
        tables = _get_resources_by_type(database_template, "AWS::DynamoDB::Table")
        assert len(tables) == 4, f"DynamoDB テーブルは4つ必要（実際: {len(tables)}）"

    @pytest.mark.parametrize(
        "table_suffix,expected",
        [
            ("sites", {"pk": "site_id", "sk": None}),
            ("check_results", {"pk": "site_id", "sk": "checked_at#target_url"}),
            ("notifications", {"pk": "site_id", "sk": "notification_id"}),
            ("status_changes", {"pk": "site_id", "sk": "changed_at"}),
        ],
    )
    def test_table_key_schema(self, database_template, table_suffix, expected):
        _, res = self._find_table(database_template, table_suffix)
        assert res is not None, f"テーブル {table_suffix} が見つからない"
        props = res["Properties"]
        key_schema = props["KeySchema"]
        pk = next(k for k in key_schema if k["KeyType"] == "HASH")
        assert pk["AttributeName"] == expected["pk"]
        if expected["sk"]:
            sk = next(k for k in key_schema if k["KeyType"] == "RANGE")
            assert sk["AttributeName"] == expected["sk"]

    def test_all_tables_on_demand(self, database_template):
        tables = _get_resources_by_type(database_template, "AWS::DynamoDB::Table")
        for name, res in tables.items():
            mode = res["Properties"].get("BillingMode")
            assert mode == "PAY_PER_REQUEST", f"{name} は PAY_PER_REQUEST が必要"

    def test_check_results_ttl(self, database_template):
        _, res = self._find_table(database_template, "check_results")
        ttl = res["Properties"].get("TimeToLiveSpecification", {})
        assert ttl.get("Enabled") is True
        assert ttl.get("AttributeName") == "ttl"

    def test_status_changes_ttl(self, database_template):
        _, res = self._find_table(database_template, "status_changes")
        ttl = res["Properties"].get("TimeToLiveSpecification", {})
        assert ttl.get("Enabled") is True
        assert ttl.get("AttributeName") == "ttl"

    def test_all_tables_have_tags(self, database_template):
        tables = _get_resources_by_type(database_template, "AWS::DynamoDB::Table")
        for name, res in tables.items():
            _assert_tags(res["Properties"])


# =============================================================================
# Cognito テスト
# =============================================================================


class TestCognito:
    def test_user_pool_exists(self, auth_template):
        pools = _get_resources_by_type(auth_template, "AWS::Cognito::UserPool")
        assert len(pools) >= 1, "Cognito UserPool が必要"

    def test_self_signup_enabled(self, auth_template):
        pools = _get_resources_by_type(auth_template, "AWS::Cognito::UserPool")
        for _, res in pools.items():
            policies = res["Properties"].get("AdminCreateUserConfig", {})
            assert (
                policies.get("AllowAdminCreateUserOnly") is not True
            ), "セルフサインアップが有効であること"

    def test_mfa_optional(self, auth_template):
        pools = _get_resources_by_type(auth_template, "AWS::Cognito::UserPool")
        for _, res in pools.items():
            mfa = res["Properties"].get("MfaConfiguration")
            assert mfa == "OPTIONAL", "MFA は OPTIONAL が必要"

    def test_pre_signup_trigger(self, auth_template):
        pools = _get_resources_by_type(auth_template, "AWS::Cognito::UserPool")
        for _, res in pools.items():
            triggers = res["Properties"].get("LambdaConfig", {})
            assert "PreSignUp" in triggers, "Pre Sign-up トリガーが必要"

    def test_user_pool_client_exists(self, auth_template):
        clients = _get_resources_by_type(
            auth_template, "AWS::Cognito::UserPoolClient"
        )
        assert len(clients) >= 1, "UserPoolClient が必要"

    def test_user_pool_tags(self, auth_template):
        pools = _get_resources_by_type(auth_template, "AWS::Cognito::UserPool")
        for _, res in pools.items():
            tags = res["Properties"].get("UserPoolTags", {})
            assert "Project" in tags, "Project タグが必要"
            assert "Name" in tags, "Name タグが必要"


# =============================================================================
# SQS テスト
# =============================================================================


class TestSQS:
    def test_three_queues_exist(self, queue_template):
        queues = _get_resources_by_type(queue_template, "AWS::SQS::Queue")
        assert len(queues) >= 3, f"SQS キューは3つ以上必要（実際: {len(queues)}）"

    def test_dlq_message_retention(self, queue_template):
        queues = _get_resources_by_type(queue_template, "AWS::SQS::Queue")
        dlq_found = False
        for name, res in queues.items():
            if "DLQ" in name or "DeadLetter" in name:
                retention = res["Properties"].get("MessageRetentionPeriod")
                assert retention == 1209600, "DLQ は 14日 (1209600秒) 保持"
                dlq_found = True
        assert dlq_found, "DLQ キューが必要"

    def test_redrive_policy(self, queue_template):
        queues = _get_resources_by_type(queue_template, "AWS::SQS::Queue")
        redrive_count = 0
        for name, res in queues.items():
            if "DLQ" in name or "DeadLetter" in name:
                continue
            redrive = res["Properties"].get("RedrivePolicy")
            if redrive:
                assert redrive.get("maxReceiveCount") == 3
                redrive_count += 1
        assert redrive_count >= 2, "CWログ監視・通知キューに RedrivePolicy が必要"

    def test_all_queues_have_tags(self, queue_template):
        queues = _get_resources_by_type(queue_template, "AWS::SQS::Queue")
        for name, res in queues.items():
            _assert_tags(res["Properties"])


# =============================================================================
# CloudFront + S3 テスト
# =============================================================================


class TestCloudFrontS3:
    def test_s3_bucket_exists(self, web_template):
        buckets = _get_resources_by_type(web_template, "AWS::S3::Bucket")
        assert len(buckets) >= 1, "S3 バケットが必要"

    def test_oac_exists(self, web_template):
        oacs = _get_resources_by_type(
            web_template, "AWS::CloudFront::OriginAccessControl"
        )
        assert len(oacs) >= 1, "CloudFront OAC が必要"

    def test_cloudfront_distribution(self, web_template):
        dists = _get_resources_by_type(
            web_template, "AWS::CloudFront::Distribution"
        )
        assert len(dists) >= 1, "CloudFront Distribution が必要"

    def test_ip_restrict_function(self, web_template):
        functions = _get_resources_by_type(
            web_template, "AWS::CloudFront::Function"
        )
        assert len(functions) >= 1, "CloudFront Function（IP制限）が必要"
        for _, res in functions.items():
            code = res["Properties"].get("FunctionCode", "")
            if isinstance(code, dict) and "Fn::Sub" in code:
                code_parts = code["Fn::Sub"]
                if isinstance(code_parts, list):
                    code = code_parts[0]
                else:
                    code = code_parts
            assert "clientIp" in str(code) or "viewer.ip" in str(
                code
            ), "IP制限ロジックが必要"

    def test_spa_error_responses(self, web_template):
        dists = _get_resources_by_type(
            web_template, "AWS::CloudFront::Distribution"
        )
        for _, res in dists.items():
            config = res["Properties"]["DistributionConfig"]
            errors = config.get("CustomErrorResponses", [])
            error_codes = [e["ErrorCode"] for e in errors]
            assert 403 in error_codes, "403 → /index.html のエラーレスポンスが必要"
            assert 404 in error_codes, "404 → /index.html のエラーレスポンスが必要"

    def test_bucket_policy_oac(self, web_template):
        policies = _get_resources_by_type(web_template, "AWS::S3::BucketPolicy")
        assert len(policies) >= 1, "S3 BucketPolicy が必要"

    def test_route53_record(self, web_template):
        records = _get_resources_by_type(
            web_template, "AWS::Route53::RecordSetGroup"
        )
        assert len(records) >= 1, "Route 53 レコードが必要"

    def test_distribution_tags(self, web_template):
        dists = _get_resources_by_type(
            web_template, "AWS::CloudFront::Distribution"
        )
        for _, res in dists.items():
            _assert_tags(res["Properties"])

    def test_bucket_tags(self, web_template):
        buckets = _get_resources_by_type(web_template, "AWS::S3::Bucket")
        for _, res in buckets.items():
            _assert_tags(res["Properties"])


# =============================================================================
# SES テスト
# =============================================================================


class TestSES:
    def test_email_identity_exists(self, ses_template):
        identities = _get_resources_by_type(
            ses_template, "AWS::SES::EmailIdentity"
        )
        assert len(identities) >= 1, "SES EmailIdentity が必要"

    def test_mail_from_domain(self, ses_template):
        identities = _get_resources_by_type(
            ses_template, "AWS::SES::EmailIdentity"
        )
        for _, res in identities.items():
            mail_from = res["Properties"].get("MailFromAttributes", {})
            domain = mail_from.get("MailFromDomain", "")
            if isinstance(domain, dict):
                assert "Fn::Sub" in domain or "Sub" in str(
                    domain
                ), "MailFrom に bounce. サブドメインが必要"
            else:
                assert "bounce." in domain

    def test_route53_records(self, ses_template):
        records = _get_resources_by_type(
            ses_template, "AWS::Route53::RecordSetGroup"
        )
        assert len(records) >= 1, "SES用 Route53 レコードが必要"

    def test_dkim_records(self, ses_template):
        records = _get_resources_by_type(
            ses_template, "AWS::Route53::RecordSetGroup"
        )
        for _, res in records.items():
            record_sets = res["Properties"].get("RecordSets", [])
            cname_count = sum(1 for r in record_sets if r.get("Type") == "CNAME")
            assert cname_count >= 3, "DKIM用 CNAME レコード3つが必要"


# =============================================================================
# メインスタック テスト
# =============================================================================


class TestMainTemplate:
    def test_parameters_exist(self, main_template):
        params = main_template.get("Parameters", {})
        required = [
            "StackName",
            "ProjectName",
            "OsasiPowertoolsPython",
            "LogLevel",
            "SubDomain",
            "AllowedIpAddresses",
            "HostedZoneId",
            "AcmCertificateArn",
        ]
        for p in required:
            assert p in params, f"パラメータ {p} が必要"

    def test_globals_function(self, main_template):
        globals_section = main_template.get("Globals", {})
        func = globals_section.get("Function", {})
        assert func.get("Runtime") == "python3.13"
        assert func.get("MemorySize") == 128
        assert func.get("Timeout") == 30

    def test_nested_stacks(self, main_template):
        stacks = _get_resources_by_type(
            main_template, "AWS::CloudFormation::Stack"
        )
        assert len(stacks) >= 4, "ネストスタック4つ以上（database, auth, queue, web）が必要"
