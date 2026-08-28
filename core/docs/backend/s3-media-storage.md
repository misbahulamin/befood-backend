# AWS S3 Media Storage (EC2)

User-uploaded media (ImageField / FileField) can be stored on S3 when
`USE_S3_MEDIA=true`. Static files stay on WhiteNoise / local staticfiles — not S3.

## Environment variables (host `.env` or systemd)

| Variable | Required when S3 on | Notes |
|----------|---------------------|--------|
| `AWS_STORAGE_BUCKET_NAME` | Yes | Bucket name |
| `AWS_S3_REGION_NAME` | Yes | e.g. `ap-south-1` |
| `AWS_ACCESS_KEY_ID` | No* | Optional if EC2 IAM instance role can access the bucket |
| `AWS_SECRET_ACCESS_KEY` | No* | Optional with IAM role |
| `AWS_S3_CUSTOM_DOMAIN` | No | CDN / custom host (no secrets) |
| `USE_S3_MEDIA` | — | `true` to enable S3 media; `false` (default) = local `MEDIA_ROOT` |

\* Prefer an IAM instance role with `s3:PutObject`, `s3:GetObject`, `s3:ListBucket`,
`s3:HeadObject` on the media bucket. Access keys in env are a fallback only.

Never commit real AWS keys to git.

## Post-deploy (EC2)

From the app directory (adjust venv / service name to your host):

```bash
# 1. Install / refresh deps (django-storages + boto3 already in requirements.txt)
pip install -r requirements.txt

# 2. Ensure AWS_* vars are set on the host; keep USE_S3_MEDIA=false until ready

# 3. Optional: copy existing local media/ to S3 (preserve paths, skip existing)
python manage.py migrate_media_to_s3 --dry-run
python manage.py migrate_media_to_s3

# 4. Enable S3 media
#    Set USE_S3_MEDIA=true in host .env or systemd Environment=

# 5. Restart the app process
sudo systemctl restart gunicorn   # or your unit name

# 6. Smoke-test: upload an image in admin/API; confirm object in S3 and HTTPS URL
```

No database migration is required for this feature.

## Rollback

```bash
# Set USE_S3_MEDIA=false on the host, then restart
sudo systemctl restart gunicorn
```

Local/EC2 disk media under `MEDIA_ROOT` remains if not deleted. S3 objects are left intact.

## Bucket checklist (AWS console)

- Region matches `AWS_S3_REGION_NAME`
- Public read via bucket policy (or CloudFront) for media objects if clients load images directly
- Block Public Access / ACLs: app uses `default_acl=None` (no object ACLs)
