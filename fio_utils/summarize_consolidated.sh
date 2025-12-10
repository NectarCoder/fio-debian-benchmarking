#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PY="python3"
if ! command -v python3 >/dev/null 2>&1; then
  if [[ -x "/usr/bin/python3" ]]; then
    PY="/usr/bin/python3"
  elif [[ -x "C:/Program Files/Python313/python.exe" ]]; then
    PY="C:/Program Files/Python313/python.exe"
  fi
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <consolidated_file1> [consolidated_file2 ...]" >&2
  exit 1
fi

"${PY}" "${SCRIPT_DIR}/summarize_consolidated.py" "$@"
