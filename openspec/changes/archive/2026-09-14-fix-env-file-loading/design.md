## Context

Current stack:

| Piece | Behavior |
|-------|----------|
| `python-decouple` | In `requirements.txt`; `base.py` uses `config()` for secrets/flags including all `AWS_*` and `USE_S3_MEDIA` |
| `core/settings/__init__.py` | `env = os.getenv('DJANGO_ENV', 'prod')` — **does not read `.env`** |
| Decouple `.env` search | Default `AutoConfig` searches from **cwd**, not necessarily `manage.py` root |
| `python-dotenv` | **Not** installed today |
| S3 media | Already gated by `USE_S3_MEDIA` in `local.py` / `prod.py` (recent `setup-s3-media-storage` change) |

User request: make `.env` load reliably from project root for local + EC2; if a loader already exists, use it without conflict; otherwise use `python-dotenv`. They also asked to plan first (this change).

## Goals / Non-Goals

**Goals:**

- Load project-root `.env` early so `DJANGO_ENV` and AWS vars are visible consistently.
- Keep `python-decouple` as the typed settings API (`config(...)`).
- Minimal surface area; no models/API/DB/upload rewrites.
- OS/systemd env overrides `.env`; missing `.env` still boots on EC2 with OS env only.

**Non-Goals:**

- Replacing `decouple` with `os.getenv` everywhere.
- Changing S3 STORAGES implementation beyond env bootstrap.
- Moving hardcoded DB passwords in `local.py`/`prod.py` (separate cleanup).
- Committing real `.env` secrets.

## Decisions

### 1. Keep python-decouple; add python-dotenv only as bootstrap

**Decision:** Add `python-dotenv` and call `load_dotenv(BASE_DIR / '.env', override=False)` early. Keep all existing `config(...)` calls.

**Rationale:** Satisfies “use existing loader” (decouple stays) and “use dotenv if needed” for explicit root-path load + populating `os.environ` so `os.getenv('DJANGO_ENV')` works. `override=False` preserves production systemd/OS precedence.

**Alternative considered:** Only switch `__init__.py` to `config('DJANGO_ENV')` without dotenv — smaller, but decouple still cwd-dependent unless `Config(RepositoryEnv(path))` is centralized. Dotenv-at-root is clearer for operators who expect “`.env` next to manage.py”.

**Alternative considered:** Replace decouple with dotenv + `os.getenv` — rejected; conflicts with existing pattern and typed `cast=bool`.

### 2. Single bootstrap location + optional entrypoints

**Decision:**

1. Resolve `BASE_DIR` as `Path(__file__).resolve().parent.parent.parent` from `core/settings/__init__.py` (same root as `manage.py`).
2. Call `load_dotenv(BASE_DIR / '.env', override=False)` at the **top** of `core/settings/__init__.py` before reading `DJANGO_ENV`.
3. Also call the same load at the top of `manage.py` (and optionally `wsgi.py` / `asgi.py`) so management commands and WSGI workers populate env before settings import if needed.

**Rationale:** Settings `__init__` is the critical path for `DJANGO_ENV`; manage/wsgi covers processes that set env earlier.

### 3. Do not re-implement AWS reads

**Decision:** Leave `base.py` AWS / `USE_S3_MEDIA` `config(...)` blocks as-is (already env-only). No hardcoded keys.

**Rationale:** Already done by `setup-s3-media-storage`; this change only ensures `.env` is loaded so those reads succeed from the file.

### 4. Default `DJANGO_ENV` remains `prod` when unset

**Decision:** Keep `os.getenv('DJANGO_ENV', 'prod')` (after dotenv load) so EC2 without `.env` and without the var still gets prod settings — do not flip default to `local` in this change.

**Rationale:** Avoid breaking production if someone deploys code without setting `DJANGO_ENV`. Local developers should set `DJANGO_ENV=local` in project-root `.env`.

### 5. Documentation only for deploy commands

**Decision:** Short note in `.env.example` + optional `core/docs/backend/env-loading.md` listing: install `python-dotenv`, place `.env` at root, restart service; no migrate.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Two libraries (decouple + dotenv) confuse maintainers | Document: dotenv = load file into env; decouple = typed `config()` |
| Local `.env` with `DJANGO_ENV=local` accidentally copied to EC2 | Ops docs: prefer systemd env on EC2; `.env` optional; never commit secrets |
| `override=False` means stale OS env wins over updated `.env` | Document that OS/systemd wins; restart after changing host env |
| Flipping default DJANGO_ENV would break prod | Explicitly keep default `prod` |

## Migration Plan

1. Add `python-dotenv` to `requirements.txt`.
2. Implement early `load_dotenv` in settings `__init__` (+ manage/wsgi as needed).
3. Verify locally: `.env` with `DJANGO_ENV=local` and AWS placeholders; no keys in code.
4. EC2: `pip install -r requirements.txt`, ensure root `.env` or systemd `Environment=`, restart gunicorn — **no** `migrate` for this change.
5. Rollback: remove dotenv calls / dependency; restore previous `__init__.py` (prod still works via OS env).

## Open Questions

- Confirm EC2 currently uses systemd `Environment=` vs a root `.env` file (both supported after this change).
- Whether `asgi.py` is used in production (if only WSGI, asgi bootstrap is optional).
