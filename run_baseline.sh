#!/bin/bash

# Configuration
SERVER_PORT=5005
SERVER_LOG="server_output.log"
CLIENT_LOG="client_output.log"

echo "[TEST] Starting baseline local test..."
echo "[TEST] Cleaning old logs..."
rm -f $SERVER_LOG $CLIENT_LOG

# Step 1: Start the server in background (unbuffered mode)
echo "[TEST] Launching server..."
python3 -u server.py > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!

# Give the server time to start
sleep 2

# Step 2: Run the client
echo "[TEST] Launching client..."
python3 -u client.py > "$CLIENT_LOG" 2>&1

# Step 3: Wait for client to finish
sleep 2

# Step 4: Gracefully stop the server
echo "[TEST] Stopping server..."
kill $SERVER_PID 2>/dev/null

# Wait a bit to ensure logs flush
sleep 1

echo "[TEST] Baseline test completed!"
echo "[TEST] Logs saved as $SERVER_LOG and $CLIENT_LOG"
