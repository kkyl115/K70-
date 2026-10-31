#!/usr/bin/env python3
"""Owner-authorized, read-only Vermeer inspection; no push/install/setting changes.

Output stays in ignored build/ by default and is never automatically published.
The payload is the project's fixed, reviewed shell collector, sent over stdin.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def device_rows(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != 'List of devices attached':
        raise ValueError('unexpected adb inventory response')
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) < 2:
            raise ValueError('malformed device record')
        rows.append((fields[0], fields[1]))
    return rows


def select_device(rows):
    # Refuse ambiguity, including another offline or unauthorized device.
    if len(rows) != 1 or rows[0][1] != 'device':
        raise ValueError('requires exactly one connected, authorized device')
    return rows[0][0]


def require_vermeer(model):
    if model.strip() != 'vermeer':
        raise ValueError('device is not vermeer; collection refused')


def require_root(identity):
    if not identity.strip().startswith('uid=0('):
        raise ValueError('root was not granted; collection refused')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb', default=shutil.which('adb'))
    p.add_argument('--root', action='store_true', help='ask existing su to run the read-only collector')
    p.add_argument('--pressure', action='store_true', help='four read-only pressure samples, ten seconds apart')
    args = p.parse_args()
    if not args.adb:
        p.error('adb not found')
    temp = ROOT / 'build' / 'adb-runtime'
    temp.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    # Avoid a locked shared adb.log on Windows, without deleting it or changing ACLs.
    env.update(TEMP=str(temp), TMP=str(temp))

    def adb(*parts, payload=None, timeout=20):
        result = subprocess.run([args.adb, *parts], input=payload,
                                capture_output=True, timeout=timeout, env=env)
        if result.returncode:
            # Avoid logging a serial number or unbounded remote output on errors.
            raise RuntimeError('adb command failed, exit=' + str(result.returncode))
        return result.stdout

    try:
        rows = device_rows(adb('devices').decode('utf-8', 'strict'))
        serial = select_device(rows)
        model = adb('-s', serial, 'shell', 'getprop ro.product.device').decode('utf-8', 'strict')
        require_vermeer(model)
        if args.root:
            require_root(adb('-s', serial, 'shell', 'su -c id', timeout=15).decode('utf-8', 'strict'))
        payload_name = 'collect-pressure-readonly.sh' if args.pressure else 'collect-readonly.sh'
        script = (ROOT / 'bootguard/preflight' / payload_name).read_bytes().replace(b'\r\n', b'\n')
        stdout = adb('-s', serial, 'shell', 'su -c sh' if args.root else 'sh',
                     payload=script, timeout=60)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        destination = ROOT / 'build' / ('device-readonly-' + stamp)
        destination.mkdir(exist_ok=False)
        (destination / 'runtime.txt').write_bytes(stdout)
        record = {'collected_utc': stamp, 'device_model_checked': 'vermeer',
                  'root_read_requested': args.root,
                  'collection_kind': 'pressure_4x10s' if args.pressure else 'runtime_snapshot',
                  'collection_end_marker_seen': stdout.rstrip().endswith(b'BOOTGUARD_READ_ONLY_COMPLETE'),
                  'collector_sha256': hashlib.sha256(script).hexdigest(),
                  'output_sha256': hashlib.sha256(stdout).hexdigest(),
                  'output_bytes': len(stdout), 'phone_settings_changed': False,
                  'phone_files_uploaded': False, 'published': False,
                  'abi_verified': False, 'deployable': False}
        (destination / 'receipt.json').write_text(json.dumps(record, indent=2) + '\n',
                                                 encoding='utf-8', newline='\n')
        print(json.dumps({'output_directory': str(destination), **record}, ensure_ascii=False))
        return 0 if record['collection_end_marker_seen'] else 2
    except subprocess.TimeoutExpired:
        print(json.dumps({'error': 'ADB request timed out; check device authorization',
                          'collection_completed': False}))
        return 2
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({'error': type(exc).__name__ + ': ' + str(exc),
                          'collection_completed': False}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    sys.exit(main())
