"""Run the shared StorageBackend contract against S3StorageBackend.

Two targets:
- ``moto``: in-process S3 mock, always runs (no Docker needed).
- ``minio``: a real S3-compatible server, used when ``S3_ENDPOINT_URL`` is set in the
  process environment (e.g. ``docker run -p 9000:9000 minio/minio server /data``), with
  ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` and optional ``S3_BUCKET``
  (default ``polskiprimal-test``). Skipped otherwise.
"""

from __future__ import annotations

import os

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from app.storage import NotFound, StorageError
from app.storage.s3 import S3StorageBackend
from tests.storage_contract import StorageBackendContract

REGION = "eu-central-1"
MOTO_BUCKET = "polskiprimal-test-moto"


def _ensure_bucket(client, bucket: str) -> None:
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        client.create_bucket(
            Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": REGION}
        )


@pytest.fixture
def moto_backend(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        backend = S3StorageBackend(bucket=MOTO_BUCKET, region=REGION)
        _ensure_bucket(backend._client, MOTO_BUCKET)
        yield backend


@pytest.fixture
def minio_backend():
    endpoint = os.environ.get("S3_ENDPOINT_URL")
    if not endpoint:
        pytest.skip("S3_ENDPOINT_URL not set; MinIO contract run skipped")
    bucket = os.environ.get("S3_BUCKET", "polskiprimal-test")
    backend = S3StorageBackend(
        bucket=bucket,
        region=os.environ.get("AWS_REGION", REGION),
        access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        endpoint_url=endpoint,
    )
    _ensure_bucket(backend._client, bucket)
    return backend


class TestS3StorageBackend(StorageBackendContract):
    @pytest.fixture(params=["moto", "minio"])
    def backend(self, request) -> S3StorageBackend:
        return request.getfixturevalue(f"{request.param}_backend")

    @pytest.mark.anyio
    async def test_rejects_non_json_values(self, backend):
        with pytest.raises(TypeError):
            await backend.put_json("x.json", {"bad": object()})

    @pytest.mark.anyio
    async def test_non_ascii_content_is_preserved(self, backend, ns):
        value = {"nazwa": "Żurawina łąkowa – świeża"}
        await backend.put_json(ns + "pl.json", value)
        assert await backend.get_json(ns + "pl.json") == value

    @pytest.mark.anyio
    async def test_list_paginates_past_1000_keys(self, backend, ns):
        for i in range(1005):
            await backend.put_json(f"{ns}k/{i:05d}.json", {"i": i})
        keys = await backend.list(ns + "k/")
        assert len(keys) == 1005
        assert keys == sorted(keys)
        for key in keys:
            await backend.delete(key)


@pytest.mark.anyio
async def test_missing_bucket_is_storage_error_not_not_found(moto_backend):
    backend = S3StorageBackend(bucket="bucket-that-does-not-exist", region=REGION)
    with pytest.raises(StorageError) as exc_info:
        await backend.get_json("a.json")
    assert not isinstance(exc_info.value, NotFound)
