# SPDX-License-Identifier: GPL-2.0-or-later
"""Original-file and dependency boundaries; no renderer, generator or desktop bpy."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct

FILE = re.compile(r'^[a-f0-9]{64}\.[a-z0-9]{1,16}$')
IMAGES = {'.png', '.jpg', '.jpeg', '.webp', '.tif', '.tiff', '.exr', '.hdr', '.bmp', '.tga'}
VIDEOS = {'.mp4', '.mov', '.mkv', '.webm', '.avi', '.mpeg', '.mpg', '.m4v'}
AUDIO = {'.wav', '.mp3', '.ogg', '.flac', '.m4a'}
OPERATORS = {'.glb':'import_scene.gltf', '.gltf':'import_scene.gltf', '.obj':'wm.obj_import',
             '.stl':'wm.stl_import', '.ply':'wm.ply_import', '.fbx':'import_scene.fbx',
             '.usd':'wm.usd_import', '.usda':'wm.usd_import', '.usdc':'wm.usd_import',
             '.usdz':'wm.usd_import', '.abc':'wm.alembic_import', '.bvh':'import_anim.bvh',
             '.dae':'wm.collada_import'}


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024), b''):value.update(block)
    return value.hexdigest()


def relative(value):
    if (not isinstance(value,str) or not value or len(value)>240 or '\\' in value or ':' in value
            or any(p in ('','.','..','_render_bundle_manifest.json') for p in value.split('/'))
            or any(ord(c)<32 or ord(c)==127 for c in value)):
        raise ValueError('UNSAFE_BUNDLE_ENTRY')
    return PurePosixPath(value)


def scoped(root, value):
    target=Path(root)
    if target.is_symlink():raise ValueError('IMPORT_DIRECTORY_SYMLINK')
    for part in relative(value).parts:
        target=target/part
        if target.is_symlink():raise ValueError('IMPORT_FILE_SYMLINK')
    if not target.resolve().is_relative_to(Path(root).resolve()):raise ValueError('IMPORT_PATH_ESCAPE')
    return target


def original(root, filename, expected):
    if (not isinstance(filename,str) or not FILE.fullmatch(filename) or not isinstance(expected,str)
            or not re.fullmatch(r'[a-f0-9]{64}',expected) or filename[:64]!=expected):
        raise ValueError('IMPORT_REQUIRES_STAGED_ORIGINAL_DIGEST')
    path=scoped(Path(root)/'Imports', filename)
    if not path.is_file() or digest(path)!=expected:raise ValueError('IMPORT_ORIGINAL_INTEGRITY_FAILED')
    return path


def bundle(root, expected):
    directory=scoped(Path(root)/'Imports', 'Bundles/'+expected)
    manifest=directory/'_render_bundle_manifest.json'
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size>2*1024*1024:
        raise ValueError('ARCHIVE_REQUIRES_STORAGE_UNPACK')
    data=json.loads(manifest.read_text())
    if data.get('original_sha256')!=expected or not isinstance(data.get('entries'),list) or len(data['entries'])>2048:
        raise ValueError('BUNDLE_MANIFEST_INVALID')
    entries={}
    for row in data['entries']:
        key=str(relative(row['path']))
        if key in entries or type(row.get('bytes')) is not int or row['bytes']<0 or not re.fullmatch(r'[a-f0-9]{64}',row.get('sha256','')):
            raise ValueError('BUNDLE_MANIFEST_INVALID')
        entries[key]=row
    return directory,entries


def verified_entry(directory, entries, name):
    key=str(relative(name));row=entries.get(key)
    if row is None:raise ValueError('BUNDLE_ENTRY_NOT_FOUND')
    path=scoped(directory,key)
    if not path.is_file() or path.stat().st_size!=row['bytes'] or digest(path)!=row['sha256']:
        raise ValueError('BUNDLE_ENTRY_INTEGRITY_FAILED')
    return path


def source(root, p, verify_dependencies=False, verified_original=None):
    path=verified_original if verified_original is not None else original(root,p.get('filename'),p.get('expected_sha256'))
    if path.suffix=='.zip':
        directory,entries=bundle(root,p['expected_sha256'])
        if not p.get('entry'):raise ValueError('ARCHIVE_IMPORT_REQUIRES_EXPLICIT_ENTRY')
        path=verified_entry(directory,entries,p['entry'])
        # A model can resolve siblings itself. Verify the entire immutable bundle
        # before handing it to an importer, including textures and material files.
        if verify_dependencies:
            for name in entries:
                if name!=p['entry']:verified_entry(directory,entries,name)
        return path,directory
    if 'entry' in p:raise ValueError('ENTRY_ONLY_SUPPORTED_FOR_UNPACKED_ARCHIVE')
    return path,path.parent


def image_header(path):
    """Bound decoder admission using original dimensions, without decoding pixels."""
    suffix=path.suffix.lower()
    with path.open('rb') as stream:
        head=stream.read(131072)
        if suffix=='.png' and head[:8]==b'\x89PNG\r\n\x1a\n' and head[12:16]==b'IHDR':
            return struct.unpack('>II',head[16:24])
        if suffix in ('.jpg','.jpeg') and head[:2]==b'\xff\xd8':
            stream.seek(2)
            for _ in range(4096):
                marker=stream.read(1)
                if marker!=b'\xff':raise ValueError('INVALID_JPEG_HEADER')
                code=stream.read(1)
                while code==b'\xff':code=stream.read(1)
                if code in (b'\xd9',b'\xda',b''):break
                if code in (b'\x01',b'\xd8') or 0xd0<=code[0]<=0xd7:continue
                data=stream.read(2)
                if len(data)!=2:break
                size=struct.unpack('>H',data)[0]
                if size<2:break
                if code[0] in (0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf):
                    data=stream.read(5)
                    height,width=struct.unpack('>HH',data[1:5]);return width,height
                stream.seek(size-2,1)
        if suffix=='.webp' and head[:4]==b'RIFF' and head[8:12]==b'WEBP':
            kind=head[12:16]
            if kind==b'VP8X':return 1+int.from_bytes(head[24:27],'little'),1+int.from_bytes(head[27:30],'little')
            if kind==b'VP8L' and head[20]==0x2f:
                bits=int.from_bytes(head[21:25],'little');return (bits&0x3fff)+1,((bits>>14)&0x3fff)+1
            if kind==b'VP8 ' and head[23:26]==b'\x9d\x01\x2a':return struct.unpack('<HH',head[26:30])[0]&0x3fff,struct.unpack('<HH',head[26:30])[1]&0x3fff
        if suffix=='.bmp' and head[:2]==b'BM' and len(head)>=26:
            width,height=struct.unpack('<ii',head[18:26]);return abs(width),abs(height)
        if suffix=='.tga' and len(head)>=18:return struct.unpack('<HH',head[12:16])
        if suffix=='.hdr' and head.startswith((b'#?RADIANCE',b'#?RGBE')):
            match=re.search(rb'(?:[+-]Y\s+(\d+)\s+[+-]X\s+(\d+))',head)
            if match:return int(match[2]),int(match[1])
        if suffix=='.exr' and head[:4]==b'v/1\x01':
            pos=8;count=0
            while pos<len(head) and head[pos] and count<4096:
                count+=1;end=head.find(b'\0',pos)
                if end<0:break
                name=head[pos:end];pos=end+1
                end=head.find(b'\0',pos);kind=head[pos:end];pos=end+1
                if end<0 or pos+4>len(head):break
                size=struct.unpack('<I',head[pos:pos+4])[0];pos+=4
                if name==b'dataWindow' and kind==b'box2i' and size==16 and pos+16<=len(head):
                    x0,y0,x1,y1=struct.unpack('<iiii',head[pos:pos+16]);return x1-x0+1,y1-y0+1
                pos+=size
        if suffix in ('.tif','.tiff') and head[:2] in (b'II',b'MM'):
            order='<' if head[:2]==b'II' else '>'
            if struct.unpack(order+'H',head[2:4])[0]==42:
                offset=struct.unpack(order+'I',head[4:8])[0];stream.seek(offset)
                count=struct.unpack(order+'H',stream.read(2))[0];values={}
                if count>4096:raise ValueError('TIFF_HEADER_TOO_LARGE')
                for _ in range(count):
                    row=stream.read(12)
                    if len(row)!=12:break
                    tag,kind,items=struct.unpack(order+'HHI',row[:8])
                    if tag in (256,257) and items==1 and kind in (3,4):values[tag]=struct.unpack(order+('H' if kind==3 else 'I'),row[8:10] if kind==3 else row[8:12])[0]
                if 256 in values and 257 in values:return values[256],values[257]
    raise ValueError('IMAGE_DIMENSIONS_UNVERIFIED_FORMAT_OR_HEADER_UNSUPPORTED')


def image_budget(path, maximum):
    if type(maximum) is not int or not 1024*1024<=maximum<=2*1024**3:raise ValueError('INVALID_IMAGE_MEMORY_BUDGET')
    try:width,height=image_header(path)
    except (IndexError,struct.error,OverflowError):raise ValueError('INVALID_IMAGE_HEADER') from None
    # Float RGBA + decoder/GPU working copies. This is admission, never resizing.
    required=width*height*32
    if width<1 or height<1 or width>131072 or height>131072:raise ValueError('INVALID_IMAGE_DIMENSIONS')
    if required>maximum:raise ValueError('IMAGE_EXCEEDS_DECODE_MEMORY_BUDGET_ORIGINAL_RETAINED')
    return width,height,required
