# Admin customer management

## Quick summary

Verified-admin **read-only** Customer 360 directory. List, search, filter, open a **lean overview** (profile + summary + active subscription summary + wallet summary), then lazy-load paginated history tabs under `/api/v1/web/customers/`.

**Performance rule:** The detail overview MUST NOT embed history arrays. All history uses paginated sub-resources.

| Method | Path | Who | Purpose |
|--------|------|-----|---------|
| GET | `/api/v1/web/customers/` | Verified admin | Paginated list + search/filters |
| GET | `/api/v1/web/customers/{public_id}/` | Verified admin | Lean detail / overview |
| GET | `/api/v1/web/customers/{public_id}/active-subscription/` | Verified admin | Current active subscription (or `null`) |
| GET | `/api/v1/web/customers/{public_id}/subscriptions/` | Verified admin | Subscription history |
| GET | `/api/v1/web/customers/{public_id}/wallet-overview/` | Verified admin | Wallet summary incl. pending funding |
| GET | `/api/v1/web/customers/{public_id}/meals/` | Verified admin | Delivery / meal history (subscription + legacy order) |
| GET | `/api/v1/web/customers/{public_id}/meal-offs/` | Verified admin | Skipped slots |
| GET | `/api/v1/web/customers/{public_id}/wallet-transactions/` | Verified admin | Wallet ledger |
| GET | `/api/v1/web/customers/{public_id}/activity/` | Verified admin | Confirmed-event activity feed |
| GET | `/api/v1/web/customers/{public_id}/active-order/` | Verified admin | **Deprecated** legacy active order |
| GET | `/api/v1/web/customers/{public_id}/orders/` | Verified admin | **Deprecated** legacy order history |

Identifiers use `CustomerProfile.public_id` (UUID).

## Permissions

| Actor | Access |
|-------|--------|
| Verified admin | All endpoints |
| Customer (even own profile) | `403` on all admin customer endpoints |
| Anonymous / deliveryman | `401` or `403` |

Customer A token → `GET .../customers/{customer-B-public_id}/` → **`403`** (object-level isolation).

## Mental model

```text
CustomerProfile (+ User)     → identity, addresses, verification
CustomerSubscription         → current service record (primary)
Order (legacy)               → pre-migration monthly orders only
OrderDelivery                → meal slots (linked to subscription OR order)
Wallet + WalletTransaction   → balance, pending funding, ledger
```

Subscription `status` values come from the backend model serializer (currently `active`, `cancelled`; tolerate new values).

## List query parameters

Allowlisted only; unknown keys → `400`.

| Param | Notes |
|-------|-------|
| `q` | Search name, email, phone (national digits, or `+880` / `880` prefixed international) |
| `is_active` | `User.is_active` |
| `is_email_verified` | Email verification |
| `has_active_subscription` | Active `CustomerSubscription` |
| `has_active_order` | **Deprecated** — legacy active `Order` |
| `has_wallet` | Customer has wallet row |
| `has_pending_recharge` | Pending wallet recharge txn exists |
| `subscription_expiring_soon` | Active sub with `cancel_effective_on` within 14 days |
| `inactive_subscription` | Has subscription history but no active subscription |
| `meal_public_id` / `package_id` | Active subscription or legacy active order package |
| `registered_from` / `registered_to` | `User.date_joined` date range |
| `sort` | `date_joined`, `-date_joined` (default), `created_at`, `-created_at`, `email`, `-email` |
| `page` / `page_size` | Default 20, max 100 |

## Phone field (list + detail)

- **Storage:** `CustomerProfile.phone` remains 10 national digits (BD mobile).
- **Admin response:** `phone` is E.164-style Bangladesh: `+880` + 10 digits (e.g. `+8801712345678`), or `null` when unset.
- **Search (`q`):** Matches name/email on the raw term; for phone, optional leading `+880` / `880` is stripped so international paste still hits stored national digits.

## Detail overview (`GET .../{public_id}/`)

Returns **only**:

- Profile + addresses
- `summary` aggregate metrics
- `active_subscription` summary (nullable)
- `wallet_summary` compact totals
- `active_order` (deprecated, legacy fallback)

Does **not** include subscription lists, meal rows, wallet transactions, or activity events.

### `summary` fields

| Field | Meaning |
|-------|---------|
| `total_subscriptions` | All subscription records |
| `total_orders` | Legacy orders |
| `total_meals_delivered` | Delivered slots (subscription + order) |
| `total_meal_offs` | Skipped slots |
| `customer_lifetime_value` | Sum of completed wallet payment debits |
| `total_wallet_spent` | Same as CLV (alias) |
| `total_wallet_recharged` | Completed recharge credits |
| `total_wallet_withdrawn` | Completed withdraw debits |
| `wallet_balance` / `wallet_currency` | Current spendable balance |
| `last_payment_at` | Latest completed payment debit |
| `last_meal_delivered_at` | Latest delivered slot |
| `current_package_expires_at` | `cancel_effective_on` or legacy order end date |
| `last_subscription_at` | Latest subscription created |
| `last_order_at` | Latest legacy order |
| `last_activity_at` | Max of confirmed activity timestamps |
| `has_legacy_orders` | Whether legacy `Order` rows exist |

### `active_subscription` summary

| Field | Meaning |
|-------|---------|
| `subscription_public_id` | UUID |
| `package_name` | Plan snapshot |
| `status` | Model status value |
| `started_on` | Service start date |
| `cancel_effective_on` | Nullable end boundary |
| `remaining_meals` | Scheduled delivery count |
| `delivered_count` / `skipped_count` | Slot aggregates |

### `wallet_summary` / `wallet-overview`

| Field | Meaning |
|-------|---------|
| `available_balance` | Spendable balance |
| `pending_recharge_amount` | Sum of pending recharge txns |
| `pending_withdraw_amount` | Sum of pending withdraw txns |
| `total_recharged` | Completed recharge credits |
| `total_withdrawn` | Completed withdraw debits |
| `total_spent` | Completed payment debits |
| `pending_funding_request_count` | Count of pending txns |

## Activity feed (confirmed events only)

Allowed `event_type` values:

- `subscription_created`, `subscription_cancelled`
- `wallet_transaction_completed` (status=completed only)
- `meal_delivered`, `meal_skipped`
- `order_created`, `order_status_changed` (legacy)

Events are **not** inferred from bare `OrderDelivery.updated_at`.

## Deprecated endpoints

`/active-order/` and `/orders/` return `Deprecation: true` and `Link: <successor>; rel="successor-version"`.

## How to verify

```bash
python manage.py test user_management.tests.test_admin_customer_management --keepdb
```

## OpenSpec

`openspec/changes/admin-customer-360-view/`
