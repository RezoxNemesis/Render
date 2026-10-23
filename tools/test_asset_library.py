"""Host filesystem/network-boundary tests. No Blender or Android output claimed."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/'full-app/scripts/render_asset_library.py'
spec=importlib.util.spec_from_file_location('asset_library_under_test',SCRIPT)
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)

class Response(io.BytesIO):
    def __init__(self,data,status=200,headers=None):
        super().__init__(data);self.status=status;self.headers=headers or {}

class AssetLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.folder=self.root/'download';self.folder.mkdir()
        self.data=b'original-full-resolution-asset'*100
        self.item={'filename':'model.blend','bytes':len(self.data),
                   'md5':hashlib.md5(self.data).hexdigest(),
                   'url':'https://dl.polyhaven.org/file/ph-assets/model.blend'}
        self.stop=threading.Event()

    def test_https_host_and_redirect_boundaries(self):
        for url in ('http://dl.polyhaven.org/a','https://evil.test/a',
                    'https://api.polyhaven.com.evil.test/a','https://user@api.polyhaven.com/a',
                    'https://api.polyhaven.com:444/a','https://api.polyhaven.com/a#secret'):
            with self.subTest(url=url),self.assertRaises(ValueError):A._url(url)
        self.assertEqual(self.item['url'],A._url(self.item['url']))
        handler=A._Redirects()
        with self.assertRaises(ValueError):
            handler.redirect_request(None,None,302,'',{},'https://evil.test/a')

    def test_dependency_paths_and_symlink_escape_rejected(self):
        for name in ('../a','/outside','textures/../../a','textures\\a',''):
            with self.subTest(name=name),self.assertRaises(ValueError):A._relative(self.folder,name)
        (self.folder/'textures').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):A._relative(self.folder,'textures/a.png')

    def test_provider_plan_keeps_requested_resolution_and_dependencies(self):
        entry=dict(self.item,size=len(self.data),include={'textures/color.png':dict(self.item,size=len(self.data),url=self.item['url']+'.png')})
        details={'blend':{'4k':{'blend':entry}}}
        main,files=A.file_plan(details,'grass_01','4k','models')
        self.assertEqual('grass_01_4k.blend',main);self.assertEqual(2,len(files))
        with self.assertRaisesRegex(ValueError,'REQUESTED_ASSET_RESOLUTION_UNAVAILABLE'):
            A.file_plan(details,'grass_01','16k','models')

    def test_download_verifies_bytes_before_atomic_publication(self):
        target=self.folder/'model.blend';seen=[]
        with patch.object(A,'_request',return_value=Response(self.data)):
            A._download_file(target,self.item,self.stop,seen.append)
        self.assertEqual(self.data,target.read_bytes());self.assertEqual(len(self.data),seen[-1])
        self.assertFalse(target.with_name(target.name+'.partial').exists())

    def test_incomplete_corrupt_and_oversized_responses_never_publish(self):
        for data in (b'truncated',b'x'*len(self.data),self.data+b'x'):
            target=self.folder/'model.blend'
            with self.subTest(length=len(data)),patch.object(A,'_request',return_value=Response(data)):
                with self.assertRaises(ValueError):A._download_file(target,self.item,self.stop,lambda n:None)
                self.assertFalse(target.exists())

    def test_range_resume_and_server_ignoring_range_both_preserve_original(self):
        target=self.folder/'model.blend';part=target.with_name(target.name+'.partial')
        for supports_range in (True,False):
            part.write_bytes(self.data[:15])
            if target.exists():target.unlink()
            response=Response(self.data[15:] if supports_range else self.data,
                              206 if supports_range else 200,{'Content-Range':'bytes 15-%d/%d'%(len(self.data)-1,len(self.data))})
            with patch.object(A,'_request',return_value=response) as request:
                A._download_file(target,self.item,self.stop,lambda n:None)
                self.assertEqual({'Range':'bytes=15-'},request.call_args.args[1])
            self.assertEqual(self.data,target.read_bytes())

    def test_pause_retains_partial_and_existing_verified_file_skips_network(self):
        target=self.folder/'model.blend';self.stop.set()
        with patch.object(A,'_request',return_value=Response(self.data)):
            with self.assertRaises(InterruptedError):A._download_file(target,self.item,self.stop,lambda n:None)
        self.assertFalse(target.exists())
        target.write_bytes(self.data)
        with patch.object(A,'_request') as request:
            A._download_file(target,self.item,self.stop,lambda n:None);request.assert_not_called()

    def test_storage_pressure_does_not_substitute_smaller_asset(self):
        target=self.folder/'model.blend'
        with patch.object(A,'_request',return_value=Response(self.data)),patch.object(A.shutil,'disk_usage',return_value=type('Disk',(),{'free':100})()):
            with self.assertRaisesRegex(OSError,'ASSET_DOWNLOAD_STORAGE_PRESSURE'):
                A._download_file(target,self.item,self.stop,lambda n:None)
        self.assertFalse(target.exists())

    def test_restart_marks_incomplete_worker_interrupted_and_bounds_receipt(self):
        job='d'*32;folder=A._library(self.root)/job;folder.mkdir()
        report={'state':'downloading','files':[dict(self.item,sha256='a'*64)],'download_id':job}
        (folder/'download.json').write_text(json.dumps(report))
        result=A.status(self.root,{'download_id':job})
        self.assertEqual('interrupted',result['state']);self.assertNotIn('url',result['files'][0])

    def test_search_filters_license_metadata_and_has_no_network_on_cache_hit(self):
        catalog={'grass_01':{'name':'Grass','type':2,'tags':['grass'],'categories':['nature'],'authors':{'Artist':'All'}},
                 'studio':{'name':'Studio','type':0,'tags':[],'categories':[]}}
        with patch.object(A,'_CATALOG',catalog),patch.object(A,'_CATALOG_THREAD',None),patch.object(A,'_request') as request:
            result=A.search(self.root,{'query':'grass','kind':'models'})
            request.assert_not_called();self.assertEqual(1,result['total_matches'])
            self.assertEqual('CC0-1.0',result['results'][0]['license']);self.assertTrue(result['catalog_is_finite'])

if __name__=='__main__':unittest.main()
