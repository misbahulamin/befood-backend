## 1. DeviceToken Admin

- [x] 1.1 Import `DeviceToken` in `user_management/admin.py`
- [x] 1.2 Add `DeviceTokenAdmin` with list_display, list_filter, search_fields, autocomplete_fields, and readonly timestamps

## 2. StaffProfile Admin

- [x] 2.1 Import `StaffProfile` in `user_management/admin.py`
- [x] 2.2 Add `StaffProfileAdmin` with list_display, search_fields, and user autocomplete

## 3. UserActivityLog Admin

- [x] 3.1 Import `UserActivityLog` in `user_management/admin.py`
- [x] 3.2 Add read-only `UserActivityLogAdmin` with list_display, search_fields, ordering, and permission overrides

## 4. Verification

- [x] 4.1 Confirm Django admin loads without import errors (`manage.py check`)
- [x] 4.2 Smoke verify changelist URLs resolve for all three models
