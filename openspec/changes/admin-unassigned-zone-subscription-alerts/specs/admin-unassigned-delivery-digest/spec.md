# Spec Delta

## Purpose

Notify verified admins with a structured digest of active meal subscribers who still lack an operational delivery sub-location, so zone assignment is completed before delivery ops miss them.

## ADDED Requirements

### Requirement: Digest lists active subscribers without sub-location

The system SHALL identify customers who have an active meal subscription and whose customer profile has no delivery sub-location assigned. Customers with only a mirrored delivery location and no sub-location MUST still be treated as unassigned. Cancelled subscriptions MUST NOT appear.

#### Scenario: Active subscriber missing sub-location is included

- **WHEN** a customer has an active subscription and `delivery_sub_location` is null
- **THEN** that customer appears in the unassigned delivery digest candidate list

#### Scenario: Assigned subscriber is excluded

- **WHEN** a customer has an active subscription and a delivery sub-location is assigned
- **THEN** that customer MUST NOT appear in the digest candidate list

#### Scenario: Cancelled subscription is excluded

- **WHEN** a customer previously subscribed but the subscription status is cancelled
- **THEN** that customer MUST NOT appear in the digest candidate list solely due to that cancelled subscription

### Requirement: Admin digest email includes required contact columns

On each non-dry-run digest execution, the system SHALL email verified admin recipients (same recipient resolution pattern as wallet funding admin notifications) a structured report. Each listed customer row MUST include display name, phone number, subscription time, and email address when available.

#### Scenario: Row includes name phone subscription time and email

- **WHEN** a digest run finds one or more unassigned active subscribers and at least one has an email on file
- **THEN** each admin recipient receives an email whose table includes name, phone, subscription time, and email for that customer

#### Scenario: Missing optional contact fields use placeholders

- **WHEN** a listed customer has no phone and/or no email on file
- **THEN** the row still appears with empty or “N/A” placeholders for missing fields while populated fields remain accurate

### Requirement: Empty digest still confirms the run

When a digest run finds no unassigned active subscribers, the system SHALL still send a short “no unassigned subscribers” summary to verified admin recipients so operators can confirm the job executed. An empty candidate list MUST NOT fail the run.

#### Scenario: No unassigned subscribers

- **WHEN** a non-dry-run digest execution finds zero qualifying customers
- **THEN** each resolved admin recipient receives a short empty-run summary and the job completes successfully

### Requirement: Digest email omits secrets

The digest email MUST include only ops-safe customer contact and subscription timing fields. It MUST NOT expose authentication tokens, passwords, wallet ledger internals, or unrelated PII beyond name, phone, email, and subscription time.

#### Scenario: Payload stays ops-safe

- **WHEN** the digest email is composed for a qualifying customer
- **THEN** the message body contains the required contact/subscription columns and does not include secrets or wallet ledger internals
