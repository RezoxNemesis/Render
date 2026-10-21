#!/usr/bin/env python3
"""Apply explicit signedness checks to the pinned original Blender Zstd reader.
Array allocation/deallocation stays UNCHANGED: it now uses genuine guardedalloc.
"""
import argparse
from pathlib import Path

PATCHES=[
 ('for (int i = 0; i < frames_num; i++) {','for (uint32_t i = 0; i < frames_num; i++) {'),
 ('if (seek_frame_start != compressed_ofs || base->seek(base, seek_frame_start, SEEK_SET) < 0) {',
  'if (seek_frame_start < 0 || static_cast<uint64_t>(seek_frame_start) != compressed_ofs ||\n      base->seek(base, seek_frame_start, SEEK_SET) < 0) {'),
 ('zstd->base->read(zstd->base, compressed_data, compressed_size) < compressed_size)',
  'zstd->base->read(zstd->base, compressed_data, compressed_size) !=\n          static_cast<int64_t>(compressed_size))'),
 ('size_t end_offset = zstd->reader.offset + size, read_len = 0;\n  while (zstd->reader.offset < end_offset) {',
  'size_t end_offset = static_cast<size_t>(zstd->reader.offset) + size, read_len = 0;\n  while (zstd->reader.offset >= 0 &&\n         static_cast<size_t>(zstd->reader.offset) < end_offset) {'),
 ('if (new_pos < 0 || new_pos > zstd->seek.uncompressed_ofs[zstd->seek.frames_num]) {',
  'if (new_pos < 0 || static_cast<uint64_t>(new_pos) >\n                         zstd->seek.uncompressed_ofs[zstd->seek.frames_num]) {')]


def prepare(source,destination):
    text=Path(source).read_text()
    for old,new in PATCHES:
        if text.count(old)!=1:raise RuntimeError('Unexpected pinned Blender source; refusing speculative patch')
        text=text.replace(old,new)
    Path(destination).write_text(text)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination')
    args=p.parse_args();prepare(args.source,args.destination)
