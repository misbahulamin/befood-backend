## ADDED Requirements

### Requirement: Backend docs state the co-consumption commission rule
The project SHALL document the referral commission eligibility rule in backend docs as: a referrer earns commission from a referred customer’s meal only when both are active subscribers and both consume the exact same meal (`service_date` + `meal_period`) on the same day. Docs MUST state that referrer consumption is `OrderDelivery.status=delivered` only (not charged), while referred remains delivered+charged; MUST describe in-place `skipped` → `success` upgrade for the same commission row; MUST list skip reasons including `REFERRER_MEAL_NOT_CONSUMED`, `REFERRER_INACTIVE`, and `REFERRED_INACTIVE`; and MUST document reconcile `--dry-run` before production write runs.

#### Scenario: Backend doc includes rule and reasons
- **WHEN** implementers read the referral backend documentation after this change
- **THEN** the co-consumption rule, referrer delivered-vs-charged distinction, in-place skip upgrade, dry-run reconcile, and machine-readable skip reasons are described

### Requirement: Mobile integration docs cover eligibility UX
The project SHALL update mobile frontend documentation to explain that commission is not earned on every referred meal delivery—both users must have active subscriptions and both must consume the same meal the same day. Docs MUST map API `status_reason` values (including `REFERRER_MEAL_NOT_CONSUMED`) to recommended user-facing copy guidance and list which screens should show the rule (earnings / commission history / referral share).

#### Scenario: Mobile doc maps skip reasons
- **WHEN** a mobile engineer integrates commission history
- **THEN** documentation provides reason-to-copy guidance for meal-mismatch and inactive skips

### Requirement: Customer web docs cover eligibility UX
The project SHALL provide customer-web frontend documentation covering the same co-consumption rule, commission history status display, and empty/skip states so the web app does not imply “any referred meal pays commission.”

#### Scenario: Customer web doc describes earnings expectation
- **WHEN** a web engineer implements the referral earnings page
- **THEN** documentation states the dual-consumption rule and how to present non-success commission rows

### Requirement: Admin panel docs cover support and audit UX
The project SHALL provide admin-panel frontend documentation describing how operators interpret skipped commissions (`REFERRER_MEAL_NOT_CONSUMED` and inactive reasons), that delivery completion for only the referred user is insufficient, that a later matching referrer delivery upgrades the same commission row to success, that historical SUCCESS rows may predate the stricter rule, how to use existing reverse/adjust flows when finance requires correction, and that ops should run reconcile `--dry-run` before write reconcile in production.

#### Scenario: Admin doc supports meal-mismatch investigation
- **WHEN** an admin support engineer investigates a missing commission
- **THEN** documentation tells them to verify both parties’ same-day same-meal delivery status (referrer needs delivered, not necessarily charged) and explains the skip reason

### Requirement: Client API contract remains additive for eligibility clarity
Unless a later change explicitly adds fields, client docs MUST treat existing commission list fields (`status`, `status_reason`, `meal_service_date`, `meal_period`) as sufficient to explain eligibility outcomes. New required request/response fields MUST NOT be introduced solely for this eligibility fix without documenting them as additive.

#### Scenario: No breaking commission list schema required
- **WHEN** clients already consume commission list `status_reason`
- **THEN** documentation instructs them to handle the new reason value without requiring a breaking schema change
