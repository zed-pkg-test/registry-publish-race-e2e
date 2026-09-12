from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import pathlib
import shutil
import tempfile
from dataclasses import dataclass


class SimulatedCrash(RuntimeError):
    pass


class ImmutableVersionConflict(RuntimeError):
    pass


class IntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class PackageKey:
    org: str
    name: str
    version: str


class FileRegistry:
    """Dependency-free reference model for atomic immutable registry publication."""

    def __init__(self, root: pathlib.Path) -> None:
        self.root = pathlib.Path(root)
        self.blobs = self.root / "blobs"
        self.metadata = self.root / "metadata"
        self.staging = self.root / "staging"
        self.locks = self.root / "locks"
        for path in (self.blobs, self.metadata, self.staging, self.locks):
            path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _digest(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def _metadata_path(self, key: PackageKey) -> pathlib.Path:
        return self.metadata / key.org / key.name / f"{key.version}.json"

    def _lock_path(self, key: PackageKey) -> pathlib.Path:
        safe = f"{key.org}--{key.name}--{key.version}.lock"
        return self.locks / safe

    @contextlib.contextmanager
    def _coordinate_lock(self, key: PackageKey):
        path = self._lock_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _atomic_write(path: pathlib.Path, payload: bytes, staging: pathlib.Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        staging.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=staging, delete=False) as handle:
            temp = pathlib.Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def _read_metadata(self, key: PackageKey) -> dict[str, object] | None:
        path = self._metadata_path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def publish(
        self,
        key: PackageKey,
        payload: bytes,
        *,
        crash_after_blob: bool = False,
    ) -> str:
        digest = self._digest(payload)
        blob = self.blobs / digest
        metadata_path = self._metadata_path(key)

        with self._coordinate_lock(key):
            current = self._read_metadata(key)
            if current is not None:
                current_digest = str(current["sha256"])
                if current_digest != digest:
                    raise ImmutableVersionConflict(
                        f"{key.org}/{key.name}@{key.version} already maps to {current_digest}"
                    )
                self._verify_blob(blob, payload, digest)
                return digest

            if blob.exists():
                self._verify_blob(blob, payload, digest)
            else:
                self._atomic_write(blob, payload, self.staging)

            if crash_after_blob:
                raise SimulatedCrash("publication interrupted after durable blob, before metadata")

            record = {
                "org": key.org,
                "name": key.name,
                "version": key.version,
                "sha256": digest,
                "size": len(payload),
                "status": "active",
            }
            encoded = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
            self._atomic_write(metadata_path, encoded, self.staging)
            return digest

    @staticmethod
    def _verify_blob(blob: pathlib.Path, expected: bytes, digest: str) -> None:
        actual = blob.read_bytes()
        if actual != expected or hashlib.sha256(actual).hexdigest() != digest:
            raise IntegrityError(f"blob {digest} failed byte/digest verification")

    def resolve(self, key: PackageKey) -> bytes:
        metadata = self._read_metadata(key)
        if metadata is None:
            raise KeyError(f"missing package metadata: {key}")
        digest = str(metadata["sha256"])
        blob = self.blobs / digest
        if not blob.is_file():
            raise IntegrityError(f"metadata references missing blob {digest}")
        payload = blob.read_bytes()
        if hashlib.sha256(payload).hexdigest() != digest:
            raise IntegrityError(f"restored blob {digest} failed checksum verification")
        if len(payload) != int(metadata["size"]):
            raise IntegrityError(f"restored blob {digest} failed size verification")
        return payload

    def referenced_digests(self) -> set[str]:
        referenced: set[str] = set()
        for path in self.metadata.rglob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            referenced.add(str(payload["sha256"]))
        return referenced

    def orphaned_blobs(self) -> list[str]:
        referenced = self.referenced_digests()
        return sorted(path.name for path in self.blobs.iterdir() if path.is_file() and path.name not in referenced)

    def repair_orphans(self, *, apply: bool = False) -> list[str]:
        orphans = self.orphaned_blobs()
        if apply:
            for digest in orphans:
                (self.blobs / digest).unlink()
        return orphans

    def snapshot_to(self, destination: pathlib.Path) -> None:
        destination = pathlib.Path(destination)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(self.root, destination)

    @classmethod
    def restore_from(cls, snapshot: pathlib.Path, destination: pathlib.Path) -> "FileRegistry":
        snapshot = pathlib.Path(snapshot)
        destination = pathlib.Path(destination)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(snapshot, destination)
        return cls(destination)
