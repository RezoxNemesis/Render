# SPDX-License-Identifier: GPL-2.0-or-later
"""Host/filesystem Phase 02 tests. Synthetic PNG != real Blender render."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

SOURCE = Path(__file__).resolve().parents[2] / "full-app/scripts/omega/phase02_render.py"
_SPEC = importlib.util.spec_from_file_location("phase02_render_under_test", SOURCE)
P = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(P)


def _chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))


def synthetic_png(width=16, height=16, seed=0):
    # Self-contained, valid RGBA PNG with actual compressed raster data.
    rows = b"".join(
        b"\0" + bytes((seed % 256, y % 256, 80, 255)) * width
        for y in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(rows))
            + _chunk(b"IEND", b""))


class Phase02HostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        P._JOB_CACHE.clear()
        self.folder = Path(self.tmp.name) / ("a" * 32)
        self.folder.mkdir()
        original = b"BLENDER" + b"\0" * 512
        (self.folder / "snapshot.blend").write_bytes(original)
        snapshot = {
            "filename": "snapshot.blend", "bytes": len(original),
            "sha256": hashlib.sha256(original).hexdigest(),
        }
        self.spec = {
            "width": 16, "height": 16, "fps": 24, "fps_base": 1.001,
            "start": 101, "end": 105, "frame_count": 5,
            "samples": 72, "engine": "CYCLES",
            "bitrate": 16000000, "output_kind": "ANIMATION",
        }
        self.manifest = {
            "version": 1, "job_id": self.folder.name, "source_scene": "OmegaCamera",
            "spec": self.spec, "snapshot": snapshot,
            "fingerprint": P._fingerprint({"spec": self.spec, "snapshot": snapshot}),
            "state": "ready", "frames": {}, "next_frame": 101,
            "quality_reduced": False,
        }
        P.atomic_json(self.folder / "manifest.json", self.manifest)

    def _commit(self, frame, data=None):
        partial = self.folder / ("frame_%06d.partial.png" % frame)
        partial.write_bytes(synthetic_png(seed=frame) if data is None else data)
        return P.commit_png(self.folder, self.manifest, frame, partial)

    def test_real_png_chunk_crc_and_dimensions_checked(self):
        path = self.folder / "valid.png"
        path.write_bytes(synthetic_png(16, 16, 47))
        receipt = P.png_proof(path)
        self.assertEqual((16, 16), (receipt["width"], receipt["height"]))
        self.assertEqual(receipt["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        path.write_bytes(path.read_bytes().replace(b"IEND", b"XEND"))
        with self.assertRaisesRegex(ValueError, "INVALID_PNG_CRC"):
            P.png_proof(path)

    def test_101_to_105_interrupted_after_103_resumes_only_104_and_105(self):
        originals = {}
        for frame in (101, 102, 103):
            self._commit(frame)
            final = self.folder / ("frame_%06d.png" % frame)
            originals[frame] = (final.stat().st_mtime_ns, final.read_bytes())
        self.assertEqual(104, self.manifest["next_frame"])
        self.assertEqual("ready", self.manifest["state"])
        P._JOB_CACHE.clear()  # Simulates dead Android/Blender process.
        restored = json.loads((self.folder / "manifest.json").read_text())
        reconciled, inspected = P.reconcile_manifest(self.folder, restored, persist=True)
        self.assertEqual(104, inspected["first_missing"])
        self.assertEqual(3, inspected["verified_frames"])
        self.manifest = reconciled
        for frame in (104, 105):
            self.assertEqual(frame, self.manifest["next_frame"])
            self._commit(frame)
        self.assertEqual("frames_complete", self.manifest["state"])
        self.assertEqual(106, self.manifest["next_frame"])
        self.assertEqual(5, len(self.manifest["frames"]))
        self.assertEqual(1.001, self.manifest["frames"]["105"]["fps_base"])
        self.assertEqual(72, self.manifest["frames"]["105"]["samples"])
        for frame, original in originals.items():
            final = self.folder / ("frame_%06d.png" % frame)
            self.assertEqual(original, (final.stat().st_mtime_ns, final.read_bytes()))
        again, status = P.reconcile_manifest(
            self.folder, self.manifest, persist=False)
        self.assertIsNone(status["first_missing"])
        self.assertEqual(5, status["verified_frames"])

    def test_corrupt_102_keeps_101_and_103_and_restores_first_missing(self):
        for frame in (101, 102, 103):
            self._commit(frame)
        stable_103 = (self.folder / "frame_000103.png").read_bytes()
        target = self.folder / "frame_000102.png"
        target.write_bytes(b"not a PNG but might exceed 64 bytes" * 4)
        P._JOB_CACHE.clear()
        recovered, details = P.reconcile_manifest(
            self.folder, self.manifest, persist=True)
        self.assertEqual(102, recovered["next_frame"])
        self.assertIn(102, details["invalid_receipts"])
        self.assertEqual(set(recovered["frames"]), {"101", "103"})
        self.manifest = recovered
        self._commit(102)
        self.assertEqual(104, self.manifest["next_frame"])
        self.assertEqual(stable_103, (self.folder / "frame_000103.png").read_bytes())

    def test_truncated_and_wrong_resolution_never_commit(self):
        for data, expected in (
            (synthetic_png()[:50], "INVALID_PNG"),
            (synthetic_png(32, 16), "FRAME_DIMENSIONS_MISMATCH"),
            (b"\x89PNG\r\n\x1a\n" + b"nonsense" * 15, "INVALID_PNG"),
        ):
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(ValueError, expected):
                    self._commit(101, data)
                self.assertEqual({}, self.manifest["frames"])
                self.assertEqual(101, self.manifest["next_frame"])
                self.assertFalse((self.folder / "frame_000101.png").exists())

    def test_power_loss_after_final_png_rename_adopts_sidecar(self):
        self._commit(101)
        before = copy.deepcopy(self.manifest)
        self._commit(102)
        published = (self.folder / "frame_000102.png").read_bytes()
        # Simulate power loss before replacement of the previous manifest.
        P.atomic_json(self.folder / "manifest.json", before)
        P._JOB_CACHE.clear()
        recovered, details = P.reconcile_manifest(self.folder, before, persist=True)
        self.assertEqual([102], details["adopted_frames"])
        self.assertEqual({"101", "102"}, set(recovered["frames"]))
        self.assertEqual(103, recovered["next_frame"])
        self.assertEqual(published, (self.folder / "frame_000102.png").read_bytes())

    def test_wrong_sidecar_revision_cannot_adopt_unjournaled_frame(self):
        previous = copy.deepcopy(self.manifest)
        self._commit(101)
        sidecar = self.folder / "frame_000101.receipt.json"
        receipt = json.loads(sidecar.read_text())
        receipt["fingerprint"] = "b" * 64
        P.atomic_json(sidecar, receipt)
        P._JOB_CACHE.clear()
        recovered, details = P.reconcile_manifest(self.folder, previous)
        self.assertEqual(101, recovered["next_frame"])
        self.assertEqual([], details["adopted_frames"])

    def test_invalid_snapshot_or_manifest_fails_closed(self):
        (self.folder / "snapshot.blend").write_bytes(b"BLENDER" + b"0" * 512)
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_HASH_MISMATCH"):
            P.reconcile_manifest(self.folder, self.manifest)
        (self.folder / "snapshot.blend").write_bytes(b"BLENDER" + b"\0" * 512)
        mismatch = copy.deepcopy(self.manifest)
        mismatch["spec"]["samples"] = 12
        with self.assertRaisesRegex(ValueError, "RENDER_MANIFEST_CONFLICT"):
            P.reconcile_manifest(self.folder, mismatch)

    def test_process_cache_avoids_quadratic_rehash(self):
        self._commit(101)
        first, status = P.reconcile_manifest(
            self.folder, self.manifest, persist=True, cached=True)
        self.assertTrue(status.get("process_cache_hit"))
        self.assertEqual(102, first["next_frame"])
        self._commit(102)
        _, second = P.reconcile_manifest(
            self.folder, self.manifest, persist=True, cached=True)
        self.assertTrue(second.get("process_cache_hit"))
        # Explicit read-only audit still checks all real SHA receipts.
        _, verified = P.reconcile_manifest(self.folder, self.manifest)
        self.assertNotIn("process_cache_hit", verified)

    def test_operations_validate_allowlist_and_job_id(self):
        self.assertEqual({}, P.validate("omega.render.preflight", {}))
        self.assertEqual({"job_id": self.folder.name}, P.validate(
            "omega.render.job_status", {"job_id": self.folder.name}))
        for operation, payload in (
            ("omega.render.unknown", {}),
            ("omega.render.preflight", {"path": "/storage/emulated/0"}),
            ("omega.render.job_status", {"job_id": "../../malicious"}),
            ("omega.render.job_status", {"job_id": self.folder.name, "script": "print(1)"}),
        ):
            with self.subTest(operation=operation, payload=payload):
                with self.assertRaises(ValueError):
                    P.validate(operation, payload)


if __name__ == "__main__":
    unittest.main()
