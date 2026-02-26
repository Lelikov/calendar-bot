#!/bin/sh
set -eu

OS_URL="http://opensearch:9200"

echo "[opensearch-init] Waiting for OpenSearch..."
for i in $(seq 1 90); do
  if curl -s "$OS_URL/_cluster/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "[opensearch-init] Creating ISM policy: logs-retention-14d"
curl -sS -X PUT "$OS_URL/_plugins/_ism/policies/logs-retention-14d" \
  -H 'Content-Type: application/json' \
  -d '{
    "policy": {
      "description": "Delete docker logs indices after 14 days",
      "default_state": "hot",
      "states": [
        {
          "name": "hot",
          "actions": [],
          "transitions": [
            {
              "state_name": "delete",
              "conditions": { "min_index_age": "14d" }
            }
          ]
        },
        {
          "name": "delete",
          "actions": [
            { "delete": {} }
          ],
          "transitions": []
        }
      ],
      "ism_template": [
        {
          "index_patterns": ["logs-docker-*"] ,
          "priority": 100
        }
      ]
    }
  }' >/dev/null

echo "[opensearch-init] Applying policy to existing logs-docker-* indices"
curl -sS -X POST "$OS_URL/_plugins/_ism/add/logs-docker-*" \
  -H 'Content-Type: application/json' \
  -d '{"policy_id":"logs-retention-14d"}' >/dev/null || true

echo "[opensearch-init] Done"
