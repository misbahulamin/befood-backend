# Mobile: wallet recharge approved push

When admin approves a pending wallet recharge, the backend may send an FCM notification to the customer’s registered device tokens.

## Display

| Field | Value |
|-------|--------|
| Title | `Wallet recharge approved` |
| Body | `Your wallet recharge of ৳{amount} has been approved successfully. Your updated balance is ৳{balance}.` |

Amounts use the **৳** symbol (same as low-balance / meal-stop pushes).

## Data payload (all string values)

| Key | Value | Use |
|-----|--------|-----|
| `type` | `wallet_recharge_approved` | Route / branch |
| `screen` | `wallet` | Open wallet screen |
| `entity_type` | `wallet_transaction` | Entity kind |
| `entity_id` | UUID `public_id` | Optional detail / history deep-link |
| `amount` | e.g. `1000.00` | Recharge amount |
| `balance` | e.g. `1500.00` | Updated wallet balance |
| `invoice_number` | e.g. `INV-WR-20260903-…` | Optional display |
| `approved_at` | ISO-8601 local datetime | Optional display |

## Suggested handling (`befood_mobile`)

1. On notification open / data message: if `type == wallet_recharge_approved` (or `screen == wallet`), navigate to the wallet / balance screen.
2. Optionally refresh wallet balance from `GET /wallet/`.
3. Do not require invoice UI in-app for this release; invoice is delivered by email.

## Related backend doc

`wallet/docs/backend/wallet-recharge-approval-notifications.md`
