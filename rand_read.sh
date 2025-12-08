#!/bin/bash

# ==============================================================================
# FIO Benchmark Script: Random Read (Targeting Hp-pr)
# Description: Tests Hypervisor Processing latency and IOPS capacity.
# ==============================================================================

# --- CONFIGURATION ---
TEST_DIR="."                    
TEST_FILE="fio_test_file"       
RUNTIME=60                      
RAMP_TIME=5                     
NUMJOBS=1                       
IODEPTH=32                      
SIZE="5G"                       

# Block sizes to test for Random Read (Small blocks stress the Hypervisor logic)
BLOCK_SIZES=("4k" "8k" "16k")

# --- PRE-FLIGHT CHECKS ---
echo "-----------------------------------------------------------------"
echo "Starting Random Read Benchmark (Target: Hp-pr)"
echo "Hypervisor Request Handling & Latency Test"
echo "-----------------------------------------------------------------"

# --- MAIN LOOP ---
for BS in "${BLOCK_SIZES[@]}"; do
    echo ""
    echo ">>> RUNNING TEST: Random Read | Block Size: $BS <<<"
    
    fio --name="rand_read_${BS}" \
        --filename="${TEST_DIR}/${TEST_FILE}" \
        --ioengine=libaio \
        --rw=randread \
        --bs="${BS}" \
        --direct=1 \
        --numjobs=${NUMJOBS} \
        --size=${SIZE} \
        --runtime=${RUNTIME} \
        --ramp_time=${RAMP_TIME} \
        --time_based \
        --iodepth=${IODEPTH} \
        --group_reporting \
        --output-format=normal > "result_rand_read_${BS}.txt"

    # Parse the human-readable output for the result line
    echo "   Completed. Results:"
    # We grep for "READ:" which contains IOPS and BW
    # Look specifically for the IOPS value in the output file later for your analysis
    grep "READ:" "result_rand_read_${BS}.txt" | head -1
    
    # Optional: Brief cooldown
    sleep 5
done

# --- CLEANUP ---
echo ""
echo "-----------------------------------------------------------------"
echo "All tests completed."
echo "Removing temporary test file..."
rm "${TEST_DIR}/${TEST_FILE}"
echo "Done."

