# Spec Delta

## Purpose

BeFood measures which Test Meal customers later subscribe, using real subscription history as source of truth, and supports privacy-conscious funnel event capture without treating clicks as orders.

## ADDED Requirements

### Requirement: Conversion derived from subscription history

The system MUST derive Test Meal conversion from authoritative subscription records, not a manually maintained Boolean alone. Historical conversion (`HAS_SUBSCRIBED_AFTER_TEST`) and current activity (`IS_CURRENTLY_ACTIVE_SUBSCRIBER`) MUST remain distinct and survive subscription cancel or expiry.

#### Scenario: Converted then cancelled still historically converted

- **WHEN** a customer had a delivered Test Meal, later activated a subscription, then cancelled
- **THEN** historical conversion remains true while currently-active is false

#### Scenario: Subscribed before Test Meal not a new conversion

- **WHEN** a customer’s first subscription started before their first Test Meal
- **THEN** they MUST NOT be counted as a new Test Meal conversion under the primary KPI

### Requirement: Primary conversion KPI after delivery

Primary conversion rate MUST be: unique customers who activated their first qualifying subscription after at least one delivered Test Meal, divided by unique customers with at least one delivered Test Meal, times 100. Denominator and date-range attribution MUST be explicit. Customers who subscribed after placing a Test Meal but before delivery MUST be reported separately and MUST NOT inflate the primary delivered-based conversion rate.

#### Scenario: Primary conversion calculation

- **WHEN** 10 unique customers have a delivered Test Meal and 4 of them first subscribe after that delivery
- **THEN** primary conversion rate is `40`

#### Scenario: Pre-delivery subscribe reported separately

- **WHEN** a customer places a Test Meal, subscribes before delivery, then the meal is delivered
- **THEN** they appear in the pre-delivery subscribe metric and are excluded from the primary after-delivery converted set

### Requirement: Funnel event ingestion with deduplication

Where instrumentation is deployed, the system SHALL accept privacy-conscious Test Meal funnel events with safe anonymous-to-authenticated correlation and deduplication. The system MUST NOT invent pre-instrumentation history. Button clicks MUST NOT be treated as completed orders.

#### Scenario: Duplicate funnel event ignored

- **WHEN** the same client submits the same funnel event identity twice
- **THEN** analytics count it once

#### Scenario: Click is not an order

- **WHEN** only CTA click events exist for a customer and no Test Meal order was created
- **THEN** order metrics remain zero for that customer
