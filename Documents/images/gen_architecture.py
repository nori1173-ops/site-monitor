from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Dynamodb
from diagrams.aws.integration import Eventbridge, SimpleQueueServiceSqs
from diagrams.aws.engagement import SimpleEmailServiceSes
from diagrams.aws.network import CloudFront, APIGateway, Route53
from diagrams.aws.security import Cognito
from diagrams.aws.storage import S3
from diagrams.aws.management import Cloudwatch
from diagrams.onprem.client import Users

OUTPUT = "/mnt/c/Users/miyaji.OSASI/git/web-alive-monitoring/Documents/images/architecture"

graph_attr = {
    "fontsize": "14",
    "fontname": "Helvetica",
    "bgcolor": "white",
    "pad": "0.3",
    "nodesep": "0.3",
    "ranksep": "0.7",
}

node_attr = {
    "fontsize": "10",
    "fontname": "Helvetica",
    "width": "1.1",
    "height": "1.3",
}

edge_attr = {
    "fontsize": "8",
    "fontname": "Helvetica",
    "color": "#666666",
}

with Diagram(
    "Web Alive Monitoring",
    filename=OUTPUT,
    outformat="png",
    direction="TB",
    show=False,
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
):
    admin = Users("管理者\n(社内)")

    with Cluster("AWS Cloud", graph_attr={"bgcolor": "#FAFAFA", "style": "rounded"}):

        r53 = Route53("Route 53\nweb-alive\n.osasi-cloud.com")

        with Cluster("フロントエンド + 認証"):
            cf = CloudFront("CloudFront\n(IP制限)")
            s3 = S3("S3 (Vue3)")
            cognito = Cognito("Cognito\n(Pre Sign-up)")

        with Cluster("API"):
            apigw = APIGateway("API Gateway\n(IP制限)")
            lambda_api = Lambda("API Handler")

        with Cluster("DynamoDB"):
            ddb_sites = Dynamodb("監視サイト設定")
            ddb_results = Dynamodb("チェック結果")

        eb = Eventbridge("EventBridge\nScheduler")

        with Cluster("URL監視"):
            lambda_check = Lambda("URL更新\nチェック")

        with Cluster("CWログ監視"):
            sqs_cw = SimpleQueueServiceSqs("CW監視\nキュー")
            lambda_cw = Lambda("CWログ\n検索")

        with Cluster("通知（非同期）"):
            sqs_notify = SimpleQueueServiceSqs("通知キュー")
            lambda_notify = Lambda("通知処理")
            ses = SimpleEmailServiceSes("SES")

    with Cluster("監視対象"):
        iot_web = Users("IoT観測\n(Web/画像)")
        cw_logs = Cloudwatch("CloudWatch\nLogs")

    # 管理者 → Route 53 → CloudFront
    admin >> r53 >> cf
    cf >> s3
    cf >> cognito

    # 管理者 → API（JWT認証）
    admin >> Edge(label="JWT", color="#009900") >> apigw
    apigw >> Edge(label="検証", color="#009900", style="dashed") >> cognito
    apigw >> lambda_api

    # API → DB
    lambda_api >> ddb_sites

    # EventBridge → URL監視（直接）
    eb >> lambda_check

    # EventBridge → CW監視（SQS経由）
    eb >> sqs_cw >> lambda_cw

    # 監視 → DB
    lambda_check >> ddb_results
    lambda_cw >> ddb_results

    # 監視 → 外部
    lambda_check >> Edge(label="HTTP GET", color="#0066CC") >> iot_web
    lambda_cw >> Edge(label="Insights", color="#0066CC") >> cw_logs

    # 通知（非同期）
    lambda_check >> Edge(color="#CC0000", style="dashed") >> sqs_notify
    lambda_cw >> Edge(color="#CC0000", style="dashed") >> sqs_notify
    sqs_notify >> lambda_notify >> ses
