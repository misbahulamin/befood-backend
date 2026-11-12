#!/usr/bin/env bash
# Run unassigned-delivery admin digest (production cron wrapper).
# Optional arg: evening|night (log/slot label only; same full candidate query).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_cron_env.sh"

SLOT="${1:-}"
mkdir -p "${PROJECT_DIR}/logs" "${PROJECT_DIR}/tmp/locks"
LOG_FILE="${PROJECT_DIR}/logs/cron-unassigned-delivery-digest.log"
LOCK_FILE="${PROJECT_DIR}/tmp/locks/cron-wrapper-unassigned-delivery-digest.lock"

{
  if command -v flock >/dev/null 2>&1; then
    flock -n 9 || {
      echo "===== $(date -Is) lock busy unassigned_delivery_digest slot=${SLOT:-none}; exiting ====="
      exit 0
    }
  fi
  echo "===== $(date -Is) send_unassigned_delivery_digest slot=${SLOT:-none} PYTHON_BIN=${PYTHON_BIN} ====="
  if [[ -n "${SLOT}" ]]; then
    "${PYTHON_BIN}" manage.py send_unassigned_delivery_digest --slot "${SLOT}"
  else
    "${PYTHON_BIN}" manage.py send_unassigned_delivery_digest
  fi
} 9>"${LOCK_FILE}" >>"${LOG_FILE}" 2>&1
