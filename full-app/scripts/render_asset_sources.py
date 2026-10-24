# SPDX-License-Identifier: GPL-2.0-or-later
"""Additional public CC0 catalog metadata, preview cache and native PBR import.

All network and archive work runs off Blender's main thread; only import calls bpy.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import threading
import time
from urllib.parse import urlencode
import zipfile
import os
import tempfile

_TASKS = {}
_ERRORS = {}
_LOCK = threading.RLock()
_ATTEMPTS = {}


def _cache(root):
    import render_asset_library as L
    folder=L._library(root)/'Metadata'
    if folder.is_symlink():raise ValueError('ASSET_METADATA_SYMLINK')
    folder.mkdir(exist_ok=True,mode=0o700)
    return folder


def _cached(root,key,fetch,ttl=86400):
    import render_asset_library as L
    path=_cache(root)/(hashlib.sha256(key.encode()).hexdigest()+'.json')
    previous=None
    if path.is_file() and not path.is_symlink() and path.stat().st_size<12*1024*1024:
        try:previous=json.loads(path.read_text())
        except (OSError,ValueError):pass
    fresh=previous is not None and time.time()-path.stat().st_mtime<ttl
    def work():
        try:
            L._atomic(path,fetch())
            with _LOCK:_ERRORS.pop(key,None)
        except Exception as error:
            with _LOCK:_ERRORS[key]=type(error).__name__
    with _LOCK:
        active=_TASKS.get(key)
        if not fresh and not (active and active.is_alive()) and time.monotonic()-_ATTEMPTS.get(key,-1e9)>30:
            _ATTEMPTS[key]=time.monotonic()
            active=threading.Thread(target=work,daemon=True);_TASKS[key]=active;active.start()
        loading=bool(active and active.is_alive())
        error=_ERRORS.get(key,'')
    return previous,loading,error


def ambient_search(root,p):
    import render_asset_library as L
    query=p.get('query','');kind=p.get('kind','all');limit=p.get('limit',20);offset=p.get('offset',0)
    dtype={'textures':'Material','hdris':'HDRI','models':'3DModel'}.get(kind)
    params={'q':query,'limit':limit,'offset':offset,'include':'downloadData,previewData'}
    if dtype:params['type']=dtype
    url='https://ambientcg.com/api/v2/full_json?'+urlencode(params)
    data,loading,error=_cached(root,url,lambda:L._json_url(url))
    results=[]
    for asset in (data or {}).get('foundAssets',[]):
        ident=asset.get('assetId','')
        if not isinstance(ident,str) or not L._ASSET.fullmatch(ident):continue
        formats=[]
        for folder in asset.get('downloadFolders',{}).values():
            for category in folder.get('downloadFiletypeCategories',{}).values():
                for item in category.get('downloads',[]):
                    formats.append({'format':item.get('attribute'),'bytes':item.get('size'),
                                    'container':item.get('filetype')})
        kind={'Material':'textures','HDRI':'hdris','3DModel':'models'}.get(asset.get('dataType'),'unknown')
        results.append({'id':'ambientcg__'+ident,'asset_id':ident,'name':asset.get('displayName',ident),
                        'kind':kind,'provider':'AmbientCG','license':'CC0-1.0',
                        'license_url':'https://docs.ambientcg.com/license/',
                        'source_url':'https://ambientcg.com/a/'+ident,
                        'preview_url':asset.get('previewImage',{}).get('256-PNG'),
                        'formats':formats[:48],
                        'native_import_available':kind=='textures',
                        'unavailable_reason':None if kind=='textures' else 'USE_POLY_HAVEN_OR_EXPLICIT_NATIVE_FILE_IMPORT'})
    return {'state':'loading' if loading else 'ready' if data else 'unavailable',
            'results':results,'total_matches':(data or {}).get('numberOfResults',0),
            'network_error':error,'provider':'AmbientCG','catalog_is_finite':True}


def _asset_details(root,ident):
    import render_asset_library as L
    url='https://ambientcg.com/api/v2/full_json?'+urlencode({'id':ident,'include':'downloadData,previewData','limit':1})
    data,loading,error=_cached(root,url,lambda:L._json_url(url))
    items=(data or {}).get('foundAssets',[])
    found=next((a for a in items if a.get('assetId')==ident),None)
    return found,loading,error


def details(root,p):
    import render_asset_library as L
    L._fields(p,('asset_id',),('asset_id',))
    ident=p['asset_id']
    ambient=isinstance(ident,str) and ident.startswith('ambientcg__')
    native=ident[11:] if ambient else ident
    if not isinstance(native,str) or not L._ASSET.fullmatch(native):raise ValueError('INVALID_ASSET_ID')
    if ambient:
        data,loading,error=_asset_details(root,native)
        if not data:return {'state':'loading' if loading else 'unavailable','network_error':error}
        formats=[]
        for folder in data.get('downloadFolders',{}).values():
            for group in folder.get('downloadFiletypeCategories',{}).values():
                formats += [{'format':f.get('attribute'),'bytes':f.get('size'),'container':f.get('filetype')}
                            for f in group.get('downloads',[])]
        return {'state':'ready','asset_id':ident,'provider':'AmbientCG','license':'CC0-1.0',
                'license_url':'https://docs.ambientcg.com/license/', 'formats':formats[:64],
                'preview_url':data.get('previewImage',{}).get('256-PNG'),
                'publisher_digest_available':False,'native_import_available':data.get('dataType')=='Material'}
    url='https://api.polyhaven.com/files/'+native
    data,loading,error=_cached(root,url,lambda:L._json_url(url))
    formats=[]
    if data:
        for section,versions in data.items():
            if not isinstance(versions,dict):continue
            for resolution,variants in versions.items():
                if not isinstance(variants,dict):continue
                for form,item in variants.items():
                    if not isinstance(item,dict) or type(item.get('size')) is not int:continue
                    dependencies=sum(x.get('size',0) for x in item.get('include',{}).values())
                    formats.append({'section':section,'resolution':resolution,'format':form,
                                    'bytes':item['size']+dependencies,'includes_dependencies':True})
    return {'state':'loading' if loading and not data else 'ready' if data else 'unavailable',
            'asset_id':ident,'provider':'Poly Haven','license':'CC0-1.0',
            'license_url':'https://polyhaven.com/license','formats':formats[:256],
            'publisher_digest_available':True,'network_error':error,
            'preview_url':'https://cdn.polyhaven.com/asset_img/thumbs/'+native+'.png?width=256'}


def preview(root,p):
    import render_asset_library as L
    result=details(root,p)
    if result.get('state')!='ready':return result
    ident=p['asset_id'];url=L._url(result['preview_url'])
    folder=L._library(root)/'Previews'
    if folder.is_symlink():raise ValueError('ASSET_PREVIEW_SYMLINK')
    folder.mkdir(exist_ok=True,mode=0o700)
    path=folder/(hashlib.sha256(ident.encode()).hexdigest()+'.png')
    if path.is_symlink():raise ValueError('ASSET_PREVIEW_SYMLINK')
    def fetch():
        with L._request(url) as response:
            data=response.read(2*1024*1024+1)
            if len(data)>2*1024*1024:raise ValueError('ASSET_PREVIEW_TOO_LARGE')
            if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('ASSET_PREVIEW_FORMAT_UNSUPPORTED')
        fd,name=tempfile.mkstemp(prefix='.render-preview-',dir=folder)
        temp=Path(name)
        with os.fdopen(fd,'wb') as output:
            output.write(data);output.flush();os.fsync(output.fileno())
        temp.replace(path)
    key='preview:'+ident
    with _LOCK:
        task=_TASKS.get(key)
        if not path.is_file() and not (task and task.is_alive()) and time.monotonic()-_ATTEMPTS.get(key,-1e9)>30:
            _ATTEMPTS[key]=time.monotonic()
            def work():
                try:fetch()
                except Exception as error:
                    with _LOCK:_ERRORS[key]=type(error).__name__
            task=threading.Thread(target=work,daemon=True);_TASKS[key]=task;task.start()
    return {'asset_id':ident,'state':'ready' if path.is_file() else 'loading',
            'preview_file':str(path) if path.is_file() else None,
            'preview_only':True,'original_asset_untouched':True,'error':_ERRORS.get(key,'')}


def download(root,p):
    import render_asset_library as L
    L._fields(p,('asset_id','kind','resolution','format'),('asset_id','kind','resolution'))
    ident=p['asset_id'][11:];resolution=p['resolution'];form=p.get('format','PNG')
    if not L._ASSET.fullmatch(ident) or resolution not in L._RESOLUTIONS or p['kind']!='textures' or form not in ('PNG','JPG'):
        raise ValueError('AMBIENTCG_IMPORT_SUPPORTS_EXPLICIT_PBR_TEXTURE_ZIPS')
    asset,loading,error=_asset_details(root,ident)
    if not asset:raise ValueError('ASSET_DETAILS_LOADING_POLL_BEFORE_DOWNLOAD' if loading else 'ASSET_DETAILS_UNAVAILABLE')
    requested=resolution.upper()+'-'+form
    files=[f for folder in asset.get('downloadFolders',{}).values()
           for category in folder.get('downloadFiletypeCategories',{}).values() for f in category.get('downloads',[])]
    item=next((f for f in files if f.get('attribute')==requested and f.get('filetype')=='zip'),None)
    if not item:raise ValueError('REQUESTED_ASSET_RESOLUTION_UNAVAILABLE')
    job=hashlib.sha256(('ambientcg:'+ident+':'+requested).encode()).hexdigest()[:32]
    folder=L._library(root)/job
    if folder.is_symlink():raise ValueError('ASSET_LIBRARY_SYMLINK')
    folder.mkdir(exist_ok=True,mode=0o700)
    with L._LOCK:
        running=L._JOBS.get(job)
        if running and running[0].is_alive():return L.status(root,{'download_id':job})
        receipt=folder/'download.json'
        previous={}
        if receipt.is_file() and not receipt.is_symlink() and receipt.stat().st_size<131072:
            previous=json.loads(receipt.read_text())
            if previous.get('state')=='downloaded':return L.status(root,{'download_id':job})
        if any(t.is_alive() for t,_ in L._JOBS.values()):raise ValueError('ANOTHER_ASSET_DOWNLOAD_RUNNING')
        report={'download_id':job,'asset_id':ident,'kind':'textures','provider':'AmbientCG',
                'license':'CC0-1.0','source_url':'https://ambientcg.com/a/'+ident,
                'resolution':resolution,'format':form,'state':'preparing','downloaded_bytes':0,
                'total_bytes':item['size'],'publisher_digest_available':False,'originals_preserved':True}
        report['_retained_files']=previous.get('files',[])
        stop=threading.Event()
        def work():
            try:
                _archive(folder,item,report,stop)
                report.pop('_retained_files',None)
                report.update(state='downloaded',error='')
            except Exception as error:
                report.update(state='paused' if isinstance(error,InterruptedError) else 'failed',
                              error=str(error) if re.fullmatch(r'[A-Z_]{3,96}',str(error)) else type(error).__name__)
            L._atomic(receipt,report)
        L._atomic(receipt,report)
        thread=threading.Thread(target=work,daemon=True);L._JOBS[job]=(thread,stop);thread.start()
    return {'download_id':job,'state':'preparing','native_import_completed':False}


def _archive(folder,item,report,stop):
    import render_asset_library as L
    size=item['size']
    if type(size) is not int or not 1<=size<=8*1024**3:raise ValueError('ASSET_ARCHIVE_SIZE_UNSUPPORTED')
    part=L._relative(folder,'original.zip.part');validator=folder/'resume.json'
    previous=json.loads(validator.read_text()) if validator.is_file() and not validator.is_symlink() else {}
    offset=part.stat().st_size if part.is_file() and previous.get('etag') else 0
    headers={'Range':'bytes=%d-'%offset,'If-Range':previous['etag']} if offset else {}
    archive=L._relative(folder,'original.zip')
    retained=next((f for f in report.get('_retained_files',[]) if f.get('filename')=='original.zip'),{})
    reuse=(archive.is_file() and archive.stat().st_size==size and retained.get('bytes')==size
           and retained.get('sha256')==L._digest(archive))
    if not reuse:
        if not part.is_file() or part.stat().st_size!=size:
            if offset>=size:offset=0;headers={}
            with L._request(item['downloadLink'],headers) as response:
                etag=response.headers.get('ETag','')
                if offset and (response.status!=206 or etag!=previous.get('etag') or not response.headers.get('Content-Range','').startswith('bytes %d-'%offset)):
                    if response.status!=200:raise ValueError('INVALID_ASSET_RESUME_RESPONSE')
                    offset=0
                L._atomic(validator,{'etag':etag,'size':size})
                with os.fdopen(os.open(part,os.O_WRONLY|os.O_CREAT|(os.O_APPEND if offset else os.O_TRUNC)|getattr(os,'O_NOFOLLOW',0),0o600),'ab' if offset else 'wb') as output:
                    done=offset;last=0
                    while True:
                        if stop.is_set():raise InterruptedError('ASSET_DOWNLOAD_PAUSED')
                        data=response.read(256*1024)
                        if not data:break
                        done+=len(data)
                        if done>size:raise ValueError('ASSET_DOWNLOAD_SIZE_MISMATCH')
                        if shutil.disk_usage(folder).free<len(data)+128*1024**2:raise ValueError('ASSET_DOWNLOAD_STORAGE_PRESSURE')
                        output.write(data);report['downloaded_bytes']=done
                        if time.monotonic()-last>.5:L._atomic(folder/'download.json',report);last=time.monotonic()
                    output.flush()
                    os.fsync(output.fileno())
        if part.stat().st_size!=size:raise ValueError('ASSET_DOWNLOAD_SIZE_MISMATCH')
        part.replace(archive)
    report['files']=[{'filename':'original.zip','bytes':size,'sha256':L._digest(archive)}]
    report['state']='extracting'
    L._atomic(folder/'download.json',report)
    with zipfile.ZipFile(archive) as z:
        entries=z.infolist()
        total=sum(e.file_size for e in entries)
        if len(entries)>128 or total>8*1024**3 or shutil.disk_usage(folder).free<total+128*1024**2:
            raise ValueError('ASSET_ARCHIVE_STORAGE_PRESSURE')
        for entry in entries:
            if stop.is_set():raise InterruptedError('ASSET_DOWNLOAD_PAUSED')
            if entry.is_dir():continue
            if stat.S_IFMT(entry.external_attr>>16) not in (0,stat.S_IFREG):raise ValueError('ASSET_ARCHIVE_SPECIAL_FILE')
            path=L._relative(folder,'Originals/'+entry.filename)
            if path.suffix.lower() not in ('.png','.jpg','.jpeg','.txt','.json','.usda'):raise ValueError('ASSET_ARCHIVE_FORMAT_UNSUPPORTED')
            path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            fd,name=tempfile.mkstemp(prefix='.render-unpack-',dir=path.parent)
            temporary=Path(name)
            with z.open(entry) as src,os.fdopen(fd,'wb') as dst:
                shutil.copyfileobj(src,dst,256*1024)
            temporary.replace(path)
            report['files'].append({'filename':str(path.relative_to(folder)),
                                    'bytes':path.stat().st_size,'sha256':L._digest(path)})
            L._atomic(folder/'download.json',report)
    report.update(integrity='HTTPS + provider size + ZIP CRC + local SHA-256; no publisher digest supplied')


def import_material(scene,root,report):
    import bpy
    import render_asset_library as L
    folder=L._library(root)/report['download_id']
    for item in report['files']:
        path=L._relative(folder,item['filename'])
        if not path.is_file() or path.stat().st_size!=item['bytes'] or L._digest(path)!=item['sha256']:
            raise ValueError('ASSET_LOCAL_INTEGRITY_FAILED')
    existing=next((m for m in bpy.data.materials if m.get('render_asset_download_id')==report['download_id']),None)
    if existing:return {'material':existing.name,'already_imported':True}
    material=bpy.data.materials.new('CC0_'+report['asset_id']);material.use_nodes=True;material.use_fake_user=True
    shader=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    try:
        for item in report['files']:
            path=L._relative(folder,item['filename']);stem=path.stem.lower()
            if path.suffix.lower() not in ('.png','.jpg','.jpeg'):continue
            socket='Base Color' if '_color' in stem else 'Roughness' if '_roughness' in stem else 'Metallic' if '_metalness' in stem else None
            normal='_normalgl' in stem
            if not socket and not normal:continue
            image=bpy.data.images.load(str(path),check_existing=True)
            if socket!='Base Color':image.colorspace_settings.name='Non-Color'
            image.pack();tex=material.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image
            if normal:
                node=material.node_tree.nodes.new('ShaderNodeNormalMap')
                material.node_tree.links.new(tex.outputs['Color'],node.inputs['Color'])
                material.node_tree.links.new(node.outputs['Normal'],shader.inputs['Normal'])
            else:material.node_tree.links.new(tex.outputs['Color'],shader.inputs[socket])
        material['render_asset_download_id']=report['download_id'];material['license']='CC0-1.0'
        ob=bpy.context.object
        if ob and ob.type=='MESH' and ob.name in scene.objects:ob.data.materials.append(material)
        return {'material':material.name,'editable':True,'originals_preserved':True,
                'displacement_auto_applied':False,'license':'CC0-1.0','already_imported':False}
    except Exception:
        bpy.data.materials.remove(material);raise
