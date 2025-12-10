#!/bin/bash

# ==============================================================================
# FIO Benchmark Script: Random Write (Targeting Hp-pr)
# Description: Measures Hypervisor Processing latency and IOPS capacity for writes.
# ==============================================================================

# --- CONFIGURATION ---
TEST_DIR="."                    
TEST_FILE="fio_test_file"       
RUNTIME=60                      
RAMP_TIME=5                     
NUMJOBS=1                       
IODEPTH=32                      
SIZE="5G"                       

# Block sizes to test for Random Write (Small blocks stress the Hypervisor logic)
BLOCK_SIZES=("2k" "4k" "8k" "12k" "16k")

# --- PRE-FLIGHT CHECKS ---
echo "-----------------------------------------------------------------"
echo "Starting Random Write Benchmark (Target: Hp-pr)"
echo "Hypervisor Write Request Handling & Latency Test"
echo "-----------------------------------------------------------------"

SCRIPT_BASENAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${0}")" && pwd -P)"
OUTPUT_DIR="${SCRIPT_DIR}/${SCRIPT_BASENAME%.*}"
mkdir -p "${OUTPUT_DIR}"
echo "Output files will be written to: ${OUTPUT_DIR}"

# --- MAIN LOOP ---
for BS in "${BLOCK_SIZES[@]}"; do
    echo ""
    echo ">>> RUNNING TEST: Random Write | Block Size: $BS <<<"
    
    fio --name="rand_write_${BS}" \
        --filename="${TEST_DIR}/${TEST_FILE}" \
        --ioengine=libaio \
        --rw=randwrite \
        --bs="${BS}" \
        --direct=1 \
        --numjobs=${NUMJOBS} \
        --size=${SIZE} \
        --runtime=${RUNTIME} \
        --ramp_time=${RAMP_TIME} \
        --time_based \
        --iodepth=${IODEPTH} \
        --group_reporting \
        --output-format=normal > "${OUTPUT_DIR}/result_rand_write_${BS}.txt"

    # Parse the human-readable output for the result line
    echo "   Completed. Results:"
    # We grep for "WRITE:" which contains IOPS and latency
    grep "WRITE:" "${OUTPUT_DIR}/result_rand_write_${BS}.txt" | head -1
    
    # CRITICAL: Sync disks and wait to clear Hypervisor/Host buffers
    sync
done

# --- CLEANUP ---
echo ""
echo "-----------------------------------------------------------------"
echo "All tests completed."
echo "Removing temporary test file..."
rm "${TEST_DIR}/${TEST_FILE}"
echo "Done."