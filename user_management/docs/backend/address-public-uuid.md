# Backend: Customer address public UUID

- Model: `CustomerAddress(PublicIdMixin, …)`
- Migration: `user_management.0006_customeraddress_public_id`
- `CustomerAddressViewSet.lookup_field = "public_id"`
- Set-default URL: `customer/addresses/<uuid:public_id>/set-default/`
