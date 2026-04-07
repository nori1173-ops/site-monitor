# セキュリティ設計書

Web死活監視システムのセキュリティ設計。認証・認可・通信暗号化・データ保護・アクセス制御を網羅する。

## 認証フロー（Cognito Lite）

### ユーザー認証（テスト画面経由）

```
ユーザー
  ↓ https://web-alive.osasi-cloud.com
CloudFront Function（IP制限）
  ↓ 許可IPのみ通過
S3（Vue3 SPA）
  ↓ カスタムログイン画面表示
aws-amplify Auth.signIn()
  ↓ USER_SRP_AUTH
Cognito User Pool
  ↓ ID Token (JWT) 発行
axios（Authorization: Bearer <token>）
  ↓ /api/* → CloudFront → /Prod/* リライト
API Gateway
  ↓ Cognito Authorizer で JWT 検証
Lambda（API Handler）
  ↓ claims['email'] で操作者を特定
```

### セルフサインアップフロー

```
ユーザー → サインアップ画面
  ├── メールアドレス + パスワード入力
  ├── Pre Sign-up Lambda トリガー → @osasi.co.jp ドメインチェック
  │   └── ドメイン不一致 → 拒否
  ├── aws-amplify Auth.signUp() → Cognito User Pool
  ├── 確認コードがメールに届く
  ├── 確認コード入力 → Auth.confirmSignUp()
  └── ログイン可能になる
```

### MFA（任意オプション）

| 項目 | 値 |
|------|-----|
| MFA設定 | OPTIONAL |
| 対応方式 | SOFTWARE_TOKEN_MFA（TOTP） |
| 対応アプリ | Google Authenticator, Microsoft Authenticator 等 |
| 設定タイミング | ユーザーが自身で任意に設定可能 |

## アクセス制御

### IP制限

| レイヤー | 実装箇所 | 対象 | 許可IP |
|---------|---------|------|--------|
| フロントエンド | CloudFront Function (viewer-request) | 全HTTPリクエスト | 210.225.75.184 |
| API | API Gateway リソースポリシー | REST API 全エンドポイント | 210.225.75.184 |

### CloudFront Function によるIP制限

WAFを使用せず CloudFront Function で実施。

| 比較項目 | WAF | CloudFront Function |
|---------|-----|-------------------|
| コスト | $5/月〜 | 無料枠内 |
| レイテンシ | 数ms | <1ms |
| 柔軟性 | ルールベース | JavaScript |
| 本要件への適合 | 適合 | 最適（シンプル・低コスト） |

### Cognito Authorizer

| 項目 | 値 |
|------|-----|
| Authorizer タイプ | COGNITO_USER_POOLS |
| 検証対象 | Authorization ヘッダーの ID Token |
| トークン有効期限 | 1時間（Cognito デフォルト） |
| リフレッシュトークン | 30日 |
| スコープ | 未使用（全認証ユーザーに全API権限） |

### 操作者による権限制御

| 操作 | 権限 |
|------|------|
| サイト一覧参照 (GET /sites) | 全認証ユーザー |
| サイト登録 (POST /sites) | 全認証ユーザー |
| サイト更新 (PUT /sites/{id}) | 作成者のみ（created_by == 操作者） |
| サイト削除 (DELETE /sites/{id}) | 作成者のみ |
| 通知設定の操作 | 対象サイトの作成者のみ |
| チェック結果・履歴参照 | 全認証ユーザー |
| テストチェック・テスト通知 | 全認証ユーザー |

## CORS設定

| 項目 | 値 |
|------|-----|
| Access-Control-Allow-Origin | CloudFront 経由のため設定不要（同一オリジン） |
| プリフライト | CloudFront が同一ドメインで配信するため CORS ヘッダーは不要 |

API Gateway への直接アクセスは IP 制限で拒否されるため、CORS の設定漏れによるリスクはない。

## SSRF対策

URL更新チェック Lambda が外部URLにHTTP GETリクエストを送信するため、SSRF対策を実施する。

| 対策 | 実装内容 |
|------|---------|
| スキーム制限 | `http://` と `https://` のみ許可 |
| プライベートIP拒否 | 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8 をブロック |
| メタデータエンドポイント拒否 | 169.254.169.254, fd00:ec2::254 をブロック |
| リダイレクト追従制限 | リダイレクト先も同じ制限を適用 |
| タイムアウト | 10秒 |
| レスポンスサイズ上限 | 10MB |

## 暗号化

### 通信暗号化

| 区間 | 暗号化方式 |
|------|----------|
| クライアント → CloudFront | TLS 1.2+（ACM証明書） |
| CloudFront → S3 | OAC（署名付きリクエスト） |
| CloudFront → API Gateway | HTTPS |
| Lambda → DynamoDB | AWS SDK（HTTPS） |
| Lambda → SQS | AWS SDK（HTTPS） |
| Lambda → SES | AWS SDK（HTTPS、us-west-2） |
| Lambda → 監視対象URL | HTTP/HTTPS（対象による） |

### データ暗号化（保存時）

| リソース | 暗号化方式 |
|---------|----------|
| DynamoDB | SSE-KMS（AWS管理キー） |
| SQS | SQS管理SSE |
| S3 | SSE-S3（AES-256） |

## シークレット管理

| シークレット | 保管場所 | 取得方式 |
|------------|---------|---------|
| Slack Webhook URL | SSM Parameter Store（SecureString） | Lambda 実行時に ssm:GetParameter |
| Cognito User Pool ID | CloudFormation Output → フロントエンド設定ファイル | ビルド時に自動生成 |
| Cognito Client ID | CloudFormation Output → フロントエンド設定ファイル | ビルド時に自動生成 |

※ APIキー認証（ワークフロー連携）は本システムでは不使用。Cognito JWT 認証のみ。

### SSM Parameter Store 構成

| パラメータ名 | タイプ | 説明 |
|-------------|--------|------|
| /web-alive-monitoring/slack-webhook-url | SecureString | Slack Incoming Webhook URL |

## 脅威モデル (STRIDE)

| 脅威 | 分類 | リスク | 対策 | 残留リスク |
|------|------|--------|------|----------|
| 外部IPからのアクセス | Spoofing | 高 | CloudFront Function IP制限 + API Gateway リソースポリシー | 低 |
| API Gateway直接アクセス | Tampering | 高 | IP制限（リソースポリシー） | 低 |
| 不正JWT使用 | Spoofing | 中 | Cognito Authorizer + トークン有効期限（1時間） | 低 |
| SSRF攻撃（監視URL経由） | Tampering | 高 | プライベートIP/メタデータブロック、スキーム制限 | 低 |
| 大量リクエスト | DoS | 中 | API Gateway スロットリング | 低 |
| DLQメッセージ滞留 | Information Disclosure | 低 | CloudWatch Alarm で検知 | 低 |
| Slack Webhook漏洩 | Information Disclosure | 中 | SSM SecureString + IAM制限 | 低 |
| ログへの機密情報出力 | Information Disclosure | 中 | レスポンスボディをログに含めない | 低 |
| 他ユーザーのサイト操作 | Elevation of Privilege | 中 | created_by による操作者チェック | 低 |

## セキュリティ対策一覧

| カテゴリ | 対策 | 実装箇所 |
|---------|------|---------|
| 通信暗号化 | HTTPS (TLS 1.2+) | CloudFront + ACM |
| アクセス制御 | 弊社IP限定 | CloudFront Function + API Gateway リソースポリシー |
| 認証 | Cognito JWT (Lite プラン) | API Gateway Cognito Authorizer |
| サインアップ制限 | @osasi.co.jp ドメインのみ | Cognito Pre Sign-up Lambda |
| MFA | OPTIONAL (TOTP) | Cognito User Pool |
| 操作者追跡 | 全データに created_by / updated_by を記録 | API Lambda |
| SSRF防御 | プライベートIP・メタデータブロック | checker Lambda |
| シークレット管理 | SSM SecureString | Slack Webhook URL |
| データ暗号化 | SSE-KMS / SQS管理SSE | DynamoDB, SQS |
| レート制限 | API Gateway スロットリング | API Gateway |
| ログ保護 | 機密データ非出力 | Lambda 実装 |
| DLQ監視 | メッセージ滞留検知 | CloudWatch Alarm |

## 監査ログ

| 対象 | ログ出力先 | 保持期間 |
|------|----------|---------|
| API呼び出し | CloudWatch Logs（Lambda実行ログ） | 30日 |
| 認証イベント | CloudWatch Logs（Cognito） | 30日 |
| データ変更 | DynamoDB（created_by, updated_by, timestamps） | 永続（TTL対象外テーブル） |
| 状態変化 | DynamoDB（status_changes テーブル） | 365日（TTL） |
