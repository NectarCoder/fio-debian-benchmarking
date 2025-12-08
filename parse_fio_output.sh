#!/usr/bin/env bash
set -euo pipefail

# Parse an fio human-readable output file and emit key=value pairs for every metric line.
# Usage: ./parse_fio_output.sh <input_file> [output_file]

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <input_file> [output_file]" >&2
  exit 1
fi

INPUT_FILE="$1"
if [[ ! -f "$INPUT_FILE" ]]; then
  echo "Input file not found: $INPUT_FILE" >&2
  exit 1
fi

if [[ $# -ge 2 ]]; then
  OUTPUT_FILE="$2"
else
  OUTPUT_FILE="${INPUT_FILE%.*}.parsed.txt"
fi

awk '
function emit(k,v){print k " = " v}
function split_pairs(line,prefix){
  n=split(line, arr, ",");
  for(i=1;i<=n;i++){
    gsub(/^ +/, "", arr[i]); gsub(/ +$/, "", arr[i]);
    split(arr[i], kv, "=");
    if(length(kv[1]) && length(kv[2])) emit(prefix kv[1], kv[2]);
  }
}
/^[A-Za-z0-9_.-]+: \(g=/ {
  job=$1; sub(":", "", job); emit("job_name", job);
  if(match($0, "rw=([^,]+)", m)) emit("rw", m[1]);
  if(match($0, "bs=\\(R\\) ([^,]+)", m)) emit("bs_r", m[1]);
  if(match($0, "\\(W\\) ([^,]+)", m)) emit("bs_w", m[1]);
  if(match($0, "\\(T\\) ([^,]+)", m)) emit("bs_t", m[1]);
  if(match($0, "ioengine=([^,]+)", m)) emit("ioengine", m[1]);
  if(match($0, "iodepth=([0-9]+)", m)) emit("iodepth", m[1]);
  next;
}
/^fio-[0-9.]+/ {
  sub("fio-", ""); emit("fio_version", $0); next;
}
/ Laying out IO file / {
  if(match($0, "\\(([0-9]+) file", m)) emit("layout_files", m[1]);
  if(match($0, "/ ([^)]+)\\)", m)) emit("layout_size", m[1]);
  next;
}
/^ *read:/    { split_pairs(substr($0, index($0, ":")+1), "read_"); next; }
/^ *write:/   { split_pairs(substr($0, index($0, ":")+1), "write_"); next; }
/^[ \t]*slat / { split_pairs(substr($0, index($0, ":")+1), "slat_"); next; }
/^[ \t]*clat / { split_pairs(substr($0, index($0, ":")+1), "clat_"); next; }
/^[ \t]*lat /  { split_pairs(substr($0, index($0, ":")+1), "lat_"); next; }

/^[ \t]*clat percentiles/ { pct_mode="clat"; next; }
pct_mode=="clat" && /^[ \t]*\|/ {
  line=$0; gsub(/[|\[\]]/, "", line);
  n=split(line, arr, ",");
  for(i=1;i<=n;i++){
    gsub(/^ +/, "", arr[i]); gsub(/ +$/, "", arr[i]);
    split(arr[i], kv, "=");
    if(length(kv[1]) && length(kv[2])) emit("clat_pct_" kv[1], kv[2]);
  }
  next;
}

/^ *bw \(/   { split_pairs(substr($0, index($0, ":")+1), "bw_"); next; }
/^ *iops/    { split_pairs(substr($0, index($0, ":")+1), "iops_"); next; }
/^ *lat \(usec\)/ { split_pairs(substr($0, index($0, ":")+1), "lat_usecpct_"); next; }
/^ *lat \(msec\)/ { split_pairs(substr($0, index($0, ":")+1), "lat_msecpct_"); next; }
/^ *cpu/     { split_pairs(substr($0, index($0, ":")+1), "cpu_"); next; }
/^ *IO depths/ { split_pairs(substr($0, index($0, ":")+1), "iodepth_dist_"); next; }
/^ *submit/  { split_pairs(substr($0, index($0, ":")+1), "submit_"); next; }
/^ *complete/ { split_pairs(substr($0, index($0, ":")+1), "complete_"); next; }
/^ *issued rwts/ {
  if(match($0, "total=([^ ]+)", m)) emit("issued_total", m[1]);
  if(match($0, "short=([^ ]+)", m)) emit("issued_short", m[1]);
  if(match($0, "dropped=([^ ]+)", m)) emit("issued_dropped", m[1]);
  next;
}
/^ *latency/ { split_pairs(substr($0, index($0, ":")+1), "latency_cfg_"); next; }
/^ *READ:/   { split_pairs(substr($0, index($0, ":")+1), "run_read_"); next; }
/^ *WRITE:/  { split_pairs(substr($0, index($0, ":")+1), "run_write_"); next; }
/^ *Disk stats/ { disk_section=1; next; }
disk_section && /^[ \t]*[A-Za-z0-9_-]+:/ {
  disk=$1; sub(":", "", disk);
  line=substr($0, index($0, ":")+1);
  n=split(line, arr, ",");
  for(i=1;i<=n;i++){
    gsub(/^ +/, "", arr[i]); gsub(/ +$/, "", arr[i]);
    split(arr[i], kv, "=");
    if(length(kv[1]) && length(kv[2])) emit("disk_" disk "_" kv[1], kv[2]);
  }
  next;
}
' "$INPUT_FILE" > "$OUTPUT_FILE"

echo "Parsed metrics written to: $OUTPUT_FILE"
