# Frontend: Customer address public UUID

## Summary

**Breaking:** Address APIs use UUID `public_id` instead of integer `id`.

| Before | After |
|--------|--------|
| `/user_management/customer/addresses/3/` | `/user_management/customer/addresses/<uuid>/` |
| `POST .../addresses/3/set-default/` | `POST .../addresses/<uuid>/set-default/` |
| Response `id` | `public_id` |

Nested addresses on profile use the same `public_id` field.

## Checklist

- [ ] Key address state by `public_id`
- [ ] Update set-default URL
- [ ] Expect 404 on integer address paths

## Related

- [`docs/public-uuid-convention.md`](../../../docs/public-uuid-convention.md)
