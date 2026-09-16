## Context

`requirements.txt` at the repo root is currently UTF-16 LE (null bytes between ASCII characters; length ~2× the logical text). Linux `pip` reads requirement files as UTF-8/ASCII by default. Decoding UTF-16 as UTF-8 yields garbage or null-interleaved package names, so `pip install -r requirements.txt` fails or mis-parses lines on CI and production Linux hosts.

Constraints from the request:

- Convert encoding only: UTF-16 → UTF-8 LF.
- Do **not** change package names or version pins.
- Keep all dependencies exactly the same.
- Verify the result is readable by Linux pip.

## Goals / Non-Goals

**Goals:**

- Rewrite `requirements.txt` as UTF-8 without BOM, LF (`\n`) line endings.
- Preserve exact dependency text (names, operators, versions, comments, blank lines).
- Prove the file has no UTF-16 NUL pattern and decodes cleanly as UTF-8 for pip.

**Non-Goals:**

- Adding, removing, or upgrading packages.
- Splitting into multiple requirement files or lockfile formats.
- Changing install/deploy workflow YAML.
- Broad encoding cleanup of other repo files (unless a single `.gitattributes` rule for `requirements.txt` is added as recurrence prevention—optional, not required for this hotfix).

## Decisions

### D1 — One-shot decode UTF-16 → write UTF-8 LF

- **Choice:** Read bytes as UTF-16 (LE, with or without BOM), normalize newlines to `\n`, write UTF-8 without BOM.
- **Why:** Matches the observed byte pattern (`61 00 69 00…`); preserves logical text unchanged.
- **Alternatives:** Manual re-type of packages — error-prone and risks version drift.

### D2 — Content freeze

- **Choice:** After conversion, compare line list (stripped of `\r` only) to the UTF-16-decoded original; fail if any package/version line differs.
- **Why:** Explicit user constraint: dependencies must stay identical.
- **Alternatives:** Trust visual diff alone — weaker for encoding-only changes.

### D3 — Pip readability verification

- **Choice:** Verify: (1) file decodes as UTF-8; (2) no `\0` bytes; (3) no `\r`; (4) `python -m pip install -r requirements.txt --dry-run` (or `pip download`/`pip install --report` dry-run) succeeds in parsing, or at minimum `pip`’s requirements parser accepts the file without encoding errors.
- **Why:** User asked to verify Linux-pip readability; dry-run avoids installing into the active env when unnecessary.
- **Alternatives:** Full `pip install` in a throwaway venv — stronger but heavier; optional if dry-run is unavailable on the local pip version.

### D4 — Optional gitattributes (defer unless trivial)

- **Choice:** Prefer encoding fix only for this change; optional follow-up `requirements.txt text eol=lf working-tree-encoding=UTF-8` if the team wants recurrence prevention.
- **Why:** Scope is a hotfix; `.gitattributes` for encoding is less commonly needed than for CRLF once the file is UTF-8 ASCII-ish.
- **Alternatives:** Add attributes now — low cost, can be a small task if desired.

## Risks / Trade-offs

- **[Risk] Wrong UTF-16 endianness guess** → **Mitigation:** Detect BOM; if absent, try LE first (observed on this Windows checkout) and confirm first lines look like package names.
- **[Risk] Trailing blank lines / `\r` mixed in** → **Mitigation:** Normalize to LF; keep the same number of content lines as the decoded source.
- **[Risk] Editors on Windows re-save as UTF-16** → **Mitigation:** Document UTF-8; optional `.gitattributes` / editor settings later.

## Migration Plan

1. Convert and commit `requirements.txt` as UTF-8 LF.
2. CI/deploy `pip install -r requirements.txt` should parse normally.
3. Rollback: revert the commit (would restore UTF-16 and break Linux pip again—prefer forward-only).

## Open Questions

- None blocking.
