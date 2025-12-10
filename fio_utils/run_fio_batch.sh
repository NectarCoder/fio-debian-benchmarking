#!/usr/bin/env bash
set -euo pipefail
shopt -s nullglob

# Run all fio workloads multiple times, collect raw outputs, parse them, and consolidate per operation.
RUNS=5
OPS=(rand_read rand_write seq_read seq_write)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# Locate `single_runs` directory. It may live either beside this script
# (e.g. `fio_utils/single_runs`) or at the repo root (`../single_runs`).
if [[ -d "${ROOT_DIR}/single_runs" ]]; then
  SCRIPTS_DIR="${ROOT_DIR}/single_runs"
elif [[ -d "${ROOT_DIR}/../single_runs" ]]; then
  SCRIPTS_DIR="${ROOT_DIR}/../single_runs"
else
  echo "Cannot find 'single_runs' directory under ${ROOT_DIR} or its parent." >&2
  exit 1
fi

COLLECT_DIR="${ROOT_DIR}/batch_results"
PARSER_SH="${ROOT_DIR}/parse_fio_output.sh"

mkdir -p "${COLLECT_DIR}"

run_op() {
  local op="$1" run_idx="$2"
  local script="${SCRIPTS_DIR}/${op}.sh"
  local outdir="${SCRIPTS_DIR}/${op}"
  local run_dir="${COLLECT_DIR}/${op}/run${run_idx}"
  local raw_dir="${run_dir}/raw"
  local parsed_dir="${run_dir}/parsed"

  if [[ ! -f "${script}" ]]; then
    echo "Missing script: ${script}" >&2
    exit 1
  fi

  mkdir -p "${run_dir}" "${raw_dir}" "${parsed_dir}"

  # Clear any leftover result files from previous attempts for this op
  rm -f "${outdir}"/result_*.txt || true

  echo "=== Run ${run_idx} / ${RUNS} :: ${op} ==="
  bash "${script}"

  # Move freshly generated raw results into the run-specific folder
  local moved=false
  for f in "${outdir}"/result_*.txt; do
    [[ -e "$f" ]] || continue
    mv "$f" "${raw_dir}/$(basename "$f")"
    moved=true
  done
  if [[ "${moved}" == "false" ]]; then
    echo "No result files found for ${op} run ${run_idx}" >&2
  fi

  # Parse each raw result file
  for f in "${raw_dir}"/result_*.txt; do
    [[ -e "$f" ]] || continue
    local base="$(basename "$f" .txt)"
    local parsed_out="${parsed_dir}/${base}.parsed.txt"
    bash "${PARSER_SH}" "$f" "$parsed_out"
  done
}

# Execute runs
for run_idx in $(seq 1 ${RUNS}); do
  for op in "${OPS[@]}"; do
    run_op "$op" "$run_idx"
  done
done

# Consolidate parsed outputs per operation
for op in "${OPS[@]}"; do
  consolidated="${COLLECT_DIR}/${op}_parsed_${RUNS}_runs.txt"
  : > "${consolidated}"
  for run_idx in $(seq 1 ${RUNS}); do
    parsed_dir="${COLLECT_DIR}/${op}/run${run_idx}/parsed"
    echo "~~~~~~~ RUN #${run_idx} ~~~~~~~" >> "${consolidated}"
    for f in "${parsed_dir}"/result_*.parsed.txt; do
      [[ -e "$f" ]] || continue
      echo "-- $(basename "$f") --" >> "${consolidated}"
      cat "$f" >> "${consolidated}"
      echo "" >> "${consolidated}"
    done
  done
  echo "Consolidated file for ${op}: ${consolidated}"
  echo "" >> "${consolidated}"
  echo "=== END ${op} ===" >> "${consolidated}"
  echo "" >> "${consolidated}"
  echo "${op}: ${consolidated}" >&2
done

echo "All done. Consolidated files are in: ${COLLECT_DIR}"
