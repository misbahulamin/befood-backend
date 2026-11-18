# Spec Delta

## ADDED Requirements

### Requirement: Empty digest skips email

When a digest run finds no unassigned active subscribers, the system MUST NOT send email to admin recipients. An empty candidate list MUST NOT fail the run; the job MUST complete successfully with no message delivered for that empty run.

#### Scenario: No unassigned subscribers

- **WHEN** a non-dry-run digest execution finds zero qualifying customers
- **THEN** no digest email is sent to admin recipients and the job completes successfully

#### Scenario: Non-empty digest still sends

- **WHEN** a non-dry-run digest execution finds one or more unassigned active subscribers and at least one verified admin recipient exists
- **THEN** those recipients receive the structured unassigned-delivery digest email

## REMOVED Requirements

### Requirement: Empty digest still confirms the run

**Reason**: Empty “none pending” emails are inbox noise; operators only want mail when there is assignment work. Job health is confirmed via cron logs (`candidate_count`, exit status), not inbox heartbeats.

**Migration**: Rely on `logs/cron-unassigned-delivery-digest.log` (and command/result logging) for empty-run confirmation. No client or API migration. After deploy, empty evening/night slots simply produce no email.
