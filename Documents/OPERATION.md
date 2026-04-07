# Web Alive Monitoring 運用ドキュメント

## 1. 環境一覧

| 項目 | 検証環境 (Dev) | 本番環境 (Production) |
|------|---------------|---------------------|
| スタック名 | WebAliveMonitoring-Dev | WebAliveMonitoring |
| フロントURL | https://web-alive-dev.osasi-cloud.com | https://web-alive.osasi-cloud.com |
| API URL | CloudFormation Output `ApiUrl` 参照 | 同左 |
| LogLevel | DEBUG | INFO |
| リージョン | ap-northeast-1 | ap-northeast-1 |
| SES リージョン | us-west-2 | us-west-2 |
| SES ドメイン | alive.osasi-cloud.com | alive.osasi-cloud.com |

---

## 2. デプロイ手順

### 2.1 バックエンド (SAM)

```bash
# 1. ビルド（コンテナ使用必須）
sam build --use-container

# 2-a. 検証環境デプロイ
sam deploy

# 2-b. 本番環境デプロイ
sam deploy --config-env production
```

**注意事項:**
- `sam build` を省略すると `requirements.txt` の依存ライブラリがインストールされない
- 本番環境は `confirm_changeset = true` のため、変更セットの確認プロンプトが表示される
- ロールバックが必要な場合は AWS コンソールの CloudFormation から手動実行

### 2.2 フロントエンド

```bash
# 1. Amplify設定ファイル生成（デプロイスクリプト経由）
#    amplifyconfiguration.ts が自動生成される

# 2. ビルド
cd frontend
npm install
npm run build

# 3. S3にアップロード
aws s3 sync dist/ s3://<WebsiteBucketName>/ --delete

# 4. CloudFrontキャッシュ無効化
aws cloudfront create-invalidation \
  --distribution-id <CloudFrontDistributionId> \
  --paths "/*"
```

**バケット名・DistributionID の取得:**

```bash
# CloudFormation Output から取得
aws cloudformation describe-stacks \
  --stack-name WebAliveMonitoring \
  --query "Stacks[0].Outputs[?OutputKey=='WebsiteBucketName'].OutputValue" \
  --output text

aws cloudformation describe-stacks \
  --stack-name WebAliveMonitoring \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionId'].OutputValue" \
  --output text
```

---

## 3. SES ドメイン検証手順

SES の EmailIdentity (`alive.osasi-cloud.com`) は SAM テンプレートで自動作成される。

Route 53 の DKIM / SPF / MailFrom レコードもテンプレートで自動管理されるため、通常は手動操作不要。

**検証ステータス確認:**

```bash
aws ses get-email-identity \
  --email-identity alive.osasi-cloud.com \
  --region us-west-2
```

`DkimAttributes.Status` が `SUCCESS` であることを確認。

**SES サンドボックス解除:**

初期状態では SES はサンドボックスモード。本番利用にはサンドボックス解除申請が必要。

---

## 4. 環境変数一覧

### Lambda 共通

| 環境変数 | 説明 | 設定元 |
|---------|------|--------|
| LOG_LEVEL | ログレベル (DEBUG/INFO) | samconfig.toml |
| SITES_TABLE_NAME | sites テーブル名 | CloudFormation |
| CHECK_RESULTS_TABLE_NAME | check_results テーブル名 | CloudFormation |
| NOTIFICATIONS_TABLE_NAME | notifications テーブル名 | CloudFormation |
| STATUS_CHANGES_TABLE_NAME | status_changes テーブル名 | CloudFormation |

### API Lambda 固有

| 環境変数 | 説明 |
|---------|------|
| CHECKER_FUNCTION_ARN | checker Lambda の ARN |
| SCHEDULER_ROLE_ARN | EventBridge Scheduler の実行ロール ARN |
| SCHEDULER_GROUP_NAME | Scheduler グループ名 (default) |
| CW_LOG_QUEUE_URL | CloudWatch ログ監視キューの URL |
| NOTIFICATION_QUEUE_URL | 通知キューの URL |
| EMAIL_DOMAIN | SES 送信元ドメイン |
| SES_REGION | SES のリージョン (us-west-2) |
| STACK_NAME | CloudFormation スタック名 |

### Checker Lambda 固有

| 環境変数 | 説明 |
|---------|------|
| NOTIFICATION_QUEUE_URL | 通知キューの URL |

### CW Checker Lambda 固有

| 環境変数 | 説明 |
|---------|------|
| NOTIFICATION_QUEUE_URL | 通知キューの URL |

### Notifier Lambda 固有

| 環境変数 | 説明 |
|---------|------|
| EMAIL_DOMAIN | SES 送信元ドメイン |
| SES_REGION | SES のリージョン |

### フロントエンド (Vite 環境変数)

| 環境変数 | 説明 | 設定ファイル |
|---------|------|------------|
| VITE_API_ENDPOINT | API Gateway の URL | .env または自動生成 |

---

## 5. トラブルシューティング

### 5.1 DLQ (Dead Letter Queue) の確認

通知処理が3回リトライしても失敗した場合、メッセージが DLQ に退避される。

```bash
# DLQ のメッセージ数を確認
aws sqs get-queue-attributes \
  --queue-url <DLQ_URL> \
  --attribute-names ApproximateNumberOfMessages

# DLQ からメッセージを確認（削除せず確認のみ）
aws sqs receive-message \
  --queue-url <DLQ_URL> \
  --max-number-of-messages 5
```

DLQ にメッセージが滞留している場合:
1. メッセージ内容を確認し、失敗原因を特定
2. 原因を修正後、DLQ のメッセージを元のキューに再送信（redrive）
3. AWS コンソールの SQS 画面から「DLQ redrive」機能を使用可能

### 5.2 Lambda ログの確認

```bash
# API Lambda のログ確認
aws logs tail /aws/lambda/WebAliveMonitoring-ApiFunction --follow

# Checker Lambda のログ確認
aws logs tail /aws/lambda/WebAliveMonitoring-CheckerFunction --follow

# CW Checker Lambda のログ確認
aws logs tail /aws/lambda/WebAliveMonitoring-CwCheckerFunction --follow

# Notifier Lambda のログ確認
aws logs tail /aws/lambda/WebAliveMonitoring-NotifierFunction --follow
```

**特定サイトのログを絞り込む場合:**

```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/WebAliveMonitoring-CheckerFunction \
  --filter-pattern '"site_id" "target-site-id"' \
  --start-time $(date -d '1 hour ago' +%s000)
```

### 5.3 EventBridge Scheduler の確認

```bash
# スケジュール一覧
aws scheduler list-schedules --group-name default

# 特定サイトのスケジュール確認
aws scheduler get-schedule \
  --name WebAliveMonitoring-site-<site_id> \
  --group-name default
```

### 5.4 チェックが実行されない場合

1. サイトの `enabled` が `true` か確認（ダッシュボードで無効状態でないか）
2. EventBridge Scheduler が `ENABLED` 状態か確認
3. Checker Lambda のログにエラーがないか確認
4. ターゲット URL へのアクセスがタイムアウトしていないか（10秒）
5. SSRF 保護によりプライベート IP がブロックされていないか

### 5.5 通知が届かない場合

**メール通知:**
1. SES のドメイン検証ステータスを確認
2. SES がサンドボックスモードでないか確認
3. 送信先メールアドレスが正しいか確認
4. SES の Bounce/Complaint メトリクスを確認

**Slack 通知:**
1. SSM Parameter Store に Webhook URL が正しく格納されているか確認
2. Webhook URL の有効期限が切れていないか確認
3. Slack チャンネルの権限設定を確認

### 5.6 フロントエンドが表示されない場合

1. CloudFront のキャッシュを無効化
2. S3 バケットにファイルがアップロードされているか確認
3. `index.html` が存在するか確認
4. CloudFront の Error Pages 設定で 403/404 が `/index.html` にリダイレクトされているか確認（SPA対応）
5. IP 制限で社内 IP が許可されているか確認

---

## 6. 監視・アラート

| 対象 | メトリクス | 閾値 | アクション |
|------|----------|------|----------|
| DLQ | ApproximateNumberOfMessages | > 0 | CloudWatch Alarm → 運用担当に通知 |
| API Lambda | Errors | > 10/5min | ログ確認 |
| Checker Lambda | Duration | > 30sec | ターゲット URL の応答確認 |

---

## 7. テスト実行

```bash
# 単体テスト + 統合テスト
python -m pytest tests/ -v

# カバレッジ付き
python -m pytest tests/ --cov=functions --cov-report=term-missing

# 特定テストのみ
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v

# フロントエンドビルド確認
cd frontend && npm run build
```
