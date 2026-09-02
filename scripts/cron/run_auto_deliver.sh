#!/usr/bin/env bash
# Run auto meal delivery for lunch or dinner (production cron wrapper).
set -euo pipefail

MEAL_PERIOD="${1:-}"
if [[ "${MEAL_PERIOD}" != "lunch" && "${MEAL_PERIOD}" != "dinner" ]]; then
  echo "Usage: $0 lunch|dinner" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_DIR}"

if [[ -f "${PROJECT_DIR}/venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${PROJECT_DIR}/venv/bin/activate"
elif [[ -f "${PROJECT_DIR}/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${PROJECT_DIR}/.venv/bin/activate"
fi

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
  echo "===== $(date -Is) auto_deliver_meals meal_period=${MEAL_PERIOD} ====="
  python manage.py auto_deliver_meals --meal-period "${MEAL_PERIOD}"
} 9>"${LOCK_FILE}" >>"${LOG_FILE}" 2>&1
