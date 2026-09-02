#!/usr/bin/env bash
# Idempotently install BeFood managed production cron jobs.
# Invoked by existing deploy.yml when this file is present — do not edit deploy YAML.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
AUTO_DELIVER_RUNNER="${PROJECT_DIR}/scripts/cron/run_auto_deliver.sh"
WALLET_THRESHOLD_RUNNER="${PROJECT_DIR}/scripts/cron/run_wallet_threshold_check.sh"

BEGIN_MARK="# BEGIN BEFOOD-MANAGED"
END_MARK="# END BEFOOD-MANAGED"

chmod +x "${AUTO_DELIVER_RUNNER}" 2>/dev/null || true
chmod +x "${WALLET_THRESHOLD_RUNNER}" 2>/dev/null || true
chmod +x "${SCRIPT_DIR}/install_managed_cron.sh" 2>/dev/null || true

MANAGED_BLOCK=$(cat <<EOF
${BEGIN_MARK}
CRON_TZ=Asia/Dhaka
# Auto mark-delivered + wallet charge for scheduled meals (reuse mark_delivery).
0 15 * * * ${AUTO_DELIVER_RUNNER} lunch
0 23 * * * ${AUTO_DELIVER_RUNNER} dinner
# Wallet low-balance reminder + meal-stop + admin summary.
0 8 * * * ${WALLET_THRESHOLD_RUNNER}
0 20 * * * ${WALLET_THRESHOLD_RUNNER}
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
echo "Installed/updated BeFood managed cron jobs (auto-deliver 15:00/23:00, wallet-threshold 08:00/20:00 Asia/Dhaka)."
echo "Project: ${PROJECT_DIR}"
crontab -l | sed -n "/${BEGIN_MARK}/,/${END_MARK}/p"
