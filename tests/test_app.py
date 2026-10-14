from datetime import datetime, timezone
from io import BytesIO

import pytest

from app import create_app


class FakePaginator:
    def paginate(self, **kwargs):
        return [{"Contents": [{"Key": "originales/demo.jpg", "Size": 4, "LastModified": datetime.now(timezone.utc)}]}]


class FakeS3:
    def __init__(self, data=b"\xff\xd8\xff\x00", content_type="image/jpeg"):
        self.data = data
        self.content_type = content_type
        self.calls = []

    def generate_presigned_url(self, operation, Params, ExpiresIn, **kwargs):
        self.calls.append((operation, Params, ExpiresIn))
        return f"https://example.invalid/{operation}"

    def head_object(self, **kwargs):
        return {"ContentLength": len(self.data), "ContentType": self.content_type}

    def get_object(self, **kwargs):
        return {"Body": BytesIO(self.data[:12])}

    def copy_object(self, **kwargs):
        self.calls.append(("copy", kwargs))

    def delete_object(self, **kwargs):
        self.calls.append(("delete", kwargs))

    def get_paginator(self, operation):
        assert operation == "list_objects_v2"
        return FakePaginator()


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "private-test")
    fake = FakeS3()
    app = create_app(fake)
    app.testing = True
    return app.test_client(), fake


def test_upload_url_valid_and_five_minute_expiry(setup):
    client, fake = setup
    response = client.post("/api/upload-url", json={"filename": "foto.jpg", "contentType": "image/jpeg", "sizeBytes": 100})
    assert response.status_code == 200
    assert response.json["key"].startswith("temporal/")
    assert fake.calls[0][0] == "put_object"
    assert fake.calls[0][2] == 300
    assert fake.calls[0][1]["ServerSideEncryption"] == "AES256"


@pytest.mark.parametrize("content_type,size", [("application/pdf", 100), ("image/jpeg", 10 * 1024 * 1024), ("image/jpeg", -1), ("image/jpeg", "100")])
def test_upload_rejects_invalid_type_or_size(setup, content_type, size):
    client, fake = setup
    response = client.post("/api/upload-url", json={"filename": "x.jpg", "contentType": content_type, "sizeBytes": size})
    assert response.status_code == 400
    assert fake.calls == []


def test_verify_valid_image_promotes_to_originals(setup):
    client, fake = setup
    key = "temporal/" + "a" * 32 + "-demo.jpg"
    response = client.post("/api/images/verify", json={"key": key})
    assert response.status_code == 201
    assert response.json["key"].startswith("originales/")
    assert any(call[0] == "copy" for call in fake.calls)


def test_verify_rejects_spoofed_image(setup):
    client, fake = setup
    fake.data = b"not an image"
    key = "temporal/" + "b" * 32 + "-demo.jpg"
    response = client.post("/api/images/verify", json={"key": key})
    assert response.status_code == 400
    assert any(call[0] == "delete" for call in fake.calls)
    assert not any(call[0] == "copy" for call in fake.calls)


def test_list_uses_fifteen_minute_urls(setup):
    client, fake = setup
    response = client.get("/api/images")
    assert response.status_code == 200
    assert response.json[0]["key"] == "originales/demo.jpg"
    assert fake.calls[0][0] == "get_object"
    assert fake.calls[0][2] == 900


def test_delete_is_limited_to_originals(setup):
    client, fake = setup
    assert client.delete("/api/images/temporal/bad.jpg").status_code == 400
    assert client.delete("/api/images/originales/demo.jpg").status_code == 200
    assert fake.calls[-1][0] == "delete"
