# API仕様書

Web死活監視システムのAPI利用手順。テスト画面からの利用方法およびAPI直接呼び出し方法を記載する。

## テスト画面アクセス

| 項目 | 値 |
|------|-----|
| URL（本番） | https://site-monitor.example-cloud.com |
| URL（検証） | https://site-monitor-dev.example-cloud.com |
| アクセス条件 | 弊社グローバルIP (203.0.113.1) からのみ |
| 認証 | Cognito ユーザーアカウント (メール/パスワード) |
| 対応ブラウザ | Chrome / Edge / Firefox (最新版) |

## Cognito認証の取得手順

### テスト画面から (自動)

1. https://site-monitor.example-cloud.com にアクセス
2. カスタムログイン画面が表示される
3. メールアドレス・パスワードを入力してサインイン
4. パスワードを忘れた場合は「パスワードをお忘れですか？」リンクからリセット可能
5. 以降のAPI呼び出しは自動的にJWTが付与される

### 新規アカウント登録（セルフサインアップ）

1. ログイン画面で「アカウント作成」をクリック
2. `@example.com` ドメインのメールアドレスとパスワードを入力
3. 確認コードがメールに届く
4. 確認コードを入力して本人確認を完了
5. ログイン可能になる

※ `@example.com` 以外のドメインはPre Sign-upトリガーにより拒否される

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
  --stack-name SiteMonitor \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" \
  --output text
```

## 各エンドポイント呼び出しサンプル

### GET /sites — 監視サイト一覧取得

```bash
# 全サイト取得
curl -s https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/sites \
  -H "Authorization: Bearer $COGNITO_TOKEN" | jq .

# 自分が登録したサイトのみ
curl -s "https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/sites?filter=mine" \
  -H "Authorization: Bearer $COGNITO_TOKEN" | jq .
```

### POST /sites — 監視サイト登録

#### URL更新チェック

```bash
curl -X POST https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/sites \
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
curl -X POST https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/sites \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $COGNITO_TOKEN" \
  -d '{
    "site_name": "SaaS送信監視",
    "monitor_type": "cloudwatch_log",
    "targets": [
      {
        "log_group": "DataTransferSystem2-ExBoard-Function1",
        "message_filter": "リクエストを送信します。",
        "json_search_word": "\"account\": \"99999999\"",
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
curl -s https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID \
  -H "Authorization: Bearer $COGNITO_TOKEN" | jq .
```

### PUT /sites/{site_id} — 監視サイト更新

```bash
curl -X PUT https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID \
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
curl -X DELETE https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID \
  -H "Authorization: Bearer $COGNITO_TOKEN"
```

### GET /sites/{site_id}/results — チェック結果一覧

```bash
curl -s https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID/results \
  -H "Authorization: Bearer $COGNITO_TOKEN" | jq .
```

### GET /sites/{site_id}/status-changes — 状態変化履歴

```bash
curl -s https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID/status-changes \
  -H "Authorization: Bearer $COGNITO_TOKEN" | jq .
```

### POST /sites/{site_id}/notifications — 通知設定追加

#### メール通知

```bash
curl -X POST https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID/notifications \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $COGNITO_TOKEN" \
  -d '{
    "type": "email",
    "destination": "admin@example.com",
    "message_template": "至急確認してください"
  }'
```

#### Slack通知

```bash
curl -X POST https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID/notifications \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $COGNITO_TOKEN" \
  -d '{
    "type": "slack",
    "destination": "/site-monitor/slack-webhook-url",
    "mention": "@channel",
    "message_template": ""
  }'
```

※ Slack Webhook URLはSSM Parameter Store（SecureString）に格納し、パラメータ名を `destination` に指定する

### POST /sites/{site_id}/test-check — 手動チェック実行

```bash
curl -X POST https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID/test-check \
  -H "Authorization: Bearer $COGNITO_TOKEN" | jq .
```

### POST /sites/{site_id}/test-notify — テスト通知送信

```bash
curl -X POST https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/sites/$SITE_ID/test-notify \
  -H "Authorization: Bearer $COGNITO_TOKEN" | jq .
```

### GET /cloudwatch/log-groups — CWロググループ一覧

```bash
curl -s https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/cloudwatch/log-groups \
  -H "Authorization: Bearer $COGNITO_TOKEN" | jq '.data[].logGroupName'
```

### DELETE /users/me — 自ユーザー削除

```bash
curl -X DELETE https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/users/me \
  -H "Authorization: Bearer $COGNITO_TOKEN"
```

※ 登録サイトが存在する場合は `400 Cannot delete user with registered sites` が返る

## 管理者API

管理者APIは Cognito JWT に加えて `X-Admin-Auth` ヘッダーが必要です。

### 管理者認証ヘッダーの設定

```bash
# 管理者認証ヘッダー（Base64エンコード）
export ADMIN_AUTH=$(echo -n 'admin:SecurePassword123' | base64)
```

### GET /admin/users — ユーザー一覧取得

```bash
curl -s https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/admin/users \
  -H "Authorization: Bearer $COGNITO_TOKEN" \
  -H "X-Admin-Auth: Basic $ADMIN_AUTH" | jq .
```

### POST /admin/users/{email}/toggle-status — ユーザー有効/無効切替

```bash
curl -X POST https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/admin/users/user@example.com/toggle-status \
  -H "Authorization: Bearer $COGNITO_TOKEN" \
  -H "X-Admin-Auth: Basic $ADMIN_AUTH"
```

### POST /admin/users/{email}/reset-password — パスワードリセット

```bash
curl -X POST https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/admin/users/user@example.com/reset-password \
  -H "Authorization: Bearer $COGNITO_TOKEN" \
  -H "X-Admin-Auth: Basic $ADMIN_AUTH"
```

### DELETE /admin/users/{email} — ユーザー削除

```bash
curl -X DELETE https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod/admin/users/user@example.com \
  -H "Authorization: Bearer $COGNITO_TOKEN" \
  -H "X-Admin-Auth: Basic $ADMIN_AUTH"
```

## Python サンプル

```python
import requests

API_BASE = "https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/Prod"
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
| 400 | Cannot delete user with registered sites | サイトが残っている状態でユーザー削除 | 先にサイトを全削除 |
| 403 | Not authorized to modify this site | 作成者以外による操作 | 作成者アカウントで操作（または管理者認証を使用） |
| 403 | Admin authentication required | 管理者APIに認証なし | X-Admin-Authヘッダーを付与 |
| 403 | Invalid admin credentials | 管理者認証情報が不正 | 正しい認証情報を使用 |
| 403 | Forbidden | IP制限でブロック | 社内ネットワークからアクセス |
| 404 | Site not found | サイトIDが不正 | 正しいsite_idを使用 |
| 500 | Internal server error | サーバー内部エラー | 時間を置いてリトライ |
