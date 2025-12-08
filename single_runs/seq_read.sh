#!/bin/bash

# ==============================================================================
# FIO Benchmark Script: Sequential Read (Targeting VHw-pr)
# ==============================================================================

# --- CONFIGURATION ---
TEST_DIR="."                    
TEST_FILE="fio_test_file"       
RUNTIME=60                      
RAMP_TIME=5                     
NUMJOBS=1                       
IODEPTH=32                      
SIZE="5G"                       

# Block sizes to test for Sequential Read
BLOCK_SIZES=("128k" "256k" "512k" "1m" "2m" "4m")

# --- PRE-FLIGHT CHECKS ---
echo "-----------------------------------------------------------------"
echo "Starting Sequential Read Benchmark (Target: VHw-pr)"
echo "Hypervisor Processing & Caching Efficiency Test"
echo "-----------------------------------------------------------------"

SCRIPT_BASENAME="$(basename \"$0\")"
SCRIPT_DIR="$(cd "$(dirname "${0}")" && pwd -P)"
OUTPUT_DIR="${SCRIPT_DIR}/${SCRIPT_BASENAME%.*}"
mkdir -p "${OUTPUT_DIR}"
echo "Output files will be written to: ${OUTPUT_DIR}"

# --- MAIN LOOP ---
for BS in "${BLOCK_SIZES[@]}"; do
    echo ""
    echo ">>> RUNNING TEST: Sequential Read | Block Size: $BS <<<"
    
    fio --name="seq_read_${BS}" \
        --filename="${TEST_DIR}/${TEST_FILE}" \
        --ioengine=libaio \
        --rw=read \
        --bs="${BS}" \
        --direct=1 \
        --numjobs=${NUMJOBS} \
        --size=${SIZE} \
        --runtime=${RUNTIME} \
        --ramp_time=${RAMP_TIME} \
        --time_based \
        --iodepth=${IODEPTH} \
        --group_reporting \
        --output-format=normal > "${OUTPUT_DIR}/result_seq_read_${BS}.txt"

    # Parse the human-readable output for the result line
    # This looks for the line containing "READ:" and prints it to your screen
    echo "   Completed. Results:"
    grep "READ:" "${OUTPUT_DIR}/result_seq_read_${BS}.txt" | head -1
    
done

# --- CLEANUP ---
echo ""
echo "-----------------------------------------------------------------"
echo "All tests completed."
echo "Removing temporary test file..."
rm "${TEST_DIR}/${TEST_FILE}"
echo "Done."