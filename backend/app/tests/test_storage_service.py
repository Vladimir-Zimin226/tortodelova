import pytest


@pytest.mark.asyncio
async def test_storage_service_save_prediction_image_builds_key_and_url(monkeypatch):
    from app.services import storage_service as ss

    calls = {}

    def fake_put_object_bytes(*, key: str, data: bytes, content_type: str):
        calls["put"] = {"key": key, "data": data, "content_type": content_type}

    def fake_build_public_url(key: str) -> str:
        calls["public_key"] = key
        return f"http://public/{key}"

    async def fake_to_thread(fn, /, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(ss, "put_object_bytes", fake_put_object_bytes)
    monkeypatch.setattr(ss, "build_public_url", fake_build_public_url)
    monkeypatch.setattr(ss.asyncio, "to_thread", fake_to_thread)

    key, url = await ss.storage_service.save_prediction_image(image_bytes=b"PNG", user_id=123)

    # В актуальном StorageService ключи в формате user-{id}/predictions/{uuid}.png
    assert key.startswith("user-123/predictions/")
    assert key.endswith(".png")
    assert url == f"http://public/{key}"
    assert calls["put"]["key"] == key
    assert calls["put"]["data"] == b"PNG"
    assert calls["put"]["content_type"] == "image/png"


@pytest.mark.asyncio
async def test_storage_service_clone_prediction_image_calls_copy(monkeypatch):
    from app.services import storage_service as ss

    calls = {}

    def fake_copy_object(*, source_key: str, dest_key: str):
        calls["copy"] = {"source_key": source_key, "dest_key": dest_key}

    def fake_build_public_url(key: str) -> str:
        return f"http://public/{key}"

    async def fake_to_thread(fn, /, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(ss, "copy_object", fake_copy_object)
    monkeypatch.setattr(ss, "build_public_url", fake_build_public_url)
    monkeypatch.setattr(ss.asyncio, "to_thread", fake_to_thread)

    new_key, new_url = await ss.storage_service.clone_prediction_image(
        source_s3_key="demo/predictions/a.png",
        target_user_id=7,
    )

    assert new_key.startswith("user-7/predictions/")
    assert new_key.endswith(".png")
    assert new_url == f"http://public/{new_key}"
    assert calls["copy"]["source_key"] == "demo/predictions/a.png"
    assert calls["copy"]["dest_key"] == new_key
