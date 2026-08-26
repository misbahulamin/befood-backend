from storages.backends.s3 import S3Storage


class S3MediaStorage(S3Storage):
    """
    S3 backend for user-uploaded media.

    Object keys match existing ImageField/FileField upload_to paths.
    Public access is expected via bucket policy (ACLs may be disabled).
    """

    default_acl = None
    file_overwrite = False
    querystring_auth = False
