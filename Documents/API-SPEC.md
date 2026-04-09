# API仕様書

Web死活監視システムのAPI利用手順。テスト画面からの利用方法およびAPI直接呼び出し方法を記載する。

## テスト画面アクセス

| 項目 | 値 |
|------|-----|
| URL（本番） | https://web-alive.osasi-cloud.com |
| URL（検証） | https://web-alive-dev.osasi-cloud.com |
| アクセス条件 | 弊社グローバルIP (210.225.75.184) からのみ |
| 認証 | Cognito ユーザーアカウント (メール/パスワード) |
| 対応ブラウザ | Chrome / Edge / Firefox (最新版) |

## Cognito認証の取得手順

### テスト画面から (自動)

1. https://web-alive.osasi-cloud.com にアクセス
2. カスタムログイン画面が表示される
3. メールアドレス・パスワードを入力してサインイン
4. 以降のAPI呼び出しは自動的にJWTが付与される

### 新規アカウント登録（セルフサインアップ）

1. ログイン画面で「アカウント作成」をクリック
2. `@osasi.co.jp` ドメインのメールアドレスとパスワードを入力
3. 確認コードがメールに届く
4. 確認コードを入力して本人確認を完了
5. ログイン可能になる

※ `@osasi.co.jp` 以外のドメインはPre Sign-upトリガーにより拒否される

### API直接呼び出し用 (手動トークン取得)

```bash
# Cognito トークン取得
aws cognito-idp initiate-auth \
  --client-id <USER_POOL_CLIENT_ID> \
  --auth-flow USER_SRP_AUTH \
  --auth-parameters USERNAME=<email>,SRP_A=<srp_a> \
  --region ap-northeast-1

# USER_PASSWORD_AUTH は無効化されているため SRP 認証を使用
# 簡易的にトークン取得する場合はフロントエンドの開発者ツールから取得する:
# 1. ブラウザでログイン
# 2. 開発者ツール → Application → Local Storage
# 3. CognitoIdentityServiceProvider.*.idToken の値をコピー
export COGNITO_TOKEN="eyJraWQi..."
```

### USER_POOL_CLIENT_ID の取得

```bash
aws cloudformation describe-stacks \
  --stack-name WebAliveMonitoring \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" \
  --output text
```

## 各エンドポイント呼び出しサンプル

### GET /sites — 監視サイト一覧取得

```bash
# 全サイト取得
curl -s https://uexyis2uh1.execute-api.ap-northeast-1.amazonaws.com/Prod/sites \
  -H "Authorization: Bearer $COGNITO_TOKEN" | jq .

# 自分が登録したサイトのみ
curl -s "https://uexyis2uh1.execute-api.ap-northeast-1.amazonaws.com/Prod/sites?filter=mine" \
  -H "Authorization: Bearer $COGNITO_TOKEN" | jq .
```

### POST /sites — 監視サイト登録

#### URL更新チェック

```bash
curl -X POST https://uexyis2uh1.execute-api.ap-northeast-1.amazonaws.com/Prod/sites \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $COGNITO_TOKEN" \
  -d '{
    "site_name": "○○ダム",
    "monitor_type": "url_check",
    "targets": [
      { "url": "https://example.com/dam/latest.png" }
    ],
    "schedule_start": "00:20",
    "schedule_interval_minutes": 60,
    "consecutive_threshold": 3,
    "enabled": true
  }'
```

#### CloudWatchログ検索

```bash
curl -X POST https://uexyis2uh1.execute-api.ap-northeast-1.amazonaws.com/Prod/sites \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $COGNITO_TOKEN" \
  -d '{
    "site_name": "SaaS送信監視",
    "monitor_type": "cloudwatch_log",
    "targets": [
      {
        "log_group": "DataTransferSystem2-OsBoard-Function1",
        "message_filter": "リクエストを送信します。",
        "json_search_word": "\"account\": \"10206721\"",
        "search_period_minutes": 60
      }
    ],
    "schedule_start": "00:00",
    "schedule_interval_minutes": 60,
    "consecutive_threshold": 3,
    "enabled": true
  }'
```

### GET /sites/{site_id} — 監視サイト詳細取得

```bash
curl -s https://uexyis2uh1.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID \
  -H "Authorization: Bearer $COGNITO_TOKEN" | jq .
```

### PUT /sites/{site_id} — 監視サイト更新

```bash
curl -X PUT https://uexyis2uh1.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $COGNITO_TOKEN" \
  -d '{
    "site_name": "○○ダム（更新）",
    "monitor_type": "url_check",
    "targets": [
      { "url": "https://example.com/dam/latest.png" },
      { "url": "https://example.com/dam/graph.png" }
    ],
    "schedule_start": "00:30",
    "schedule_interval_minutes": 30,
    "consecutive_threshold": 5,
    "enabled": true
  }'
```

※ 作成者以外が更新しようとすると `403 Not authorized to modify this site` が返る

### DELETE /sites/{site_id} — 監視サイト削除

```bash
curl -X DELETE https://uexyis2uh1.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID \
  -H "Authorization: Bearer $COGNITO_TOKEN"
```

### GET /sites/{site_id}/results — チェック結果一覧

```bash
curl -s https://uexyis2uh1.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID/results \
  -H "Authorization: Bearer $COGNITO_TOKEN" | jq .
```

### GET /sites/{site_id}/status-changes — 状態変化履歴

```bash
curl -s https://uexyis2uh1.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID/status-changes \
  -H "Authorization: Bearer $COGNITO_TOKEN" | jq .
```

### POST /sites/{site_id}/notifications — 通知設定追加

#### メール通知

```bash
curl -X POST https://uexyis2uh1.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID/notifications \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $COGNITO_TOKEN" \
  -d '{
    "type": "email",
    "destination": "admin@osasi.co.jp",
    "message_template": "至急確認してください"
  }'
```

#### Slack通知

```bash
curl -X POST https://uexyis2uh1.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID/notifications \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $COGNITO_TOKEN" \
  -d '{
    "type": "slack",
    "destination": "/web-alive-monitoring/slack-webhook-url",
    "mention": "@channel",
    "message_template": ""
  }'
```

※ Slack Webhook URLはSSM Parameter Store（SecureString）に格納し、パラメータ名を `destination` に指定する

### POST /sites/{site_id}/test-check — 手動チェック実行

```bash
curl -X POST https://uexyis2uh1.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID/test-check \
  -H "Authorization: Bearer $COGNITO_TOKEN" | jq .
```

### POST /sites/{site_id}/test-notify — テスト通知送信

```bash
curl -X POST https://uexyis2uh1.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID/test-notify \
  -H "Authorization: Bearer $COGNITO_TOKEN" | jq .
```

### GET /cloudwatch/log-groups — CWロググループ一覧

```bash
curl -s https://uexyis2uh1.execute-api.ap-northeast-1.amazonaws.com/Prod/cloudwatch/log-groups \
  -H "Authorization: Bearer $COGNITO_TOKEN" | jq '.data[].logGroupName'
```

## Python サンプル

```python
import requests

API_BASE = "https://uexyis2uh1.execute-api.ap-northeast-1.amazonaws.com/Prod"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {cognito_token}"
}

# サイト一覧取得
response = requests.get(f"{API_BASE}/sites", headers=headers)
sites = response.json()["data"]
for site in sites:
    print(f"{site['site_name']}: {site['last_check_status']}")

# サイト登録
new_site = requests.post(f"{API_BASE}/sites", headers=headers, json={
    "site_name": "テスト現場",
    "monitor_type": "url_check",
    "targets": [{"url": "https://example.com/test.png"}],
    "schedule_start": "00:00",
    "schedule_interval_minutes": 60,
})
site_id = new_site.json()["data"]["site_id"]
print(f"Created: {site_id}")
```

## エラーコード一覧と対処法

| HTTP | エラーメッセージ | 原因 | 対処法 |
|------|----------------|------|--------|
| 400 | site_name is required | 必須フィールド未指定 | リクエストボディを確認 |
| 400 | targets must be a non-empty array | 監視対象が空 | 1件以上のターゲットを指定 |
| 400 | No notifications configured | 通知設定がない状態でテスト通知 | 通知設定を先に追加 |
| 403 | Not authorized to modify this site | 作成者以外による操作 | 作成者アカウントで操作 |
| 403 | Forbidden | IP制限でブロック | 社内ネットワークからアクセス |
| 404 | Site not found | サイトIDが不正 | 正しいsite_idを使用 |
| 500 | Internal server error | サーバー内部エラー | 時間を置いてリトライ |
