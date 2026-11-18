import pytest
from botocore.exceptions import ClientError

from scribegraph.config import ConfigError, get_settings
from scribegraph.services.storage import (
    LocalStorageService,
    R2StorageService,
    get_storage,
    index_key,
)


def test_local_roundtrip_is_atomic(site):
    storage = LocalStorageService(site)
    assert storage.get_object("blogs/ml/x.md") is None
    storage.put_object("blogs/ml/x.md", "hello")
    assert storage.get_object("blogs/ml/x.md") == "hello"
    assert not list(site.rglob("*.tmp"))


@pytest.mark.parametrize("key", ["../evil.md", "blogs/../../evil.md"])
def test_local_storage_refuses_paths_outside_its_folder(site, key):
    with pytest.raises(ValueError):
        LocalStorageService(site).put_object(key, "x")


def test_article_index_tolerates_empty_and_broken_files(site):
    storage = LocalStorageService(site)
    path = site / "blogs" / "ml" / "articles.json"
    path.parent.mkdir(parents=True)
    path.write_text("")  # the original repo shipped some of these as 0-byte files
    assert storage.get_articles("ml") == []
    path.write_text("{broken")
    assert storage.get_articles("ml") == []


def test_save_articles_sorts_newest_first(site):
    storage = LocalStorageService(site)
    storage.save_articles(
        "ml", [{"id": "a", "date": "2026-01-01"}, {"id": "b", "date": "2026-03-01"}]
    )
    assert [a["id"] for a in storage.get_articles("ml")] == ["b", "a"]


def test_last_published_and_history(site, seed):
    seed(
        "ml",
        [
            {"id": "blogs/ml/a.md", "file": "blogs/ml/a.md", "title": "A", "date": "2026-01-01"},
            {"id": "blogs/ml/b.md", "file": "blogs/ml/b.md", "title": "B", "date": "2026-03-02"},
        ],
    )
    storage = LocalStorageService(site)
    assert storage.last_published(["ml", "dl"]) == {"ml": "2026-03-02", "dl": None}
    assert [h["title"] for h in storage.recent_history("ml", limit=1)] == ["B"]


def test_auto_backend_uses_local_without_r2_credentials(monkeypatch):
    monkeypatch.setenv("storage__backend", "auto")
    get_settings.cache_clear()
    assert isinstance(get_storage(), LocalStorageService)

    for name in ("account_id", "access_key_id", "secret_access_key", "bucket_name"):
        monkeypatch.setenv(f"r2__{name}", "x")
    get_settings.cache_clear()
    assert get_settings().storage_backend == "r2"


def test_r2_needs_full_configuration(monkeypatch):
    monkeypatch.setenv("storage__backend", "r2")
    get_settings.cache_clear()
    with pytest.raises(ConfigError, match="R2"):
        get_storage()


class FakeS3:
    def __init__(self, error_code: str | None = None):
        self.objects: dict[str, dict] = {}
        self.error_code = error_code

    def get_object(self, Bucket, Key):
        if self.error_code:
            raise ClientError({"Error": {"Code": self.error_code}}, "GetObject")
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")

        class Body:
            def __init__(self, data):
                self.data = data

            def read(self):
                return self.data

        return {"Body": Body(self.objects[Key]["Body"])}

    def put_object(self, **kwargs):
        self.objects[kwargs["Key"]] = kwargs


def _r2(monkeypatch, client: FakeS3) -> R2StorageService:
    import boto3

    for name in ("account_id", "access_key_id", "secret_access_key", "bucket_name"):
        monkeypatch.setenv(f"r2__{name}", f"test-{name}")
    get_settings.cache_clear()
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: client)
    return R2StorageService()


def test_r2_roundtrip(monkeypatch):
    client = FakeS3()
    storage = _r2(monkeypatch, client)
    assert storage.get_articles("ml") == []
    storage.save_articles("ml", [{"id": "blogs/ml/a.md", "date": "2026-01-01"}])
    assert storage.get_articles("ml")[0]["id"] == "blogs/ml/a.md"
    stored = client.objects[index_key("ml")]
    assert stored["ContentType"].startswith("application/json")
    assert storage.uri("blogs/ml/a.md") == "r2://test-bucket_name/blogs/ml/a.md"


def test_r2_read_errors_are_raised_not_treated_as_missing(monkeypatch):
    # Regression: the original returned None on any error, so a transient failure made the
    # next save overwrite the whole article index with a single entry.
    storage = _r2(monkeypatch, FakeS3(error_code="AccessDenied"))
    with pytest.raises(ClientError):
        storage.get_articles("ml")
