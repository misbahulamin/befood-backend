# Django App Structure Reference

Progressive-disclosure reference. Agents load this on demand via `.cursor/rules/django-standard-structure.mdc`.
This file is **not** an always-apply Cursor rule.

## Legacy compatibility

Feature-suffixed modules such as `api/pm_views.py` / `api/transfer_views.py` already exist in this repo.
They remain valid until a dedicated refactor migrates them. Do not force an immediate merge when editing those files.
Prefer consolidated `api/views.py`, `serializers.py`, and `openapi.py` for **new** work when practical.

## 1. Purpose

Apply this target structure to every Django or Django REST Framework app in this repository.

Avoid creating **new** feature-specific framework files such as:

- `api/pm_views.py`
- `api/pm_serializers.py`
- `api/pm_openapi.py`
- `api/transfer_views.py`
- `api/transfer_serializers.py`
- `api/transfer_schema.py`

Keep framework-facing code consolidated and group related code inside each file using clear section headers.

Business logic must be placed in `services/`. Reusable helpers, validators, and constants must be placed in `utils/`.

---

## 2. Required Django App Structure

Every Django app should follow this structure unless a project-level architectural decision explicitly requires otherwise:

```text
your_app/
├── __init__.py
├── admin.py
├── apps.py
├── filters.py
├── models.py
├── permissions.py
├── authentication.py
├── middleware.py
├── signals.py
├── qr_parser.py
├── tasks.py
├── api/
│   ├── __init__.py
│   ├── openapi.py
│   ├── serializers.py
│   ├── views.py
|   └── urls.py
│
├── services/
│   ├── __init__.py
│   ├── machine_services.py
│   ├── maintenance_services.py
│   └── transfer_services.py
│
├── utils/
│   ├── __init__.py
│   ├── validators.py
│   ├── helpers.py
│   └── constants.py
│
├── tests/
│   ├── __init__.py
│   ├── test_views.py
│   ├── test_services.py
│   ├── test_models.py
│   └── test_serializers.py
│
├── migrations/
│   └── __init__.py
│
├── management/
│   ├── __init__.py
│   └── commands/
│       └── __init__.py
│
└── docs/
    ├── BACKEND_TECHNICAL.md
    └── FRONTEND_INTEGRATION.md
```

Only create optional files when they are actually needed:

- `permissions.py`
- `authentication.py`
- `middleware.py`
- `signals.py`
- `qr_parser.py`
- `tasks.py`
- `filters.py`

Always use `__init__.py`. Never create `init.py`.

---

## 3. Mandatory File Responsibilities

### `models.py`

Keep all database models for the Django app in `models.py`.

Allowed content:

- Django model classes
- model managers and querysets that are tightly coupled to the model
- model-level constraints
- model indexes
- small model properties
- small model methods that represent true model behavior

Do not place large workflows, API orchestration, reporting logic, notification workflows, transfer workflows, preventive-maintenance workflows, or cross-model business operations in model methods.

Move complex business logic to the appropriate service module.

### `serializers.py`

Keep all DRF serializers for the app in `serializers.py`.

Group serializers by feature using section headers.

Serializers may:

- validate request data
- validate field relationships
- convert model instances to API representations
- call a service function after validation

Serializers must not contain:

- long database workflows
- multi-step state transitions
- duplicated business rules
- unrelated notification logic
- large query-building functions
- external integration orchestration

### `views.py`

Keep all DRF views, viewsets, and API views for the app in `views.py`.

Group views by feature using section headers.

Views must remain thin. A view should mainly:

1. authenticate and authorize
2. parse request parameters
3. invoke a serializer or service
4. return a response

Do not implement complex business logic directly in a view.

### `urls.py`

Keep all URL patterns for the app in `urls.py`.

Requirements:

- use clear, stable route names
- group routes by feature
- avoid duplicate paths
- use consistent trailing-slash behavior
- keep route registration close to the related feature section
- update imports when consolidating old modules

### `openapi.py`

Keep all app-specific OpenAPI and Swagger documentation helpers in `openapi.py`.

This includes:

- `extend_schema` definitions
- request examples
- response examples
- reusable OpenAPI parameters
- reusable response schemas
- app-specific API documentation constants

Do not create parallel files such as `pm_openapi.py`, `transfer_schema.py`, or `machine_openapi.py`.

### `filters.py`

Keep all `django-filter` filter sets in `filters.py`.

Use filters instead of manually parsing and duplicating complex query parameter logic in multiple views.

### `admin.py`

Keep all Django admin registrations and admin classes in `admin.py`.

Group admin classes by feature using section headers.

### `permissions.py`

Keep custom DRF permission classes in `permissions.py`.

Permissions should answer access-control questions only. Do not place business workflows in permission classes.

### `authentication.py`

Keep custom authentication backends and DRF authentication classes in `authentication.py`.

### `middleware.py`

Keep app-specific middleware in `middleware.py`.

Do not create middleware for logic that belongs in a view, service, signal, or permission.

### `signals.py`

Keep Django signal receivers in `signals.py`.

Signal handlers must be short and predictable. Delegate non-trivial work to services or Celery tasks.

Ensure signals are registered through `apps.py` when required.

### `qr_parser.py`

Keep QR parsing and QR payload interpretation in `qr_parser.py` only when QR parsing is a significant app-specific responsibility.

Pure reusable parsing helpers may be placed in `utils/helpers.py`.

### `tasks.py`

Keep Celery tasks in `tasks.py`.

Celery tasks should delegate core business logic to services so the same logic can be reused synchronously and tested independently.

---

## 4. Service-Layer Rules

Use `services/` for complex business logic.

Examples:

- preventive-maintenance workflows
- machine status changes
- machine transfer workflows
- location-history creation
- breakdown lifecycle handling
- multi-model writes
- transaction management
- notification orchestration
- performance-sensitive query workflows
- idempotent commands
- external service coordination

Recommended modules:

```text
services/
├── __init__.py
├── machine_services.py
├── maintenance_services.py
└── transfer_services.py
```

Create another service module only when the responsibility is clearly separate and the existing service file would become too broad.

Service functions should:

- use descriptive verb-based names
- accept explicit arguments
- return predictable values
- raise domain-appropriate exceptions
- use `transaction.atomic()` for multi-step writes
- prevent duplicated business-rule implementations
- be independently testable
- avoid depending on HTTP request objects
- avoid returning DRF `Response` objects

Good examples:

```python
def change_machine_status(*, machine, new_status, actor, location=None):
    ...

def transfer_machine(*, machine, destination, requested_by):
    ...

def complete_pm_check(*, machine, checklist_data, completed_by):
    ...
```

Bad examples:

```python
def do_it(data):
    ...

def process(request):
    ...

def helper(obj):
    ...
```

---

## 5. Utility-Layer Rules

Use `utils/` only for reusable, mostly stateless helpers.

```text
utils/
├── __init__.py
├── validators.py
├── helpers.py
└── constants.py
```

### `utils/validators.py`

Use for reusable validators that do not belong exclusively to one serializer or model field.

### `utils/helpers.py`

Use for small reusable helper functions.

Helpers must not hide major business workflows.

### `utils/constants.py`

Use for stable app-level constants, enums, mappings, and configuration-independent values.

Do not duplicate constants across views, serializers, models, and services.

---

## 6. Required Section Headers

Use visible section headers to group code by feature in shared files.

Use this exact style:

```python
# ============================================================================
# PREVENTIVE MAINTENANCE VIEWS
# ============================================================================
```

Apply the same structure in `views.py`, `serializers.py`, `openapi.py`, `admin.py`, `filters.py`, and other shared files when multiple features exist.

Example `views.py`:

```python
# ============================================================================
# PREVENTIVE MAINTENANCE VIEWS
# ============================================================================


class PreventiveMaintenanceListView(...):
    ...


class PreventiveMaintenanceCreateView(...):
    ...


# ============================================================================
# MACHINE TRANSFER VIEWS
# ============================================================================


class MachineTransferView(...):
    ...


# ============================================================================
# QR SCAN VIEWS
# ============================================================================


class QRScanView(...):
    ...
```

Example `serializers.py`:

```python
# ============================================================================
# PREVENTIVE MAINTENANCE SERIALIZERS
# ============================================================================


class PreventiveMaintenanceSerializer(...):
    ...


# ============================================================================
# MACHINE TRANSFER SERIALIZERS
# ============================================================================


class MachineTransferSerializer(...):
    ...
```

Keep two blank lines between top-level classes and functions, following PEP 8.

---

## 7. Do Not Recreate the Old `api/` Structure

Do not create a new `api/` package for normal app code.

Do not create feature-specific framework files such as:

```text
api/
├── pm_views.py
├── pm_serializers.py
├── pm_openapi.py
├── transfer_views.py
├── transfer_serializers.py
└── transfer_schema.py
```

Use the following mapping instead:

```text
api/pm_views.py                 -> views.py
api/transfer_views.py           -> views.py
api/pm_serializers.py           -> serializers.py
api/transfer_serializers.py     -> serializers.py
api/pm_openapi.py               -> openapi.py
api/transfer_schema.py          -> openapi.py
```

Move complex logic found in those files into the correct `services/` module.

Do not create compatibility wrapper modules unless they are temporarily required to prevent a breaking deployment. If a wrapper is necessary, mark it clearly as temporary and remove it after imports are migrated.

---

## 8. Existing-Code Refactoring Rules

When working in an app that already uses the old structure:

1. Do not add new code to deprecated feature-specific files.
2. Consolidate the touched feature into the standard files.
3. Update imports in:
   - `urls.py`
   - tests
   - admin configuration
   - services
   - tasks
   - signals
   - other apps
4. Preserve public API behavior unless the task explicitly requests a breaking change.
5. Preserve URL paths and URL names unless a route change is requested.
6. Preserve serializer field names and response formats unless an API change is requested.
7. Preserve database behavior and migration history.
8. Run or update tests after moving code.
9. Remove old modules only after all imports are migrated.
10. Check for circular imports after consolidation.
11. Never delete working code merely to satisfy the folder layout.
12. Prefer a safe incremental migration over a destructive rewrite.

Before finishing a structural refactor, search the repository for imports of every moved module.

---

## 9. Import Rules

Use clear, stable imports.

Preferred:

```python
from maintenance.services.maintenance_services import complete_pm_check
from maintenance.services.transfer_services import transfer_machine
from maintenance.utils.constants import PM_STATUS_DUE
```

For imports inside the same app, consistent relative imports are also acceptable:

```python
from .services.maintenance_services import complete_pm_check
from .utils.constants import PM_STATUS_DUE
```

Do not use wildcard imports:

```python
from .services import *
```

Avoid circular imports by:

- keeping HTTP concerns in views
- keeping representation concerns in serializers
- keeping business logic in services
- keeping reusable constants in `utils/constants.py`
- importing models locally only when genuinely necessary

---

## 10. View Design Rules

Views should be small and readable.

Preferred pattern:

```python
class MachineTransferView(APIView):
    permission_classes = [CanTransferMachine]

    def post(self, request, machine_id):
        serializer = MachineTransferRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = transfer_machine(
            machine_id=machine_id,
            requested_by=request.user,
            **serializer.validated_data,
        )

        response_serializer = MachineTransferSerializer(result)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
```

Avoid:

- deeply nested conditionals
- large transactions in views
- repeated query logic
- duplicated permission checks
- direct creation of many related objects
- notification sending inside views
- large response-dictionary construction when a serializer is appropriate

---

## 11. Serializer Design Rules

Use separate serializers when request and response shapes differ.

Recommended naming:

```python
MachineTransferRequestSerializer
MachineTransferSerializer
MachineStatusChangeRequestSerializer
MachineStatusHistorySerializer
PreventiveMaintenanceCreateSerializer
PreventiveMaintenanceDetailSerializer
```

Use `validate_<field>()` for field-specific validation and `validate()` for cross-field validation.

Do not use serializer methods as a hidden replacement for the service layer.

---

## 12. Model and Database Rules

When changing models:

- create proper migrations
- add indexes for frequent filters and ordering fields
- use database constraints for critical invariants
- use meaningful `related_name` values
- use timezone-aware timestamps
- avoid unbounded query loops
- prevent N+1 queries with `select_related()` and `prefetch_related()`
- use `exists()` for existence checks
- use `values()` or `values_list()` when full model instances are unnecessary
- use bulk operations only when signals and per-object validation are not required
- keep migrations backward-safe when possible

Do not manually edit old applied migrations unless the task explicitly requires migration repair.

---

## 13. Performance Rules

For list and monitoring endpoints:

- inspect query counts
- paginate large responses
- avoid loading unnecessary columns
- avoid serializer-triggered N+1 queries
- use `select_related()` for foreign keys and one-to-one relationships
- use `prefetch_related()` for many-to-many and reverse relationships
- avoid calling `.count()` repeatedly
- avoid per-row database queries inside loops
- avoid returning oversized nested payloads
- use annotations only when they improve the query plan
- keep expensive calculations out of request loops when they can be precomputed or cached

Do not optimize by changing API behavior without documenting the change.

---

## 14. Transaction and Concurrency Rules

Use `transaction.atomic()` for operations that must succeed or fail together.

Use `select_for_update()` when concurrent updates could create inconsistent state, such as:

- machine status transitions
- maintenance completion
- transfer approval
- inventory-like counters
- idempotency-sensitive workflows

Validate the current state again inside the transaction.

Do not rely only on application-level checks when a database constraint can enforce the invariant.

---

## 15. Exception and Response Rules

Services should raise domain exceptions or Django validation exceptions.

Views should translate exceptions into consistent API responses.

Do not return a DRF `Response` from a service.

Use consistent error structures already established by the project.

Do not expose internal stack traces, database errors, secrets, or implementation details to API clients.

---

## 16. Testing Structure

All tests must be placed in the `tests/` package.

Required baseline:

```text
tests/
├── __init__.py
├── test_views.py
├── test_services.py
├── test_models.py
└── test_serializers.py
```

For larger apps, split tests by feature while keeping them under `tests/`:

```text
tests/
├── __init__.py
├── test_pm_views.py
├── test_pm_services.py
├── test_transfer_views.py
├── test_transfer_services.py
├── test_models.py
└── test_serializers.py
```

Do not create new root-level files such as:

- `tests_pm.py`
- `tests_machine_transfer.py`
- `tests_performance_hotfix.py`
- `test_workflow_api_performance.py`

Move or replace root-level test files when the related code is touched.

Tests should cover:

- successful behavior
- validation failures
- permission failures
- state-transition rules
- transaction rollback
- idempotency where relevant
- query count or performance regressions for critical endpoints
- serializer request and response contracts

Use factories or shared fixtures instead of repeating large setup blocks.

---

## 17. Documentation Rules

Keep app-level technical documentation in `docs/`.

### `docs/BACKEND_TECHNICAL.md`

Document:

- architecture
- models
- workflows
- service responsibilities
- background tasks
- state transitions
- important constraints
- performance considerations
- deployment or migration notes

### `docs/FRONTEND_INTEGRATION.md`

Document:

- endpoints
- authentication requirements
- request payloads
- response payloads
- status values
- validation errors
- frontend workflow notes
- backward-incompatible API changes

Update documentation when endpoint behavior or payloads change.

---

## 18. Naming Rules

Use descriptive names.

Classes:

```python
PreventiveMaintenanceListView
MachineTransferRequestSerializer
MachineStatusHistory
CanTransferMachine
```

Functions:

```python
get_machine_maintenance_summary
change_machine_status
create_machine_transfer
validate_transfer_destination
```

Avoid vague names:

```python
handle_data
do_action
process_item
common_helper
manage
execute
```

Use singular model names and plural route names where appropriate.

---

## 19. Code Quality Rules

All generated or modified code must:

- follow PEP 8
- use meaningful names
- include type hints for service and utility functions where practical
- avoid dead code
- avoid commented-out code
- avoid duplicated logic
- avoid unnecessary abstractions
- preserve compatibility unless a breaking change is requested
- include concise docstrings for non-obvious public functions and classes
- keep comments focused on why, not what
- pass the existing formatter, linter, and test configuration
- use project settings rather than hard-coded secrets or environment values

Do not add placeholder code such as:

```python
pass
TODO
NotImplementedError
```

unless the user explicitly asks for a scaffold.

---

## 20. Security Rules

Always:

- enforce permissions on every protected endpoint
- validate object ownership or company/branch scope
- avoid trusting client-supplied organization identifiers
- prevent insecure direct object references
- sanitize file names and validate uploads
- keep secrets in environment variables
- avoid logging tokens, passwords, QR secrets, or sensitive payloads
- use serializer validation for external input
- use parameterized ORM operations
- verify that list endpoints cannot leak data across companies or branches

---

## 21. Cursor Implementation Behavior

When asked to implement or modify a feature:

1. Inspect the current app structure.
2. Identify the correct standard destination file.
3. Reuse existing services and utilities when appropriate.
4. Do not create a feature-specific `api/` module.
5. Keep views and serializers thin.
6. Add or update service-layer logic.
7. Add or update tests under `tests/`.
8. Update `openapi.py` for API documentation.
9. Update app documentation when the contract changes.
10. Report the files changed and any migration or compatibility concerns.

When a request conflicts with this rule, follow this rule unless the user explicitly instructs otherwise for that specific task.

---

## 22. Final Structural Checklist

Before completing a Django task, verify:

- [ ] No new feature-specific file was added under `api/`.
- [ ] Views are in `views.py`.
- [ ] Serializers are in `serializers.py`.
- [ ] OpenAPI schemas are in `openapi.py`.
- [ ] Filters are in `filters.py`.
- [ ] Complex business logic is in `services/`.
- [ ] Reusable helpers are in `utils/`.
- [ ] Tests are under `tests/`.
- [ ] Shared files use feature section headers.
- [ ] Imports and URLs were updated.
- [ ] API behavior remains compatible unless intentionally changed.
- [ ] Relevant tests were added or updated.
- [ ] No circular imports were introduced.
- [ ] No `init.py` file was created; package files are named `__init__.py`.
- [ ] Documentation was updated when necessary.
