## ADDED Requirements

### Requirement: Wallet-threshold candidates include identity-verified phone-only customers

Customer candidate queries used for meal-stop, resume, and low-balance reminder automation MUST include customers who are identity-verified via phone (or email or social). The system MUST NOT filter these candidates with `is_email_verified=True` alone when that would exclude phone-verified customers with blank email.

#### Scenario: Phone-only active subscriber appears in threshold candidates

- **WHEN** threshold candidate selection runs and a phone-verified customer has blank email, active user flag, and an ACTIVE subscription meeting other candidate rules
- **THEN** that customer is included in the candidate set

#### Scenario: Completely unverified customer excluded

- **WHEN** a customer has neither verified phone nor verified email nor social identity
- **THEN** that customer is excluded from threshold candidates

### Requirement: Meal-close low-balance list includes phone-only subscribers

Meal Close low-balance delivery listing MUST NOT require `subscription__customer__is_email_verified=True` (or equivalent email-only filter). Identity-verified phone-only subscribers with qualifying low-balance deliveries MUST appear.

#### Scenario: Phone-only low-balance delivery visible in meal close

- **WHEN** meal-close builds the low-balance delivery list and a phone-only identity-verified subscriber has a qualifying delivery
- **THEN** that delivery is included and may show blank email for display
