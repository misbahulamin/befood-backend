## ADDED Requirements

### Requirement: Admin schedule detail exposes dual meal pricing

When a verified admin retrieves full monthly menu schedule detail (including published menus used by the admin published-menus page), each assignment slot that includes final-price exposure MUST include additive dual-pricing fields computed on the backend:

- shared cost inputs: selected/ingredient cost and operational cost
- `subscriber_pricing` with `profit_percent`, `profit_amount`, and `final_price`
- `instant_pricing` with `profit_percent`, `profit_amount`, and `final_price` from the latest active Instant meal settings
- flat aliases `subscriber_price` and `instant_price` equal to the respective final prices when priced

Existing `final_meal_price` (subscriber) MUST remain present and unchanged in meaning. Customer-visible and public schedule payloads MUST NOT receive Instant margin internals unless an existing public Instant endpoint already defines those fields.

#### Scenario: Published slot returns subscriber and Instant ladders

- **WHEN** a verified admin retrieves a published schedule whose lunch slot has ingredient cost `48.15`, operational cost `4.13`, subscriber profit percent `14.45`, and Instant settings profit percent `70.00`
- **THEN** the lunch assignment includes ingredient/operational costs, subscriber final price `59.24` with profit `6.96`, Instant final price `85.99` with profit `33.71` (money quantized with half-up), and `final_meal_price` still equals the subscriber final price

#### Scenario: Instant settings change refreshes Instant ladder only

- **WHEN** Instant meal settings `profit_percent` changes from `70` to `80` and the admin refreshes the same published schedule detail without republishing
- **THEN** Instant final price and Instant profit update for the new percent, and subscriber `final_meal_price` / subscriber profit snapshots remain unchanged

#### Scenario: Existing final_meal_price clients keep working

- **WHEN** a client reads only `final_meal_price` from admin schedule assignments after dual-pricing fields are added
- **THEN** the field remains present with the subscriber selling price and no required schema break

### Requirement: Dual pricing uses Instant settings and publish cost basis

For published slots, dual pricing MUST prefer publish-time ingredient and operational cost snapshots when present. Instant `profit_percent` MUST come from `InstantMealSettings` (latest active singleton settings), not from the cycle plan and not from a hardcoded constant. Subscriber pricing MUST continue to reflect plan profit used at publish (snapshots), not Instant settings.

#### Scenario: Instant percent not taken from cycle plan

- **WHEN** the cycle plan profit percent is `14.45` and Instant settings profit percent is `70.00`
- **THEN** `instant_pricing.profit_percent` is `70.00` and `subscriber_pricing.profit_percent` reflects the subscriber/plan value used for that slot

#### Scenario: Missing snapshots do not fabricate zero Instant price

- **WHEN** an admin views a draft or unpriceable slot without resolvable cost snapshots or live costs
- **THEN** Instant and subscriber pricing fields are null or omitted per API contract and MUST NOT return fabricated `0.00` selling prices
