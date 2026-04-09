# フロントエンド設計書

Web死活監視システムの管理画面。Vue 3 + Vuetify 4 + Vite + Pinia + Amplify Auth で構成する。

## 技術スタック

| 項目 | 選定 | バージョン | 理由 |
|------|------|----------|------|
| フレームワーク | Vue 3 (Composition API) | 3.5.x | ユーザー指定 |
| UIライブラリ | Vuetify 4 | 4.0.x | Material Design、管理画面に適したコンポーネント群 |
| ビルドツール | Vite | 8.0.x | 高速ビルド、Vue3との親和性 |
| 状態管理 | Pinia | 3.0.x | Vue3標準の状態管理ライブラリ |
| HTTP通信 | axios | 1.7.x | API Gateway との通信 |
| 認証SDK | aws-amplify | 6.14.x | Cognito認証の統合 |
| ルーター | vue-router | 5.0.x | SPA画面遷移 |
| アイコン | @mdi/font | 7.4.x | Material Design Icons |
| 言語 | TypeScript | 6.0.x | 型安全性 |

## 画面遷移

```
/signup         → サインアップ画面
/login          → ログイン画面
/               → ダッシュボード（認証必須）
/sites/:id      → サイト登録・編集画面（認証必須）
/sites/:id/notifications → 通知設定画面（認証必須）
/sites/:id/history       → チェック履歴画面（認証必須）
/admin/users    → 管理者ユーザー管理画面（認証必須 + 管理者認証）
```

### ルーティングガード

- `meta.requiresAuth: true` のルートは認証済みでなければ `/login` にリダイレクト
- ログイン済みで `/login` / `/signup` にアクセスした場合は `/` にリダイレクト
- `router.beforeEach` で `useAuthStore().checkAuth()` を呼び出して認証状態を確認
- `/admin/users` はルーターガードで認証必須 + ページ表示時に管理者認証ダイアログを表示

## コンポーネント構成

### ページコンポーネント（views/）

| コンポーネント | パス | 責務 |
|--------------|------|------|
| LoginView.vue | /login | カスタムログイン画面 |
| SignupView.vue | /signup | セルフサインアップ + 確認コード入力 |
| DashboardView.vue | / | 全監視サイトの状態一覧 |
| SiteEditView.vue | /sites/:id | 監視設定のCRUD |
| NotificationView.vue | /sites/:id/notifications | 通知設定の管理 |
| HistoryView.vue | /sites/:id/history | チェック結果 + 状態変化履歴 |
| AdminUsersView.vue | /admin/users | ユーザー管理（管理者用） |

### レイアウトコンポーネント（components/）

| コンポーネント | 責務 |
|--------------|------|
| AppLayout.vue | レイアウト制御（ヘッダー、サインアウト、ナビゲーション） |

### ダッシュボードコンポーネント（components/dashboard/）

| コンポーネント | 責務 | 主要Props |
|--------------|------|----------|
| SummaryCards.vue | サマリーカード（監視数・正常・欠測・無効） | normalCount, alertCount, disabledCount |
| SiteCard.vue | サイトカード（状態色分け、現場名、最終チェック日時） | site |

## 状態管理（Pinia ストア）

### auth ストア (`stores/auth.ts`)

```typescript
const email = ref<string | null>(null)
const isAuthenticated = computed(() => email.value !== null)
const loading = ref(false)
const error = ref<string | null>(null)
```

| メソッド | 説明 |
|---------|------|
| checkAuth() | 現在の認証状態を確認（getCurrentUser） |
| login(email, password) | サインイン（signIn） |
| signup(email, password) | サインアップ（signUp） |
| confirmSignup(email, code) | 確認コード検証（confirmSignUp） |
| resetPassword(email) | パスワードリセット開始（resetPassword） |
| confirmResetPassword(email, code, newPassword) | パスワードリセット確認（confirmResetPassword） |
| deleteAccount() | 自ユーザー削除（DELETE /users/me） |
| logout() | サインアウト（signOut） |

### sites ストア (`stores/sites.ts`)

```typescript
const sites = ref<Site[]>([])
const checkResults = ref<CheckResult[]>([])
const statusChanges = ref<StatusChange[]>([])
const notifications = ref<Notification[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
```

| メソッド | API | 説明 |
|---------|-----|------|
| fetchSites(filter?) | GET /sites | サイト一覧取得 |
| fetchSiteById(id) | GET /sites/{id} | サイト詳細取得 |
| createSite(data) | POST /sites | サイト登録 |
| updateSite(id, data) | PUT /sites/{id} | サイト更新 |
| deleteSite(id) | DELETE /sites/{id} | サイト削除 |
| fetchCheckResults(id) | GET /sites/{id}/results | チェック結果取得 |
| fetchStatusChanges(id) | GET /sites/{id}/status-changes | 状態変化履歴取得 |
| fetchNotifications(id) | GET /sites/{id}/notifications | 通知設定取得 |
| createNotification(id, data) | POST /sites/{id}/notifications | 通知設定追加 |
| updateNotification(id, nid, data) | PUT /sites/{id}/notifications/{nid} | 通知設定更新 |
| deleteNotification(id, nid) | DELETE /sites/{id}/notifications/{nid} | 通知設定削除 |
| testCheck(id) | POST /sites/{id}/test-check | 手動チェック実行 |
| testNotify(id) | POST /sites/{id}/test-notify | テスト通知送信 |

| 算出プロパティ | 説明 |
|--------------|------|
| enabledSites | 有効なサイトのみ |
| normalCount | 正常状態のサイト数 |
| alertCount | 欠測/エラー状態のサイト数 |
| disabledCount | 無効状態のサイト数 |

## API連携方式

### axios インスタンス (`services/api.ts`)

```typescript
const api = axios.create({
  baseURL: import.meta.env.VITE_API_ENDPOINT,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use(async (config) => {
  const session = await fetchAuthSession()
  const token = session.tokens?.idToken?.toString()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
```

- `VITE_API_ENDPOINT` はデプロイスクリプトで自動生成、または `.env` で設定
- リクエストインターセプターで Cognito ID Token を自動付与
- レスポンスは `ApiResponse<T>` 型（`{ success, data?, error? }`）

## Amplify 認証設定

```typescript
import { Amplify } from 'aws-amplify'

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: 'ap-northeast-1_XXXXX',
      userPoolClientId: 'XXXXX',
    },
  },
})
```

- `userPoolId` / `userPoolClientId` はデプロイスクリプトで CloudFormation Output から取得し、設定ファイルを自動生成
- 自動生成される設定ファイルは `.gitignore` に追加（Git管理しない）

## 画面詳細

### ログイン画面（/login）

- メールアドレス・パスワード入力フォーム
- 「パスワードをお忘れですか？」リンクからパスワードリセットフローへ遷移
- パスワードリセットフロー:
  1. メールアドレス入力 → 確認コード送信
  2. 確認コード + 新パスワード入力 → パスワード更新
  3. ログイン画面に戻る

### ダッシュボード（/）

- サマリーカード: 監視数・正常・欠測・無効の4つ
- カード形式でサイト一覧表示（左ボーダーで状態色分け: 緑=正常, 赤=欠測, グレー=無効）
- 状態フィルター + 現場名検索で絞り込み
- 欠測中サイトが上位に表示（ソート）
- 表示切替: 「自分の登録分」/「全体」（デフォルト: 自分の登録分）
- 各カードに登録者（メールアドレス）を表示
- 右下FABボタンでサイト新規登録

### サイト登録・編集画面（/sites/:id）

- 3セクション構成: 基本情報 → 監視スケジュール → 通知設定
- 監視種別: カード選択式（URL更新チェック / CloudWatchログ検索）
- 監視対象URL: 複数登録可（動的追加/削除）
- CWログ監視: ロググループはAPI経由で自動取得したリストから選択
- テストチェック実行ボタンで事前確認可能
- 登録者・最終更新者・更新日時を画面下部に表示

### 通知設定画面（/sites/:id/notifications）

- メール通知・Slack通知を個別にON/OFF
- Slack Webhook URLはSSM Parameter名で指定
- テスト通知送信ボタン

### チェック履歴画面（/sites/:id/history）

- チェック結果の時系列一覧
- 状態変化履歴（正常⇔異常の遷移タイミングと原因URLを時系列表示）

### 管理者ユーザー管理画面（/admin/users）

- 画面アクセス時にベーシック認証ダイアログを表示（ユーザー名・パスワード入力）
- 認証成功後、Cognito User Poolの全ユーザー一覧を表示
- 各ユーザーの表示項目: メールアドレス、ステータス、有効/無効、作成日時、登録サイト数
- 操作ボタン:
  - 有効/無効トグル: ユーザーアカウントの有効化/無効化
  - パスワードリセット: 確認コード付きメールを送信
  - ユーザー削除: サイト登録がない場合のみ削除可能
- 管理者認証情報は `X-Admin-Auth` ヘッダーとしてAPIリクエストに付与

## ビルド・デプロイ

| 項目 | 値 |
|------|-----|
| ビルドコマンド | `vue-tsc -b && vite build` |
| 出力ディレクトリ | `frontend/dist/` |
| デプロイ先 | S3 Bucket → CloudFront 配信 |
| 環境変数 | `VITE_API_ENDPOINT`（API Gateway URL） |

### デプロイ手順

```bash
cd frontend
npm install
npm run build
aws s3 sync dist/ s3://<WebsiteBucketName>/ --delete
aws cloudfront create-invalidation \
  --distribution-id <CloudFrontDistributionId> \
  --paths "/*"
```
