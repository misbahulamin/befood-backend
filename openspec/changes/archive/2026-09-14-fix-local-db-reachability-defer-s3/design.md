## Context

Default `DJANGO_ENV` is `local` (`core/settings/__init__.py`). `local.py` currently hardcodes production RDS (`befood-postgres-prod.c56oegiikk4d.ap-south-1.rds.amazonaws.com`), so `makemigrations` / DB access times out from the developer network. `prod.py` hardcodes a different RDS host, embeds password in source, and has a broken `HOST` string (missing closing quote). Prod always calls `validate_aws_media_settings` and sets `STORAGES = PROD_STORAGES`; the team wants S3 deferred (commented) until credentials are verified.

No `.env` is present locally; `.env.example` already documents `DB_*` and AWS vars.

## Goals / Non-Goals

**Goals:**

- Local management commands and tests use a reachable database via `DB_*` env (localhost defaults).
- Prod DB config is env-only, syntactically valid, no secrets in git.
- S3 media path in prod is commented/disabled with clear re-enable notes; boot does not require AWS credentials.
- After fix: run smoke checks (`makemigrations`/`check`/`test` as appropriate), migrate on reachable DB, push to `main`.

**Non-Goals:**

- Opening AWS security groups or VPN to prod RDS from every laptop.
- Fully implementing/verifying S3 uploads in this change (explicitly deferred).
- Changing API contracts or domain models.
- Committing real `.env` secrets.

## Decisions

1. **Local DB via `config('DB_*')` with localhost defaults**  
   - Restore env-driven Postgres in `local.py` (same pattern as commented block in `prod.py`).  
   - Alternatives: SQLite for local — rejected as primary because project already standardizes on Postgres for parity; SQLite may remain as a commented fallback only if useful for offline smoke.  
   - Prefer Postgres defaults matching `.env.example` (`befood` / `postgres` / `localhost`).

2. **Prod DB via env only; remove hardcoded credentials**  
   - Uncomment/use `config('DB_NAME')` etc.  
   - Fix the current syntax error as part of rewriting the block.  
   - Alternatives: keep host in code “for convenience” — rejected (secrets + wrong host drift caused this incident).

3. **Defer S3 by commenting prod wiring; keep filesystem/default storage**  
   - Comment `validate_aws_media_settings(...)`, `STORAGES = PROD_STORAGES`, and leave AWS vars in base/`USE_S3_MEDIA` as-is so local optional S3 stays behind `USE_S3_MEDIA=false`.  
   - Ensure `USE_S3_MEDIA` default remains false in `.env.example`.  
   - Alternatives: feature-flag module — overkill; comments + `USE_S3_MEDIA` match user request.

4. **Verification order before push**  
   1) Settings import / `django check`  
   2) `makemigrations` (no hang on unreachable host)  
   3) Targeted tests if any settings tests exist; else minimal smoke  
   4) `migrate` against local (or reachable) DB  
   5) Commit + push `main` when user-approved apply completes  

5. **Do not commit passwords** that currently appear in settings files; rotate if they were ever pushed historically (call out in tasks).

## Risks / Trade-offs

- [Local without Postgres installed] → Document `.env` + Docker/local Postgres; fail fast with clear connection error instead of long timeout to AWS.  
- [Prod deploy missing `DB_*`] → Fail at startup via missing config (prefer explicit over silent wrong DB).  
- [Media uploads break in prod while S3 commented] → Accept temporary local/disk or broken media until S3 re-enabled; document in tasks.  
- [Hardcoded secrets already in git history] → Remove from working tree; recommend credential rotation outside this change.  
- [Push to main] → Only after green smoke; avoid force-push.

## Migration Plan

1. Apply settings edits; update `.env.example` if needed.  
2. Developer creates local `.env` with `DJANGO_ENV=local` and local `DB_*`.  
3. Run check / makemigrations / migrate / tests.  
4. Deploy: set `DJANGO_ENV=prod` + `DB_*` on host; keep S3 commented until follow-up.  
5. Rollback: revert settings commit; restore previous env.

## Open Questions

- Exact prod RDS endpoint/name to put in server env (not in repo) — operator fills at deploy.  
- Whether production should use WhiteNoise-only static + default `FileSystemStorage` for media while S3 is deferred (assumed yes).
