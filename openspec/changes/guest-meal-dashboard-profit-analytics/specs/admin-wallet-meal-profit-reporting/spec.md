# Spec Delta

## ADDED Requirements

### Requirement: Admin Profit aggregates include realized Guest Meal contributions
Admin Profit overview, range totals, package/customer/meal-period breakdowns, daily chart, and history that represent total realized meal business MUST include realized Guest Meal revenue, attributable cost, and profit. Regular and Guest Meal contributions MUST remain distinguishable via additive response fields or history source markers. Delivery-stop counts MUST remain distinct from food-box or ledger-row quantity semantics.

#### Scenario: Range totals reconcile regular plus guest
- **WHEN** the filtered range contains regular realized revenue `33.55` / food cost `30.50` / profit `3.05` and guest realized revenue `140.00` / food cost `61.00` / profit `79.00`
- **THEN** total range revenue is `173.55`, total food cost is `91.50`, and total profit is `82.05`, and clients can also read regular vs guest breakdowns

#### Scenario: Daily chart uses the same ledger source
- **WHEN** a Guest Meal is realized on service date D inside the chart window
- **THEN** that day’s chart profit and revenue include the guest realization amounts from the same reporting source as the summary cards

#### Scenario: Filters apply to guest realizations
- **WHEN** Admin Profit filters by service-date range, meal period, package, or customer
- **THEN** Guest Meal realizations are included or excluded using the same filter dimensions as regular meal realizations

### Requirement: Existing regular meal profit consumers remain compatible
Existing Admin Profit and Admin Wallet profit response fields used by current clients MUST keep working. Guest-aware totals MUST be introduced additively or by extending the same ledger-backed aggregates without removing legacy keys. Regular subscription meal recognition rules MUST remain unchanged for deliveries without guest boxes.

#### Scenario: Regular-only delivery unchanged
- **WHEN** a charged regular delivery has no linked Guest Meal orders
- **THEN** its profit recognition and contribution to aggregates match the pre-change regular-meal behavior
