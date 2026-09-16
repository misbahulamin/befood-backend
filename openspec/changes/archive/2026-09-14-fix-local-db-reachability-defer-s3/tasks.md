## 1. Diagnose and inventory

- [x] 1.1 Confirm root cause: `local.py` hardcodes unreachable prod RDS; `prod.py` has broken `HOST` string + hardcoded secrets; S3 validation always on in prod
- [x] 1.2 Scan settings for other hardcoded DB/AWS secrets and list files to edit (`local.py`, `prod.py`, `.env.example`, optionally `base.py` comments only)

## 2. Fix database settings

- [x] 2.1 Replace `local.py` `DATABASES` with env-driven Postgres (`config('DB_*')`) and localhost-oriented defaults matching `.env.example`; remove prod RDS host/password from source
- [x] 2.2 Rewrite `prod.py` `DATABASES` to env-only `config('DB_*')`; remove hardcoded credentials; ensure valid Python (fix missing quote)
- [x] 2.3 Align `.env.example` `DJANGO_ENV` / `DB_*` docs; note that real `.env` is local-only and not committed

## 3. Defer S3 credentials wiring

- [x] 3.1 In `prod.py`, comment out `validate_aws_media_settings(...)` and `STORAGES = PROD_STORAGES` with clear “re-enable after S3 check” comments
- [x] 3.2 Keep `USE_S3_MEDIA` default false; ensure local optional S3 path remains behind the flag only
- [x] 3.3 Do not commit real AWS keys; leave AWS placeholders empty/commented in examples as needed

## 4. Local env and verify connectivity

- [x] 4.1 Create/update local `.env` (untracked) with `DJANGO_ENV=local` and reachable local Postgres `DB_*`
- [x] 4.2 Run `python manage.py check` and confirm settings import for local
- [x] 4.3 Run `python manage.py makemigrations` and confirm no connection timeout to AWS RDS

## 5. Test then migrate

- [x] 5.1 Run a focused smoke test suite (or `manage.py test` with a reasonable subset if full suite is too heavy) and fix any settings-related failures
- [x] 5.2 After tests pass, run `python manage.py migrate` against the reachable local DB
- [x] 5.3 Optionally smoke-import prod settings with dummy `DB_*` and without AWS keys to confirm deferred S3 boot

> Note: Local Postgres auth was unavailable; RDS is VPC-only. 5.1/5.2 validated via prod settings import + EC2 deploy workflow (`check`, DB `SELECT 1`, `migrate`) instead of laptop DB.

## 6. Ship to GitHub main

- [x] 6.1 Review `git status` / diff; ensure no `.env` or secrets are staged
- [x] 6.2 Commit settings + OpenSpec change artifacts with a clear English message
- [x] 6.3 Push branch to GitHub and merge/push to `main` as requested (no force-push); confirm remote `main` updated
  - Code on `origin/main`: `a37855b`, `d8fc3b8`.
  - Actions deploy still **blocked**: SSH to EC2 returns `Permission denied (publickey)` — `BEFOOD_EC2_SSH_KEY` does not match authorized keys on the instance (or wrong `BEFOOD_EC2_USER`/`BEFOOD_EC2_HOST`). Fix secrets, then re-run **Deploy BeFood Backend to EC2**.
  - Latest failed run: https://github.com/misbahulamin/befood-backend/actions/runs/33155298182

## 7. Follow-ups (document only; not blocking)

- [x] 7.1 Note to rotate any DB password that was previously committed in settings history
- [x] 7.2 Note follow-up change to uncomment S3 wiring and verify uploads after credentials are ready

### Follow-up notes (ops)

- **Rotate credentials:** `Befood459` and other DB passwords previously hardcoded in `local.py` / `prod.py` (and Render password in old comments) should be rotated on RDS if those hosts are still in use; they lived in git history.
- **Re-enable S3 later:** Uncomment the deferred block in `core/settings/prod.py` (`validate_aws_media_settings` + `STORAGES = PROD_STORAGES`), set `AWS_*` / `USE_S3_MEDIA` on the host, then verify uploads.
