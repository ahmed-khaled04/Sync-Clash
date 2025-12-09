#!/bin/bash

SERVER_CMD="python3 server.py"
CLIENT_CMD="python3 client.py"   # modify if your client file is different
CLIENT_COUNT=4
DURATION=10                     # time to run each test in seconds
IFACE="eth0"                    # change if needed (check using ip link show)

run_test() {
    TEST_NAME=$1
    NETEM=$2

    echo "=============================="
    echo " Running: $TEST_NAME"
    echo "=============================="

    mkdir -p results/$TEST_NAME

    # Apply netem rule if exists
    if [ "$NETEM" != "none" ]; then
        sudo tc qdisc add dev $IFACE root netem $NETEM
    fi

    for i in {1..5}; do
        echo ">>> Run $i for $TEST_NAME"

        RUN_DIR="results/$TEST_NAME/run$i"
        mkdir -p $RUN_DIR

        # Cleanup old files
        rm -f server*.csv client*.csv position_error_results.csv summary_metrics.csv *.png

        # Start server
        $SERVER_CMD > $RUN_DIR/server.log &
        SERVER_PID=$!

        sleep 1

        # Start clients
        for ((c=1; c<=CLIENT_COUNT; c++)); do
            $CLIENT_CMD > $RUN_DIR/client$c.log &
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
        python3 compute_positional_error.py

        echo "[INFO] Analyzing logs..."
        python3 analyze_logs.py

        # move all CSVs + plots
        mv server*.csv client*.csv position_error_results.csv summary_metrics.csv *.png $RUN_DIR 2>/dev/null

        echo "[✓] Finished run $i"
        echo "-----------------------------------"
    done

    sudo tc qdisc del dev $IFACE root 2>/dev/null
}


# # ========== BASELINE ==========
run_test "baseline" "none"

# ========== LOSS 2% ==========
# run_test "loss_2" "loss 2%"

# # ========== LOSS 5% ==========
# run_test "loss_5" "loss 5%"

# # ========== DELAY 100ms ==========
# run_test "delay_100ms" "delay 100ms"
