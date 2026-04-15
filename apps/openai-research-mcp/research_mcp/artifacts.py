from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from .errors import InvalidInputError


class LocalDirectoryObjectStore:
    def __init__(self, root: str | Path, *, public_base_url: str | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None

    def _safe_name(self, name: str) -> str:
        if ".." in name or name.startswith("/"):
            raise InvalidInputError("unsafe object key")
        return name

    def put_text(self, relative_name: str, content: str) -> dict:
        object_key = self._safe_name(relative_name)
        path = self.root / object_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        out = {"object_key": object_key, "sha256": digest, "local_path": str(path)}
        if self.public_base_url:
            out["download_url"] = "{}/{}".format(self.public_base_url, object_key)
        return out


class MarkdownArtifactExporter:
    def __init__(self, object_store: LocalDirectoryObjectStore):
        self.object_store = object_store

    def export_report(self, *, title: str, narrative: str, documents: list[dict]) -> dict:
        artifact_id = "sandbox-report-artifact-{}".format(uuid.uuid4().hex[:16])
        lines = ["# {}".format(title), "", narrative, "", "## Sources", ""]
        for doc in documents:
            lines.append("- {} — {}".format(doc["title"], doc["url"]))
        body = "\n".join(lines).rstrip() + "\n"
        stored = self.object_store.put_text("{}.md".format(artifact_id), body)
        manifest = {
            "artifact_id": artifact_id,
            "object_key": stored["object_key"],
            "sha256": stored["sha256"],
            "sources": [{"id": d["id"], "url": d["url"]} for d in documents],
            "local_path": stored["local_path"],
        }
        manifest_store = self.object_store.put_text(
            "{}.md.manifest.json".format(artifact_id),
            json.dumps(manifest, indent=2, sort_keys=True),
        )
        public = {
            "artifact_id": artifact_id,
            "object_key": stored["object_key"],
            "sha256": stored["sha256"],
            "manifest_object_key": manifest_store["object_key"],
        }
        if "download_url" in stored:
            public["download_url"] = stored["download_url"]
        return public
