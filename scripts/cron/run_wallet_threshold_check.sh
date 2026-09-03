#!/usr/bin/env bash
# Run wallet balance threshold check (production cron wrapper).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_cron_env.sh"

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
  echo "===== $(date -Is) check_wallet_balance_thresholds PYTHON_BIN=${PYTHON_BIN} ====="
  "${PYTHON_BIN}" manage.py check_wallet_balance_thresholds
} 9>"${LOCK_FILE}" >>"${LOG_FILE}" 2>&1
