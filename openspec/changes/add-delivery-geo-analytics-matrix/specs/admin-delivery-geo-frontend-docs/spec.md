# Spec Delta

## Purpose

Frontend contract documentation so the Admin Panel can render delivery geo analytics matrices, rankings, filters, and drill-downs without reverse-engineering APIs.

## ADDED Requirements

### Requirement: Frontend docs for geo analytics screens
The system SHALL publish frontend integration docs under `delivery_zones/docs/frontend/` describing the geo analytics admin screens: auth headers, base paths, required `from`/`to`, optional `meal_period` and hierarchy filters, response field meanings, ranking sections, empty states, and error codes (`400`/`401`/`403`/`404`).

#### Scenario: Docs list matrix and rankings contracts
- **WHEN** a frontend engineer opens the geo analytics frontend doc
- **THEN** the doc includes endpoint paths, query parameters, and example JSON for the hierarchical matrix and ranking sections

### Requirement: Docs describe drill-down into customers and churn
Frontend docs MUST explain how matrix row actions deep-link into admin customer list and churn customer list using geo and lifecycle query parameters, including Bridge vs Contract notes for sub-location assignment if still relevant.

#### Scenario: Drill-down mapping documented
- **WHEN** a frontend engineer implements “View customers in this sub-location”
- **THEN** the doc specifies which customer-list query parameters to pass

### Requirement: Docs distinguish day ops summary from period geo analytics
Frontend docs MUST clearly separate live day/meal `ops/summary` (operations board) from period geo analytics (business analysis), including when to call which API.

#### Scenario: Ops vs analytics guidance
- **WHEN** a frontend engineer builds both Delivery Zones ops and Geo Analytics pages
- **THEN** the doc states ops/summary is for a single service_date + meal_period and geo analytics is for from/to ranges
