from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.registry_atomicity_model import (
    FileRegistry,
    ImmutableVersionConflict,
    IntegrityError,
    PackageKey,
    SimulatedCrash,
)


class RegistryAtomicityTests(unittest.TestCase):
    def test_interrupted_publish_is_invisible_and_repair_is_dry_run_first(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            registry = FileRegistry(Path(raw) / "registry")
            key = PackageKey("acme", "widget", "1.0.0")
            payload = b"deterministic-package-v1"

            with self.assertRaises(SimulatedCrash):
                registry.publish(key, payload, crash_after_blob=True)

            with self.assertRaises(KeyError):
                registry.resolve(key)

            orphaned = registry.repair_orphans(apply=False)
            self.assertEqual(len(orphaned), 1)
            self.assertEqual(orphaned, registry.orphaned_blobs())

            removed = registry.repair_orphans(apply=True)
            self.assertEqual(removed, orphaned)
            self.assertEqual(registry.orphaned_blobs(), [])

            registry.publish(key, payload)
            self.assertEqual(registry.resolve(key), payload)

    def test_same_version_is_idempotent_but_changed_bytes_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            registry = FileRegistry(Path(raw) / "registry")
            key = PackageKey("acme", "widget", "1.0.0")

            first = registry.publish(key, b"payload-a")
            second = registry.publish(key, b"payload-a")
            self.assertEqual(first, second)
            self.assertEqual(registry.resolve(key), b"payload-a")

            with self.assertRaises(ImmutableVersionConflict):
                registry.publish(key, b"payload-b")

            self.assertEqual(registry.resolve(key), b"payload-a")
            self.assertEqual(registry.orphaned_blobs(), [])

    def test_concurrent_identical_publish_converges_to_one_identity(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            registry = FileRegistry(Path(raw) / "registry")
            key = PackageKey("acme", "widget", "1.0.0")
            payload = b"same-payload-for-all-publishers"

            with ThreadPoolExecutor(max_workers=8) as pool:
                digests = list(pool.map(lambda _: registry.publish(key, payload), range(32)))

            self.assertEqual(len(set(digests)), 1)
            self.assertEqual(registry.resolve(key), payload)
            metadata = list((registry.root / "metadata").rglob("*.json"))
            blobs = list((registry.root / "blobs").iterdir())
            self.assertEqual(len(metadata), 1)
            self.assertEqual(len(blobs), 1)
            self.assertEqual(registry.orphaned_blobs(), [])

    def test_snapshot_restore_requires_checksum_verified_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            live = FileRegistry(root / "live")
            a = PackageKey("acme", "alpha", "1.0.0")
            b = PackageKey("acme", "beta", "2.0.0")
            live.publish(a, b"alpha-bytes")
            live.publish(b, b"beta-bytes")

            snapshot = root / "snapshot"
            live.snapshot_to(snapshot)
            restored = FileRegistry.restore_from(snapshot, root / "restored")

            self.assertEqual(restored.resolve(a), b"alpha-bytes")
            self.assertEqual(restored.resolve(b), b"beta-bytes")
            self.assertEqual(restored.orphaned_blobs(), [])

            digest = next(iter(restored.referenced_digests()))
            (restored.blobs / digest).write_bytes(b"corrupt")
            with self.assertRaises(IntegrityError):
                if restored._read_metadata(a)["sha256"] == digest:
                    restored.resolve(a)
                else:
                    restored.resolve(b)


if __name__ == "__main__":
    unittest.main()
