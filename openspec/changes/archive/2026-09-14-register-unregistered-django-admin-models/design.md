## Context

`user_management` defines `DeviceToken`, `StaffProfile`, and `UserActivityLog` but only the first two lack any Django Admin registration. `DeviceToken` was extended for FCM push delivery; operators need visibility into active tokens per user for support. `UserActivityLog` stores audit metadata but is not browsable. Other models in the same app (`CustomerProfile`, `RiderProfile`, `CustomerAuthOTP`) already have well-established `ModelAdmin` patterns in `user_management/admin.py`.

## Goals / Non-Goals

**Goals:**

- Register three missing models in `user_management/admin.py`
- Provide useful list/search/filter for support workflows
- Keep `UserActivityLog` immutable via admin permission overrides
- Match existing admin conventions (autocomplete, readonly timestamps)

**Non-Goals:**

- Admin bulk actions (deactivate tokens, export)
- Registering models in other apps (`business/`, etc.)
- API or model schema changes
- Custom admin templates or inlines

## Decisions

### 1. Single-file registration in `user_management/admin.py`

**Decision:** Add all three ModelAdmin classes to the existing `user_management/admin.py`.

**Rationale:** All three models live in `user_management.models`; the file already registers sibling models. No new admin module needed.

**Alternatives considered:** Separate `user_management/admin/device_token.py` — rejected as over-engineering for three small classes.

### 2. DeviceToken — editable with guarded readonly fields

**Decision:** Allow add/change for `DeviceToken` (support may need manual deactivation via `is_active`). Mark `created_at`, `updated_at`, and `last_used_at` as readonly.

**Rationale:** Token lifecycle is primarily API-driven, but admin edit of `is_active` helps support without raw SQL.

**Alternatives considered:** Fully read-only like `PushCampaign` — rejected; manual deactivation is a common support need.

### 3. UserActivityLog — fully read-only

**Decision:** Override `has_add_permission`, `has_change_permission`, and `has_delete_permission` to return `False`.

**Rationale:** Activity logs are append-only audit records; mutation via admin would undermine trust.

### 4. StaffProfile — standard CRUD admin

**Decision:** Standard ModelAdmin with `autocomplete_fields = ('user',)`.

**Rationale:** Small lookup table; no special security posture beyond existing Django Admin staff access.

## Risks / Trade-offs

- **[Risk] Token values visible in admin** → Acceptable for internal staff-only admin; same exposure as `PushLog.device_token` in notifications admin.
- **[Risk] Manual token edits could conflict with API upsert** → Mitigation: document that API is source of truth; admin edits limited to `is_active` support cases.
- **[Risk] Large DeviceToken table slow changelist** → Mitigation: default ordering `-created_at`, list filters on `is_active` and `platform`; pagination handled by Django Admin defaults.

## Migration Plan

1. Add ModelAdmin classes to `user_management/admin.py`
2. Deploy — no migration required
3. Rollback: remove the three `@admin.register` blocks

## Open Questions

- None — scope is limited to three models in one file.
