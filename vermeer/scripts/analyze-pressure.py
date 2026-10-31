#!/usr/bin/env python3
"""Offline analysis of bounded BootGuard pressure captures; no phone access."""
import argparse
import hashlib
import json
import math
from pathlib import Path

COMPLETE = 'BOOTGUARD_READ_ONLY_COMPLETE'


def parse_capture(text):
    lines = text.splitlines()
    if not lines or lines[-1] != COMPLETE:
        raise ValueError('incomplete capture')
    samples, sample, key = [], None, None
    for line in lines[:-1]:
        if line.startswith('SAMPLE '):
            if sample is not None or line != 'SAMPLE ' + str(len(samples)):
                raise ValueError('invalid sample sequence')
            sample, key = {}, None
        elif line.startswith('PATH '):
            key = line[5:]
            if sample is None or key in sample:
                raise ValueError('duplicate or misplaced path')
            sample[key] = []
        elif line == 'END_SAMPLE':
            if sample is None:
                raise ValueError('unexpected sample end')
            samples.append(sample)
            sample, key = None, None
        elif sample is not None and key is not None:
            sample[key].append(line)
        else:
            raise ValueError('unframed capture data')
    if sample is not None or not 2 <= len(samples) <= 64:
        raise ValueError('need 2 to 64 complete samples')
    return samples


def first(sample, key):
    lines = sample.get(key, [])
    return lines[0] if lines and lines[0] != 'UNKNOWN' else None


def counters(sample):
    result = {}
    for line in sample.get('/proc/vmstat', []):
        fields = line.split()
        if len(fields) == 2 and fields[1].isascii() and fields[1].isdigit():
            result[fields[0]] = int(fields[1])
    return result


def pressure(sample, resource):
    result = {}
    for line in sample.get('/proc/pressure/' + resource, []):
        fields = line.split()
        if not fields or fields[0] not in ('some', 'full'):
            continue
        values = dict(part.split('=', 1) for part in fields[1:] if '=' in part)
        total = values.get('total', '')
        if total.isascii() and total.isdigit():
            result[fields[0]] = int(total)
    return result


def analyze(text):
    samples = parse_capture(text)
    times, widths, boot_ids = [], [], []
    for sample in samples:
        try:
            start = float(first(sample, '/proc/uptime').split()[0])
            end = float(first(sample, 'UPTIME_END').split()[0])
        except (AttributeError, ValueError, IndexError) as exc:
            raise ValueError('missing/invalid uptime') from exc
        if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start <= end:
            raise ValueError('invalid sample time')
        times.append((start + end) / 2)
        widths.append(end - start)
        boot_ids.append(first(sample, '/proc/sys/kernel/random/boot_id'))
    if not all(boot_ids) or len(set(boot_ids)) != 1:
        raise ValueError('boot identity missing or changed; cannot compare counters')
    windows = []
    for i, (left, right) in enumerate(zip(samples, samples[1:])):
        elapsed = times[i + 1] - times[i]
        if elapsed <= 0:
            raise ValueError('uptime did not increase')
        issues, rates, psi = [], {}, {}
        lc, rc = counters(left), counters(right)
        for name in sorted(lc.keys() | rc.keys()):
            if name not in lc or name not in rc or rc[name] < lc[name]:
                rates[name] = None
                issues.append('missing or reset counter: ' + name)
            else:
                rates[name] = {'delta': rc[name] - lc[name],
                               'per_second': (rc[name] - lc[name]) / elapsed}
        for resource in ('cpu', 'memory', 'io'):
            lp, rp = pressure(left, resource), pressure(right, resource)
            psi[resource] = {}
            for kind in ('some', 'full'):
                # System-level CPU full is not a usable pressure metric on this ABI.
                if resource == 'cpu' and kind == 'full':
                    continue
                if kind not in lp or kind not in rp or rp[kind] < lp[kind]:
                    psi[resource][kind] = None
                    issues.append('missing or reset PSI: ' + resource + '/' + kind)
                    continue
                delta = rp[kind] - lp[kind]
                error = (widths[i] + widths[i + 1]) / 2
                if delta > (elapsed + error) * 1e6:
                    psi[resource][kind] = None
                    issues.append('PSI delta exceeds observation window: ' + resource + '/' + kind)
                    continue
                psi[resource][kind] = {'stall_us': delta,
                                       'approx_wall_time_percent': delta / elapsed / 10000}
        pages = first(left, 'PAGE_SIZE')
        page_size = int(pages) if pages and pages.isascii() and pages.isdigit() else None
        swap = {}
        for name in ('pswpin', 'pswpout'):
            rate = rates.get(name)
            swap[name + '_MiB_per_second'] = (
                rate['per_second'] * page_size / (1 << 20)
                if rate and page_size and pages == first(right, 'PAGE_SIZE') else None)
        windows.append({'from_sample': i, 'to_sample': i + 1,
                        'elapsed_seconds_approx': elapsed, 'psi': psi,
                        'vmstat': rates, 'swap': swap, 'issues': issues})
    return {'schema_version': 1, 'sample_count': len(samples),
            'sample_read_duration_seconds': widths,
            'same_boot_verified': True, 'windows': windows,
            'battery_status_by_sample': [first(s, '/sys/class/power_supply/battery/status') for s in samples],
            'battery_temperature_deciC_by_sample': [first(s, '/sys/class/power_supply/battery/temp') for s in samples],
            'mglru_enabled_by_sample': [first(s, '/sys/kernel/mm/lru_gen/enabled') for s in samples],
            'controlled_benchmark': False, 'performance_improvement_verified': False,
            'notes': ['Reads are sequential; rates use sample midpoint uptime and are approximate.',
                      'PSI percentages are stall wall time, not CPU utilization or app latency.',
                      'Missing/reset counters remain unknown, never zero-filled.',
                      'VM counter units follow their names; pswpin/pswpout count pages.',
                      'Foreground workload, charging, temperature and module activity are uncontrolled.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    args = parser.parse_args()
    raw = args.capture.read_bytes()
    result = analyze(raw.decode('utf-8'))
    result['raw_capture_sha256'] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(result, indent=2, allow_nan=False))
