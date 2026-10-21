#!/usr/bin/env python3
"""Inspect a pinned community FULL native Blender Android release; never execute it.

The verified upstream binary is a candidate native dependency, not proof of device
compatibility. Preserve exact source provenance and every exported host interface.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import urllib.request
import zipfile

SOURCE='https://github.com/simfeo/blender.git'
COMMIT='d93bd33cba768e19ee4387a31c0ea137ee2f0047'
APK_URL='https://github.com/simfeo/blender/releases/download/android-alpha-4/blender-full.apk'
APK_SHA256='3fe775a1e14470ebfcd3c25ae32b57003433f04552f896880631ae98b1f18aea'
APK_BYTES=286561495


def run(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],text=True,
        env={**os.environ,'GIT_LFS_SKIP_SMUDGE':'1','GIT_TERMINAL_PROMPT':'0'},timeout=240)


def audit(out):
    out=Path(out).absolute();out.mkdir(parents=True,exist_ok=True)
    apk=out/'blender-full.apk'
    digest=hashlib.sha256();count=0
    with urllib.request.urlopen(APK_URL,timeout=90) as response,apk.open('wb') as stream:
        while True:
            block=response.read(1024*1024)
            if not block:break
            count+=len(block)
            if count>APK_BYTES:raise RuntimeError('Full engine artifact larger than pinned release')
            digest.update(block);stream.write(block)
    if count!=APK_BYTES or digest.hexdigest()!=APK_SHA256:raise RuntimeError('Pinned full engine APK integrity mismatch')
    manifest={'source':SOURCE,'source_commit':COMMIT,'apk_url':APK_URL,'apk_sha256':APK_SHA256,'apk_bytes':count,
              'inspection_only':True,'device_runtime_verified':False}
    with zipfile.ZipFile(apk) as archive:
        entries=[]
        for entry in archive.infolist():
            p=PurePosixPath(entry.filename)
            if p.is_absolute() or '..' in p.parts:raise RuntimeError('Unsafe APK member')
            entries.append({'path':entry.filename,'bytes':entry.file_size,'compressed':entry.compress_size})
        (out/'apk-inventory.json').write_text(json.dumps(entries,indent=2))
    android=os.environ.get('ANDROID_HOME','')
    aapts=sorted(Path(android).glob('build-tools/*/aapt2')) if android else []
    if aapts:
        badging=subprocess.check_output([str(aapts[-1]),'dump','badging',str(apk)],text=True,timeout=60)
        (out/'apk-badging.txt').write_text(badging)
    source=out/'source-checkout';source.mkdir(exist_ok=True)
    run(source,'init','-q');run(source,'remote','add','origin',SOURCE)
    run(source,'-c','protocol.version=2','fetch','--filter=blob:none','--depth=1','origin',COMMIT)
    if run(source,'rev-parse','FETCH_HEAD').strip()!=COMMIT:raise RuntimeError('Source commit mismatch')
    names=run(source,'ls-tree','-r','--name-only',COMMIT).splitlines()
    selected=[name for name in names if (name.endswith(('.java','.kt','.gradle','.gradle.kts'))
        or 'AndroidManifest' in name or ('android' in name.lower() and name.endswith(('.sh','.py','.cmake','.md','.xml','.txt','.hh','.cc','.cpp','.h','.c'))))]
    (out/'android-source-paths.json').write_text(json.dumps(selected,indent=2))
    candidates=selected+['.gitmodules','COPYING','doc/license/GPL-license.txt','doc/license/GPL3-license.txt']
    for name in candidates:
        try:
            content=run(source,'show',COMMIT+':'+name)
        except subprocess.CalledProcessError:
            continue
        if len(content.encode())>2*1024*1024:continue
        destination=out/'source'/name;destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(content)
    (out/'provenance.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))
    shutil.rmtree(source)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    audit(parser.parse_args().output)
