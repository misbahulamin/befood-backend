## ADDED Requirements

### Requirement: Ingredient customer visibility is independent of costing

The system SHALL allow verified admins to set `is_customer_visible` on each ingredient (default `true`). Cost calculations and plan line inclusion MUST treat customer-hidden ingredients the same as visible ones when they appear on a plan. Inactive ingredients (`is_active=false`) remain governed by existing active-ingredient rules for new plan edits and are orthogonal to `is_customer_visible`.

#### Scenario: Create costing-only ingredient

- **WHEN** a verified admin creates “Masala Cost” with valid pricing and `is_customer_visible=false`
- **THEN** the system stores the ingredient as inactive-for-customer-display but available for plan costing when active

#### Scenario: Hidden ingredient still costs on finalize

- **WHEN** a draft plan includes a customer-hidden active ingredient with servings and a valid plan-line `product_role`
- **THEN** finalize and summary include that line’s product cost in package totals

#### Scenario: Toggle visibility without changing role or price

- **WHEN** a verified admin patches only `is_customer_visible` on an ingredient
- **THEN** the system updates that flag and does not alter pricing fields

### Requirement: Customer and public menus omit non-visible ingredients

The system SHALL omit ingredients with `is_customer_visible=false` from customer-facing and public menu ingredient lists, including today-menu, authenticated package monthly menu, and public meal offering `menu_items`. Omitted ingredients MUST still remain on the underlying schedule/plan for admin and costing. Visible menu entries MUST expose `product_role` from the relevant package’s plan line when a plan context exists.

#### Scenario: Masala Cost hidden from package menu

- **WHEN** a published schedule slot contains Beef (`is_customer_visible=true`) and Masala Cost (`is_customer_visible=false`)
- **THEN** the customer package-menu response for that slot lists Beef and does not list Masala Cost

#### Scenario: Today menu hides non-visible items

- **WHEN** today’s revealed period includes a non-customer-visible ingredient on the published schedule
- **THEN** the today-menu ingredient list excludes that ingredient

#### Scenario: Public meal menu_items filtered

- **WHEN** an unauthenticated client retrieves a public meal offering whose finalized plan includes a non-customer-visible line
- **THEN** `menu_items` excludes that ingredient while still reflecting visible lines

#### Scenario: Admin schedule still shows hidden ingredients

- **WHEN** a verified admin retrieves the full monthly schedule detail
- **THEN** the response includes customer-hidden ingredients assigned to slots
