#!/bin/bash
# CloudFormation Outputs から frontend/.env を自動生成するスクリプト
#
# Usage:
#   ./scripts/generate-env.sh [stack-name]
#
# Example:
#   ./scripts/generate-env.sh WebAliveMonitoring-Dev
#   ./scripts/generate-env.sh WebAliveMonitoring-Prod

set -euo pipefail

STACK_NAME="${1:-WebAliveMonitoring-Dev}"
ENV_FILE="frontend/.env"

echo "Fetching CloudFormation Outputs from stack: ${STACK_NAME}"

get_output() {
  local key="$1"
  aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='${key}'].OutputValue" \
    --output text
}

API_URL=$(get_output "ApiUrl")
USER_POOL_ID=$(get_output "UserPoolId")
USER_POOL_CLIENT_ID=$(get_output "UserPoolClientId")
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"

cat > "${ENV_FILE}" << EOF
VITE_API_ENDPOINT=${API_URL}
VITE_COGNITO_USER_POOL_ID=${USER_POOL_ID}
VITE_COGNITO_CLIENT_ID=${USER_POOL_CLIENT_ID}
VITE_COGNITO_REGION=${REGION}
EOF

echo "Generated ${ENV_FILE}:"
cat "${ENV_FILE}"
