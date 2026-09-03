#!/usr/bin/env bash
# Idempotently install BeFood managed production cron jobs.
# Invoked by existing deploy.yml when this file is present — do not edit deploy YAML.
#
# Production EC2 host timezone is UTC (Etc/UTC). Ubuntu cron evaluates schedules in UTC.
# Business times are Asia/Dhaka (UTC+6, no DST). Do NOT use CRON_TZ — convert BD → UTC.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
AUTO_DELIVER_RUNNER="${PROJECT_DIR}/scripts/cron/run_auto_deliver.sh"
WALLET_THRESHOLD_RUNNER="${PROJECT_DIR}/scripts/cron/run_wallet_threshold_check.sh"

BEGIN_MARK="# BEGIN BEFOOD-MANAGED"
END_MARK="# END BEFOOD-MANAGED"

# Wrappers resolve venv via scripts/cron/_cron_env.sh (sibling ../venv on production).
chmod +x "${AUTO_DELIVER_RUNNER}" 2>/dev/null || true
chmod +x "${WALLET_THRESHOLD_RUNNER}" 2>/dev/null || true
chmod +x "${SCRIPT_DIR}/install_managed_cron.sh" 2>/dev/null || true

# UTC crontab hours (Asia/Dhaka business → UTC):
#   Lunch 15:00 BD → 09:00 UTC | Dinner 23:00 BD → 17:00 UTC
#   Wallet 08:00 BD → 02:00 UTC | Wallet 20:00 BD → 14:00 UTC
MANAGED_BLOCK=$(cat <<EOF
${BEGIN_MARK}
# Host cron timezone: UTC
# Business timezone: Asia/Dhaka
# Auto mark-delivered + wallet charge for scheduled meals (reuse mark_delivery).
0 9 * * * ${AUTO_DELIVER_RUNNER} lunch
0 17 * * * ${AUTO_DELIVER_RUNNER} dinner
# Wallet low-balance reminder + meal-stop + admin summary.
0 2 * * * ${WALLET_THRESHOLD_RUNNER}
0 14 * * * ${WALLET_THRESHOLD_RUNNER}
${END_MARK}
EOF
)

EXISTING="$(crontab -l 2>/dev/null || true)"
# Strip previous managed block (awk between markers inclusive).
FILTERED="$(printf '%s\n' "${EXISTING}" | awk -v b="${BEGIN_MARK}" -v e="${END_MARK}" '
  $0 == b {skip=1; next}
  $0 == e {skip=0; next}
  !skip {print}
')"

# Drop trailing blank lines then append managed block.
FILTERED="$(printf '%s\n' "${FILTERED}" | sed -e :a -e '/^\n*$/{$d;N;ba' -e '}')"
NEW_CRON="$(printf '%s\n\n%s\n' "${FILTERED}" "${MANAGED_BLOCK}")"

printf '%s\n' "${NEW_CRON}" | crontab -
echo "Installed/updated BeFood managed cron jobs (UTC schedules; Asia/Dhaka business times)."
echo "  Auto-deliver: 09:00/17:00 UTC (= 15:00/23:00 Asia/Dhaka)"
echo "  Wallet-threshold: 02:00/14:00 UTC (= 08:00/20:00 Asia/Dhaka)"
echo "  CRON_TZ is not used (host cron is UTC)."
echo "Project: ${PROJECT_DIR}"
crontab -l | sed -n "/${BEGIN_MARK}/,/${END_MARK}/p"
