## ADDED Requirements

### Requirement: Docs state validate is not attribution
Frontend and admin documentation SHALL state that `POST /referrals/validate/` only checks code usability and records analytics events, and MUST NOT describe a successful validate response as proof that a referral relationship was created. Docs MUST state that attribution requires a subsequent brand-new customer create path that sends `referral_code` with `X-Client-Type: mobile`.

#### Scenario: Mobile engineer reads validate contract
- **WHEN** a mobile engineer follows referral customer docs after this change
- **THEN** the docs tell them to persist the code from deep link or validate response until first successful new-customer create, and to send it again on register / phone verify / oauth

### Requirement: Docs cover web invite to mobile handoff
Customer-web and mobile docs SHALL describe that public invite links may land on web, that web registration must not send `referral_code` (rejected), and that credited referral signup requires opening/installing the mobile app with the code carried into the mobile create APIs.

#### Scenario: Web invite does not imply web attribution
- **WHEN** a web engineer implements an invite landing page
- **THEN** documentation instructs them not to expect `ReferralRelationship` from web register, and to deep-link into the mobile app with the code

### Requirement: Admin docs explain conversion funnel metrics
Admin-panel documentation SHALL map Conversion Funnel columns to API fields and MUST explain that Validations / Valid OK are validate attempts (not unique users), Registrations are `ReferralRelationship` counts, and Subscribers are referred customers with an active meal subscription. Docs MUST mention that large Valid OK with low Registrations commonly means clients validated without completing mobile attributed create, and SHOULD point operators to attribution skip reasons when observability fields exist.

#### Scenario: Ops interprets Valid OK drop-off
- **WHEN** an admin sees Valid OK much larger than Registrations
- **THEN** documentation explains attempt inflation and missing create-path handoff before assuming commission or subscription bugs
