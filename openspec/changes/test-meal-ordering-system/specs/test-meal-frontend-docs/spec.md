# Spec Delta

## Purpose

Backend ships Flutter and Admin Panel integration documentation for Test Meal eligibility, checkout, history, admin management, payments, and analytics so clients can implement without reverse-engineering the API.

## ADDED Requirements

### Requirement: Flutter Test Meal integration guide

The system SHALL publish frontend documentation covering authenticated eligibility/CTA gating, package list, date and meal period selection, live quote, delivery windows, saved address select/add, order confirmation, quota exhaustion messaging, and order history. Docs MUST include full routes, auth headers, request/response examples, and error codes for the customer flow.

#### Scenario: Guide covers eligibility through history

- **WHEN** a Flutter engineer opens the Test Meal frontend guide
- **THEN** the document lists the ordered API sequence from eligibility to confirmation and history with example JSON

### Requirement: Admin Panel Test Meal integration guide

The system SHALL publish frontend documentation for Admin Panel covering order list/detail fields, filters, manual payment recording, conversion indicators, revenue splits, funnel/analytics charts, and required permissions. Docs MUST match the admin API contract shipped in this change.

#### Scenario: Guide covers unpaid payment recording

- **WHEN** an Admin Panel engineer opens the Test Meal admin frontend guide
- **THEN** the document describes how to list unpaid orders and call record-payment with example payloads

### Requirement: Backend technical notes

The system SHALL publish backend technical documentation summarizing models, settings, quota/payment rules, status transitions, ops integration, and verification steps (tests/Swagger). Documentation MUST be written in English per project rules.

#### Scenario: Backend doc lists settings defaults

- **WHEN** a backend engineer opens the Test Meal backend guide
- **THEN** default lifetime quota and box charge settings are documented
