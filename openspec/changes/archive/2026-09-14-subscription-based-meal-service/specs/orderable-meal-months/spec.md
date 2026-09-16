## REMOVED Requirements

### Requirement: Customer can list orderable meal months for a meal package

**Reason:** The Order Now 13-month picker is no longer the purchase path.
**Migration:** Customer lists active subscribable plans (`subscription-plan-catalog`) and subscribes once. Unpublished months no longer block subscribe; they only skip slot generation for that month.
