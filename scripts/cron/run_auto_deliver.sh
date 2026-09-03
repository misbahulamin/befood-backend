#!/usr/bin/env bash
# Run auto meal delivery for lunch or dinner (production cron wrapper).
set -euo pipefail

MEAL_PERIOD="${1:-}"
if [[ "${MEAL_PERIOD}" != "lunch" && "${MEAL_PERIOD}" != "dinner" ]]; then
  echo "Usage: $0 lunch|dinner" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_cron_env.sh"

mkdir -p "${PROJECT_DIR}/logs" "${PROJECT_DIR}/tmp/locks"
LOG_FILE="${PROJECT_DIR}/logs/cron-auto-deliver-${MEAL_PERIOD}.log"
LOCK_FILE="${PROJECT_DIR}/tmp/locks/cron-wrapper-auto-deliver-${MEAL_PERIOD}.lock"

{
  if command -v flock >/dev/null 2>&1; then
    flock -n 9 || {
      echo "===== $(date -Is) lock busy meal_period=${MEAL_PERIOD}; exiting ====="
      exit 0
    }
  fi
  echo "===== $(date -Is) auto_deliver_meals meal_period=${MEAL_PERIOD} PYTHON_BIN=${PYTHON_BIN} ====="
  "${PYTHON_BIN}" manage.py auto_deliver_meals --meal-period "${MEAL_PERIOD}"
} 9>"${LOCK_FILE}" >>"${LOG_FILE}" 2>&1
