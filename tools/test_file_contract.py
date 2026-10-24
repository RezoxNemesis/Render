"""Original-byte, image-admission and bundle-integrity checks; no bpy or rendered assets."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import render_file_contract as F

class FileContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'Imports').mkdir()
    def original(self,data,extension):
        sha=hashlib.sha256(data).hexdigest();name=sha+'.'+extension
        path=self.root/'Imports'/name;path.write_bytes(data);return path,name,sha
    def test_original_digest_and_scope_are_required(self):
        path,name,sha=self.original(b'owner original bytes','glb')
        self.assertEqual(path,F.original(self.root,name,sha))
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'INTEGRITY'):F.original(self.root,name,sha)
        for name in ('../private','/absolute','a.glb'):
            with self.assertRaises(ValueError):F.original(self.root,name,sha)
    def test_memory_admission_never_resizes_original(self):
        header=b'\x89PNG\r\n\x1a\n'+struct.pack('>I',13)+b'IHDR'+struct.pack('>II',8192,4096)+b'\x08\x06\0\0\0'
        path,_,_=self.original(header,'png')
        self.assertEqual((8192,4096),F.image_header(path))
        with self.assertRaisesRegex(ValueError,'MEMORY_BUDGET'):F.image_budget(path,128*1024**2)
        self.assertEqual((8192,4096,1024**3),F.image_budget(path,1024**3));self.assertEqual(header,path.read_bytes())
    def test_hdr_exr_and_tiff_dimensions_without_decoding(self):
        path,_,_=self.original(b'#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 512 +X 1024\n','hdr')
        self.assertEqual((1024,512),F.image_header(path))
        data=b'v/1\x01'+struct.pack('<I',2)+b'dataWindow\0box2i\0'+struct.pack('<Iiiii',16,0,0,2047,1023)+b'\0'
        path,_,_=self.original(data,'exr');self.assertEqual((2048,1024),F.image_header(path))
        data=b'II'+struct.pack('<HIH',42,8,2)+struct.pack('<HHII',256,4,1,640)+struct.pack('<HHII',257,4,1,480)
        path,_,_=self.original(data,'tiff');self.assertEqual((640,480),F.image_header(path))
    def test_bundle_entry_is_verified_and_dependency_tamper_is_rejected(self):
        _,name,sha=self.original(b'zip-byte-fixture','zip');directory=self.root/'Imports/Bundles'/sha
        (directory/'models').mkdir(parents=True);file=directory/'models/body.obj';file.write_bytes(b'asset-byte-fixture')
        entry={'path':'models/body.obj','bytes':file.stat().st_size,'sha256':F.digest(file)}
        (directory/'_render_bundle_manifest.json').write_text(json.dumps({'original_sha256':sha,'entries':[entry]}))
        self.assertEqual((file,directory),F.source(self.root,{'filename':name,'expected_sha256':sha,'entry':'models/body.obj'},True))
        file.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'INTEGRITY'):F.source(self.root,{'filename':name,'expected_sha256':sha,'entry':'models/body.obj'},True)
    def test_bundle_paths_reject_traversal_and_symlink(self):
        for entry in ('../secret','/root','a\\b','a//b','a/../b','C:/private','_render_bundle_manifest.json'):
            with self.assertRaises(ValueError):F.relative(entry)
        outside=self.root/'outside';outside.write_bytes(b'preserved')
        (self.root/'Imports/link').symlink_to(outside)
        with self.assertRaisesRegex(ValueError,'SYMLINK'):F.scoped(self.root/'Imports','link')

if __name__=='__main__':unittest.main()
