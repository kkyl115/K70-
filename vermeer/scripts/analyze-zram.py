#!/usr/bin/env python3
"""Decode a captured zram mm_stat; never read or change the phone itself."""
import argparse
import json
from pathlib import Path


def analyze(text):
    fields = text.strip().split()
    if len(fields) < 3 or any(not s.isascii() or not s.isdigit() for s in fields):
        raise ValueError('mm_stat requires at least three nonnegative integer counters')
    original, compressed, allocated = map(int, fields[:3])
    if any(int(s) > (1 << 64) - 1 for s in fields):
        raise ValueError('counter exceeds u64')
    # Only the first three fields are common to all supported kernel revisions.
    # same-filled pages can use no compressed payload; avoid division by zero.
    return {
        'source': 'caller_supplied_mm_stat', 'unit': 'bytes',
        'logical_original_bytes': original,
        'compressed_payload_bytes': compressed,
        'allocator_memory_bytes': allocated,
        'payload_compression_ratio': original / compressed if compressed else None,
        'effective_ratio_including_allocator': original / allocated if allocated else None,
        'net_memory_saved_bytes': original - allocated,
        'trailing_counters_raw': fields[3:],
        'notes': ['disksize is logical capacity, not preallocated RAM',
                  'swap used is not the physical compressed memory size',
                  'one snapshot cannot establish latency, energy, or algorithm superiority'],
        'performance_improvement_verified': False,
    }


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mm_stat', type=Path, help='text file containing one captured mm_stat line')
    a = p.parse_args()
    print(json.dumps(analyze(a.mm_stat.read_text(encoding='utf-8')), indent=2))
