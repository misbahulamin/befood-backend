## ADDED Requirements

### Requirement: Local settings use environment database configuration
When `DJANGO_ENV` is not `prod`, the application MUST configure the default database from environment variables (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`) with localhost-oriented defaults suitable for developer machines. Local settings MUST NOT hardcode a production RDS hostname.

#### Scenario: Makemigrations does not target unreachable prod RDS by default
- **WHEN** a developer runs `python manage.py makemigrations` with default `DJANGO_ENV=local` and local `DB_*` (or defaults pointing at localhost)
- **THEN** Django MUST attempt to connect only to that local/configured host and MUST NOT use `befood-postgres-prod` (or other prod RDS) hostnames from settings source

#### Scenario: Database credentials are not embedded in local settings source
- **WHEN** `core/settings/local.py` is reviewed in source control
- **THEN** it MUST NOT contain plaintext production database passwords or production RDS endpoints

### Requirement: Production database settings are env-driven and valid
When `DJANGO_ENV=prod`, the application MUST load `DATABASES['default']` exclusively from environment variables and MUST ship syntactically valid Python settings (no broken string literals).

#### Scenario: Prod settings import without syntax errors
- **WHEN** Django loads `core.settings` with `DJANGO_ENV=prod` and required `DB_*` env vars set
- **THEN** settings MUST import successfully and the default engine MUST be PostgreSQL using those env values

#### Scenario: No production DB secrets in repository settings
- **WHEN** `core/settings/prod.py` is reviewed in source control
- **THEN** it MUST NOT contain hardcoded database passwords or hostnames that act as the sole source of truth (env vars MUST be used)
