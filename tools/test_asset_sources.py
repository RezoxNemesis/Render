"""Offline metadata/archive regressions. No Blender, asset import or network."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile
import render_asset_library as L
import render_asset_sources as S

class AssetSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.folder=self.root/'download';self.folder.mkdir()
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:z.writestr('Material_Color.png',b'opaque-original-texture-bytes')
        self.data=data.getvalue();self.item={'size':len(self.data),'downloadLink':'https://ambientcg.com/get?file=fixture.zip'}
        self.report={'download_id':'a'*32,'files':[]}
    def test_complete_partial_is_verified_and_finalized_without_invalid_range_request(self):
        (self.folder/'original.zip.part').write_bytes(self.data)
        (self.folder/'resume.json').write_text(json.dumps({'etag':'fixture','size':len(self.data)}))
        with patch.object(L,'_request',side_effect=AssertionError('must not request bytes=size-')):
            S._archive(self.folder,self.item,self.report,threading.Event())
        self.assertEqual(self.data,(self.folder/'original.zip').read_bytes())
        self.assertEqual(2,len(self.report['files']))
        self.assertEqual(hashlib.sha256(self.data).hexdigest(),self.report['files'][0]['sha256'])
    def test_interrupted_extraction_reuses_locally_hash_bound_original(self):
        (self.folder/'original.zip').write_bytes(self.data)
        self.report['_retained_files']=[{'filename':'original.zip','bytes':len(self.data),
            'sha256':hashlib.sha256(self.data).hexdigest()}]
        with patch.object(L,'_request',side_effect=AssertionError('original must be reused')):
            S._archive(self.folder,self.item,self.report,threading.Event())
        self.assertEqual(b'opaque-original-texture-bytes',(self.folder/'Originals/Material_Color.png').read_bytes())
    def test_old_extraction_temporary_symlink_cannot_truncate_another_file(self):
        (self.folder/'original.zip.part').write_bytes(self.data)
        originals=self.folder/'Originals';originals.mkdir();victim=self.root/'artist-project.blend';victim.write_bytes(b'unchanged')
        (originals/'Material_Color.png.part').symlink_to(victim)
        with patch.object(L,'_request',side_effect=AssertionError('local ZIP only')):
            S._archive(self.folder,self.item,self.report,threading.Event())
        self.assertEqual(b'unchanged',victim.read_bytes())
        self.assertEqual(b'opaque-original-texture-bytes',(originals/'Material_Color.png').read_bytes())
    def test_merged_limit_one_never_duplicates_or_exceeds_the_limit(self):
        def poly(root,p):
            return {'state':'ready','provider':'Poly Haven','results':[{'id':'poly','license':'CC0-1.0'}] if p.get('offset',0)==0 else [],'total_matches':1}
        def ambient(root,p):
            return {'state':'ready','provider':'AmbientCG','results':[{'id':'ambient','license':'CC0-1.0'}] if p.get('offset',0)==0 else [],'total_matches':1}
        with patch.object(L,'_poly_search',side_effect=poly),patch.object(S,'ambient_search',side_effect=ambient):
            first=L.search(self.root,{'limit':1,'offset':0});second=L.search(self.root,{'limit':1,'offset':1})
        self.assertEqual(['poly'],[v['id'] for v in first['results']]);self.assertEqual(['ambient'],[v['id'] for v in second['results']])
        self.assertTrue(first['catalog_is_finite']);self.assertIsNone(second['next_offset'])
    def test_both_unavailable_providers_cannot_be_reported_ready(self):
        unavailable={'state':'unavailable','results':[],'total_matches':0}
        with patch.object(L,'_poly_search',return_value=dict(unavailable,provider='Poly Haven')),patch.object(S,'ambient_search',return_value=dict(unavailable,provider='AmbientCG')):
            self.assertEqual('unavailable',L.search(self.root,{})['state'])

if __name__=='__main__':unittest.main()
