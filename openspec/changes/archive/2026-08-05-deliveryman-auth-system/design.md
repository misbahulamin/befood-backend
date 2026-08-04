## Context

Customer and admin auth already live in `user_management`: Django `User` + role profiles (`CustomerProfile`, `AdminProfile`), Token auth, email activation for customers, and `AdminProfile.is_verified` gating for admin login. A sparse `RiderProfile` and a `delivery` ops app exist, but there is no Delivery Man registration, email verification, admin approval, or role-scoped login.

Stakeholders: Delivery Man applicants (mobile/web), verified admins (web management panel), and future delivery-ops features that will authorize via the same profile/group.

Constraints:
- Stay consistent with customer/admin auth (services layer, thin DRF views, Token auth, message/`detail` style errors).
- Prefer extending `RiderProfile` rather than inventing a parallel profile table.
- Mount under `user_management/` like existing auth routes.
- New list/detail resources that leave the system MUST use `public_id` (UUID) per project convention.
- Business logic in `user_management/services/`; do not put approval workflows in views.

## Goals / Non-Goals

**Goals:**
- Delivery Man can register, verify email, and (only after admin approval) log in.
- After email verification, the account appears in an admin pending queue with full review fields (name, email, phone, address, and other registration data).
- Admin can list (filter pending/approved/rejected), view detail, approve, reject, and manage verified status.
- Approval sets `is_verified = True`, activates login, and sends a confirmation email.
- Login clearly rejects pending (email-verified but not approved) accounts with a dedicated message (English and/or Bangla as documented).
- Design remains extendable for future delivery assignment APIs via group + `rider_profile`.

**Non-Goals:**
- Delivery assignment, tracking, live location, or fee-rule product work.
- KYC document upload / ID image storage pipelines (beyond optional simple text fields if needed for registration).
- Renaming `RiderProfile` / `delivery` models to “DeliveryMan*” in the database.
- Changing customer or admin auth contracts.
- Building a full standalone Admin SPA; this change delivers APIs + Django admin so the existing admin web client can implement the section.

## Decisions

### 1. Reuse `RiderProfile` as the Delivery Man profile
- **Choice:** Extend `RiderProfile` with registration/approval fields instead of creating `DeliveryManProfile`. API and docs use “Delivery Man” / `deliveryman` path segments; ORM keeps `rider_profile` related name for compatibility with `delivery` ops.
- **Rationale:** Avoids dual profiles for the same person; ops models already speak “rider.”
- **Alternatives considered:**
  - New `DeliveryManProfile` — clearer naming, but duplicates role identity and breaks future FK assumptions on `RiderProfile`.
  - Put flags only on `User` — mixes roles and loses role-specific address/phone uniqueness.

### 2. Dual gate: email verification then admin approval
- **Choice:** Lifecycle:
  1. Register → `User.is_active=False`, `is_email_verified=False`, `approval_status=pending`, `is_verified=False`
  2. Email verify → `is_email_verified=True`, `email_verified_at` set; **do not** enable login yet (`is_active` stays `False` until approval)
  3. Admin approve → `approval_status=approved`, `is_verified=True`, `verified_at` set, `is_active=True`, send approval email
  4. Admin reject → `approval_status=rejected`, `is_verified=False`, `is_active=False`, store rejection reason; login remains blocked
- **Rationale:** Matches product flow (“request appears after email verify”; login only after admin approve). Mirrors `AdminProfile.is_verified` + `is_active` sync pattern.
- **Alternatives considered:**
  - Activate user on email verify and only check `is_verified` at login — also works, but leaving `is_active=False` until approval prevents Token misuse if something else authenticates the user.
  - Auto-approve after email — rejected by product requirement.

### 3. Group name `DELIVERY_MAN`
- **Choice:** `Group.objects.get_or_create(name='DELIVERY_MAN')` on registration (same pattern as `CUSTOMER` / `ADMIN`).
- **Rationale:** Matches product language and keeps room for a future distinct `STAFF` role; `RiderProfile` remains the data model.
- **Alternatives considered:** `RIDER` only — closer to model name but less clear in admin UIs that say “Delivery Man.”

### 4. URL surface under `user_management`
- **Choice:**
  - Public auth:  
    - `POST /user_management/deliveryman/register/`  
    - `POST /user_management/deliveryman/login/`  
    - `GET /user_management/deliveryman/verify-email/<uidb64>/<token>/`  
    - `POST /user_management/deliveryman/resend-verification/`  
    - `GET /user_management/deliveryman/me/` (authenticated delivery man)
  - Admin management (verified admin only):  
    - `GET /user_management/admin/deliverymen/` (filterable list)  
    - `GET /user_management/admin/deliverymen/<uuid:public_id>/`  
    - `POST /user_management/admin/deliverymen/<uuid:public_id>/approve/`  
    - `POST /user_management/admin/deliverymen/<uuid:public_id>/reject/`  
    - optional `PATCH` for verified-status/notes adjustments
- **Rationale:** Same mount style as `customer/register/` and `admin/login/`. Requested bare `/deliveryman/registration/` is documented as the conceptual resource; concrete paths stay namespaced for consistency and to avoid colliding with the `delivery/` ops app.
- **Alternatives considered:** Top-level `/deliveryman/` include — possible later alias; not required for v1 if docs state the canonical paths.

### 5. Profile fields to add on `RiderProfile`
- **Choice:** Add at minimum:
  - `PublicIdMixin` (`public_id`)
  - `phone` (unique, 10-digit validation like customer)
  - `address` (text)
  - `is_email_verified`, `email_verified_at`
  - `approval_status` (`pending` | `approved` | `rejected`)
  - `is_verified` (True iff approved; kept for parity with admin language and login checks)
  - `verified_at`, `rejected_at`
  - `rejection_reason` / `admin_notes` (text, blank OK)
  - keep existing vehicle/availability/geo fields for future ops
  - timestamps via `TimeStampedModel` if not already present
- Registration payload: email, password, first_name, last_name, phone, address (+ optional vehicle_type/license_number if cheap to collect now).
- **Rationale:** Covers admin review fields named in the product brief without over-building KYC.
- **Alternatives considered:** Separate approval table — unnecessary for one-to-one profile state.

### 6. Email verification reuse with role-specific endpoints
- **Choice:** Reuse `EmailVerificationTokenGenerator` and send helpers; add Delivery Man templates and a dedicated verify/resend path that updates `RiderProfile` (not `CustomerProfile`). Do **not** overload the customer verify URL to activate riders.
- **Rationale:** Customer verify currently assumes `customer_profile`; sharing the URL would create unsafe branching and wrong activation side effects.
- **Alternatives considered:** Single polymorphic verify endpoint — possible later refactor; higher risk for this change.

### 7. Login response and pending message
- **Choice:** `DeliverymanLoginSerializer` checks, in order:
  1. Invalid credentials → generic invalid credentials (same as customer; no user enumeration)
  2. Missing `rider_profile` / wrong role → not authorized for delivery man login
  3. Email not verified → ask to verify email
  4. Email verified but not approved (`is_verified=False` / status pending or rejected) → dedicated message:  
     `"Your information has not been approved by admin yet. Please wait until your account verification is completed."`  
     (Bangla variant may be returned via `Accept-Language` or a documented `message_bn` field — pick one approach in implementation and document it; default English body required)
  5. Success → Token + user + groups + `rider_profile` summary (`is_verified`, phone, etc.)
- **Rationale:** Product requires a clear pending-approval UX distinct from “verify email.”
- **Alternatives considered:** Soft-login with limited token — rejected; pending users must not receive auth tokens.

### 8. Admin management API + Django admin
- **Choice:** Implement verified-admin DRF endpoints for list/detail/approve/reject (primary for Admin Panel UI) **and** register `RiderProfile` in Django admin as operational fallback (approve/reject actions mirroring `AdminProfileAdmin` sync of `is_active`).
- Pending queue default filter: `is_email_verified=True` AND `approval_status=pending`.
- Approve/reject MUST be service functions (`approve_deliveryman`, `reject_deliveryman`) used by both API and admin.
- **Rationale:** Admin web already uses custom admin login APIs; management section needs HTTP APIs. Django admin covers ops without waiting on UI.
- **Alternatives considered:** Django admin only — insufficient for the stated Admin Panel section.

### 9. Permissions
- **Choice:** Registration/login/verify/resend are public (AllowAny). `me` requires authenticated user with `rider_profile` + `is_verified`. Admin deliverymen endpoints require `is_verified_admin` (same helper as `AdminCurrentUserView`).
- **Rationale:** Matches existing admin access helper; prevents non-admin staff from approving riders.

### 10. Documentation & tests
- **Choice:** Backend + frontend docs under `user_management/docs/`; tests for register, verify, pending login block, approve email, successful login, reject, permission denials, and admin list filters.
- **Rationale:** Project documentation rules for new API contracts.

## Risks / Trade-offs

- **[Risk] Naming confusion (Rider vs Delivery Man)** → Mitigation: document mapping clearly; API paths use `deliveryman`; model stays `RiderProfile`.
- **[Risk] Shared email across customer and delivery man roles** → Mitigation: one `User.email` globally; registration rejects duplicate emails; a person cannot hold two role profiles on the same email without a future multi-role design (out of scope).
- **[Risk] Email verify link opens backend URL (same as customer today)** → Mitigation: keep parity with customer activation; frontend can wrap later without changing token logic.
- **[Risk] Rejected users re-register with same email** → Mitigation: reject duplicate email; allow admin to re-approve or provide a documented “reopen” path (approve again) instead of delete/recreate.
- **[Risk] Token issued before approval if `is_active` mishandled** → Mitigation: never set `is_active=True` until approve; login must also require `is_verified`.

## Migration Plan

1. Add migration extending `RiderProfile` (new fields + `public_id` backfill for any existing rows).
2. Deploy backend with new endpoints (backward compatible; no customer/admin API breaks).
3. Configure email templates in the usual template dirs.
4. Admin UI can integrate against admin deliverymen APIs.
5. Rollback: remove URL routes / revert migration only if no approved production riders depend on new columns; prefer forward-fix if data exists.

## Open Questions

- Whether Bangla pending-login copy is a separate response field, `Accept-Language`, or UI-only (backend always English) — default recommendation: English `detail`/`message` from API; Bangla rendered by client unless product insists on server-side BN.
- Whether optional vehicle/license fields are required at registration or collected later in a profile-completion step — default: optional at registration.
- Whether rejected applicants receive an email — default: yes, short rejection notice with optional reason; can be deferred if email volume is a concern.
