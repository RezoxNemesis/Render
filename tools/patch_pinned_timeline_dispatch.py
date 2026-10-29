#!/usr/bin/env python3
"""Exact, source-equivalent ARM64 fix for the pinned Android alpha-4 engine.

The source patch is shipped beside the binary provenance. Unknown binaries are
never modified. This preserves the full engine and its existing KHR fallback.
"""
import hashlib
import json
from pathlib import Path
import struct

ORIGINAL_SHA256 = '35bec73f5bfc21179221686f383bfcf92c5b08d3f0f471f74b167a142b6691b9'
PATCHED_SHA256 = 'a87b805df88ab64b4af21baac98bf380de9b0a1d90ac5525c082c5aceac29d59'
SITES = ((0x5fc11c8, 19), (0x5fc11f8, 19), (0x5fc1250, 19),
         (0x5fc12a8, 19), (0x5fc1300, 19), (0x5fc1358, 19),
         (0x5fc19c8, 25), (0x5fc1e68, 9))


def _patch_elf_bytes(original, expected_sha256=ORIGINAL_SHA256):
    """Private byte transformation; alternate digest is for synthetic ELF tests."""
    if hashlib.sha256(original).hexdigest() != expected_sha256:
        raise ValueError('TIMELINE_ENGINE_SHA256_MISMATCH')
    if (len(original) < 64 or original[:6] != b'\x7fELF\x02\x01'
            or struct.unpack_from('<H', original, 18)[0] != 183):
        raise ValueError('TIMELINE_ENGINE_NOT_ARM64_ELF')
    phoff = struct.unpack_from('<Q', original, 32)[0]
    size, count = struct.unpack_from('<HH', original, 54)
    if size != 56 or not 1 <= count <= 128 or phoff+size*count > len(original):
        raise ValueError('TIMELINE_ENGINE_INVALID_SEGMENTS')
    segments = [struct.unpack_from('<IIQQQQQQ', original, phoff+i*size)
                for i in range(count)]
    patched = bytearray(original)
    changes = []
    for address, base_register in SITES:
        matches = [s for s in segments if s[0] == 1 and s[1] & 1
                   and s[3] <= address and address+36 <= s[3]+s[5]]
        if len(matches) != 1:
            raise ValueError('TIMELINE_CALL_OUTSIDE_EXECUTABLE_SEGMENT')
        segment = matches[0]
        offset = segment[2]+address-segment[3]
        if offset+36 > len(original):
            raise ValueError('TIMELINE_CALL_OUTSIDE_FILE')
        old = 0xf9400000 | ((0x66c0//8) << 10) | (base_register << 5) | 8
        new = 0xf9400000 | ((0x5c30//8) << 10) | (base_register << 5) | 8
        following = [struct.unpack_from('<I', original, at)[0]
                     for at in range(offset+4, offset+36, 4)]
        if (struct.unpack_from('<I', original, offset)[0] != old
                or 0xd63f0100 not in following):
            raise ValueError('TIMELINE_CALL_INSTRUCTION_MISMATCH')
        struct.pack_into('<I', patched, offset, new)
        changes.append({'virtual_address': hex(address), 'file_offset': offset,
                        'old_instruction': hex(old), 'new_instruction': hex(new)})
    return bytes(patched), changes


def apply_pinned_fix(library, notices):
    library, notices = Path(library), Path(notices)
    source_patch = Path(__file__).resolve().parents[1] / 'patches/blender-timeline-core.patch'
    if not source_patch.is_file():
        raise ValueError('TIMELINE_CORRESPONDING_SOURCE_PATCH_MISSING')
    original = library.read_bytes()
    patched, changes = _patch_elf_bytes(original)
    if hashlib.sha256(patched).hexdigest() != PATCHED_SHA256:
        raise ValueError('TIMELINE_PATCHED_ENGINE_SHA256_MISMATCH')
    # This path is a generated staging library, not the verified input APK.
    temporary = library.with_name(library.name+'.timeline-stage')
    temporary.write_bytes(patched)
    temporary.replace(library)
    notices.mkdir(parents=True, exist_ok=True)
    (notices/source_patch.name).write_bytes(source_patch.read_bytes())
    proof = {'patch': 'render-timeline-core-v1',
             'upstream_commit': 'd93bd33cba768e19ee4387a31c0ea137ee2f0047',
             'source_patch': source_patch.name,
             'original_library_sha256': ORIGINAL_SHA256,
             'patched_library_sha256': PATCHED_SHA256,
             'source_equivalent_instruction_changes': changes,
             'engine_features_removed': False,
             'native_editor_readiness_proven_by_packaging': False}
    (notices/'Render-Native-Engine-Patches.json').write_text(json.dumps(proof, indent=2)+'\n')
    return proof
