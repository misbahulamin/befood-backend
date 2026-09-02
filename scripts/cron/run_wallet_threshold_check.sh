#!/usr/bin/env bash
# Run wallet balance threshold check (production cron wrapper).
set -euo pipefail

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
LOG_FILE="${PROJECT_DIR}/logs/cron-wallet-threshold-check.log"
LOCK_FILE="${PROJECT_DIR}/tmp/locks/cron-wrapper-wallet-threshold-check.lock"

{
  if command -v flock >/dev/null 2>&1; then
    flock -n 9 || {
      echo "===== $(date -Is) lock busy wallet_threshold_check; exiting ====="
      exit 0
    }
  fi
  echo "===== $(date -Is) check_wallet_balance_thresholds ====="
  python manage.py check_wallet_balance_thresholds
} 9>"${LOCK_FILE}" >>"${LOG_FILE}" 2>&1
