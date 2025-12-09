#!/usr/bin/env python3
"""
Parse fio human-readable output (single run) and emit key=value pairs for every metric.
Usage:
  parse_fio_output.py <input_file> [output_file]

This script is written to be portable and avoids relying on advanced awk dialects.
"""

import argparse
import re
import sys
from pathlib import Path

KEY_PREFIXES = {
    'read': 'read_',
    'write': 'write_',
    'slat': 'slat_',
    'clat': 'clat_',
    'lat': 'lat_',
    'bw': 'bw_',
    'iops': 'iops_',
    'cpu': 'cpu_',
    'iodepth': 'iodepth_',
}

re_job_header = re.compile(r'^(?P<job>[A-Za-z0-9_.-]+):.*rw=(?P<rw>[^,\s]+).*ioengine=(?P<ioengine>[^,\s]+).*iodepth=(?P<iodepth>\d+)', re.I)
re_group_jobs = re.compile(r'^(?P<job>[A-Za-z0-9_.-]+): \(groupid=(?P<groupid>\d+), jobs=(?P<jobs>\d+)\):.*err=\s*(?P<err>[^:]+):\s*pid=(?P<pid>\d+):\s*(?P<timestamp>.+)$', re.I)
re_bs_r = re.compile(r'bs=\(R\)\s*(?P<bsr>[^,\s]+)', re.I)
re_bs_w = re.compile(r'\(W\)\s*(?P<bsw>[^,\s]+)', re.I)
re_bs_t = re.compile(r'\(T\)\s*(?P<bst>[^,\s]+)', re.I)
re_fio_version = re.compile(r'^fio-(?P<version>[0-9.]+)')
re_layout = re.compile(r'Laying out IO file.*\((?P<files>\d+) file[s]? / (?P<size>[^)]+)\)')
# Generic key=value in a comma separated list
re_kv = re.compile(r'(?P<key>[A-Za-z0-9._%/\(\)-]+)=(?P<value>[^,]+)')
# Percentile style e.g. "1.00th=[  359]"
re_percentile = re.compile(r'(?P<pct>[0-9]+(?:\.[0-9]+)?th)=\[\s*(?P<val>[^\]]+)\]')
# Disk stats device line e.g. "sda: ios=..."
re_disk_dev = re.compile(r'^(?P<dev>[A-Za-z0-9_-]+):\s*(?P<rest>.+)')
# Run summary lines
re_run_read = re.compile(r'^\s*READ:')
re_run_write = re.compile(r'^\s*WRITE:')


def normalize_key(k: str) -> str:
    """Normalise key to a safe metric name: remove spaces, convert some chars to underscores."""
    k = k.strip()
    # remove parentheses and slash chars in the label
    k = k.replace('(', '').replace(')', '')
    # convert percent and slash to words
    k = k.replace('%', 'pct')
    k = k.replace('/', '_')
    k = re.sub(r'[\s:]+', '_', k)
    k = re.sub(r'[^A-Za-z0-9_\.\-]', '', k)
    k = k.lower()
    return k


def describe(key: str) -> str | None:
    # Exact key descriptions
    desc_map = {
        'job_name': 'fio job name',
        'rw': 'workload type (read/write/randread/randwrite/rw)',
        'ioengine': 'fio ioengine used',
        'iodepth': 'queue depth per job',
        'bs_r': 'read block size range',
        'bs_w': 'write block size range',
        'bs_t': 'total block size range',
        'groupid': 'fio group id',
        'jobs': 'number of jobs (threads/processes)',
        'err': 'fio job error code',
        'pid': 'fio job pid',
        'timestamp': 'fio-reported wall-clock timestamp',
        'fio_version': 'fio version',
        'layout_files': 'number of files laid out',
        'layout_size': 'file size used for layout',
        'read_iops': 'read IOPS (fio)',
        'read_bw': 'read bandwidth (fio)',
        'read_io': 'total read bytes transferred',
        'read_run': 'read run duration (msec range)',
        'write_iops': 'write IOPS (fio)',
        'write_bw': 'write bandwidth (fio)',
        'write_io': 'total write bytes transferred',
        'write_run': 'write run duration (msec range)',
        'slat_min': 'submission latency min (ns)',
        'slat_max': 'submission latency max (ns)',
        'slat_avg': 'submission latency avg (ns)',
        'slat_stdev': 'submission latency stdev (ns)',
        'clat_min': 'completion latency min (usec)',
        'clat_max': 'completion latency max (usec)',
        'clat_avg': 'completion latency avg (usec)',
        'clat_stdev': 'completion latency stdev (usec)',
        'lat_usec_min': 'total latency min (usec)',
        'lat_usec_max': 'total latency max (usec)',
        'lat_usec_avg': 'total latency avg (usec)',
        'lat_usec_stdev': 'total latency stdev (usec)',
        'bw_min': 'bandwidth sample min',
        'bw_max': 'bandwidth sample max',
        'bw_per': 'bandwidth sample coverage percent',
        'bw_avg': 'bandwidth sample avg',
        'bw_stdev': 'bandwidth sample stdev',
        'bw_samples': 'bandwidth samples count',
        'iops_min': 'iops sample min',
        'iops_max': 'iops sample max',
        'iops_avg': 'iops sample avg',
        'iops_stdev': 'iops sample stdev',
        'iops_samples': 'iops samples count',
        'cpu_usr': 'cpu user percent',
        'cpu_sys': 'cpu system percent',
        'cpu_ctx': 'context switches',
        'cpu_majf': 'major faults',
        'cpu_minf': 'minor faults',
        'iodepth_dist_1': 'percent time at queue depth 1',
        'iodepth_dist_2': 'percent time at queue depth 2',
        'iodepth_dist_4': 'percent time at queue depth 4',
        'iodepth_dist_8': 'percent time at queue depth 8',
        'iodepth_dist_16': 'percent time at queue depth 16',
        'iodepth_dist_32': 'percent time at queue depth 32',
        'iodepth_dist_>=64': 'percent time at queue depth >=64',
        'submit_0': 'submit queue depth bucket 0 percent',
        'submit_4': 'submit queue depth bucket 4 percent',
        'submit_8': 'submit queue depth bucket 8 percent',
        'submit_16': 'submit queue depth bucket 16 percent',
        'submit_32': 'submit queue depth bucket 32 percent',
        'submit_64': 'submit queue depth bucket 64 percent',
        'submit_>=64': 'submit queue depth bucket >=64 percent',
        'complete_0': 'complete queue depth bucket 0 percent',
        'complete_4': 'complete queue depth bucket 4 percent',
        'complete_8': 'complete queue depth bucket 8 percent',
        'complete_16': 'complete queue depth bucket 16 percent',
        'complete_32': 'complete queue depth bucket 32 percent',
        'complete_64': 'complete queue depth bucket 64 percent',
        'complete_>=64': 'complete queue depth bucket >=64 percent',
        'issued_total': 'issued rwts totals (r,w,trim,sync)',
        'issued_short': 'short ios (r,w,trim,sync)',
        'issued_dropped': 'dropped ios (r,w,trim,sync)',
        'latency_cfg_target': 'latency target config',
        'latency_cfg_window': 'latency window config',
        'latency_cfg_percentile': 'latency percentile target',
        'latency_cfg_depth': 'latency depth config',
        'run_read_bw': 'run summary read bandwidth',
        'run_read_io': 'run summary read bytes',
        'run_read_run': 'run summary read duration',
        'run_write_bw': 'run summary write bandwidth',
        'run_write_io': 'run summary write bytes',
        'run_write_run': 'run summary write duration',
    }

    # Patterned keys
    if key.startswith('clat_pct_'):
        return 'completion latency percentile (usec)'
    if key.startswith('lat_usecpct_'):
        return 'percent of IOs in latency bucket (usec)'
    if key.startswith('lat_msecpct_'):
        return 'percent of IOs in latency bucket (msec)'
    if key.startswith('disk_'):
        return 'per-disk fio disk stats'
    if key.startswith('run_read_'):
        return 'run summary (read)'
    if key.startswith('run_write_'):
        return 'run summary (write)'

    return desc_map.get(key)


def emit(out_list, k, v):
    desc = describe(k)
    if desc:
        out_list.append(f"{k} = {v}\t# {desc}")
    else:
        out_list.append(f"{k} = {v}")


def parse_kv_list(line, prefix, out_list):
    for m in re_kv.finditer(line):
        k = normalize_key(m.group('key'))
        v = m.group('value').strip()
        # Trim surrounding spaces
        v = v.strip()
        emit(out_list, prefix + k, v)


def parse_percentile_line(line, prefix, out_list):
    for m in re_percentile.finditer(line):
        pct = m.group('pct')
        val = m.group('val').strip()
        emit(out_list, prefix + pct, val)


def parse_disk_stats(dev, rest, out_list):
    # split rest on commas and parse key=val
    for m in re_kv.finditer(rest):
        k = normalize_key(m.group('key'))
        v = m.group('value').strip()
        # if value has slash, split into read and write
        if '/' in v and ',' not in v:  # already splitting by commas above
            part_a, part_b = v.split('/', 1)
            emit(out_list, f'disk_{dev}_{k}_read', part_a.strip())
            emit(out_list, f'disk_{dev}_{k}_write', part_b.strip())
        else:
            emit(out_list, f'disk_{dev}_{k}', v)


def parse_file(path: Path) -> list:
    out = []
    pct_mode = None
    disk_section = False

    with path.open('r', encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            line = raw.rstrip('\n')
            sline = line.strip()
            # Reset disk section on blank line
            if sline == '':
                disk_section = False
                pct_mode = None
                continue

            if re_fio_version.match(sline):
                m = re_fio_version.match(sline)
                emit(out, 'fio_version', m.group('version'))
                continue

            if 'Laying out IO file' in sline:
                m = re_layout.search(sline)
                if m:
                    emit(out, 'layout_files', m.group('files'))
                    emit(out, 'layout_size', m.group('size'))
                continue

            m = re_group_jobs.search(sline)
            if m:
                emit(out, 'job_name', m.group('job'))
                emit(out, 'groupid', m.group('groupid'))
                emit(out, 'jobs', m.group('jobs'))
                emit(out, 'err', m.group('err'))
                emit(out, 'pid', m.group('pid'))
                emit(out, 'timestamp', m.group('timestamp'))
                continue

            m = re_job_header.search(sline)
            if m:
                emit(out, 'job_name', m.group('job'))
                if m.group('rw'):
                    emit(out, 'rw', m.group('rw'))
                if m.group('ioengine'):
                    emit(out, 'ioengine', m.group('ioengine'))
                if m.group('iodepth'):
                    emit(out, 'iodepth', m.group('iodepth'))
                # also capture bs types if present
                mm = re_bs_r.search(sline)
                if mm:
                    emit(out, 'bs_r', mm.group('bsr'))
                mm = re_bs_w.search(sline)
                if mm:
                    emit(out, 'bs_w', mm.group('bsw'))
                mm = re_bs_t.search(sline)
                if mm:
                    emit(out, 'bs_t', mm.group('bst'))
                continue

            # special: percentiles block
            if sline.lower().startswith('clat percentiles') or sline.lower().startswith('clat percentiles (usec):'):
                pct_mode = 'clat'
                continue
            if pct_mode == 'clat' and sline.startswith('|'):
                # remove leading | or spaces
                parse_percentile_line(sline, 'clat_pct_', out)
                continue

            # run summary lines
            if re_run_read.match(sline):
                parse_kv_list(sline, 'run_read_', out)
                continue
            if re_run_write.match(sline):
                parse_kv_list(sline, 'run_write_', out)
                continue

            # read, write and generic key-value lines
            if sline.startswith('read:'):
                parse_kv_list(sline.split(':', 1)[1], 'read_', out)
                continue
            if sline.startswith('write:'):
                parse_kv_list(sline.split(':', 1)[1], 'write_', out)
                continue
            if sline.startswith('slat'):
                parse_kv_list(sline.split(':', 1)[1], 'slat_', out)
                continue
            if sline.startswith('clat') and 'percentiles' not in sline.lower():
                parse_kv_list(sline.split(':', 1)[1], 'clat_', out)
                continue
            if sline.startswith('lat (usec)') or sline.startswith('lat (usec)   :'):
                parse_kv_list(sline.split(':', 1)[1], 'lat_usec_', out)
                continue
            if sline.startswith('lat (msec)'):
                parse_kv_list(sline.split(':', 1)[1], 'lat_msec_', out)
                continue
            if sline.startswith('bw (') or sline.startswith('bw ('):
                parse_kv_list(sline.split(':', 1)[1], 'bw_', out)
                continue
            if sline.startswith('iops') and 'iops' in sline:
                parse_kv_list(sline.split(':', 1)[1], 'iops_', out)
                continue
            if sline.startswith('lat (usec)'):
                parse_kv_list(sline.split(':', 1)[1], 'lat_usecpct_', out)
                continue

            if sline.startswith('cpu'):
                parse_kv_list(sline.split(':', 1)[1], 'cpu_', out)
                continue
            if sline.startswith('IO depths'):
                parse_kv_list(sline.split(':', 1)[1], 'iodepth_dist_', out)
                continue
            if sline.startswith('submit'):
                parse_kv_list(sline.split(':', 1)[1], 'submit_', out)
                continue
            if sline.startswith('complete'):
                parse_kv_list(sline.split(':', 1)[1], 'complete_', out)
                continue

            if 'issued rwts' in sline:
                # total=..., short=..., dropped=...
                m_total = re.search(r'total=([^ ]+)', sline)
                m_short = re.search(r'short=([^ ]+)', sline)
                m_dropped = re.search(r'dropped=([^ ]+)', sline)
                if m_total:
                    emit(out, 'issued_total', m_total.group(1))
                if m_short:
                    emit(out, 'issued_short', m_short.group(1))
                if m_dropped:
                    emit(out, 'issued_dropped', m_dropped.group(1))
                continue

            if sline.startswith('latency'):
                parse_kv_list(sline.split(':', 1)[1], 'latency_cfg_', out)
                continue

            if 'Disk stats' in sline:
                disk_section = True
                continue
            if disk_section:
                m = re_disk_dev.match(sline)
                if m:
                    dev = m.group('dev')
                    rest = m.group('rest')
                    parse_disk_stats(dev, rest, out)
                    continue

            # general key=val anywhere else (fallback)
            for m in re_kv.finditer(sline):
                k = normalize_key(m.group('key'))
                v = m.group('value').strip()
                emit(out, k, v)

    return out


def main():
    p = argparse.ArgumentParser(description='Parse fio human-readable output and emit key=value pairs')
    p.add_argument('input_file', type=Path)
    p.add_argument('output_file', nargs='?', type=Path)
    args = p.parse_args()

    if not args.input_file.exists():
        print(f"Input not found: {args.input_file}", file=sys.stderr)
        sys.exit(2)

    outfile = args.output_file if args.output_file else args.input_file.with_suffix('.parsed.txt')

    metrics = parse_file(args.input_file)
    with outfile.open('w', encoding='utf-8') as fh:
        for m in metrics:
            fh.write(m + '\n')

    print(f"Parsed metrics written to: {outfile}")


if __name__ == '__main__':
    main()
