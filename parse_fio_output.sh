#!/usr/bin/env bash
set -euo pipefail

# Wrapper: call the Python parser if available
INPUT_FILE="$1"
if [[ $# -ge 2 ]]; then
  OUTPUT_FILE="$2"
else
  OUTPUT_FILE="${INPUT_FILE%.*}.parsed.txt"
fi

if command -v python3 >/dev/null 2>&1; then
  python3 "${BASH_SOURCE%/*}/single_runs/parse_fio_output.py" "$INPUT_FILE" "$OUTPUT_FILE"
else
  echo "Python 3 not available; please install python3 to use this parser." >&2
  exit 1
fi
