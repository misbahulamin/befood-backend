#!/usr/bin/env bash
# Shared environment for BeFood managed cron wrappers.
# Sourced by run_*.sh — do not invoke directly from crontab.
# Resolves PROJECT_DIR and an absolute PYTHON_BIN.
# NEVER call bare `python` / system python — wrappers must use "${PYTHON_BIN}".

_CRON_ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${_CRON_ENV_DIR}/../.." && pwd)"
cd "${PROJECT_DIR}"

_befood_resolve_python() {
  local candidates=()
  local cand

  # Discovery order (first executable bin/python wins):
  # 1) BEFOOD_VENV  2) VENV_PATH  3) sibling ../venv
  # 4) PROJECT_DIR/venv  5) PROJECT_DIR/.venv
  if [[ -n "${BEFOOD_VENV:-}" ]]; then
    candidates+=("${BEFOOD_VENV}")
  fi
  if [[ -n "${VENV_PATH:-}" ]]; then
    candidates+=("${VENV_PATH}")
  fi
  candidates+=("$(dirname "${PROJECT_DIR}")/venv")
  candidates+=("${PROJECT_DIR}/venv")
  candidates+=("${PROJECT_DIR}/.venv")

  for cand in "${candidates[@]}"; do
    if [[ -x "${cand}/bin/python" ]]; then
      VENV_PATH="${cand}"
      PYTHON_BIN="${cand}/bin/python"
      return 0
    fi
  done
  return 1
}

if ! _befood_resolve_python; then
  echo "ERROR: BeFood cron could not find an executable venv python." >&2
  echo "  Looked for: BEFOOD_VENV/bin/python, VENV_PATH/bin/python," >&2
  echo "    sibling ../venv/bin/python, PROJECT_DIR/venv/bin/python, PROJECT_DIR/.venv/bin/python" >&2
  echo "  PROJECT_DIR=${PROJECT_DIR}" >&2
  echo "  Hint: production layout is /home/ubuntu/befood-backend + /home/ubuntu/venv" >&2
  exit 1
fi

export DJANGO_ENV="${DJANGO_ENV:-prod}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-core.settings}"
