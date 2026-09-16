## Context

Customer signup today lives entirely in `user_management` and requires seven fields before email verification:

| Field | Storage | Required today |
|-------|---------|----------------|
| `email` | `User.email` | Yes |
| `password` | `User` password hash | Yes |
| `first_name` / `last_name` | `User` | Yes |
| `phone` | `CustomerProfile.phone` (unique, 10 digits) | Yes |
| `occupation` | `CustomerProfile.Occupation` choices | Yes |
| `is_bachelor` | `CustomerProfile` boolean (marital proxy; no `marital_status` column) | Yes |

Flow today:

1. `POST /user_management/customer/register/` → inactive `User` + `CustomerProfile` + `CUSTOMER` group + activation email
2. `GET /user_management/verify-email/<uidb64>/<token>/` (24h `EmailVerificationTokenGenerator`) → `is_email_verified`, `is_active=True`
3. `POST /user_management/login/` (DRF Token) — blocked only until email verified
4. Progressive/extended data via `PATCH /user_management/customer/profile/` — but `phone`, `occupation`, `is_bachelor`, and names are **not** writable there today

Constraints:

- Reuse existing email verification, auth (Token + password), error style (DRF field errors), and service-layer patterns.
- Customer-only; admin / deliveryman / staff flows untouched.
- Non-destructive migrations; preserve all existing customer rows.
- No new architectural patterns (no repository layer, no JWT switch, no new verification system).
- Frontend owns modal timing; backend only persists submitted steps and exposes completion metadata.

## Goals / Non-Goals

**Goals:**

- Reduce signup friction to **email + password** (existing credential model preserved; “email-only identity” without inventing passwordless auth).
- Keep verification semantics: successful verify = **account registration complete** and login-eligible.
- Enable **immediate, partial** persistence of onboarding fields after login via existing profile PATCH.
- Expose **derived** onboarding completion (`missing_fields`, `completed`) separately from extended `profile_completed` / `profile_completion_percentage`.
- Ship a controlled backward-compatible registration contract so older clients do not hard-fail during rollout.

**Non-Goals:**

- Rewriting email verification, login, or Token auth.
- Changing admin / deliveryman / staff registration or permissions.
- Adding a new `marital_status` enum or renaming `is_bachelor`.
- Frontend modal scheduling / UX sequencing.
- Merging onboarding completion into the existing extended food/delivery completion scorer.
- OTP, magic-link-as-login, or JWT migration.
- Complex concurrency locking beyond existing last-write-wins PATCH behavior.

## Decisions

### 1. Registration contract: email + password required; legacy fields optional during compatibility window

**Choice:** `CustomerRegistrationSerializer` requires only `email` and `password`. Legacy fields (`first_name`, `last_name`, `phone`, `occupation`, `is_bachelor`) remain **optional** for a documented compatibility window; if present and valid, they are persisted at signup.

**Why:** Ideal product goal is email-first signup, but the project already uses password + DRF Token. Dropping password would be a larger auth rewrite (out of scope). Making legacy fields optional (not rejected) is the minimal-risk client rollout versus hard-breaking mobile/web forms still sending seven fields.

**Alternatives considered:**

| Alternative | Rejected because |
|-------------|------------------|
| Email only, no password | Requires passwordless / OTP / magic-link login rewrite |
| Immediately reject legacy fields | Breaks existing clients without a migration period |
| API versioning (`/v2/register`) | Heavier than optional fields for this additive behavior change |
| Feature flag only | Still need nullable DB columns and optional serializer fields |

### 2. Reuse existing verification and login gates unchanged

**Choice:** Continue `send_activation_email` / `EmailVerificationTokenGenerator` / verify + resend endpoints. Login remains gated solely by credentials + `is_email_verified` / `is_active` / `customer_profile` presence — **not** by onboarding completeness.

**Why:** Specs require no duplicate verification system; incomplete profile must not block login.

### 3. Nullable onboarding columns on `CustomerProfile`

**Choice:** Migrate `phone`, `occupation`, and `is_bachelor` to `null=True, blank=True`. Keep `unique=True` on `phone` (multiple SQL `NULL`s allowed; mirror `RiderProfile.phone` pattern). Do not backfill or clear existing values.

**Why:** DB currently forbids creating a profile without these fields. Nullable columns are required for email+password registration. Derivation of “missing” uses `None` / empty string checks — no new redundant boolean columns.

**Alternatives considered:** Placeholder sentinel phones (`0000000000`) — pollutes uniqueness and admin search; rejected.

### 4. Extend existing `PATCH /user_management/customer/profile/` instead of a new endpoint

**Choice:** Expand `CustomerExtendedProfileUpdateSerializer` (or a clearly named sibling used by the same view) to allow writes to:

- `first_name`, `last_name` (on related `User`)
- `phone`, `occupation`, `is_bachelor` (on `CustomerProfile`)
- Keep existing extended writable fields (`gender`, `birth_date`, etc.)

**Why:** Specs forbid unnecessary duplicate endpoints; view already uses `partial=True` and immediate save.

**Implementation notes:**

- Persist inside serializer `update()` / thin service helper with `transaction.atomic()` when touching both `User` and `CustomerProfile`.
- Reuse `validate_bangladesh_phone` / existing 10-digit uniqueness rules for phone when provided.
- Reuse `CustomerProfile.Gender` and `Occupation` choices; `is_bachelor` remains boolean.
- Privileged / server-owned fields stay read-only: `is_email_verified`, `email_verified_at`, `profile_completed`, `profile_completion_percentage`, groups, `is_active`, etc.
- Explicit `null` clearing: only for fields that are nullable and already supported by DRF partial semantics; do not invent new clear-all behavior.

### 5. Onboarding completion is derived, separate from extended profile completion

**Choice:** Add a small service (e.g. `profile_onboarding.py`) that computes:

```text
ONBOARDING_FIELDS = first_name, last_name, phone, occupation, is_bachelor, gender

missing_fields = [f for f in ONBOARDING_FIELDS if absent]
completed = len(missing_fields) == 0
# optional informational percentage = populated / total
```

Absence rules:

- Names: blank/whitespace-only → missing
- `phone`, `occupation`, `gender`: `None` or blank → missing
- `is_bachelor`: `None` → missing (`True`/`False` both count as present)

Expose under a distinct key such as `onboarding_completion` (or `profile_completion` nested under onboarding naming that does **not** collide with existing `profile_completed` / `profile_completion_percentage`) on:

- `GET /user_management/me/`
- `GET` / `PATCH` response of `/user_management/customer/profile/`

**Why:** Specs require derived state and clear separation from extended food/delivery completion metrics already stored on the model.

### 6. Login /me payload stays additive

**Choice:** Keep existing response shapes; **add** onboarding metadata and ensure nullable profile fields serialize as `null`. Optionally include onboarding metadata in `get_login_response` for fewer round-trips — additive only.

**Why:** Additive fields are backward compatible for clients that ignore unknown keys.

### 7. Idempotency and concurrency

**Choice:** Rely on existing PATCH last-write-wins. Same payload twice → same stored state. No new locking or Idempotency-Key for profile steps.

**Why:** Matches current profile update architecture; over-engineering concurrency is a non-goal.

### 8. Analytics / logging

**Choice:** If an event bus already exists at implement time, emit coarse events (`customer_registration_completed` after verify, `customer_profile_onboarding_completed` when derived complete). Otherwise skip new infra. Never log raw email/phone/name in application logs beyond existing patterns.

### 9. Documentation and tests

**Choice:** Update `docs/customer-auth-api.md`, `docs/customer-profile-api.md`, and add `user_management/docs/frontend/` onboarding contract. Extend `test_customer_auth.py` and `test_customer_profile.py` for the scenario list in the proposal; add a smoke assertion that deliveryman/admin register/login tests still pass.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Existing clients still require sending all seven fields | Optional legacy fields during compatibility window; document sunset; clients can keep sending extras safely |
| Unique `phone` with many `NULL`s behaves differently across DBs | Use standard nullable unique (already used on `RiderProfile`); add tests for two users both without phone |
| Admin filters/search assume non-null phone | Admin serializers already tolerate optional fields elsewhere; verify admin list/detail with null phone |
| Clients confuse onboarding vs extended `profile_completed` | Distinct response key + docs; do not overwrite existing completion fields from onboarding derivation |
| Mass assignment of privileged fields | Strict serializer allow-list; tests asserting `is_email_verified` / `profile_completed` ignore |
| Registration creates users with empty names | Acceptable; progressive PATCH fills names; admin UI may show blank until filled |
| `is_bachelor` null changes “false vs unset” semantics | Document clearly; missing_fields treats only `None` as missing |
| Temporary dual meaning of “complete registration” in product language | Specs: verification = account registered; onboarding = profile complete |

## Migration Plan

1. **Schema:** Non-destructive migration — `phone`, `occupation`, `is_bachelor` → nullable; no data deletion or forced defaults that overwrite existing rows.
2. **Code deploy:** Ship serializer/service/view changes in the same release as the migration (or migration first if zero-downtime requires it).
3. **Client rollout:** Publish updated frontend docs; mobile/web drop required profile fields at signup and use PATCH + `missing_fields` post-login.
4. **Compatibility window:** Keep accepting optional legacy registration fields until clients are confirmed migrated; then a follow-up change may remove them from the register serializer (separate OpenSpec if desired).
5. **Rollback:** Revert app code; leave nullable columns in place (safe). Do **not** re-require non-null without a data backfill plan.

## Open Questions

- Exact JSON key name for onboarding metadata (`onboarding_completion` vs nested under `customer_profile`) — prefer `onboarding_completion` at the same level as `customer_profile` on `/me/` to avoid colliding with extended completion fields; confirm during apply if frontend already drafted a name.
- Whether login response must include `onboarding_completion` in v1 of this change or only `/me/` + profile GET (default: include on `/me/` and profile; login optional additive).
- Length of the legacy-field compatibility window (product/release decision; default: keep optional until a dedicated cleanup change).
