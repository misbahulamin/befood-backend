# Spec Delta

## ADDED Requirements

### Requirement: Admin campaign counters reflect FCM outcomes after dispatch

After dispatch finishes, list and detail responses MUST show a terminal `status` of `completed` or `failed`. `total_sent` MUST equal the count of recipients with FCM status `sent`. Presence of customer inbox rows MUST NOT by itself increment `total_sent`.

#### Scenario: Poll shows completed with zero sent after total FCM failure

- **WHEN** an admin polls a campaign whose FCM attempts all failed after dispatch
- **THEN** the detail response has terminal `status=completed` or `failed`, `total_sent=0`, and failed recipients include `error_message`

#### Scenario: Stuck processing campaigns are recoverable by operators

- **WHEN** a campaign remains `processing` longer than the stuck threshold because a worker died mid-dispatch
- **THEN** operators can re-run stuck dispatch via the management command and the campaign reaches a terminal status
