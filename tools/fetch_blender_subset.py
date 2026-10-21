#!/usr/bin/env python3
"""Fetch a pristine pinned Blender source subset at BUILD time only, not on Android."""
import argparse
import os
from pathlib import Path
import subprocess

COMMIT='fbe82a46101643c5cf8d7ab331d6a47566008fa7'
REMOTE='https://github.com/blender/blender.git'
PARTS=['intern/guardedalloc','intern/atomic','intern/profile','source/blender/blenlib']


def git(root,*args,capture=False):
    env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_LFS_SKIP_SMUDGE':'1'}
    result=subprocess.run(['git','-C',str(root),*args],check=True,timeout=240,env=env,
                          stdout=subprocess.PIPE if capture else None,text=True)
    return result.stdout.strip() if capture else None


def ensure(destination):
    destination=Path(destination).absolute()
    if destination.is_symlink():raise RuntimeError('Refusing symlink dependency checkout')
    destination.parent.mkdir(parents=True,exist_ok=True)
    lock=destination.parent/(destination.name+'.lock')
    with lock.open('a+') as handle:
        if os.name=='posix':
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
        if not (destination/'.git').exists():
            if destination.exists() and any(destination.iterdir()):
                raise RuntimeError('Dependency directory already contains unrelated data')
            destination.mkdir(exist_ok=True)
            git(destination,'init','-q')
            git(destination,'remote','add','origin',REMOTE)
            git(destination,'sparse-checkout','init','--cone')
            git(destination,'sparse-checkout','set',*PARTS)
            git(destination,'-c','protocol.version=2','fetch','--filter=blob:none','--depth=1','origin',COMMIT)
            git(destination,'checkout','--quiet','--detach',COMMIT)
        if git(destination,'rev-parse','HEAD',capture=True)!=COMMIT:
            raise RuntimeError('Pinned Blender revision mismatch; refusing to overwrite checkout')
        git(destination,'diff','--quiet','HEAD','--',*PARTS)
        for part in PARTS:
            if not (destination/part).is_dir():raise RuntimeError('Incomplete sparse source: '+part)
    print('Verified original Blender source revision '+COMMIT)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--destination',required=True)
    ensure(parser.parse_args().destination)
