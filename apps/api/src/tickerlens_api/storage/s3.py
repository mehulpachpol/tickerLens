from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse, urlunparse

import boto3
from botocore.config import Config

from tickerlens_api.settings import settings


@dataclass(frozen=True)
class PutObjectResult:
    bucket: str
    key: str


def _client_config() -> Config:
    if settings.s3_force_path_style:
        return Config(s3={"addressing_style": "path"})
    return Config()


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region_name,
        config=_client_config(),
    )


def put_object_fileobj(*, bucket: str, key: str, fileobj, content_type: str | None) -> PutObjectResult:
    client = get_s3_client()
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    client.upload_fileobj(fileobj, bucket, key, ExtraArgs=extra_args or None)
    return PutObjectResult(bucket=bucket, key=key)


def presign_get_object(*, bucket: str, key: str, expires_in_seconds: int = 3600) -> str:
    client = get_s3_client()
    url = client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in_seconds,
    )
    public = settings.s3_public_endpoint_url
    if not public:
        return url

    try:
        u = urlparse(url)
        p = urlparse(public)
        if not p.scheme or not p.netloc:
            return url
        return urlunparse((p.scheme, p.netloc, u.path, u.params, u.query, u.fragment))
    except Exception:
        return url


def download_object_to_path(*, bucket: str, key: str, path: str) -> int:
    client = get_s3_client()
    with open(path, "wb") as f:
        client.download_fileobj(bucket, key, f)
    try:
        return os.path.getsize(path)
    except OSError:
        return 0
