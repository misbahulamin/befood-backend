# Deferred domains — public UUID readiness

Stub apps not yet mounted in `core/urls.py`:

| App | Models (examples) | When mounting |
|-----|-------------------|---------------|
| `wallet` | Wallet, WalletTransaction, TopUpRequest, WalletPayment | Add `PublicIdMixin` / `public_id` before first client serializer |
| `payments` | PaymentMethod, PaymentIntent, PaymentTransaction, Refund | Same |
| `delivery` | RiderLocation, DeliveryAssignment, DeliveryTracking, DeliveryFeeRule | Same |
| `promotions` | Coupon, CouponUsage, Promotion | Same |
| `notifications` | Notification, NotificationTemplate, … | Same |

## Checklist before first public endpoint

- [ ] Model has `public_id` (unique, indexed, default uuid4)
- [ ] Safe migration / backfill if table already has rows
- [ ] `lookup_field = "public_id"`
- [ ] Customer serializer omits integer `id`
- [ ] Frontend + backend docs mention UUID identity
- [ ] Cursor rule `.cursor/rules/public-uuid-resources.mdc` followed in review
