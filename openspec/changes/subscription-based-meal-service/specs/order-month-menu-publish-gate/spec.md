## REMOVED Requirements

### Requirement: Order create requires published menu for selected meal month

**Reason:** Subscribe must succeed even when a future month in the rolling horizon is unpublished. Forcing a published menu at purchase recreated monthly checkout.
**Migration:** Do not require a published `MonthlyMenuSchedule` to create a `CustomerSubscription`. Generate slots only for months that have a published schedule (`subscription-delivery-continuity`).
