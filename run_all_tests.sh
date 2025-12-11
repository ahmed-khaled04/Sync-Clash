#!/bin/bash

SERVER_CMD="python server.py"
CLIENT_CMD="python client.py"   # modify if your client file is different
CLIENT_COUNT=4
DURATION=15              # time to run each test in seconds

run_test() {
    TEST_NAME=$1

    echo "=============================="
    echo " Running: $TEST_NAME"
    echo "=============================="

    mkdir -p results/$TEST_NAME

    for i in {1..5}; do
        echo ">>> Run $i for $TEST_NAME"

        RUN_DIR="results/$TEST_NAME/run$i"
        mkdir -p $RUN_DIR

        # Cleanup old files
        rm -f server*.csv client*.csv position_error_results.csv summary_metrics.csv *.png

        # Start server
        $SERVER_CMD > $RUN_DIR/server.log 2>&1 &
        SERVER_PID=$!

        sleep 1

        # Start clients
        for ((c=1; c<=CLIENT_COUNT; c++)); do
            $CLIENT_CMD > $RUN_DIR/client$c.log 2>&1 &
            CLIENT_PIDS[$c]=$!
        done

        sleep $DURATION

        # Stop all processes
        kill $SERVER_PID 2>/dev/null
        for pid in "${CLIENT_PIDS[@]}"; do
            kill $pid 2>/dev/null
        done

        sleep 2

        echo "[INFO] Computing positional error..."
        python compute_positional_error.py

        echo "[INFO] Analyzing logs..."
        python analyze_logs.py

        # move all CSVs + plots
        mv server*.csv client*.csv position_error_results.csv summary_metrics.csv *.png $RUN_DIR 2>/dev/null

        echo "[✓] Finished run $i"
        echo "-----------------------------------"
    done

}


# # ========== BASELINE ==========
# run_test "baseline" 

# ========== LOSS 2% ==========
# run_test "loss_2"

# # ========== LOSS 5% ==========
# run_test "loss_5" 

# # ========== DELAY 100ms ==========
run_test "delay_100ms" 
