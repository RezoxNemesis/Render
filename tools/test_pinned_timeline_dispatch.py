"""Guard and payload-preservation tests; fixture is not a functioning engine."""
import hashlib
import struct
import unittest
from patch_pinned_timeline_dispatch import SITES, _patch_elf_bytes


class TimelinePatchTests(unittest.TestCase):
    def fixture(self):
        data = bytearray(b'unchanged-payload'*1024)
        data[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', data, 18, 183)
        struct.pack_into('<Q', data, 32, 64)
        struct.pack_into('<HH', data, 54, 56, 1)
        struct.pack_into('<IIQQQQQQ', data, 64, 1, 5, 4096, 0x5fc0000, 0, 12288, 12288, 4096)
        for address, reg in SITES:
            offset = 4096+address-0x5fc0000
            struct.pack_into('<II', data, offset,
                             0xf9400000 | ((0x66c0//8)<<10) | (reg<<5) | 8,
                             0xd63f0100)
        return data

    def transform(self, data):
        return _patch_elf_bytes(data, hashlib.sha256(data).hexdigest())

    def test_changes_only_counter_loads_and_preserves_all_other_payload(self):
        original = self.fixture()
        changed, proof = self.transform(original)
        self.assertEqual(8, len(proof))
        allowed = set()
        for item in proof:
            offset = item['file_offset']
            allowed.update(range(offset, offset+4))
            word = struct.unpack_from('<I', changed, offset)[0]
            self.assertEqual(0x5c30, ((word>>10)&0xfff)*8)
            self.assertEqual(0xd63f0100, struct.unpack_from('<I', changed, offset+4)[0])
        actual = {i for i, (a, b) in enumerate(zip(original, changed)) if a != b}
        self.assertTrue(actual <= allowed)
        self.assertEqual(16, len(actual))
        self.assertEqual(len(original), len(changed))

    def test_rejects_unknown_library_before_modification(self):
        data = self.fixture()
        before = bytes(data)
        with self.assertRaisesRegex(ValueError, 'SHA256_MISMATCH'):
            _patch_elf_bytes(data)
        self.assertEqual(before, data)

    def test_rejects_wrong_abi_and_nonexecutable_sites(self):
        data = self.fixture()
        struct.pack_into('<H', data, 18, 62)
        with self.assertRaisesRegex(ValueError, 'NOT_ARM64_ELF'):
            self.transform(data)
        data = self.fixture()
        struct.pack_into('<I', data, 68, 4)
        with self.assertRaisesRegex(ValueError, 'OUTSIDE_EXECUTABLE'):
            self.transform(data)

    def test_rejects_unexpected_instruction_and_missing_call(self):
        for delta in (0, 4):
            data = self.fixture()
            at = 4096+SITES[0][0]-0x5fc0000+delta
            struct.pack_into('<I', data, at, 0xd503201f)
            with self.assertRaisesRegex(ValueError, 'INSTRUCTION_MISMATCH'):
                self.transform(data)


if __name__ == '__main__':
    unittest.main()
