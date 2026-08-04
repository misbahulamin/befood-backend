# Delivery Man authentication (backend)

## Quick summary

Delivery partners register as **Delivery Men** (`RiderProfile` + `DELIVERY_MAN` group), verify email, wait for admin approval, then log in with a Token.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/user_management/deliveryman/register/` | Public | Create inactive account + send verify email |
| GET | `/user_management/deliveryman/verify-email/<uidb64>/<token>/` | Public | Mark email verified (does **not** unlock login) |
| POST | `/user_management/deliveryman/resend-verification/` | Public | Resend verify email |
| POST | `/user_management/deliveryman/login/` | Public | Login only if email verified **and** admin approved |
| GET | `/user_management/deliveryman/me/` | Token + verified DM | Current session profile |
| GET | `/user_management/admin/deliverymen/` | Verified admin | List (default = pending queue) |
| GET | `/user_management/admin/deliverymen/<public_id>/` | Verified admin | Detail |
| POST | `/user_management/admin/deliverymen/<public_id>/approve/` | Verified admin | Approve + confirmation email |
| POST | `/user_management/admin/deliverymen/<public_id>/reject/` | Verified admin | Reject + optional reason email |
| PATCH | `/user_management/admin/deliverymen/<public_id>/verified-status/` | Verified admin | Set/revoke `is_verified` |

## Permissions matrix

| Actor | Register / verify / login | `me` | Admin deliverymen APIs |
|-------|---------------------------|------|------------------------|
| Anonymous | Yes (register/verify/login) | No | No |
| Delivery Man (pending) | Login blocked | No | No |
| Delivery Man (approved) | Login OK | Yes | No |
| Verified admin / superuser | N/A | No | Yes |

## Key model: `RiderProfile`

- ORM related name: `user.rider_profile` (ops app already says “rider”).
- Public identity: `public_id` (UUID).
- Identity: `phone` (unique, 10 digits when set), `address`.
- Email gate: `is_email_verified`, `email_verified_at`.
- Admin gate: `approval_status` (`pending` \| `approved` \| `rejected`), `is_verified`, `verified_at`, `rejected_at`, `rejection_reason`, `admin_notes`.
- Ops fields kept: `vehicle_type`, `license_number`, `is_available`, lat/lng.

Group on register: `DELIVERY_MAN`.

## Lifecycle

```text
register → email verify → admin pending queue → approve → login
                              ↘ reject → login blocked
```

1. **Register** — `User.is_active=False`, `approval_status=pending`, `is_verified=False`.
2. **Email verify** — sets `is_email_verified=True` only; **does not** set `is_active`.
3. **Admin approve** — `approval_status=approved`, `is_verified=True`, `is_active=True`, approval email.
4. **Admin reject** — `approval_status=rejected`, `is_verified=False`, `is_active=False`, rejection email.
5. **Login** requires correct password + `rider_profile` + email verified + `is_verified` + `is_active`.

Pending/rejected login `detail`:

```text
Your information has not been approved by admin yet. Please wait until your account verification is completed.
```

## Business rules

- Duplicate email (any `User`) or duplicate Delivery Man phone → 400 validation.
- Approve before email verification → 422.
- Pending queue default: `is_email_verified=True` AND `approval_status=pending`. Unverified registrations are hidden from that default.
- Use `pending_only=false` or explicit `approval_status=` to browse other rows.
- Revoke via `verified-status` sets `is_verified=False`, deactivates user, blocks login; re-approve restores access.

## Services

- `user_management.services.deliveryman_auth` — register, login response, approve/reject/verified-status.
- `user_management.services.deliveryman_email` — activation / approval / rejection emails (separate from customer verify URLs).

## How to verify

```bash
python manage.py test user_management.tests.test_deliveryman_auth
```

Also: Django admin → **Rider profiles** (approve/reject actions).

## Related OpenSpec

`openspec/changes/deliveryman-auth-system/`
