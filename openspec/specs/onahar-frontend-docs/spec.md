## Purpose

Frontend implementation documentation for Onahar public page, customer dashboard, homepage teaser, and admin management UI, including API contracts.

## Requirements

### Requirement: Frontend documentation for Onahar surfaces

The system SHALL provide frontend implementation documentation (under `onahar/docs/frontend/`) that enables a frontend developer to implement the Public Onahar Page, logged-in Customer Onahar Dashboard, Homepage teaser section, and Admin Onahar management UI without reading backend source code. Documentation MUST be written in English and MUST include feature overview, user flows, page/section structure, authentication requirements, error handling, pagination/filtering, and image/media handling notes.

#### Scenario: Docs cover public page structure

- **WHEN** a frontend developer opens the Onahar frontend documentation
- **THEN** it MUST describe Public Onahar Page sections for overall statistics, contributor leaderboard, transparency ledger, and distribution history/detail

#### Scenario: Docs cover customer and admin flows

- **WHEN** a frontend developer implements customer and admin Onahar UIs from the docs
- **THEN** the docs MUST describe current-month progress, lifetime/history, privacy settings, admin target configuration, and distribution create/publish/media flows

### Requirement: Frontend documentation includes API contracts

The Onahar frontend documentation MUST list all relevant API endpoints with method, path, auth requirements, request parameters/body fields, success response examples, and important error responses for at least: public statistics, leaderboard, contribution/distribution ledger, distribution list/detail, customer progress, contribution history, privacy preference, global fund (admin), target configuration (admin), and distribution management (admin). Documentation MUST explain monthly progress calculation behavior (no carry-forward, multi-contribution, target snapshot) in product language.

#### Scenario: Docs include response examples for stats and progress

- **WHEN** a frontend developer integrates the homepage teaser and customer progress bar
- **THEN** the documentation MUST include example JSON responses for public stats and customer progress endpoints sufficient to bind UI without inspecting serializers

#### Scenario: Docs explain monthly calculation rules

- **WHEN** a frontend developer needs to explain why last month's incomplete points disappeared
- **THEN** the documentation MUST state that monthly cycles do not carry forward remaining points and that remainders expire at month close
