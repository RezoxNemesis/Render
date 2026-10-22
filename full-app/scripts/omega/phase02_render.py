# SPDX-License-Identifier: GPL-2.0-or-later
"""OMEGA Phase 02: crash-consistent, independently verifiable native frame receipts.

This module is importable without Blender for host tests. Only execute/audit
access bpy; no remote Python, network, gallery, or caller-selected file paths.
The old Android manifest is kept backward compatible with additive fields.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import time
import zlib

CONTRACT_VERSION = "RENDER-OMEGA-1"
OPERATION_NAMES = ("omega.render.preflight", "omega.render.job_status")
_ID = re.compile(r"^[0-9a-f]{32}$")
_PNG = b"\x89PNG\r\n\x1a\n"
_JOB_CACHE = {}  # Process-local only; never used as proof across Android restarts.


def _fingerprint(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     allow_nan=False).encode("utf8")
    return hashlib.sha256(raw).hexdigest()


def sync_directory(path):
    """Best-effort directory durability; never misreport file sync as done."""
    try:
        fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return False  # Some Android filesystems cannot fsync directories.
    try:
        os.fsync(fd)
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


def atomic_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf8") as writer:
        json.dump(obj, writer, sort_keys=True, allow_nan=False)
        writer.flush()
        os.fsync(writer.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def sync_file(path):
    with Path(path).open("rb") as stream:
        os.fsync(stream.fileno())


def _hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_job_id(job_id):
    if not isinstance(job_id, str) or not _ID.fullmatch(job_id):
        raise ValueError("INVALID_JOB_ID")
    return job_id


def _safe_job_folder(root, job_id):
    directory = Path(root).resolve()
    folder = directory / _safe_job_id(job_id)
    if folder.is_symlink() or folder.resolve().parent != directory:
        raise ValueError("JOB_OUTSIDE_SCOPE")
    return folder


def png_proof(path):
    """Stream and CRC-verify every chunk, IHDR pixel dimensions, IDAT and IEND.

    A PNG header or nonzero file size alone does not prove an image. CRC
    integrity is not visual acceptance; no claim about scene appearance.
    """
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("INVALID_PNG")
    digest = hashlib.sha256()
    total = 0
    found_idat = False
    found_iend = False
    width = height = None
    with path.open("rb") as stream:
        sig = stream.read(8)
        if sig != _PNG:
            raise ValueError("INVALID_PNG_SIGNATURE")
        digest.update(sig)
        total += len(sig)
        chunk_index = 0
        while True:
            header = stream.read(8)
            if len(header) != 8:
                raise ValueError("INVALID_PNG_TRUNCATED")
            digest.update(header)
            total += 8
            length, kind = struct.unpack(">I4s", header)
            if length > 1024 * 1024 * 1024:
                raise ValueError("INVALID_PNG_CHUNK_LENGTH")
            if chunk_index == 0 and (kind != b"IHDR" or length != 13):
                raise ValueError("INVALID_PNG_IHDR")
            crc = zlib.crc32(kind)
            remaining = length
            ihdr = b""
            while remaining:
                part = stream.read(min(1024 * 1024, remaining))
                if not part:
                    raise ValueError("INVALID_PNG_TRUNCATED")
                digest.update(part)
                crc = zlib.crc32(part, crc)
                if kind == b"IHDR":
                    ihdr += part
                remaining -= len(part)
                total += len(part)
            stored = stream.read(4)
            if len(stored) != 4:
                raise ValueError("INVALID_PNG_TRUNCATED")
            digest.update(stored)
            total += 4
            if crc & 0xffffffff != struct.unpack(">I", stored)[0]:
                raise ValueError("INVALID_PNG_CRC")
            if kind == b"IHDR":
                width, height, depth, color, compression, filt, interlace = struct.unpack(
                    ">IIBBBBB", ihdr)
                if (not width or not height or depth not in (1, 2, 4, 8, 16)
                        or color not in (0, 2, 3, 4, 6) or compression or filt
                        or interlace not in (0, 1)):
                    raise ValueError("INVALID_PNG_IHDR")
            elif kind == b"IDAT":
                if length:
                    found_idat = True
            elif kind == b"IEND":
                if length or not found_idat or stream.read(1):
                    raise ValueError("INVALID_PNG_IEND")
                found_iend = True
                break
            chunk_index += 1
            if chunk_index > 1000000:
                raise ValueError("INVALID_PNG_CHUNK_COUNT")
    if not found_iend or not width or not height:
        raise ValueError("INVALID_PNG")
    return {"width": width, "height": height,
            "sha256": digest.hexdigest(), "bytes": total}


def _snapshot_verified(folder, manifest):
    receipt = manifest.get("snapshot")
    if not isinstance(receipt, dict) or receipt.get("filename") != "snapshot.blend":
        raise ValueError("CHECKPOINT_CONFLICT")
    path = folder / "snapshot.blend"
    if path.is_symlink() or not path.is_file() or path.stat().st_size < 256:
        raise ValueError("CHECKPOINT_MISSING")
    with path.open("rb") as stream:
        if stream.read(7) != b"BLENDER":
            raise ValueError("CHECKPOINT_INVALID")
    if (path.stat().st_size != receipt.get("bytes")
            or _hash_file(path) != receipt.get("sha256")):
        raise ValueError("CHECKPOINT_HASH_MISMATCH")
    if manifest.get("fingerprint") != _fingerprint({
            "spec": manifest.get("spec"), "snapshot": receipt}):
        raise ValueError("RENDER_MANIFEST_CONFLICT")


def _frame_name(frame):
    return "frame_%06d.png" % frame


def _receipt_name(frame):
    return "frame_%06d.receipt.json" % frame


def _verify_frame(folder, frame, spec, receipt, fingerprint):
    if not isinstance(receipt, dict) or receipt.get("filename") != _frame_name(frame):
        return False
    path = folder / _frame_name(frame)
    try:
        actual = png_proof(path)
        if (actual["bytes"] != receipt.get("bytes")
                or actual["sha256"] != receipt.get("sha256")
                or actual["width"] != spec["width"]
                or actual["height"] != spec["height"]):
            return False
        # Legacy manifests contain only filename/bytes/hash. New receipts
        # additionally bind frame and source revision, but retain compatibility.
        if ("frame" in receipt and receipt["frame"] != frame) or (
                "fingerprint" in receipt and receipt["fingerprint"] != fingerprint):
            return False
        return True
    except (OSError, ValueError, TypeError, KeyError):
        return False


def _validated_spec(manifest):
    spec = manifest.get("spec")
    if not isinstance(spec, dict):
        raise ValueError("RENDER_MANIFEST_CONFLICT")
    start, end = spec.get("start"), spec.get("end")
    if (type(start) is not int or type(end) is not int
            or not 1 <= start <= end <= 100000
            or spec.get("frame_count") != end - start + 1
            or type(spec.get("width")) is not int or type(spec.get("height")) is not int
            or not 16 <= spec["width"] <= 8192
            or not 16 <= spec["height"] <= 8192):
        raise ValueError("RENDER_MANIFEST_CONFLICT")
    return spec


def _cache_stamp(folder, manifest):
    snapshot = folder / "snapshot.blend"
    info = snapshot.stat()
    return (manifest["fingerprint"], info.st_size, info.st_mtime_ns,
            manifest["next_frame"], len(manifest["frames"]), manifest["state"])


def reconcile_manifest(folder, manifest, persist=False, cached=False):
    """Recover first missing/corrupt absolute frame without duplicating good PNGs.

    Pre-rename sidecar receipts are fsynced before the final PNG rename. If the
    process dies after PNG rename but before manifest commit, a matching sidecar
    proves source identity and safely adopts the completed frame on restart.
    """
    folder = Path(folder)
    if folder.is_symlink() or folder.name != _safe_job_id(manifest.get("job_id")):
        raise ValueError("JOB_OUTSIDE_SCOPE")
    spec = _validated_spec(manifest)
    # Real native bpy process caches full integrity scans between successive
    # frames. On an Android process restart this cache is empty and EVERY
    # old frame and the frozen Blender checkpoint is SHA-verified again.
    # Explicit status/audit calls always bypass the cache.
    if cached:
        try:
            if _JOB_CACHE.get(str(folder.resolve())) == _cache_stamp(folder, manifest):
                return manifest, {"first_missing": (
                    None if manifest["next_frame"] > spec["end"]
                    else manifest["next_frame"]),
                    "verified_frames": len(manifest["frames"]), "adopted_frames": [],
                    "invalid_receipts": [], "changed": False, "process_cache_hit": True}
        except (OSError, KeyError, TypeError):
            pass
    _snapshot_verified(folder, manifest)
    fingerprint = manifest["fingerprint"]
    old_frames = manifest.get("frames")
    if not isinstance(old_frames, dict):
        raise ValueError("RENDER_MANIFEST_CONFLICT")
    frames = {}
    adopted = []
    invalid = []
    for frame in range(spec["start"], spec["end"] + 1):
        key = str(frame)
        receipt = old_frames.get(key)
        if _verify_frame(folder, frame, spec, receipt, fingerprint):
            frames[key] = receipt
            continue
        sidecar = folder / _receipt_name(frame)
        if sidecar.is_file() and not sidecar.is_symlink() and sidecar.stat().st_size <= 4096:
            try:
                proof = json.loads(sidecar.read_text(encoding="utf8"))
                if _verify_frame(folder, frame, spec, proof, fingerprint) and (
                        proof.get("fingerprint") == fingerprint):
                    frames[key] = proof
                    adopted.append(frame)
                    continue
            except (OSError, ValueError, TypeError):
                pass
        if key in old_frames:
            invalid.append(frame)
    missing = next((f for f in range(spec["start"], spec["end"] + 1)
                    if str(f) not in frames), spec["end"] + 1)
    updated = dict(manifest)
    updated["frames"] = frames
    updated["next_frame"] = missing
    if missing <= spec["end"]:
        updated["state"] = "ready"
    elif manifest.get("state") not in ("encoded", "encoding"):
        updated["state"] = "frames_complete"
    changed = any(updated.get(k) != manifest.get(k) for k in (
        "frames", "next_frame", "state"))
    if persist and changed:
        atomic_json(folder / "manifest.json", updated)
    if persist:
        _JOB_CACHE[str(folder.resolve())] = _cache_stamp(folder, updated)
    return updated, {"first_missing": None if missing > spec["end"] else missing,
                     "verified_frames": len(frames), "adopted_frames": adopted,
                     "invalid_receipts": invalid, "changed": changed}


def commit_png(folder, manifest, frame, temporary):
    """Two-phase, fsynced commit of a Blender-rendered PNG master."""
    folder = Path(folder)
    spec = _validated_spec(manifest)
    if type(frame) is not int or not spec["start"] <= frame <= spec["end"]:
        raise ValueError("INVALID_FRAME")
    temporary = Path(temporary)
    target = folder / _frame_name(frame)
    if temporary.parent.resolve() != folder.resolve() or temporary.is_symlink():
        raise ValueError("JOB_OUTSIDE_SCOPE")
    proof = png_proof(temporary)
    if (proof["width"], proof["height"]) != (spec["width"], spec["height"]):
        raise ValueError("FRAME_DIMENSIONS_MISMATCH")
    sync_file(temporary)
    receipt = {
        "filename": target.name, "bytes": proof["bytes"], "sha256": proof["sha256"],
        "width": proof["width"], "height": proof["height"], "frame": frame,
        "fingerprint": manifest["fingerprint"],
        "engine": spec["engine"], "samples": spec["samples"],
        "fps": spec["fps"], "fps_base": spec.get("fps_base", 1.0),
        "verified_at_epoch_seconds": int(time.time()),
    }
    atomic_json(folder / _receipt_name(frame), receipt)
    os.replace(temporary, target)
    sync_directory(folder)
    manifest["frames"][str(frame)] = receipt
    manifest["next_frame"] = next((index for index in range(spec["start"], spec["end"] + 1)
                                    if str(index) not in manifest["frames"]),
                                   spec["end"] + 1)
    manifest["state"] = ("frames_complete" if manifest["next_frame"] > spec["end"]
                         else "ready")
    atomic_json(folder / "manifest.json", manifest)
    _JOB_CACHE[str(folder.resolve())] = _cache_stamp(folder, manifest)
    return receipt


def validate(operation, payload):
    if operation not in OPERATION_NAMES:
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
    if not isinstance(payload, dict):
        raise ValueError("INVALID_ARGUMENTS")
    permitted = set() if operation == OPERATION_NAMES[0] else {"job_id"}
    required = set() if operation == OPERATION_NAMES[0] else {"job_id"}
    if set(payload) - permitted or not required.issubset(payload):
        raise ValueError("INVALID_ARGUMENTS")
    if "job_id" in payload:
        _safe_job_id(payload["job_id"])
    return dict(payload)


def _native_scene(context):
    try:
        import bpy
    except ImportError as error:
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE") from error
    scene = context.get("scene") if isinstance(context, dict) else None
    if scene is None or not isinstance(scene, bpy.types.Scene):
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
    return scene


def execute(operation, payload, context):
    p = validate(operation, payload)
    scene = _native_scene(context)
    if operation == "omega.render.preflight":
        render = scene.render
        if scene.camera is None:
            raise ValueError("CAMERA_REQUIRED")
        if render.engine not in ("CYCLES", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
            raise ValueError("REQUESTED_RENDER_ENGINE_UNAVAILABLE")
        if render.engine == "CYCLES":
            settings = getattr(scene, "cycles", None)
            if settings is None:
                raise ValueError("REQUESTED_CYCLES_ENGINE_NOT_AVAILABLE")
            samples = int(settings.samples)
        else:
            settings = getattr(scene, "eevee", None)
            if settings is None:
                raise ValueError("REQUESTED_EEVEE_SAMPLE_CONTROL_UNAVAILABLE")
            samples = getattr(settings, "taa_render_samples", None)
            if samples is None:
                samples = getattr(settings, "taa_samples", None)
            if samples is None:
                raise ValueError("REQUESTED_EEVEE_SAMPLE_CONTROL_UNAVAILABLE")
        return {
            "operation": operation, "state": "succeeded", "scene": scene.name,
            "source_revision": context.get("capability_revision", "unknown"),
            "created": [], "artifact": {"kind": "none", "sha256": None},
            "native_execution_verified": True, "visual_quality_verified": False,
            "quality_reduced": False, "warnings": [],
            "engine": render.engine, "samples": int(samples),
            "requested_width": render.resolution_x,
            "requested_height": render.resolution_y,
            "resolution_percentage": render.resolution_percentage,
            "fps": render.fps, "fps_base": render.fps_base,
        }
    folder = _safe_job_folder(context["production_root"], p["job_id"])
    path = folder / "manifest.json"
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("RENDER_MANIFEST_UNAVAILABLE")
    manifest = json.loads(path.read_text(encoding="utf8"))
    if manifest.get("job_id") != p["job_id"]:
        raise ValueError("RENDER_MANIFEST_CONFLICT")
    revised, audit_result = reconcile_manifest(folder, manifest, persist=False)
    return {
        "operation": operation, "state": "succeeded", "scene": scene.name,
        "source_revision": revised["fingerprint"], "created": [],
        "artifact": {"kind": "blend", "sha256": revised["snapshot"]["sha256"]},
        "native_execution_verified": True, "visual_quality_verified": False,
        "quality_reduced": False, "warnings": [],
        "job_id": p["job_id"], "job_state": revised["state"],
        "next_frame": revised["next_frame"], **audit_result,
    }


def audit(operation, payload, context):
    return execute(operation, payload, context)
