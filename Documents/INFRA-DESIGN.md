# インフラ設計書

Web死活監視システムのAWSインフラ構成。SAMテンプレートによるネストスタック構成で全リソースを管理する。

## スタック構成

メインスタック + 8ネストスタック + SES別スタックの構成。

| スタック | テンプレート | 説明 |
|---------|------------|------|
| メイン | template.yaml | ネスト定義、共通パラメータ、Cognito Pre Sign-up Lambda |
| DatabaseStack | stacks/database/template.yaml | DynamoDB テーブル（4テーブル） |
| AuthStack | stacks/auth/template.yaml | Cognito User Pool + Client |
| QueueStack | stacks/queue/template.yaml | SQS キュー（3キュー） |
| CheckerStack | stacks/checker/template.yaml | URL更新チェック Lambda |
| CwCheckerStack | stacks/cw_checker/template.yaml | CloudWatchログ検索 Lambda |
| ApiStack | stacks/api/template.yaml | API Gateway + API Lambda + Scheduler Role |
| NotifierStack | stacks/notifier/template.yaml | 通知処理 Lambda |
| WebStack | stacks/web/template.yaml | S3 + CloudFront + Route 53 |
| SESスタック | stacks/ses/template.yaml | SES EmailIdentity + Route 53 DNS（別リージョン: us-west-2） |

### スタック間の依存関係

```
template.yaml (メイン)
  ├── DatabaseStack ─────────────────────────────────────────┐
  ├── AuthStack ─────────────────────────────────────────────┤
  ├── QueueStack ────────────────────────────────────────────┤
  ├── CheckerStack   ← DatabaseStack, QueueStack            │
  ├── CwCheckerStack ← DatabaseStack, QueueStack            │
  ├── ApiStack       ← DatabaseStack, AuthStack, QueueStack │
  ├── NotifierStack  ← DatabaseStack, QueueStack            │
  └── WebStack       （独立）                                │
                                                            │
stacks/ses/template.yaml （独立デプロイ、us-west-2）         │
```

## メインスタック (template.yaml)

### パラメータ設計

| パラメータ | 型 | デフォルト（Dev） | 本番値 | 説明 |
|-----------|-----|-----------------|--------|------|
| StackName | String | WebAliveMonitoring-Dev | WebAliveMonitoring | スタック名 |
| ProjectName | String | web-alive-monitoring | web-alive-monitoring | コスト配分タグ |
| OsasiPowertoolsPython | String | arn:aws:lambda:...:79 | 同左 | 社内Lambdaレイヤー ARN |
| LogLevel | String | DEBUG | INFO | Lambdaログレベル |
| SubDomain | String | web-alive-dev | web-alive | CloudFrontサブドメイン |
| AllowedIpAddresses | CommaDelimitedList | 210.225.75.184 | 同左 | IP制限 |
| HostedZoneId | String | Z2TVUBVNI4RE7N | 同左 | Route 53 ホストゾーンID |
| AcmCertificateArn | String | arn:aws:acm:us-east-1:... | 同左 | SSL証明書 ARN |

### Globals設定

| 項目 | 値 |
|------|-----|
| Runtime | python3.13 |
| MemorySize | 128 MB |
| Timeout | 30秒 |
| Architecture | x86_64 |
| Layers | OsasiPowertoolsPython |

## DatabaseStack — DynamoDB テーブル

### テーブル一覧

| テーブル | キー構成 | TTL | 説明 |
|---------|---------|-----|------|
| sites | PK: `site_id` | なし | 監視サイト設定 |
| check_results | PK: `site_id`, SK: `checked_at#target_url` | 90日 | チェック結果 |
| notifications | PK: `site_id`, SK: `notification_id` | なし | 通知設定 |
| status_changes | PK: `site_id`, SK: `changed_at` | 365日 | 状態変化履歴 |

### 共通設定

| 項目 | 値 |
|------|-----|
| BillingMode | PAY_PER_REQUEST（オンデマンド） |
| SSE | KMS暗号化有効（AWS管理キー） |
| タグ | Project: web-alive-monitoring |

## AuthStack — Cognito User Pool

### User Pool 設定

| 項目 | 値 |
|------|-----|
| User Pool名 | `{StackName}-user-pool` |
| セルフサインアップ | 有効 |
| ユーザー名属性 | email |
| 自動検証 | email |
| MFA | OPTIONAL（SOFTWARE_TOKEN_MFA） |
| Pre Sign-up トリガー | CognitoPreSignUpFunction（`@osasi.co.jp`ドメイン制限） |

### User Pool Client 設定

| 項目 | 値 |
|------|-----|
| Client名 | `{StackName}-client` |
| クライアントシークレット | なし（SPA用） |
| 認証フロー | USER_SRP_AUTH, REFRESH_TOKEN_AUTH |
| UserExistenceErrors | ENABLED（ユーザー存在エラーを隠蔽） |

## QueueStack — SQS キュー

| キュー | 用途 | VisibilityTimeout | リトライ |
|--------|------|-------------------|---------|
| CloudWatchLogQueue | CWログ監視のSQS経由実行 | 300秒 | 最大3回 → DLQ |
| NotificationQueue | 通知処理の非同期化 | 60秒 | 最大3回 → DLQ |
| DeadLetterQueue (DLQ) | 最終失敗メッセージ退避 | - | 14日保持 |

全キューでSQS管理SSE暗号化を有効化。

## CheckerStack — URL更新チェック Lambda

| 項目 | 値 |
|------|-----|
| 関数名 | `{StackName}-checker` |
| Runtime | python3.13 |
| MemorySize | 128 MB |
| Timeout | 30秒 |
| トリガー | EventBridge Scheduler（1サイト1スケジュール） |

### IAMポリシー

| 権限 | リソース |
|------|---------|
| dynamodb:GetItem, UpdateItem, PutItem | sites, check_results, status_changes テーブル |
| sqs:SendMessage | NotificationQueue |

## CwCheckerStack — CloudWatchログ検索 Lambda

| 項目 | 値 |
|------|-----|
| 関数名 | `{StackName}-cw-checker` |
| Runtime | python3.13 |
| MemorySize | 256 MB |
| Timeout | 300秒（5分） |
| ReservedConcurrentExecutions | 1（同時実行制限） |
| トリガー | SQS (CloudWatchLogQueue) |

### IAMポリシー

| 権限 | リソース |
|------|---------|
| dynamodb:GetItem, UpdateItem, PutItem | sites, check_results, status_changes テーブル |
| sqs:SendMessage | NotificationQueue |
| sqs:ReceiveMessage, DeleteMessage, GetQueueAttributes | CloudWatchLogQueue |
| logs:StartQuery, GetQueryResults, DescribeLogGroups | 全ロググループ |

## ApiStack — API Gateway + Lambda

### API Lambda

| 項目 | 値 |
|------|-----|
| 関数名 | `{StackName}-api` |
| Runtime | python3.13 |
| MemorySize | 128 MB |
| Timeout | 30秒 |
| トリガー | API Gateway (REST API) |

### 環境変数

| 変数 | 値 |
|------|-----|
| SITES_TABLE_NAME | DatabaseStack出力 |
| CHECK_RESULTS_TABLE_NAME | DatabaseStack出力 |
| NOTIFICATIONS_TABLE_NAME | DatabaseStack出力 |
| STATUS_CHANGES_TABLE_NAME | DatabaseStack出力 |
| CHECKER_FUNCTION_ARN | CheckerStack出力 |
| SCHEDULER_ROLE_ARN | SchedulerRole ARN |
| SCHEDULER_GROUP_NAME | default |
| CW_LOG_QUEUE_URL | QueueStack出力 |
| NOTIFICATION_QUEUE_URL | QueueStack出力 |
| EMAIL_DOMAIN | alive.osasi-cloud.com |
| SES_REGION | us-west-2 |

### IAMポリシー

| 権限 | リソース |
|------|---------|
| dynamodb:Scan, GetItem, PutItem, UpdateItem, DeleteItem, Query | 全4テーブル |
| scheduler:CreateSchedule, UpdateSchedule, DeleteSchedule, GetSchedule | * |
| iam:PassRole | SchedulerRole |
| lambda:InvokeFunction | CheckerFunction, CwCheckerFunction |
| sqs:SendMessage | NotificationQueue, CloudWatchLogQueue |
| logs:DescribeLogGroups | * |

### API Gateway 設定

| 項目 | 値 |
|------|-----|
| タイプ | REST API (Regional) |
| ステージ | Prod |
| Authorizer | Cognito User Pool Authorizer |
| リソースポリシー | IP制限（AllowedIpAddresses） |

### Scheduler実行ロール

| 権限 | リソース |
|------|---------|
| lambda:InvokeFunction | CheckerFunction |
| sqs:SendMessage | CloudWatchLogQueue |

## NotifierStack — 通知処理 Lambda

| 項目 | 値 |
|------|-----|
| 関数名 | `{StackName}-notifier` |
| Runtime | python3.13 |
| MemorySize | 128 MB |
| Timeout | 60秒 |
| トリガー | SQS (NotificationQueue) |

### IAMポリシー

| 権限 | リソース |
|------|---------|
| dynamodb:GetItem, Query | sites, notifications テーブル |
| sqs:ReceiveMessage, DeleteMessage, GetQueueAttributes | NotificationQueue |
| ses:SendEmail | alive.osasi-cloud.com（us-west-2） |
| ssm:GetParameter | /web-alive-monitoring/* |

## WebStack — S3 + CloudFront + Route 53

### S3

| 項目 | 値 |
|------|-----|
| バケット名 | `{SubDomain}-website-{AccountId}` |
| パブリックアクセス | 全ブロック |
| アクセス | CloudFront OAC 経由のみ |

### CloudFront

| 項目 | 値 |
|------|-----|
| DefaultRootObject | index.html |
| Default Origin | S3 (OAC) |
| ViewerProtocolPolicy | redirect-to-https |
| PriceClass | PriceClass_200 |
| Certificate | ACM (us-east-1) |
| CloudFront Function | IP制限 (viewer-request) |
| エラーページ | 403/404 → /index.html（SPA対応） |

### CloudFront Function

IP制限を CloudFront Function (viewer-request) で実施。

```javascript
function handler(event) {
  var request = event.request;
  var clientIp = event.viewer.ip;
  var allowedIps = 'ALLOWED_IPS'.split(',');

  if (allowedIps.indexOf(clientIp) === -1) {
    return {
      statusCode: 403,
      statusDescription: 'Forbidden',
      body: { encoding: 'text', data: 'Access denied' }
    };
  }
  return request;
}
```

### Route 53

| レコード | タイプ | 値 |
|---------|--------|-----|
| `{SubDomain}.osasi-cloud.com` | A (Alias) | CloudFront Distribution |

## SESスタック (別デプロイ)

SES EmailIdentity は us-west-2 リージョンにデプロイ（SES サンドボックス解除済みリージョン）。

### リソース

| リソース | 説明 |
|---------|------|
| EmailIdentity | `alive.osasi-cloud.com` ドメイン検証 |
| MailFrom | `bounce.alive.osasi-cloud.com` |
| Route 53 レコード | DKIM (CNAME x3) + SPF (TXT) + MailFrom (MX, TXT) |

### 送信元

```
OSASI.NET<noreply@alive.osasi-cloud.com>
```

## samconfig.toml

```toml
[default.deploy.parameters]
stack_name = "WebAliveMonitoring-Dev"
region = "ap-northeast-1"
s3_bucket = "osasi-sam-ap-northeast-1"
s3_prefix = "WebAliveMonitoring-Dev"
confirm_changeset = false
parameter_overrides = [
    "StackName=WebAliveMonitoring-Dev",
    "LogLevel=DEBUG",
    "SubDomain=web-alive-dev",
]

[production.deploy.parameters]
stack_name = "WebAliveMonitoring"
s3_prefix = "WebAliveMonitoring"
confirm_changeset = true
parameter_overrides = [
    "StackName=WebAliveMonitoring",
    "LogLevel=INFO",
    "SubDomain=web-alive",
]
```

## デプロイ手順

```bash
# 1. ビルド（コンテナ使用必須）
sam build --use-container

# 2. 検証環境デプロイ
sam deploy

# 3. 本番環境デプロイ
sam deploy --config-env production
```

## ディレクトリ構成

```
web-alive-monitoring/
├── template.yaml                    # メインスタック
├── samconfig.toml                   # 環境別設定
├── stacks/
│   ├── api/template.yaml            # API Gateway + Lambda
│   ├── auth/template.yaml           # Cognito
│   ├── checker/template.yaml        # URL更新チェック Lambda
│   ├── cw_checker/template.yaml     # CWログ検索 Lambda
│   ├── database/template.yaml       # DynamoDB
│   ├── notifier/template.yaml       # 通知処理 Lambda
│   ├── queue/template.yaml          # SQS キュー
│   ├── ses/template.yaml            # SES (us-west-2)
│   └── web/template.yaml            # S3 + CloudFront + Route 53
├── functions/
│   ├── api/                         # API Handler Lambda
│   ├── checker/                     # URL更新チェック Lambda
│   ├── cw_checker/                  # CWログ検索 Lambda
│   ├── notifier/                    # 通知処理 Lambda
│   └── cognito_trigger/             # Cognito Pre Sign-up Lambda
├── frontend/                        # Vue3 SPA
├── openapi/                         # OpenAPI仕様 + Swagger UI
├── Documents/                       # 設計書
└── tests/                           # テスト
```
