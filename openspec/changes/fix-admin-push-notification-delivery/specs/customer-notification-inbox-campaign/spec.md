# Spec Delta

## Purpose

Defines how admin push campaigns create customer in-app inbox notifications separately from Firebase push delivery and admin sent counters.

## ADDED Requirements

### Requirement: Campaign dispatch creates inbox rows independently of FCM

When an admin push campaign is dispatched, the system MUST create one unread customer inbox notification per distinct targeted user who is not skipped for push preference, even when the user has no active device token or FCM send later fails. Inbox persistence failures MUST NOT abort FCM dispatch.

#### Scenario: Inbox created for user without active device

- **WHEN** a campaign targets a customer with no active device token
- **THEN** the customer still receives one inbox notification for that campaign and the recipient row remains failed for FCM with a no-device error

#### Scenario: Inbox created even when FCM fails for the token

- **WHEN** a campaign targets a customer with an active token and FCM returns a failure for that token
- **THEN** the customer still has one inbox notification for that campaign while the recipient FCM status is `failed`

#### Scenario: Multi-device customer gets a single inbox row

- **WHEN** a campaign targets a customer with multiple active device tokens
- **THEN** the system creates exactly one inbox notification for that user for the campaign

### Requirement: Inbox visibility must not be treated as FCM sent success

Customer inbox APIs MAY show a campaign message while admin campaign `total_sent` remains zero when no FCM delivery succeeded. Admin `total_sent` MUST count only successful FCM deliveries.

#### Scenario: Web inbox shows message while admin sent is zero

- **WHEN** dispatch creates inbox rows but every FCM attempt fails or no pending tokens exist
- **THEN** the customer can still load the message from the notification inbox API and the campaign `total_sent` stays `0`
