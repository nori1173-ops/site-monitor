# API詳細設計書

Web死活監視システムのREST API設計。全19エンドポイントを単一Lambda関数で処理し、API Gateway + Cognito Authorizerで認証する。

## エンドポイント一覧

| メソッド | パス | タグ | 説明 |
|---------|------|------|------|
| GET | /sites | Sites | 監視サイト一覧取得 |
| POST | /sites | Sites | 監視サイト登録 |
| GET | /sites/{site_id} | Sites | 監視サイト詳細取得 |
| PUT | /sites/{site_id} | Sites | 監視サイト更新 |
| DELETE | /sites/{site_id} | Sites | 監視サイト削除 |
| GET | /sites/{site_id}/results | Results | チェック結果一覧取得 |
| GET | /sites/{site_id}/status-changes | Results | 状態変化履歴取得 |
| GET | /sites/{site_id}/notifications | Notifications | 通知設定一覧取得 |
| POST | /sites/{site_id}/notifications | Notifications | 通知設定追加 |
| PUT | /sites/{site_id}/notifications/{notification_id} | Notifications | 通知設定更新 |
| DELETE | /sites/{site_id}/notifications/{notification_id} | Notifications | 通知設定削除 |
| POST | /sites/{site_id}/test-check | Test | 手動チェック実行（テスト用） |
| POST | /sites/{site_id}/test-notify | Test | テスト通知送信 |
| DELETE | /users/me | Users | 自ユーザー削除 |
| GET | /admin/users | Admin | ユーザー一覧取得（管理者用） |
| POST | /admin/users/{email}/toggle-status | Admin | ユーザー有効/無効切替（管理者用） |
| POST | /admin/users/{email}/reset-password | Admin | パスワードリセット（管理者用） |
| DELETE | /admin/users/{email} | Admin | ユーザー削除（管理者用） |
| GET | /cloudwatch/log-groups | CloudWatch | CWロググループ一覧取得 |

※ CloudFront経由時 `/api/*` → API Gateway `/Prod/*` にリライト

## 認証方式

| 方式 | ヘッダー | 対象 |
|------|---------|------|
| Cognito JWT | `Authorization: Bearer <ID Token>` | 一般エンドポイント |
| Basic認証 | `X-Admin-Auth: Basic <base64(user:pass)>` | `/admin/*` エンドポイント |

- API Gateway の Cognito Authorizer で JWT を検証
- Lambda 側で `event['requestContext']['authorizer']['claims']['email']` から操作者メールアドレスを取得
- サイト削除・更新は作成者（`created_by`）のみ許可（403 Forbidden）
- **管理者オーバーライド**: `X-Admin-Auth` ヘッダーが有効な場合、他ユーザーのサイトも PUT/DELETE 可能
- `/admin/*` エンドポイントは Cognito JWT に加え、`X-Admin-Auth` ヘッダーによるベーシック認証が必須
- 管理者認証情報は CloudFormation パラメータ `AdminCredentials`（`user:password` 形式）で設定

## レスポンスエンベロープ

全エンドポイント共通のレスポンス形式。

### 成功時

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

### エラー時

```json
{
  "success": false,
  "data": null,
  "error": "エラーメッセージ"
}
```

## POST /sites — 監視サイト登録

### リクエスト

```json
{
  "site_name": "○○ダム",
  "monitor_type": "url_check",
  "targets": [
    { "url": "https://example.com/dam/latest.png" },
    { "url": "https://example.com/dam/graph.png" }
  ],
  "schedule_start": "00:20",
  "schedule_interval_minutes": 60,
  "consecutive_threshold": 3,
  "enabled": true
}
```

| フィールド | 型 | 必須 | デフォルト | 説明 |
|-----------|------|------|----------|------|
| site_name | string | Yes | - | 現場名（最大200文字） |
| monitor_type | string | Yes | - | `url_check` / `cloudwatch_log` |
| targets | array | Yes | - | 監視対象リスト（1件以上） |
| schedule_start | string | Yes | - | 監視開始時刻（HH:MM形式） |
| schedule_interval_minutes | integer | Yes | - | 監視間隔（分）。5/10/15/30/60/180/360/720/1440 |
| consecutive_threshold | integer | No | 3 | 連続欠測閾値 |
| enabled | boolean | No | true | 有効/無効 |

#### targets — URL更新チェック

```json
{ "url": "https://example.com/dam/latest.png" }
```

| フィールド | 型 | 必須 | 説明 |
|-----------|------|------|------|
| url | string (URI) | Yes | 監視対象URL（http/httpsのみ） |

#### targets — CloudWatchログ検索

```json
{
  "log_group": "DataTransferSystem2-OsBoard-Function1",
  "message_filter": "リクエストを送信します。",
  "json_search_word": "\"account\": \"10206721\"",
  "search_period_minutes": 60
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|------|------|------|
| log_group | string | Yes | CloudWatchロググループ名 |
| message_filter | string | No | メッセージフィルタ |
| json_search_word | string | No | JSON検索ワード |
| search_period_minutes | integer | Yes | 検索期間（分） |

### レスポンス (201 Created)

```json
{
  "success": true,
  "data": {
    "site_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "site_name": "○○ダム",
    "monitor_type": "url_check",
    "targets": [
      { "url": "https://example.com/dam/latest.png" },
      { "url": "https://example.com/dam/graph.png" }
    ],
    "schedule_start": "00:20",
    "schedule_interval_minutes": 60,
    "consecutive_threshold": 3,
    "enabled": true,
    "scheduler_arn": "arn:aws:scheduler:ap-northeast-1:989982802989:schedule/default/WebAliveMonitoring-site-a1b2c3d4",
    "last_check_status": null,
    "last_checked_at": null,
    "consecutive_miss_count": 0,
    "created_by": "user@osasi.co.jp",
    "updated_by": "user@osasi.co.jp",
    "created_at": "2026-04-06T00:00:00+00:00",
    "updated_at": "2026-04-06T00:00:00+00:00"
  },
  "error": null
}
```

### EventBridge Scheduler 連携

サイト登録時に以下の処理を自動実行する:

1. `schedule_start` と `schedule_interval_minutes` から Cron 式を生成
2. EventBridge Scheduler にスケジュールを作成（1サイト = 1スケジュール）
3. スケジュールの ARN を `scheduler_arn` として DynamoDB に記録
4. スケジュール作成に失敗した場合、DynamoDB レコードもロールバック

#### Cron式生成ロジック

| schedule_start | schedule_interval_minutes | 生成されるCron式 |
|---------------|--------------------------|-----------------|
| 00:20 | 60 | `cron(20 * * * ? *)` |
| 00:05 | 10 | `cron(5/10 * * * ? *)` |
| 00:50 | 1440 | `cron(50 0 * * ? *)` |

## GET /sites — 監視サイト一覧取得

### クエリパラメータ

| パラメータ | 型 | 必須 | 説明 |
|-----------|------|------|------|
| filter | string | No | `mine` を指定すると自分が登録したサイトのみ返す |

### レスポンス (200 OK)

```json
{
  "success": true,
  "data": [
    {
      "site_id": "a1b2c3d4-...",
      "site_name": "○○ダム",
      "monitor_type": "url_check",
      "targets": [ ... ],
      "schedule_start": "00:20",
      "schedule_interval_minutes": 60,
      "consecutive_threshold": 3,
      "enabled": true,
      "last_check_status": "updated",
      "last_checked_at": "2026-04-06T01:20:00+00:00",
      "consecutive_miss_count": 0,
      "created_by": "user@osasi.co.jp",
      "updated_by": "user@osasi.co.jp",
      "created_at": "2026-04-05T00:00:00+00:00",
      "updated_at": "2026-04-05T00:00:00+00:00"
    }
  ],
  "error": null
}
```

## GET /sites/{site_id} — 監視サイト詳細取得

パスパラメータ `site_id` (UUID) で指定したサイトの詳細を返す。レスポンス形式は POST /sites と同一。

## PUT /sites/{site_id} — 監視サイト更新

リクエスト形式は POST /sites と同一。以下の追加処理を行う:

1. `created_by` と操作者が一致するか検証（不一致時 403）
2. スケジュール設定が変更された場合、EventBridge Scheduler を更新
3. `updated_by` を操作者メールアドレスで更新

## DELETE /sites/{site_id} — 監視サイト削除

1. `created_by` と操作者が一致するか検証（不一致時 403）
2. EventBridge Scheduler のスケジュールを削除
3. DynamoDB からサイトレコードを削除
4. 関連する通知設定も削除

### レスポンス (200 OK)

```json
{
  "success": true,
  "data": { "message": "Site deleted" },
  "error": null
}
```

## GET /sites/{site_id}/results — チェック結果一覧取得

### レスポンス (200 OK)

```json
{
  "success": true,
  "data": [
    {
      "site_id": "a1b2c3d4-...",
      "checked_at#target_url": "2026-04-06T01:20:00+00:00#https://example.com/dam/latest.png",
      "status": "updated",
      "last_modified": "Sat, 05 Apr 2026 12:00:00 GMT",
      "etag": "\"abc123\"",
      "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "consecutive_miss_count": 0
    }
  ],
  "error": null
}
```

## GET /sites/{site_id}/status-changes — 状態変化履歴取得

### レスポンス (200 OK)

```json
{
  "success": true,
  "data": [
    {
      "site_id": "a1b2c3d4-...",
      "changed_at": "2026-04-06T03:20:00+00:00",
      "previous_status": "updated",
      "new_status": "not_updated",
      "trigger_url": "https://example.com/dam/latest.png"
    }
  ],
  "error": null
}
```

## POST /sites/{site_id}/notifications — 通知設定追加

### リクエスト

```json
{
  "type": "email",
  "destination": "admin@osasi.co.jp",
  "mention": "",
  "message_template": "確認してください",
  "enabled": true
}
```

| フィールド | 型 | 必須 | デフォルト | 説明 |
|-----------|------|------|----------|------|
| type | string | Yes | - | `email` / `slack` |
| destination | string | Yes | - | メールアドレス or SSM Parameter名（Slack Webhook URL） |
| mention | string | No | "" | Slackメンション先（`@channel`等） |
| message_template | string | No | "" | 通知メッセージテンプレート |
| enabled | boolean | No | true | 有効/無効 |

### レスポンス (201 Created)

```json
{
  "success": true,
  "data": {
    "site_id": "a1b2c3d4-...",
    "notification_id": "f1e2d3c4-...",
    "type": "email",
    "destination": "admin@osasi.co.jp",
    "mention": "",
    "message_template": "確認してください",
    "enabled": true
  },
  "error": null
}
```

## GET /sites/{site_id}/notifications — 通知設定一覧取得

レスポンスは通知設定の配列。

## PUT /sites/{site_id}/notifications/{notification_id} — 通知設定更新

リクエスト形式は POST と同一。

## DELETE /sites/{site_id}/notifications/{notification_id} — 通知設定削除

### レスポンス (200 OK)

```json
{
  "success": true,
  "data": { "message": "Notification deleted" },
  "error": null
}
```

## POST /sites/{site_id}/test-check — 手動チェック実行

対象サイトの checker Lambda を同期 Invoke し、即座にチェック結果を返す。

- `url_check` タイプ: checker Lambda を直接呼び出し
- `cloudwatch_log` タイプ: cw_checker Lambda を直接呼び出し

### レスポンス (200 OK)

```json
{
  "success": true,
  "data": {
    "site_id": "a1b2c3d4-...",
    "results": [
      {
        "target_url": "https://example.com/dam/latest.png",
        "status": "updated",
        "last_modified": "Sat, 05 Apr 2026 12:00:00 GMT"
      }
    ]
  },
  "error": null
}
```

## POST /sites/{site_id}/test-notify — テスト通知送信

対象サイトに設定された全通知先にテストメッセージを送信する。

### レスポンス (200 OK)

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "type": "email",
        "destination": "admin@osasi.co.jp",
        "status": "sent",
        "error": null
      },
      {
        "type": "slack",
        "destination": "/web-alive-monitoring/slack-webhook-url",
        "status": "sent",
        "error": null
      }
    ]
  },
  "error": null
}
```

## GET /cloudwatch/log-groups — CWロググループ一覧取得

AWSアカウント内のCloudWatchロググループ一覧をLambda経由で取得する。CWログ監視の登録画面でロググループ選択に使用。

### レスポンス (200 OK)

```json
{
  "success": true,
  "data": [
    {
      "logGroupName": "/aws/lambda/DataTransferSystem2-OsBoard-Function1",
      "storedBytes": 1048576
    },
    {
      "logGroupName": "/aws/lambda/NetMAIL-Backend-Subscriber",
      "storedBytes": 524288
    }
  ],
  "error": null
}
```

## DELETE /users/me — 自ユーザー削除

認証済みユーザーが自分自身のCognitoアカウントを削除する。サイトが登録されている場合は削除不可。

### 前提条件

- 操作者が登録したサイトが0件であること

### レスポンス (200 OK)

```json
{
  "success": true,
  "data": { "message": "User deleted" },
  "error": null
}
```

### エラー

| HTTP | メッセージ | 条件 |
|------|----------|------|
| 400 | Cannot delete user with registered sites. Delete all sites first. | サイトが残っている |

## GET /admin/users — ユーザー一覧取得（管理者用）

Cognito User Poolに登録された全ユーザーの一覧を返す。管理者認証（`X-Admin-Auth`）が必須。

### レスポンス (200 OK)

```json
{
  "success": true,
  "data": [
    {
      "email": "user@osasi.co.jp",
      "status": "CONFIRMED",
      "enabled": true,
      "created_at": "2026-04-06T00:00:00+00:00",
      "site_count": 3
    }
  ],
  "error": null
}
```

各ユーザーの `site_count` はDynamoDBのsitesテーブルから `created_by` でカウントした値。

## POST /admin/users/{email}/toggle-status — ユーザー有効/無効切替（管理者用）

指定ユーザーのCognitoアカウントを有効化（AdminEnableUser）または無効化（AdminDisableUser）する。現在の状態をトグルする。

### レスポンス (200 OK)

```json
{
  "success": true,
  "data": { "message": "User disabled", "enabled": false },
  "error": null
}
```

## POST /admin/users/{email}/reset-password — パスワードリセット（管理者用）

指定ユーザーのパスワードをリセットする（AdminResetUserPassword）。ユーザーに確認コード付きメールが送信され、次回ログイン時に新パスワードの設定が求められる。

### レスポンス (200 OK)

```json
{
  "success": true,
  "data": { "message": "Password reset initiated" },
  "error": null
}
```

## DELETE /admin/users/{email} — ユーザー削除（管理者用）

指定ユーザーのCognitoアカウントを削除する（AdminDeleteUser）。サイトが登録されている場合は削除不可。

### 前提条件

- 対象ユーザーが登録したサイトが0件であること

### レスポンス (200 OK)

```json
{
  "success": true,
  "data": { "message": "User deleted" },
  "error": null
}
```

### エラー

| HTTP | メッセージ | 条件 |
|------|----------|------|
| 400 | Cannot delete user with registered sites | サイトが残っている |

## エラーコード一覧

| HTTP | エラーメッセージ | 発生条件 | 対処法 |
|------|----------------|---------|--------|
| 400 | site_name is required | site_name 未指定 | site_name を指定 |
| 400 | monitor_type must be url_check or cloudwatch_log | monitor_type 不正 | 正しい値を指定 |
| 400 | targets must be a non-empty array | targets が空 | 1件以上の監視対象を指定 |
| 400 | schedule_start must be HH:MM format | schedule_start 不正 | HH:MM 形式で指定 |
| 400 | schedule_interval_minutes must be one of: 5,10,... | 間隔不正 | 許可された値を指定 |
| 400 | type must be email or slack | 通知タイプ不正 | email / slack を指定 |
| 400 | destination is required | 通知先未指定 | destination を指定 |
| 400 | No notifications configured | テスト通知時に通知設定なし | 通知設定を追加してから実行 |
| 400 | Cannot delete user with registered sites. Delete all sites first. | サイトが残っている状態でユーザー削除 | 先にサイトを全削除 |
| 403 | Not authorized to modify this site | 作成者以外による更新/削除 | 作成者のアカウントで操作（または管理者認証を使用） |
| 403 | Admin authentication required | 管理者エンドポイントに管理者認証なし | X-Admin-Authヘッダーを付与 |
| 403 | Invalid admin credentials | 管理者認証情報が不正 | 正しい認証情報を使用 |
| 404 | Site not found | 指定site_idが存在しない | 正しいsite_idを指定 |
| 404 | Notification not found | 指定notification_idが存在しない | 正しいIDを指定 |
| 500 | Internal server error | サーバー内部エラー | ログを確認してリトライ |
| 500 | Scheduler creation failed | EventBridge Scheduler作成失敗 | IAMロール・権限を確認 |

## EventBridge Scheduler 管理設計

### スケジュール命名規則

```
{StackName}-site-{site_id}
```

例: `WebAliveMonitoring-site-a1b2c3d4-e5f6-7890-abcd-ef1234567890`

### スケジュール設定

| 項目 | 値 |
|------|-----|
| グループ名 | `default` |
| スケジュール式 | Cron式（`schedule_start` + `schedule_interval_minutes` から生成） |
| ターゲット | URL監視: checker Lambda ARN / CWログ監視: SQS キュー URL |
| ペイロード | `{"site_id": "<site_id>"}` |
| 実行ロール | `{StackName}-SchedulerRole`（Lambda Invoke + SQS SendMessage 権限） |
| リトライポリシー | デフォルト（最大185回） |
| 状態 | サイト `enabled=true` → ENABLED / `enabled=false` → DISABLED |

### ライフサイクル

| 操作 | スケジューラ操作 |
|------|----------------|
| サイト登録 (POST /sites) | `create_schedule` |
| サイト更新 (PUT /sites) | `update_schedule`（Cron式・ターゲット・状態を更新） |
| サイト削除 (DELETE /sites) | `delete_schedule` |
| 有効/無効切替 | `update_schedule`（State を ENABLED/DISABLED に変更） |

## API Gateway 設定

### リソースポリシー（IP制限）

```json
{
  "Effect": "Allow",
  "Principal": "*",
  "Action": "execute-api:Invoke",
  "Resource": "arn:aws:execute-api:ap-northeast-1:*:*/*",
  "Condition": {
    "IpAddress": {
      "aws:SourceIp": ["210.225.75.184/32"]
    }
  }
}
```

### スロットリング

| 項目 | 値 |
|------|-----|
| バースト制限 | 500リクエスト |
| レート制限 | 100リクエスト/秒 |

## OpenAPI仕様

完全なOpenAPI 3.0.3仕様は `/openapi/openapi.yaml` を参照。Swagger UIは `https://openapi.osasi-cloud.com/web-alive-monitoring/` で閲覧可能。
