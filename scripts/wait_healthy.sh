#!/usr/bin/env bash

set -euo pipefail

TIMEOUT="${1:-90}"
INTERVAL=3
ELAPSED=0

CHECKS=(
  "Prometheus:http://localhost:9090/-/healthy"
  "Alertmanager:http://localhost:9093/-/healthy"
  "Loki:http://localhost:3100/ready"
  "Tempo:http://localhost:3200/ready"
  "Grafana:http://localhost:3000/api/health"
  "otel-collector:http://localhost:8888/metrics"
)

echo "Waiting up to ${TIMEOUT}s for the stack to become healthy..."

while true; do
  all_ok=true
  for entry in "${CHECKS[@]}"; do
    name="${entry%%:*}"
    url="${entry#*:}"
    if ! curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
      all_ok=false
      failing="$name"
    fi
  done

  if $all_ok; then
    echo "All components healthy after ${ELAPSED}s."
    exit 0
  fi

  if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
    echo "Timed out after ${TIMEOUT}s. Last failing check: ${failing:-unknown}." >&2
    echo "--- docker compose ps ---" >&2
    docker compose -f observability/docker-compose.signalpost.yml ps >&2 || true
    exit 1
  fi

  sleep "$INTERVAL"
  ELAPSED=$((ELAPSED + INTERVAL))
done
