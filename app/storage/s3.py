"""Amazon S3 implementation of :class:`StorageBackend` (Requirements 2.1, 2.5, 2.6, 8.2).

This is the ONLY module allowed to import boto3. Routes, services and templates talk to
the abstract ``StorageBackend`` and never to S3 directly (R2.2).

boto3 is synchronous, so each call runs in a worker thread via ``asyncio.to_thread`` to
keep the event loop free. Works against real S3 and S3-compatible servers such as MinIO
(set ``endpoint_url``).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.storage.base import NotFound, ReserveResult, StorageBackend, StorageError

# Error codes S3 / MinIO use for "object does not exist".
_MISSING_KEY_CODES = {"NoSuchKey", "404", "NotFound"}


def _validate_key(key: str) -> None:
    if not isinstance(key, str) or not key:
        raise ValueError("Storage key must be a non-empty string")


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


class S3StorageBackend(StorageBackend):
    """Stores each JSON object as one S3 object (``application/json``, UTF-8).

    Credentials are optional here: when ``access_key_id``/``secret_access_key`` are not
    given, boto3's default credential chain is used (IAM role, shared config, ...).
    """

    def __init__(
        self,
        bucket: str,
        region: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        endpoint_url: str | None = None,
        client: Any | None = None,
    ) -> None:
        if not bucket:
            raise ValueError("S3StorageBackend requires a bucket name")
        self._bucket = bucket
        self._client = client or boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            endpoint_url=endpoint_url,
            config=Config(
                retries={"max_attempts": 3, "mode": "standard"},
                # Path-style addressing works for both AWS and MinIO.
                s3={"addressing_style": "path"} if endpoint_url else None,
            ),
        )

    @property
    def bucket(self) -> str:
        return self._bucket

    # --- sync helpers (run in a thread) ----------------------------------------

    def _get_sync(self, key: str) -> dict:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            raw = response["Body"].read()
        except ClientError as exc:
            if _error_code(exc) in _MISSING_KEY_CODES:
                raise NotFound(key) from None
            raise StorageError(f"S3 get failed for '{key}': {_error_code(exc)}") from exc
        except BotoCoreError as exc:
            raise StorageError(f"S3 get failed for '{key}': {exc}") from exc
        return json.loads(raw.decode("utf-8"))

    def _put_sync(self, key: str, body: bytes) -> None:
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=body,
                ContentType="application/json; charset=utf-8",
            )
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(f"S3 put failed for '{key}': {exc}") from exc

    def _list_sync(self, prefix: str) -> list[str]:
        keys: list[str] = []
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                keys.extend(obj["Key"] for obj in page.get("Contents", []))
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(f"S3 list failed for prefix '{prefix}': {exc}") from exc
        return sorted(keys)

    def _delete_sync(self, key: str) -> None:
        try:
            # S3 returns success for missing keys, matching the interface contract.
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(f"S3 delete failed for '{key}': {exc}") from exc

    # --- StorageBackend API ----------------------------------------------------

    async def get_json(self, key: str) -> dict:
        _validate_key(key)
        return await asyncio.to_thread(self._get_sync, key)

    async def put_json(self, key: str, value: dict) -> None:
        _validate_key(key)
        if not isinstance(value, dict):
            raise TypeError("put_json value must be a dict")
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")  # TypeError if not JSON
        await asyncio.to_thread(self._put_sync, key, body)

    async def list(self, prefix: str) -> list[str]:
        return await asyncio.to_thread(self._list_sync, prefix)

    async def delete(self, key: str) -> None:
        _validate_key(key)
        await asyncio.to_thread(self._delete_sync, key)

    async def try_reserve(self, slot_key: str, request: dict) -> ReserveResult:
        """Phase 1: record a ``requested`` reservation; never decrement slot quantity (R8.2).

        S3 has no atomic read-modify-write, so stock is deliberately left untouched and the
        farmer confirms manually. Option B/C backends replace this with atomic deduction.
        """
        return await self._record_reservation_request(slot_key, request)
