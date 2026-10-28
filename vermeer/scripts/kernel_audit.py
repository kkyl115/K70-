#!/usr/bin/env python3
"""Offline, read-only kernel/boot/config/module inspection; never a flash approval."""
import argparse
import gzip
import hashlib
import json
import lzma
from pathlib import Path
import re
import struct
import sys
import zlib

def sha(data):
    return hashlib.sha256(data).hexdigest()

def bounded(data, offset, size):
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError('truncated or out-of-bounds structure')
    return data[offset:offset + size]

def u32(data, offset):
    return struct.unpack('<I', bounded(data, offset, 4))[0]

def align(value, page):
    return (value + page - 1) // page * page

def inspect_image(data):
    result = {'bytes': len(data), 'sha256': sha(data), 'avb_verified': False,
              'deployable': False, 'scope': 'structure only; not signature or device compatibility'}
    if data.startswith(b'ANDROID!'):
        version = u32(data, 40)
        if version not in (3, 4):
            raise ValueError('only Android boot header v3/v4 supported; older images require upstream unpack_bootimg')
        size = u32(data, 20)
        if size != (1580 if version == 3 else 1584):
            raise ValueError('invalid boot header size')
        bounded(data, 0, size)
        kernel_size, ramdisk_size = u32(data, 8), u32(data, 12)
        kernel = bounded(data, 4096, kernel_size)
        ramdisk_offset = 4096 + align(kernel_size, 4096)
        bounded(data, ramdisk_offset, ramdisk_size)
        signature_size = u32(data, 1580) if version == 4 else 0
        bounded(data, ramdisk_offset + align(ramdisk_size, 4096), signature_size)
        result.update(kind='boot/init_boot', header_version=version, kernel_size=kernel_size,
                      ramdisk_size=ramdisk_size, boot_signature_size=signature_size,
                      kernel_sha256=sha(kernel) if kernel_size else None,
                      cmdline=bounded(data, 44, 1536).split(b'\0', 1)[0].decode('utf-8', 'replace'))
        result['kernel'] = inspect_kernel(kernel) if kernel_size else None
    elif data.startswith(b'VNDRBOOT'):
        version, page = u32(data, 8), u32(data, 12)
        if version not in (3, 4) or page < 2048 or page > 65536 or page & (page-1):
            raise ValueError('invalid vendor_boot version/page')
        header_size = u32(data, 2096)
        if header_size != (2112 if version == 3 else 2128):
            raise ValueError('invalid vendor_boot header size')
        bounded(data, 0, header_size)
        ramdisk_size, dtb_size = u32(data, 24), u32(data, 2100)
        off = align(header_size, page)
        ramdisk = bounded(data, off, ramdisk_size)
        off += align(ramdisk_size, page)
        dtb = bounded(data, off, dtb_size)
        off += align(dtb_size, page)
        result.update(kind='vendor_boot', header_version=version, page_size=page,
                      ramdisk_sha256=sha(ramdisk), dtb_sha256=sha(dtb), dtb_size=dtb_size)
        if version == 4:
            table_size, count, entry_size, bootconfig_size = struct.unpack('<4I', bounded(data, 2112, 16))
            table = bounded(data, off, table_size)
            if entry_size < 108 or count * entry_size > table_size:
                raise ValueError('invalid vendor ramdisk table')
            for i in range(count):
                length, start = struct.unpack('<2I', table[i*entry_size:i*entry_size+8])
                bounded(ramdisk, start, length)
            bounded(data, off + align(table_size, page), bootconfig_size)
            result.update(ramdisk_fragment_count=count, bootconfig_size=bootconfig_size)
    elif data[:4] == b'\xd7\xb7\xab\x1e':
        magic, total, head, entry, count, off, page, version = struct.unpack('>8I', bounded(data,0,32))
        bounded(data,0,total)
        if head < 32 or entry < 32 or off < head or off + entry * count > total:
            raise ValueError('invalid DTBO table')
        for i in range(count):
            length, start = struct.unpack('>2I', bounded(data,off+i*entry,8))
            bounded(data[:total],start,length)
        result.update(kind='dtbo', entry_count=count, version=version)
    elif data[:4] == b'AVB0':
        bounded(data,0,256)
        auth, aux = struct.unpack('>2Q', data[12:28])
        bounded(data,256,auth+aux)
        result.update(kind='vbmeta', algorithm_type=struct.unpack('>I', data[28:32])[0],
                      flags=struct.unpack('>I', data[120:124])[0])
    else:
        result.update(kind='kernel', kernel=inspect_kernel(data))
        if not result['kernel']['arm64_image_magic']:
            raise ValueError('unrecognized image format')
    if len(data) >= 64 and data[-64:-60] == b'AVBf':
        original, offset, size = struct.unpack('>3Q', data[-52:-28])
        bounded(data, offset, size)
        if original > len(data):
            raise ValueError('invalid AVB footer original size')
        result['avb_footer'] = {'original_size': original, 'vbmeta_offset': offset, 'vbmeta_size': size}
    return result

def inspect_kernel(data):
    result = {'arm64_image_magic': data[56:60] == b'ARM\x64', 'ikconfig': None}
    result['versions'] = sorted(set(x.decode('ascii') for x in re.findall(rb'5\.15\.\d+-android13-[\w.\-]+',data)))[:12]
    start, end = data.find(b'IKCFG_ST'), data.find(b'IKCFG_ED')
    if start >= 0 and end > start:
        dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
        config = dec.decompress(data[start+8:end], 4*1024*1024)
        if not dec.eof:
            raise ValueError('IKCONFIG truncated or exceeds 4MiB')
        result['ikconfig'] = config.decode('utf-8')
        result['ikconfig_sha256'] = sha(config)
    return result

def parse_config(text):
    result = {}
    for line in text.splitlines():
        if line.startswith('CONFIG_') and '=' in line:
            key, value = line.split('=', 1)
            result[key] = value
        elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
            result[line[2:-11]] = 'n'
    return result

def elf_module(data):
    if data[:6] != b'\x7fELF\x02\x01' or len(data) < 64:
        raise ValueError('requires little-endian ELF64 module')
    if struct.unpack('<H',data[18:20])[0] != 183 or struct.unpack('<H',data[16:18])[0] != 1:
        raise ValueError('requires relocatable AArch64 ELF')
    shoff = struct.unpack('<Q',data[40:48])[0]
    entsize, count, stridx = struct.unpack('<3H',data[58:64])
    if entsize != 64 or not count or stridx >= count:
        raise ValueError('unsupported section table')
    sections = [struct.unpack('<IIQQQQIIQQ', bounded(data,shoff+i*entsize,64)) for i in range(count)]
    names = bounded(data,sections[stridx][4],sections[stridx][5])
    def string(buf, offset):
        if offset >= len(buf) or b'\0' not in buf[offset:]:
            raise ValueError('invalid string offset')
        return buf[offset:].split(b'\0',1)[0].decode('utf-8', 'strict')
    by_name = {string(names,s[0]):s for s in sections}
    def content(name):
        s = by_name.get(name)
        return bounded(data,s[4],s[5]) if s else b''
    info = content('.modinfo').split(b'\0')
    vermagic = [x[9:].decode() for x in info if x.startswith(b'vermagic=')]
    versions = content('__versions')
    if len(versions) % 64:
        raise ValueError('invalid 5.15 __versions entry size')
    crcs = {string(versions[i+8:i+64],0): struct.unpack('<Q',versions[i:i+8])[0]
            for i in range(0,len(versions),64)}
    undefined = set()
    for s in sections:
        if s[1] != 2:
            continue
        if s[6] >= len(sections) or s[9] != 24 or s[5] % 24:
            raise ValueError('invalid ELF symtab')
        st = sections[s[6]]
        strings = bounded(data,st[4],st[5])
        syms = bounded(data,s[4],s[5])
        for i in range(0,len(syms),24):
            name, info, other, ndx, val, size = struct.unpack('<IBBHQQ',syms[i:i+24])
            if ndx == 0 and name and info >> 4 == 1:
                undefined.add(string(strings,name))
    return {'sha256':sha(data), 'vermagic':vermagic, 'versions':crcs, 'undefined':sorted(undefined)}

def compare_module(module, symvers_text, expected_vermagic):
    exports = {}
    for line in symvers_text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            exports[parts[1]] = int(parts[0],16)
    missing = sorted(set(module['undefined']) - exports.keys())
    mismatches = {k:{'module':v,'kernel':exports.get(k)} for k,v in module['versions'].items()
                  if exports.get(k) != v}
    unversioned = sorted(set(module['undefined']) - module['versions'].keys())
    reasons = []
    if module['vermagic'] != [expected_vermagic]: reasons.append('vermagic_mismatch')
    if missing: reasons.append('missing_exports')
    if mismatches: reasons.append('crc_mismatch')
    if unversioned or not module['versions']: reasons.append('missing_crc_evidence')
    return {'symbol_crc_check': 'FAIL' if reasons else 'PASS', 'reasons': reasons,
            'missing':missing,'crc_mismatches':mismatches,'unversioned':unversioned,
            'full_abi_verified':False,'deployable':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    image=sub.add_parser('image'); image.add_argument('path',type=Path); image.add_argument('--config-out',type=Path)
    mod=sub.add_parser('module'); mod.add_argument('path',type=Path); mod.add_argument('--symvers',type=Path); mod.add_argument('--vermagic')
    conf=sub.add_parser('config-diff'); conf.add_argument('before',type=Path); conf.add_argument('after',type=Path)
    a=p.parse_args()
    try:
        if a.command == 'image':
            result=inspect_image(a.path.read_bytes())
            kernel=result.get('kernel') or {}
            config=kernel.pop('ikconfig',None)
            if a.config_out and config:
                with a.config_out.open('x',encoding='utf-8',newline='\n') as out: out.write(config)
        elif a.command == 'module':
            data=a.path.read_bytes()
            if a.path.suffix == '.gz': data=gzip.decompress(data)
            elif a.path.suffix == '.xz': data=lzma.decompress(data)
            result=elf_module(data)
            if a.symvers and a.vermagic: result['comparison']=compare_module(result,a.symvers.read_text(),a.vermagic)
        else:
            left,right=parse_config(a.before.read_text()),parse_config(a.after.read_text())
            result={k:{'before':left.get(k),'after':right.get(k)} for k in sorted(left.keys()|right.keys()) if left.get(k)!=right.get(k)}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if result.get('comparison',{}).get('symbol_crc_check') == 'FAIL': return 2
        return 0
    except (OSError,ValueError,struct.error,zlib.error) as exc:
        print(json.dumps({'error':str(exc),'deployable':False})); return 2

if __name__ == '__main__': sys.exit(main())
