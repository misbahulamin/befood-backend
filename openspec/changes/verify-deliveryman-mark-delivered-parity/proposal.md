## Why

Ops expects deliveryman **mark delivered** to apply the same meal-completion business rules as the auto-deliver cron (`run_auto_deliver.sh` → `auto_deliver_meals` → `run_auto_delivery`), with the only intentional difference being *who* confirms: cron at period end vs the rider after handing over food. Today both paths already share `mark_delivery_and_notify` → wallet charge / Onahar / referral / FCM, but auto-delivery also **pre-filters** candidates (live parent + exclude `meal_service_blocked_low_balance`) while the deliveryman mark API only enforces zone membership. That gap can let a rider mark a low-balance meal-stop customer who was never cooked and whom cron would skip. We need a verify-and-align pass so rider mark-delivered stays in lockstep with cron eligibility (admin override remains separate).

## What Changes

- Audit and document the shared vs divergent checks between `orders.services.auto_meal_delivery` and `DeliverymanMarkDeliveryView`.
- Align deliveryman mark-delivered **eligibility** with auto-delivery for non-admin actors: reject when the customer is meal-stop blocked (`meal_service_blocked_low_balance=true`), in addition to existing zone + `mark_delivery` wallet/status rules.
- Keep **admin** mark-delivered as the intentional override (already allowed under `wallet-meal-stop`).
- Add focused tests proving: (1) rider + cron share charge/idempotency/notify path; (2) rider cannot mark a low-balance-blocked scheduled slot that cron would exclude; (3) admin still can.
- Update deliveryman / auto-delivery docs to state the parity contract and the admin exception.
- **Non-breaking** for success payload shape; blocked marks return a clear error (likely `422` with a stable `error_code`).

## Capabilities

### New Capabilities

- `deliveryman-mark-delivered-parity`: Deliveryman mark-delivered MUST reuse the same domain completion path as auto-delivery and MUST apply the same non-admin eligibility gates (live parent / not cancelled, not low-balance meal-stop blocked), differing only in actor confirmation and zone authorization.

### Modified Capabilities

- `wallet-meal-stop`: Clarify that the “manual mark-delivery remains available while blocked” exception applies to **admin/operator** mark-delivery, not deliveryman field mark-delivery (which MUST follow auto-delivery exclusion).

## Impact

- **Code:** `delivery_zones/api/deliveryman_views.py` (and/or a small shared eligibility helper reused with `auto_meal_delivery.eligible_delivery_queryset`); possibly `orders/services/auto_meal_delivery.py` / `order_delivery.py` if eligibility is centralized.
- **API:** `POST /user_management/deliveryman/deliveries/{public_id}/mark/` — new rejection when customer is meal-stop blocked; zone `403` and wallet `422` behaviors unchanged otherwise.
- **Related change:** board list filtering is covered by `filter-low-balance-from-deliveryman-board`; this change covers the **mark** path so a known `public_id` cannot bypass the same rule.
- **Docs:** `delivery_zones/docs/frontend/zone-based-delivery.md`, `delivery_zones/docs/backend/zone-based-delivery.md`, `orders/docs/backend/auto-meal-delivery.md`.
- **Tests:** `delivery_zones/tests/test_zone_based_delivery.py`, optionally `orders/tests/test_auto_meal_delivery.py` for shared helper coverage.
- **Out of scope:** changing cron schedule/wrappers, kitchen cooking APIs, wallet charge amount/idempotency keys, or removing admin override.
