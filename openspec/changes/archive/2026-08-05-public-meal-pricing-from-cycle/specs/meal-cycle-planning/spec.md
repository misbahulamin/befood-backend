## ADDED Requirements

### Requirement: Finalize publishes package price onto the meal

On successful finalize, the system MUST set the linked `MealCategory.total_price` to the plan’s `snapshot_total_cost` in the same transaction as finalize, so the meal becomes purchase-priced from cycle costing.

#### Scenario: Finalize updates meal total_price

- **WHEN** a verified admin finalizes a plan whose `snapshot_total_cost` is `4431.93`
- **THEN** the linked meal’s `total_price` becomes `4431.93` and public pricing status becomes `priced`

### Requirement: Reopen keeps last published meal price

When a finalized plan is reopened, the system MUST return the plan to draft for editing and MUST NOT clear the meal’s already published `total_price` until a subsequent finalize overwrites it.

#### Scenario: Reopen does not blank storefront price

- **WHEN** a meal was priced by finalize and the admin reopens that plan
- **THEN** the plan is `draft` and the meal `total_price` remains the previously published value

## MODIFIED Requirements

### Requirement: Finalize locks a plan and returns meal details

The system SHALL allow a verified admin to finalize a draft plan. On finalize the system MUST validate that the sum of `servings_count` for ingredients with `product_role=main` equals the cycle’s `total_meals`, MUST persist snapshot totals, MUST set status to `finalized`, MUST publish `snapshot_total_cost` onto the linked meal’s `total_price`, and MUST return the full meal details summary including the published meal price.

#### Scenario: Successful finalize for April

- **WHEN** a draft April plan’s main servings sum to `60` and the admin finalizes
- **THEN** the plan becomes `finalized` and the response includes product cost, other cost, profit, total cost, per-meal rate, and the meal’s updated `total_price`

#### Scenario: Finalize blocked when main servings mismatch

- **WHEN** main servings sum to a value other than `total_meals`
- **THEN** the system rejects finalize with a validation error identifying the expected and actual totals and MUST NOT change the meal’s `total_price`

#### Scenario: Finalized plan rejects line edits

- **WHEN** a plan is `finalized` and an admin attempts to change servings
- **THEN** the system rejects the change until the plan is reopened

### Requirement: Admin can reopen a finalized plan

The system SHALL allow a verified admin to reopen a finalized plan, returning it to `draft` so lines and margins can be edited again, while preserving the meal’s last published `total_price`.

#### Scenario: Reopen enables edits

- **WHEN** a verified admin reopens a finalized plan
- **THEN** the plan status is `draft` and servings updates are accepted

## REMOVED Requirements

### Requirement: Public meal APIs remain unchanged

**Reason:** Customers need finalized meal details on the public meal resource to decide purchases.  
**Migration:** Implement public offering fields on meal detail per `public-meal-offering`; keep supplier unit prices and draft plans admin-only.
