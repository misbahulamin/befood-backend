## Context

Deploy workflow (`.github/workflows/deploy.yml`) SSH-runs production steps through step 9:

```bash
bash "$PROJECT_DIR/scripts/cron/install_managed_cron.sh"
```

On the Linux host, bash fails immediately:

```text
set: pipefail
: invalid option name
```

Local inspection shows all three cron wrappers are stored with CRLF (`\r\n`). Bash parses `set -euo pipefail\r`, so the option name becomes `pipefail\r`, which is invalid. This matches the split error lines (`pipefail` then a lone `:`).

Constraints carried from prior managed-cron work:

- Do **not** edit deploy YAML.
- Cron schedule/content stays the same (auto-deliver + wallet threshold).
- Scripts must remain plain bash, runnable with `bash script.sh`.

## Goals / Non-Goals

**Goals:**

- Make `scripts/cron/*.sh` LF-only so Linux deploy and crontab wrappers succeed.
- Prevent recurrence via `.gitattributes` `eol=lf` for shell scripts.
- Keep cron job semantics unchanged.

**Non-Goals:**

- Changing cron schedules, markers, or management-command behavior.
- Editing `.github/workflows/deploy.yml`.
- Broad repo-wide CRLF cleanup beyond shell scripts (unless a minimal related rule is useful).
- Changing shebang / requiring `/bin/bash` absolute path beyond current `#!/usr/bin/env bash`.

## Decisions

### D1 — Root cause is CRLF, not missing `pipefail` support

- **Choice:** Treat this as line-ending corruption, not a dash/sh vs bash issue.
- **Why:** Deploy already invokes `bash .../install_managed_cron.sh`; bash supports `pipefail`. The `\r` after `pipefail` explains the exact error shape.
- **Alternatives:** Rewrite `set -euo pipefail` to three lines / drop `pipefail` — masks the real bug and still leaves later lines fragile (`$'\r'` in paths/vars).

### D2 — Normalize existing files + enforce with `.gitattributes`

- **Choice:** Rewrite the three cron scripts to LF, and add:

  ```gitattributes
  *.sh text eol=lf
  ```

  Optionally also `scripts/** text eol=lf` if we want belt-and-suspenders for non-`.sh` helpers later; start with `*.sh`.
- **Why:** `.gitattributes` is the durable fix for Windows contributors; one-time LF convert fixes production now.
- **Alternatives:** Only convert files without attributes — will regress on the next Windows edit/commit. EditorConfig alone is weaker across clones/CI.

### D3 — Verification before merge / after deploy

- **Choice:** Local checks: no `\r` in `scripts/cron/*.sh`; `bash -n` on each script. After deploy: step 9 succeeds and `crontab -l` shows the managed block.
- **Why:** Cheap, matches existing docs already mentioning `bash -n`.
- **Alternatives:** Add CI job for line endings — valuable later, out of scope for this hotfix unless trivial.

### D4 — No deploy YAML change

- **Choice:** Keep calling the installer exactly as today.
- **Why:** Prior OpenSpec changes forbid YAML edits for managed cron; LF fix is sufficient.

## Risks / Trade-offs

- **[Risk] Git may still show “changed” files after attributes if index has CRLF** → **Mitigation:** After adding `.gitattributes`, re-normalize with `git add --renormalize scripts/cron/*.sh` (or rewrite files explicitly) so the blob stored in git is LF.
- **[Risk] Existing server working tree still has CRLF until next pull** → **Mitigation:** Normal deploy `git pull` / fetch updates files; if needed, one-time `sed -i 's/\r$//' scripts/cron/*.sh` on the host.
- **[Risk] Other `*.sh` elsewhere pick up `eol=lf` unexpectedly** → **Mitigation:** Intended and desirable for Linux deploy scripts; low downside on Windows (Git still checks out LF for those paths).

## Migration Plan

1. Land LF scripts + `.gitattributes` on `main`.
2. Re-run production deploy; step 9 should install/update managed cron and continue to nginx/Gunicorn.
3. Rollback: revert the commit (would restore CRLF and break again—prefer forward fix only). Content rollback of cron lines is unchanged from prior docs.

## Open Questions

- None blocking. Optional follow-up: CI check that fails if any `scripts/**/*.sh` contains `\r`.
