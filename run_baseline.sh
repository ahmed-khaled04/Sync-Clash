#!/bin/bash

TEST_DURATION=15   # seconds to run the client/server
SERVER_IP="192.168.159.1"

echo "==============================="
echo "   BASELINE TEST STARTING"
echo "==============================="

# 1. Cleanup old logs

echo "[INFO] Cleaning old logs..."

rm -f server_positions.csv \
      client_positions.csv \
      server_metrics.csv \
      client_metrics.csv \
      position_error_results.csv \
      summary_metrics.csv

echo "[OK] Old logs removed."


# --------------------------------
# 2. Start server
# --------------------------------

echo "[INFO] Starting server..."
python server.py &
SERVER_PID=$!

sleep 1

echo "[OK] Server running (PID $SERVER_PID)"



# 3. Start client


echo "[INFO] Starting client..."
python client.py &
CLIENT_PID=$!

echo "[OK] Client running (PID $CLIENT_PID)"


# 4. Let test run


echo "[INFO] Running baseline for $TEST_DURATION seconds..."
sleep $TEST_DURATION



# 5. Stop processes
echo "[INFO] Stopping server and client..."

kill $CLIENT_PID 2>/dev/null
kill $SERVER_PID 2>/dev/null

sleep 1

echo "[OK] Processes stopped."



# 6. Compute positional error


echo "[INFO] Computing positional error..."
python compute_positional_error.py


# 7. Generate summary & plots

echo "[INFO] Generating metrics summary and plots..."
python analyze_logs.py


echo ""
echo "==============================="
echo "   BASELINE TEST COMPLETE"
echo "==============================="
echo "Check generated files:"
echo " - summary_metrics.csv"
echo " - latency_plot.png"
echo " - jitter_plot.png"
echo " - cpu_plot.png"
echo " - positional_error_plot.png"
echo "==============================="

