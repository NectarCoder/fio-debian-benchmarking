# fio-debian-benchmarking

Small collection of scripts to run simple fio workloads, parse human-readable fio output, and summarize consolidated results for comparisons.

## Summary
This repository contains helper scripts to run common FIO microbenchmarks (random/sequential read/write), parse the human-readable outputs produced by `fio`, and summarize consolidated results over multiple runs. These tools are designed to be lightweight and work in POSIX shells (bash/WSL) and require Python 3 for parsing and summarization.

## Contents
- `single_runs/` - Example single-run fio workload scripts (random read/write, sequential read/write). Each script runs fio across a set of block sizes and writes a result file per workload.
- `fio_utils/` - Utility scripts and parsers:
	- `parse_fio_output.py` - Python parser that converts a human fio output file into key=value pairs (one per metric).
	- `parse_fio_output.sh` - Small wrapper to invoke the Python parser.
	- `run_fio_batch.sh` - Batch-run script that runs the workloads in `single_runs/` multiple times and consolidates parsed results.
	- `summarize_consolidated.py` - Python script that reads consolidated `_parsed_*.txt` files and emits a human-friendly summary (throughput, iops, derived latency).
	- `summarize_consolidated.sh` - Wrapper to call the summarizer with Python.

## Requirements
- fio (https://fio.readthedocs.io)
- bash (or WSL/Git Bash on Windows)
- Python 3.8+ (for the parsing and summarization scripts)

Note: The scripts assume a Unix-like environment (bash) — on Windows, use WSL or Git Bash to run them.

## Quick start
1. Run a small single-run script to generate results. Example (in repo root):

```bash
cd fio_utils
bash ../single_runs/rand_read.sh
```

2. Parse a single result file (if not using the batch script):

```bash
bash fio_utils/parse_fio_output.sh single_runs/rand_read/result_rand_read_4k.txt
# or run directly with python3
python3 fio_utils/parse_fio_output.py single_runs/rand_read/result_rand_read_4k.txt
```

3. Run the batch runner (runs each workload multiple times, parses, and consolidates results):

```bash
bash fio_utils/run_fio_batch.sh
```

4. Summarize consolidated results (produces `_summary.txt` per consolidated input):

```bash
bash fio_utils/summarize_consolidated.sh fio_utils/batch_results/rand_read_parsed_5_runs.txt
```

## How it works
- The single-run scripts in `single_runs/` call `fio` with a set of block sizes and standard options (libaio, direct, group_reporting).
- Each run produces a human-readable `result_*.txt` file.
- The Python parser `parse_fio_output.py` converts these human-readable files into `key = value` pairs (one-per-line) suitable for quick scanning and automated processing.
- `run_fio_batch.sh` executes the single-run scripts repeatedly (defaults to 5 runs), moves raw outputs to a `batch_results` tree, parses them, and collates the parsed files.
- `summarize_consolidated.py` reads these consolidated parsed files and computes derived metrics (throughput in decimal GB/s, iops in kIOPS, derived latency using Little's Law) and writes a compact summary per consolidated file.

## Example output
- Parsed output: `result_rand_read_4k.parsed.txt` contains lines like:

```
job_name = rand_read_4k	# fio job name
rw = randread	# workload type (read/write/randread/randwrite/rw)
read_iops = 12345	# read IOPS (fio)
read_bw = 45.6MiB/s	# read bandwidth (fio)
...
```

- Summary file snippet (from `summarize_consolidated.py`):

```
===== RUN #1 =====
rand_read_4k: throughput_GBps=0.0456, iops_k=12.345, derived_latency_ms=2.593, iodepth=32, clat_avg_ms=0.313
```

## Notes & Tips
- The scripts create and remove a temporary `fio_test_file` in the `single_runs` directory; if testing on important storage, modify `TEST_DIR`/`TEST_FILE` in the scripts accordingly.
- The parsing is written defensively to handle most human fio outputs; if you use `--output-format=json` in `fio`, you may prefer to integrate a different JSON-based parser.
