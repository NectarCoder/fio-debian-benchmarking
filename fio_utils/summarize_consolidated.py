#!/usr/bin/env python3
"""
Summarize consolidated fio parsed outputs across runs.

Usage:
  summarize_consolidated.py <consolidated_file1> [consolidated_file2 ...]

For each consolidated file (created by run_fio_batch.sh), produce a summary
report in the same directory with suffix `_summary.txt`, computing:
- Throughput in GB/s (decimal, 1 GB = 1e9 bytes)
- IOPS in thousands (kIOPS)
- Derived latency (ms) via Little's Law: latency_ms = (iodepth / iops_per_sec) * 1000
- Additional helpful fields: job_name, block size (from job name when possible), iodepth, source keys used.

Input format assumption: consolidated files contain sections like:
~~~~~~~ RUN #1 ~~~~~~~
-- result_rand_read_2k.parsed.txt --
key = value
...
"""
from __future__ import annotations
import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

GB_DEC = 1_000_000_000  # decimal GB

@dataclass
class Record:
    run: int
    file: str
    job_name: Optional[str]
    metrics: Dict[str, str]

    def get(self, key: str) -> Optional[str]:
        return self.metrics.get(key)


def parse_key_val(line: str) -> Optional[tuple[str, str]]:
    if '=' not in line:
        return None
    parts = line.split('=', 1)
    key = parts[0].strip()
    val = parts[1].strip()
    # strip trailing inline comment starting with '#'
    if '#' in val:
        val = val.split('#', 1)[0].strip()
    return key, val


def parse_consolidated(path: Path) -> List[Record]:
    records: List[Record] = []
    run_num = None
    current_file = None
    current_metrics: Dict[str, str] = {}
    job_name = None

    def flush():
        nonlocal current_metrics, job_name, current_file, run_num
        if run_num is not None and current_file is not None and current_metrics:
            records.append(Record(run=run_num, file=current_file, job_name=job_name, metrics=current_metrics))
        current_metrics = {}
        job_name = None
        current_file = None

    with path.open('r', encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            line = raw.strip('\n')
            if line.startswith('~~~~~~~ RUN #'):
                flush()
                m = re.search(r'RUN #([0-9]+)', line)
                if m:
                    run_num = int(m.group(1))
                continue
            if line.startswith('-- ') and line.endswith(' --'):
                flush()
                current_file = line[3:-3].strip()
                continue
            kv = parse_key_val(line)
            if kv:
                k, v = kv
                current_metrics[k] = v
                if k == 'job_name':
                    job_name = v
    flush()
    return records


def parse_numeric(val: str) -> Optional[float]:
    try:
        return float(val)
    except ValueError:
        return None


size_pat = re.compile(r'([0-9.]+)\s*([KMGTP]?i?B)/s', re.I)
iops_pat = re.compile(r'([0-9.]+)\s*([kKmM]?)')

def bw_to_gbps(val: str) -> Optional[float]:
    # Accept forms like '165MiB/s', '103MB/s', '5486MiB/s (5752MB/s)', etc.
    # Use the first bandwidth token containing B/s.
    m = size_pat.search(val)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2).lower()
    factor = 1.0
    if unit.startswith('kib'):
        factor = 1024
    elif unit.startswith('kb'):
        factor = 1_000
    elif unit.startswith('mib'):
        factor = 1024 ** 2
    elif unit.startswith('mb'):
        factor = 1_000_000
    elif unit.startswith('gib'):
        factor = 1024 ** 3
    elif unit.startswith('gb'):
        factor = 1_000_000_000
    elif unit.startswith('tib'):
        factor = 1024 ** 4
    elif unit.startswith('tb'):
        factor = 1_000_000_000_000
    bytes_per_sec = num * factor
    return bytes_per_sec / GB_DEC


def iops_to_k(val: str) -> Optional[float]:
    # Accept forms like '84.4k', '50221.53', '23.2k'
    m = iops_pat.match(val.strip())
    if not m:
        return None
    num = float(m.group(1))
    suffix = m.group(2).lower()
    if suffix == 'k':
        num *= 1_000
    elif suffix == 'm':
        num *= 1_000_000
    return num / 1_000  # return kIOPS


def derive_latency_ms(iops_k: Optional[float], iodepth: Optional[float]) -> Optional[float]:
    if iops_k is None or iodepth is None:
        return None
    iops = iops_k * 1_000
    if iops <= 0:
        return None
    return (iodepth / iops) * 1000.0


def first_available(metrics: Dict[str, str], keys: List[str]) -> Optional[str]:
    for k in keys:
        if k in metrics:
            return metrics[k]
    return None


def summarize_record(rec: Record) -> Dict[str, Optional[str]]:
    m = rec.metrics
    iodepth_val = first_available(m, ['iodepth'])
    iodepth = parse_numeric(iodepth_val) if iodepth_val else None

    # Bandwidth: prefer run summary, then read/write_bw, then bw_avg (KiB/s)
    bw_raw = first_available(m, ['run_read_bw', 'run_write_bw', 'read_bw', 'write_bw'])
    bw_gbps = bw_to_gbps(bw_raw) if bw_raw else None

    if bw_gbps is None and 'bw_avg' in m:
        # bw_avg is likely in KiB/s
        try:
            kib_s = float(m['bw_avg'])
            bytes_s = kib_s * 1024
            bw_gbps = bytes_s / GB_DEC
        except ValueError:
            bw_gbps = None

    iops_raw = first_available(m, ['read_iops', 'write_iops'])
    iops_k = iops_to_k(iops_raw) if iops_raw else None

    if iops_k is None and 'iops_avg' in m:
        try:
            iops_k = float(m['iops_avg']) / 1000.0
        except ValueError:
            iops_k = None

    derived_latency = derive_latency_ms(iops_k, iodepth)

    # Add optional useful metric: clat_avg/usec if present
    clat_avg = m.get('clat_avg')
    clat_avg_ms = None
    if clat_avg:
        try:
            clat_avg_ms = float(clat_avg) / 1000.0  # clat_avg in usec
        except ValueError:
            clat_avg_ms = None

    return {
        'run': rec.run,
        'file': rec.file,
        'job_name': rec.job_name,
        'iodepth': f"{iodepth:.0f}" if iodepth is not None else None,
        'throughput_GBps': f"{bw_gbps:.4f}" if bw_gbps is not None else None,
        'iops_k': f"{iops_k:.3f}" if iops_k is not None else None,
        'derived_latency_ms': f"{derived_latency:.3f}" if derived_latency is not None else None,
        'clat_avg_ms': f"{clat_avg_ms:.3f}" if clat_avg_ms is not None else None,
        'bw_source': bw_raw,
        'iops_source': iops_raw,
    }


def summarize_file(path: Path) -> Path:
    records = parse_consolidated(path)
    summary_path = path.with_name(path.stem + '_summary.txt')
    lines: List[str] = []
    lines.append(f"Summary for {path.name}")
    lines.append("")
    current_run = None
    for rec in records:
        s = summarize_record(rec)
        if current_run != s['run']:
            current_run = s['run']
            lines.append(f"===== RUN #{current_run} =====")
        block = rec.job_name or rec.file
        line = (
            f"{block}: "
            f"throughput_GBps={s['throughput_GBps'] or 'n/a'}, "
            f"iops_k={s['iops_k'] or 'n/a'}, "
            f"derived_latency_ms={s['derived_latency_ms'] or 'n/a'}, "
            f"iodepth={s['iodepth'] or 'n/a'}, "
            f"clat_avg_ms={s['clat_avg_ms'] or 'n/a'}"
        )
        lines.append(line)
        # add source hints when available
        src_bits = []
        if s['bw_source']:
            src_bits.append(f"bw_src={s['bw_source']}")
        if s['iops_source']:
            src_bits.append(f"iops_src={s['iops_source']}")
        if src_bits:
            lines.append("  (" + "; ".join(src_bits) + ")")
    lines.append("")
    with summary_path.open('w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))
    return summary_path


def main():
    ap = argparse.ArgumentParser(description="Summarize fio consolidated parsed outputs")
    ap.add_argument('inputs', nargs='+', type=Path, help='Consolidated files to summarize')
    args = ap.parse_args()

    for p in args.inputs:
        if not p.exists():
            print(f"Input not found: {p}")
            continue
        out = summarize_file(p)
        print(f"Wrote summary: {out}")


if __name__ == '__main__':
    main()
