"""Article storage backends.

Both backends use the same layout, which the static site reads directly::

    blogs/<domain>/articles.json   index of published articles, newest first
    blogs/<domain>/<slug>.md       article body in Markdown

* ``LocalStorageService`` writes into ``scribegraph/web`` (or ``storage__local_dir``),
  so articles can be committed to Git and served by GitHub Pages.
* ``R2StorageService`` writes to a Cloudflare R2 bucket (S3-compatible API).
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from scribegraph.config import ConfigError, Settings, get_settings

log = logging.getLogger(__name__)

Article = dict[str, Any]


def index_key(domain: str) -> str:
    return f"blogs/{domain}/articles.json"


def article_key(domain: str, slug: str) -> str:
    return f"blogs/{domain}/{slug}.md"


class StorageService(ABC):
    """Common article-index logic on top of two primitives: get and put a text object."""

    name = "storage"

    @abstractmethod
    def get_object(self, key: str) -> str | None:
        """Return the object's text, or ``None`` if it does not exist."""

    @abstractmethod
    def put_object(self, key: str, data: str, content_type: str = "text/plain") -> None:
        """Create or replace an object. Raises on failure."""

    @abstractmethod
    def uri(self, key: str) -> str:
        """Human-readable location of an object, for logs."""

    def get_json(self, key: str) -> Any:
        raw = self.get_object(key)
        if raw is None or not raw.strip():
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Could not parse JSON at %s; treating it as empty.", self.uri(key))
            return None

    def get_articles(self, domain: str) -> list[Article]:
        data = self.get_json(index_key(domain))
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def save_articles(self, domain: str, articles: list[Article]) -> None:
        # sorted() is stable, so a new article placed first stays first on its date.
        ordered = sorted(articles, key=lambda a: str(a.get("date", "")), reverse=True)
        body = json.dumps(ordered, indent=2, ensure_ascii=False) + "\n"
        self.put_object(index_key(domain), body, "application/json")

    def recent_history(self, domain: str, limit: int = 5) -> list[Article]:
        """The newest ``limit`` articles, trimmed to the fields the topic planner needs."""
        articles = sorted(
            self.get_articles(domain), key=lambda a: str(a.get("date", "")), reverse=True
        )
        return [
            {
                "title": a.get("title", ""),
                "topic": a.get("topic", ""),
                "subtopics": a.get("subtopics", ""),
            }
            for a in articles[:limit]
        ]

    def last_published(self, domains: Iterable[str]) -> dict[str, str | None]:
        """Latest article date per domain (``None`` if the domain has no articles)."""
        result: dict[str, str | None] = {}
        for domain in domains:
            dates = [str(a["date"]) for a in self.get_articles(domain) if a.get("date")]
            result[domain] = max(dates) if dates else None
        return result


class LocalStorageService(StorageService):
    name = "local"

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"Refusing to access a path outside the storage folder: {key!r}")
        return path

    def get_object(self, key: str) -> str | None:
        path = self._path(key)
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def put_object(self, key: str, data: str, content_type: str = "text/plain") -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(data, encoding="utf-8", newline="\n")
        tmp.replace(path)  # atomic on the same filesystem
        log.info("  saved %s", self.uri(key))

    def uri(self, key: str) -> str:
        path = self._path(key)
        try:
            return os.path.relpath(path)
        except ValueError:  # different drive on Windows
            return str(path)


class R2StorageService(StorageService):
    name = "r2"

    def __init__(self, settings: Settings | None = None):
        r2 = (settings or get_settings()).r2
        if not r2.configured:
            raise ConfigError(
                "Cloudflare R2 storage is selected but not fully configured. Set r2__account_id, "
                "r2__access_key_id, r2__secret_access_key and r2__bucket_name, "
                "or use storage__backend=local."
            )
        import boto3  # only needed for this backend

        self.bucket = r2.bucket_name.strip(" =\"'")
        self.client = boto3.client(
            service_name="s3",
            endpoint_url=f"https://{r2.account_id.strip()}.r2.cloudflarestorage.com",
            aws_access_key_id=r2.access_key_id.strip(),
            aws_secret_access_key=r2.secret_access_key.strip(),
            region_name="auto",
        )

    def get_object(self, key: str) -> str | None:
        from botocore.exceptions import ClientError

        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404", "NotFound"}:
                return None
            # Any other error must stop the run. Treating it as "missing" (as the original
            # code did) would make the next save overwrite the whole article index.
            raise
        return response["Body"].read().decode("utf-8")

    def put_object(self, key: str, data: str, content_type: str = "text/plain") -> None:
        cache = "no-cache" if key.endswith(".json") else "public, max-age=3600"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data.encode("utf-8"),
            ContentType=f"{content_type}; charset=utf-8",
            CacheControl=cache,
        )
        log.info("  uploaded %s", self.uri(key))

    def uri(self, key: str) -> str:
        return f"r2://{self.bucket}/{key}"


def get_storage(settings: Settings | None = None) -> StorageService:
    """The configured storage backend (see ``storage__backend``)."""
    settings = settings or get_settings()
    if settings.storage_backend == "r2":
        return R2StorageService(settings)
    return LocalStorageService(settings.storage.local_dir)
