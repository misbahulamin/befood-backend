## ADDED Requirements

### Requirement: Production can boot without live S3 credentials
While S3 media integration is deferred, production settings MUST NOT require AWS S3 bucket validation or S3 storage backends to import and run management commands. S3-related wiring that is temporarily disabled MUST remain in source as commented blocks (or equivalent clearly reversible disablement) so the team can re-enable after credential verification.

#### Scenario: Prod settings import without S3 credentials
- **WHEN** `DJANGO_ENV=prod` and AWS access keys / bucket credentials are unset or incomplete
- **THEN** Django settings MUST still import successfully without raising `ImproperlyConfigured` for missing S3 media settings

#### Scenario: Deferred S3 is explicitly marked for later re-enable
- **WHEN** a developer inspects production settings after this change
- **THEN** the disabled S3 storage / validation blocks MUST be present as comments (or documented toggle) indicating they will be uncommented after S3 credentials are verified

### Requirement: Optional local S3 remains opt-in
Local settings MUST continue to enable S3 media only when explicitly requested (e.g. `USE_S3_MEDIA=true`); default local boot MUST NOT require S3.

#### Scenario: Default local boot without S3
- **WHEN** `DJANGO_ENV=local` and `USE_S3_MEDIA` is false or unset
- **THEN** the application MUST boot using non-S3 default media storage and MUST NOT call production S3 validation
