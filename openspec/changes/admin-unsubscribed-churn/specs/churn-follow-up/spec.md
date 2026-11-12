# Spec Delta

## Purpose

Lets verified admins track win-back outreach for churned customers with status, notes, and actor attribution.

## ADDED Requirements

### Requirement: Follow-up model and statuses
The system SHALL persist `ChurnFollowUp` rows with customer FK, status in `{not_contacted, contacted, interested, won_back, lost}`, optional note, admin actor, and `created_at` (and updated timestamp when status changes).

#### Scenario: Create follow-up
- **WHEN** a verified admin creates a follow-up for a customer with status `contacted` and a note
- **THEN** the row MUST be stored with that admin as actor

### Requirement: Follow-up CRUD APIs
Verified admins MUST be able to create, list (scoped by customer and/or filters), retrieve, and update follow-ups via `/api/v1/web/churn/follow-ups/` (collection and detail). Non-admins MUST receive `401`/`403`. Unknown ids MUST return `404`.

#### Scenario: Update status to won_back
- **WHEN** admin patches a follow-up status to `won_back`
- **THEN** the stored status MUST become `won_back` and list payloads MUST reflect it

#### Scenario: Non-admin forbidden
- **WHEN** a customer token lists follow-ups
- **THEN** the response MUST be `403`
