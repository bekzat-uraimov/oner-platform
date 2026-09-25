"""Cloudflare R2. R2 speaks the S3 API, so a download link is an ordinary SigV4
presigned GET — computed locally with no network call, which is why this is
testable without a bucket.
"""

import re
from collections.abc import Iterator
from datetime import datetime
from functools import lru_cache
from pathlib import PurePosixPath
from urllib.parse import quote
from uuid import uuid4

import boto3
from botocore.config import Config

from app.core.config import get_settings

MATERIAL_PREFIX = "materials/"

# What new_storage_key produces: the prefix, 32 hex characters, and an optional
# short extension. Used to check a key came from us before we store it.
_MATERIAL_KEY = re.compile(rf"{MATERIAL_PREFIX}[0-9a-f]{{32}}(\.[a-z0-9]{{1,8}})?$")

_SAFE_SUFFIX = re.compile(r"\.[A-Za-z0-9]{1,8}$")


class StorageNotConfigured(Exception):
    """R2 credentials are missing, so any URL we signed would be rejected."""


def new_storage_key(filename: str) -> str:
    """Pick the object key ourselves, keeping only the extension.

    The uploader never chooses where its bytes land: a caller-supplied key could
    overwrite an existing material, or use `../` to escape the prefix entirely.
    """
    match = _SAFE_SUFFIX.search(PurePosixPath(filename).name)
    suffix = match.group(0).lower() if match else ""
    return f"{MATERIAL_PREFIX}{uuid4().hex}{suffix}"


def is_material_key(key: str) -> bool:
    """Whether a key looks like one new_storage_key issued."""
    return _MATERIAL_KEY.fullmatch(key) is not None


def download_filename(title: str, key: str) -> str:
    """A filename safe to put in a Content-Disposition header.

    Any run of whitespace, CR/LF and tabs included, becomes one space; then
    everything but letters, digits, spaces and . ( ) - is dropped. A newline or
    a quote left in would end the header early. The extension comes from the
    storage key so the file opens correctly.
    """
    spaced = re.sub(r"\s+", " ", title)
    cleaned = re.sub(r"[^\w .()-]", "", spaced).strip() or "download"
    suffix = PurePosixPath(key).suffix
    if suffix and not cleaned.lower().endswith(suffix.lower()):
        cleaned += suffix
    return cleaned


def content_disposition(filename: str) -> str:
    """An attachment header that survives a non-Latin name.

    Header values are ASCII. A Cyrillic title goes in filename* (RFC 6266),
    percent-encoded, which browsers prefer; filename is the fallback for any
    client that doesn't read it.
    """
    if filename.isascii():
        return f'attachment; filename="{filename}"'
    suffix = PurePosixPath(filename).suffix
    fallback = "download" + (suffix if suffix.isascii() else "")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"


class R2Client:
    def __init__(
        self,
        *,
        account_id: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        url_ttl_s: int,
        upload_ttl_s: int = 900,
    ):
        self.bucket = bucket
        self.url_ttl_s = url_ttl_s
        self.upload_ttl_s = upload_ttl_s
        self.configured = bool(account_id and bucket and access_key_id and secret_access_key)
        self._s3 = boto3.client(
            "s3",
            # Unconfigured, botocore still validates the URL; a blank account id
            # would make it raise here, and every storage route would 500
            # instead of answering 503.
            endpoint_url=f"https://{account_id or 'unset'}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id or "unset",
            aws_secret_access_key=secret_access_key or "unset",
            # R2 has no regions, but SigV4 demands one.
            region_name="auto",
            # Deletes and listings are real network calls. Fail fast rather than
            # hang an admin request; whatever doesn't get deleted, the sweep will.
            config=Config(
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=15,
                retries={"max_attempts": 3},
            ),
        )

    def download_url(self, key: str, filename: str) -> str:
        if not self.configured:
            raise StorageNotConfigured("R2 credentials are not configured")

        return self._s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                # Save as the material's title, not the opaque storage key. This
                # also forces a download, so an uploaded .html can never render
                # inline on the bucket's origin.
                "ResponseContentDisposition": content_disposition(filename),
            },
            ExpiresIn=self.url_ttl_s,
        )

    def upload_url(self, key: str) -> str:
        """A presigned PUT so the browser sends bytes straight to R2.

        Longer-lived than a download link: a big PDF on a slow connection needs
        the whole upload to finish inside the window, and unlike a download link
        this one is useless to anyone who can't already reach the admin API.
        """
        if not self.configured:
            raise StorageNotConfigured("R2 credentials are not configured")

        # Content-Type is deliberately unsigned — pinning it would make the
        # browser match the header exactly, and downloads force `attachment`
        # regardless of what the object claims to be.
        return self._s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=self.upload_ttl_s,
        )

    def delete_objects(self, keys: list[str]) -> list[str]:
        """Delete objects, returning the keys R2 refused to delete."""
        if not self.configured:
            raise StorageNotConfigured("R2 credentials are not configured")

        refused = []
        # The S3 API takes at most 1000 keys per batch delete.
        for start in range(0, len(keys), 1000):
            res = self._s3.delete_objects(
                Bucket=self.bucket,
                Delete={
                    "Objects": [{"Key": key} for key in keys[start : start + 1000]],
                    "Quiet": True,  # report failures only
                },
            )
            refused += [error["Key"] for error in res.get("Errors", [])]
        return refused

    def list_objects(self, prefix: str) -> Iterator[tuple[str, datetime]]:
        """Every (key, last modified) under a prefix, across all pages."""
        if not self.configured:
            raise StorageNotConfigured("R2 credentials are not configured")

        pages = self._s3.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=prefix
        )
        for page in pages:
            for obj in page.get("Contents", []):
                yield obj["Key"], obj["LastModified"]


@lru_cache
def get_storage() -> R2Client:
    s = get_settings()
    return R2Client(
        account_id=s.r2_account_id,
        bucket=s.r2_bucket,
        access_key_id=s.r2_access_key_id,
        secret_access_key=s.r2_secret_access_key,
        url_ttl_s=s.material_url_ttl_s,
        upload_ttl_s=s.material_upload_ttl_s,
    )
