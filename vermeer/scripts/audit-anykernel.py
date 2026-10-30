#!/usr/bin/env python3
"""Inspect an AnyKernel ZIP without running or extracting its installer/tools.

This is a bounded static inventory, NOT a shell interpreter or flash approval.
Only an explicit --config-out writes the extracted IKCONFIG to a new local file.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
import zipfile

from kernel_audit import inspect_image, parse_config

MAX_ARCHIVE = 512 * 1024 * 1024
MAX_TOTAL = 768 * 1024 * 1024
MAX_MEMBER = 256 * 1024 * 1024
MAX_TEXT = 2 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_members(infos):
    if not infos or len(infos) > 4096:
        raise ValueError('empty archive or too many members')
    total, seen = 0, set()
    for info in infos:
        name = info.filename
        parts = name.rstrip('/').split('/')
        if (not name or '\\' in name or ':' in name or name.startswith('/')
                or any(p in ('', '.', '..') for p in parts)
                or any(ord(c) < 32 for c in name)):
            raise ValueError('unsafe member name')
        canonical = name.rstrip('/').casefold()
        if canonical in seen:
            raise ValueError('duplicate/case-colliding member')
        seen.add(canonical)
        mode = info.external_attr >> 16
        kind = stat.S_IFMT(mode)
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError('links and special members refused')
        if info.flag_bits & 1:
            raise ValueError('encrypted member refused')
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise ValueError('unsupported compression')
        if info.file_size > MAX_MEMBER:
            raise ValueError('member exceeds size limit')
        total += info.file_size
        if total > MAX_TOTAL:
            raise ValueError('expanded archive exceeds size limit')


def audit(path):
    path = Path(path)
    if path.stat().st_size > MAX_ARCHIVE:
        raise ValueError('archive exceeds size limit')
    # Read once so the recorded archive hash and parsed bytes are identical.
    import io
    with path.open('rb') as source:
        payload = source.read(MAX_ARCHIVE + 1)
    if len(payload) > MAX_ARCHIVE:
        raise ValueError('archive grew beyond size limit')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        infos = archive.infolist()
        validate_members(infos)
        candidates = [i.filename for i in infos if i.filename.split('/')[-1] == 'anykernel.sh']
        if len(candidates) != 1:
            raise ValueError('requires exactly one anykernel.sh')
        prefix = candidates[0][:-len('anykernel.sh')]
        names = {i.filename for i in infos}
        if prefix + 'Image' not in names:
            raise ValueError('requires a raw Image beside anykernel.sh')
        inventory, image, scripts = [], None, {}
        wanted_scripts = ('anykernel.sh', 'tools/ak3-core.sh',
                          'META-INF/com/google/android/update-binary')
        for info in infos:
            if info.is_dir():
                continue
            raw = archive.read(info)  # zipfile verifies each CRC; never execute.
            inventory.append({'path': info.filename, 'bytes': len(raw), 'sha256': sha(raw)})
            if info.filename == prefix + 'Image':
                image = raw
            relative = info.filename[len(prefix):] if info.filename.startswith(prefix) else None
            if relative in wanted_scripts:
                if len(raw) > MAX_TEXT:
                    raise ValueError('installer text exceeds size limit')
                scripts[relative] = raw.decode('utf-8', errors='strict')
        kernel_report = inspect_image(image)
        if kernel_report['kind'] != 'kernel':
            raise ValueError('Image must be raw ARM64 kernel, not boot image')
        config = kernel_report['kernel'].pop('ikconfig', None)
        parsed = parse_config(config) if config is not None else {}
        literal_assignments = {}
        for number, line in enumerate(scripts['anykernel.sh'].splitlines(), 1):
            match = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_.]*)=([^\s;]+)', line.strip())
            if match:
                literal_assignments.setdefault(match[1], []).append({'line': number, 'value': match[2]})
        # Presence is evidence only. It does not prove that a branch executes.
        markers = {}
        pattern = re.compile(r'patch_vbmeta|PATCHVBMETAFLAG|do.devicecheck|do.check_boot_version|'
                             r'no_magisk_check|slot_select|SLOT_SELECT|^block=|'
                             r'flash_boot|write_boot|dd if=|cat boot-new.img', re.I)
        for name, content in scripts.items():
            markers[name] = [{'line': n, 'text': line.strip()[:400]}
                             for n, line in enumerate(content.splitlines(), 1) if pattern.search(line)]
        strings = re.findall(rb'[\x20-\x7e]{6,}', image)
        identities = sorted({s.decode('ascii') for s in strings
                             if re.fullmatch(rb'v\d+\.\d+\.\d+(?:-[\w.@-]+)?', s)
                             or s in (b'SUSFS Inline Hook', b'baseband_guard')})[:100]
        result = {
            'schema_version': 1, 'archive_name': path.name,
            'archive_bytes': len(payload), 'archive_sha256': sha(payload),
            'member_crc_verified': True, 'members': inventory,
            'package_prefix': prefix,
            'recovery_entry_at_archive_root': 'META-INF/com/google/android/update-binary' in names,
            'kernel': kernel_report, 'embedded_identity_strings': identities,
            'bbg': {k: parsed.get(k, 'not_recorded') for k in
                    ('CONFIG_BBG', 'CONFIG_BBG_BLOCK_BOOT', 'CONFIG_BBG_BLOCK_RECOVERY', 'CONFIG_LSM')},
            'literal_assignments_only': literal_assignments, 'script_markers_only': markers,
            'script_semantics_fully_audited': False, 'runtime_image_identity_verified': False,
            'runtime_bbg_verified': False, 'abi_verified': False, 'deployable': False,
        }
        return result, config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--config-out', type=Path)
    args = parser.parse_args()
    try:
        report, config = audit(args.archive)
        if args.config_out:
            if config is None:
                raise ValueError('IKCONFIG missing; no config written')
            with args.config_out.open('x', encoding='utf-8', newline='\n') as out:
                out.write(config)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, zipfile.BadZipFile, NotImplementedError, RuntimeError) as exc:
        print(json.dumps({'error': str(exc), 'deployable': False}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    sys.exit(main())
