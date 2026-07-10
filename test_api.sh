#!/usr/bin/env bash
set -e
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
API_KEY="${API_KEY:-change-me}"

printf '\n== health ==\n'
curl -s "$BASE_URL/health"
printf '\n\n== providers ==\n'
curl -s "$BASE_URL/api/providers"
printf '\n\n== create conversation ==\n'
RESP=$(curl -s -X POST "$BASE_URL/api/conversations" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"title":"CLI Test"}')
printf '%s\n' "$RESP"
CID=$(printf '%s' "$RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin)["conversation_id"])')
printf '\n== chat ==\n'
curl -s -X POST "$BASE_URL/api/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"conversation_id\":\"$CID\",\"message\":\"Say hello in one sentence\",\"provider\":\"openai\",\"model\":\"gpt-4.1-mini\"}"
printf '\n'
