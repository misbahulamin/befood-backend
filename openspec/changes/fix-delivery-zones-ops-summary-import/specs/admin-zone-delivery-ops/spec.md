# Spec Delta

## Purpose

Gives verified admins a zone/location delivery ops summary and Delivery Man workload for a chosen service date and meal period so kitchen and dispatch planning stay accurate.

## ADDED Requirements

### Requirement: Ops summary HTTP endpoint succeeds for valid filters
The system SHALL accept verified-admin `GET` requests for delivery-zone ops summary with required `service_date` and `meal_period` query parameters and SHALL return JSON ops summary data with HTTP 200 when those parameters are valid. The system MUST NOT fail the request with an unhandled server error caused by unresolved view dependencies.

#### Scenario: Valid lunch summary returns JSON
- **WHEN** a verified admin requests ops summary with a valid ISO `service_date` and `meal_period=lunch`
- **THEN** the response status is 200 and the body includes ops summary fields such as `service_date`, `meal_period`, `zones`, and `delivery_man_workload`

#### Scenario: Invalid query still uses structured API errors
- **WHEN** a verified admin requests ops summary with unsupported query parameters or a missing `meal_period`
- **THEN** the system returns a structured client error (4xx) with an `error_code`, not an unhandled 500 NameError
