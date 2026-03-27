#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env.local}"

cd "$ROOT"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

if [ -z "${GSTACK_TEXT_API_URL:-}" ]; then
  echo "GSTACK_TEXT_API_URL is not set" >&2
  exit 1
fi

if [ -z "${GSTACK_TEXT_API_KEY:-}" ]; then
  echo "GSTACK_TEXT_API_KEY is not set" >&2
  exit 1
fi

curl --location "$GSTACK_TEXT_API_URL" \
  --header "Authorization: Bearer $GSTACK_TEXT_API_KEY" \
  --header "Content-Type: application/json" \
  --data "{
    \"model\": \"${GSTACK_TEXT_API_MODEL:-glm-5}\",
    \"messages\": [
      {
        \"role\": \"user\",
        \"content\": \"你好\"
      }
    ]
  }"
