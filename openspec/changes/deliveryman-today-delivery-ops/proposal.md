## Why

BeFood Express Delivery Men already run zone-scoped today’s deliveries and Mark Delivered on mobile, but the rider app cannot cleanly support **To Deliver / Delivered tabs**, **today’s metrics**, or **package-wise breakdown**. Completed stops already persist on `OrderDelivery` (they only leave the default board because of status filtering), yet rider-facing APIs do not expose delivered history, summary KPIs, or structured package fields. Customer admin activity also omits which Delivery Man completed the meal. We need additive mobile capabilities on the existing architecture — not a parallel delivery system.

## What Changes

- **Extend deliveryman today-board** to support status-scoped lists: pending (`scheduled`) vs delivered for the active meal window / business today, reusing `OrderDelivery.status` (no new status vocabulary)
- **Add deliveryman today summary API** with total / delivered / pending counts plus dynamic package breakdown from subscription/order meal snapshots
- **Additive board row fields**: structured `package_name` / `package_public_id` (and keep existing `meal_name` / `menu_items_label` / `status` for backward compatibility); optional delivered timestamps and rider attribution on delivered rows
- **Enrich customer activity `meal_delivered` events** with Delivery Man identity (`delivered_by_rider` / display name) in summary + refs — reuse composed activity feed, no new activity table
- **Confirm / document** existing mark-delivered attribution (`marked_by`, `delivered_by_rider`, `delivered_at` / `marked_at`), zone authorization, idempotent duplicate mark, and Asia/Dhaka business-date handling — fix only if gaps appear during implementation
- **Frontend contract docs** for BeFood Express mobile (pending/delivered tabs, summary, package fields) — mobile app code changes out of scope for this backend change
- Not **BREAKING**: default `GET .../today-board/` remains scheduled-only; existing response keys stay; new query modes / endpoints / fields are additive

## Capabilities

### New Capabilities

- `deliveryman-today-ops`: Verified Delivery Man APIs for today’s pending vs delivered boards, today summary metrics, and package breakdown scoped to the rider’s assigned zone and active meal window
- `deliveryman-today-ops-frontend-docs`: Mobile contract for To Deliver / Delivered tabs, summary KPIs, and package display fields (backend docs only; Flutter implementation later)

### Modified Capabilities

- `order-delivery-tracking`: Clarify rider mark path keeps durable delivered rows + rider attribution; no requirement to soft-delete deliveries on mark
- `admin-customer-history`: Activity feed `meal_delivered` items MUST include Delivery Man identity when `delivered_by_rider` (or equivalent) is known

## Impact

- **Backend (`befood-backend`)**:
  - Primary: `delivery_zones/services/board.py`, `delivery_zones/api/deliveryman_views.py`, serializers/URLs under `user_management/api/urls.py`
  - Summary service (extend board module or small sibling service) using existing `zone_scoped_deliveries` + meal-off timezone
  - Customer activity: `user_management/services/admin_customer.py` (`build_activity_events`)
  - Possibly light documentation updates to zone-based / deliveryman board docs
  - Tests in `delivery_zones/tests/` and admin customer activity tests
- **Reused (do not replace)**: `RiderProfile`, `DeliveryZone.assigned_delivery_man`, `OrderDelivery` statuses, `mark_delivery` / `record_phase_a_delivered`, `IsVerifiedDeliveryman`, `delivery_in_rider_zone`, `get_current_delivery_period` (Asia/Dhaka)
- **Already covered elsewhere**: Admin Delivery Man 360 metrics (`delivery-man-360-analytics`) — this change adds **rider-self** today summary, not admin 360
- **Out of scope**: Flutter app UI (`befood_deliveryman_mobile`), new parallel delivery tables, weakening zone auth, live GPS streaming, payroll
- **Mobile consumers**: Current app uses `meal_name`, `menu_items_label`, and translates `status=scheduled` → “নির্ধারিত”; backend adds structured package fields so a later mobile update can de-emphasize status chips without breaking today’s app
