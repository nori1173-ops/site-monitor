# 料金見積

Web死活監視システムの月額コスト見積。DESIGN.md §11 をベースに整理。

## 前提条件

| 項目 | 値 |
|------|------|
| リージョン | ap-northeast-1（東京） |
| 料金基準 | AWS Pricing MCP (Price List API) から取得（2026年3月時点、税別・USD） |
| 監視対象サイト数 | 100サイト（URL監視） + 10サイト（CWログ監視） |
| 平均監視間隔 | 1時間（24回/日） |
| 管理者ユーザー数 | 5名 |
| 通知頻度 | 月30回程度（異常時のみ） |
| CW Logs Insightsスキャン量 | 1クエリあたり約10MB |

## リソース構成

| リソース | 仕様 | 根拠 |
|---------|------|------|
| API Gateway | REST API, Regional | stacks/api/template.yaml |
| Lambda (API) | Python 3.13, 128MB, タイムアウト30秒 | stacks/api/template.yaml |
| Lambda (Checker) | Python 3.13, 128MB, タイムアウト30秒 | stacks/checker/template.yaml |
| Lambda (CW Checker) | Python 3.13, 256MB, タイムアウト300秒 | stacks/cw_checker/template.yaml |
| Lambda (Notifier) | Python 3.13, 128MB, タイムアウト60秒 | stacks/notifier/template.yaml |
| Lambda (Pre Sign-up) | Python 3.13, 128MB, タイムアウト30秒 | template.yaml |
| DynamoDB | オンデマンド (PAY_PER_REQUEST), SSE-KMS | stacks/database/template.yaml |
| SQS | 3キュー (CWログ + 通知 + DLQ) | stacks/queue/template.yaml |
| Cognito | Lite プラン | stacks/auth/template.yaml |
| S3 | Standard, SSE-S3 | stacks/web/template.yaml |
| CloudFront | PriceClass_200 | stacks/web/template.yaml |
| CloudFront Function | IP制限 | stacks/web/template.yaml |
| Route 53 | Aレコード（エイリアス） | stacks/web/template.yaml |
| ACM | SSL証明書（us-east-1） | 既存 |
| SES | EmailIdentity (us-west-2) | stacks/ses/template.yaml |
| EventBridge Scheduler | 1サイト1スケジュール | API Lambda 経由で動的管理 |

## 単価一覧（MCP取得値）

| サービス | 単価 | 単位 |
|---------|------|------|
| Lambda リクエスト | $0.20 | /100万リクエスト |
| Lambda Duration | $0.0000166667 | /GB-秒 |
| DynamoDB 書込（オンデマンド） | $0.715 | /100万WRU |
| DynamoDB 読込（オンデマンド） | $0.1425 | /100万RRU |
| CloudFront HTTPS | $0.012 | /1万リクエスト |
| SES メール送信 | $0.10 | /1,000通 |
| CW Logs 取込（Standard） | $0.76 | /GB |
| CW Logs Insights | $0.0076 | /GBスキャン |
| Cognito Lite | $0.0055 | /MAU |
| EventBridge Scheduler | 無料 | 1,400万回/月まで |
| SQS | 無料 | 100万リクエスト/月まで |

## サービス別コスト（無料利用枠適用前）

| サービス | 算出根拠 | 月額（USD） |
|---------|---------|------------|
| **Lambda** | | |
| - URLチェッカー（リクエスト） | 72,000回 x $0.0000002/回 | $0.01 |
| - URLチェッカー（Duration） | 72,000回 x 0.128GB x 5秒 = 46,080 GB秒 x $0.0000166667 | **$0.77** |
| - CWログ検索（リクエスト） | 7,200回 x $0.0000002/回 | $0.00 |
| - CWログ検索（Duration） | 7,200回 x 0.256GB x 3秒 = 5,530 GB秒 x $0.0000166667 | $0.09 |
| - API Handler | 3,000回 x 0.128GB x 0.5秒 = 192 GB秒 | $0.00 |
| - Notifier | 30回（無視可能） | $0.00 |
| **DynamoDB（オンデマンド）** | | |
| - 書き込み | 72,000 WRU/月 x $0.000000715 | $0.05 |
| - 読み込み | 144,000 RRU/月 x $0.0000001425 | $0.02 |
| **EventBridge Scheduler** | 72,000回/月（1,400万回/月まで無料） | $0.00 |
| **S3** | SPA静的ファイル 10MB + リクエスト数千件 | $0.01 |
| **CloudFront** | HTTPS 10,000リクエスト x $0.0000012/回 | $0.01 |
| **Route 53** | 既存 osasi-cloud.com ゾーンにレコード追加（ゾーン追加なし） | $0.00 |
| **Cognito（Lite）** | 5 MAU x $0.0055/MAU | $0.03 |
| **SQS** | CW監視キュー + 通知キュー + DLQ（100万リクエスト/月まで無料） | $0.00 |
| **SES（メール）** | 30通/月 x $0.0001/通 | $0.00 |
| **CW Logs 取込** | Lambda実行ログ 0.075GB x $0.76/GB | $0.06 |
| **CW Logs Insights** | 7,200クエリ x 0.01GB/クエリ = 72GB x $0.0076/GB | $0.55 |
| | | |
| **合計（無料枠適用前）** | | **約 $1.60/月** |

### Lambda Duration 計算根拠

```
URLチェッカー:
  メモリ: 128MB = 0.128GB
  実行時間: 平均5秒/リクエスト
  リクエスト数: 100サイト x 24回/日 x 30日 = 72,000回
  GB秒: 72,000 x 0.128 x 5 = 46,080 GB秒
  コスト: 46,080 x $0.0000166667 = $0.77

CWログ検索:
  メモリ: 256MB = 0.256GB
  実行時間: 平均3秒/リクエスト
  リクエスト数: 10サイト x 24回/日 x 30日 = 7,200回
  GB秒: 7,200 x 0.256 x 3 = 5,530 GB秒
  コスト: 5,530 x $0.0000166667 = $0.09
```

## 無料利用枠適用後

| 無料利用枠 | 内容 | 削減額 |
|-----------|------|--------|
| Lambda リクエスト | 100万回/月まで無料 | -$0.01 |
| Lambda Duration | 400,000 GB秒/月まで無料 | **-$0.86**（全量無料枠内） |

| | 無料枠あり（初年度） | 無料枠なし（2年目以降） |
|------|------|------|
| **月額合計** | **約 $0.73** | **約 $1.60** |
| **年額合計** | **約 $8.76** | **約 $19.20** |

## スケール時の見積（500サイト）

| 項目 | 100+10サイト | 500+50サイト |
|------|------------|-------------|
| Lambda Duration | $0.86 | $4.30 |
| DynamoDB | $0.07 | $0.35 |
| CW Logs Insights | $0.55 | $2.75 |
| その他 | $0.12 | $0.60 |
| **合計（無料枠なし）** | **$1.60** | **$8.00** |

## コスト構造の特徴

1. **Lambda Duration が最大コスト要因**: 月額の約50%を占める。メモリ128MBで算出しており、不足時は256MBに引き上げ（コスト2倍）
2. **CW Logs Insights のスキャン量**: 対象ログの規模に大きく依存。1クエリ10MBは楽観的見積であり、大規模ログの場合は10倍（$5.50/月）になる可能性あり
3. **EventBridge Scheduler**: 1,400万回/月まで無料。1サイト1スケジュールでも全く問題なし
4. **SQS**: 100万リクエスト/月まで無料。本システムの想定規模では課金対象外
5. **Cognito Lite**: 50,000 MAUまでは$0.0055/MAU。本システムの5ユーザーでは$0.03/月
6. **SES**: 1,000通あたり$0.10。月30通程度では実質無料

## 注意事項

- Lambda無料枠はAWSアカウント全体で共有。他サービスとの共用時は枠を超える可能性あり
- CW Logs取込コストはログ保持期間を短縮してもストレージ料金（$0.033/GB/月）のみ削減
- DynamoDB の check_results テーブルにはTTL（90日）を設定し、ストレージコストを抑制
- 為替レート（USD/JPY）の変動により円建てコストは変動する
