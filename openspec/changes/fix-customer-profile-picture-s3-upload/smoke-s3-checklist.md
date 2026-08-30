# Manual smoke checklist (USE_S3_MEDIA=true)

Run when AWS credentials/bucket are available (local or EC2):

1. Set in `.env`: `USE_S3_MEDIA=true`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, and keys or IAM role.
2. Restart the Django process.
3. Authenticate as a customer; `POST /api/v1/user_management/customer/profile/image/` with a JPG as field `image`.
4. Confirm `200` + HTTPS `profile_image_url`.
5. Open the URL in a browser; confirm the image loads.
6. In S3 console, confirm object under `profiles/users/<slug>/profile_picture.jpg`.
7. Upload a second image; confirm the previous object is removed or no longer referenced.
8. `PATCH` profile with `{ "profile_image_url": null }`; confirm object cleared and GET returns null.

Automated coverage (filesystem media): `user_management/tests/test_customer_profile_picture.py`.
