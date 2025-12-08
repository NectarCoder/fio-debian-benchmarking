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
BLOCK_SIZES=("256k" "512k" "1m")

# --- PRE-FLIGHT CHECKS ---
echo "-----------------------------------------------------------------"
echo "Starting Sequential Read Benchmark (Target: VHw-pr)"
echo "Hypervisor Processing & Caching Efficiency Test"
echo "-----------------------------------------------------------------"

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
        --output-format=normal > "result_seq_read_${BS}.txt"

    # Parse the human-readable output for the result line
    # This looks for the line containing "READ:" and prints it to your screen
    echo "   Completed. Results:"
    grep "READ:" "result_seq_read_${BS}.txt" | head -1
    
done

# --- CLEANUP ---
echo ""
echo "-----------------------------------------------------------------"
echo "All tests completed."
echo "Removing temporary test file..."
rm "${TEST_DIR}/${TEST_FILE}"
echo "Done."