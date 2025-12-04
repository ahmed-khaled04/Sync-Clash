#!/bin/bash
set -e

# WSL local traffic goes over lo
IFACE="lo"

DURATION=30             # seconds per test
OUTDIR="logs/tests"

mkdir -p "$OUTDIR"

run_scenario () {
  NAME="$1"
  NETEM_RULE="$2"

  echo "=== Scenario: $NAME ==="

  # Clear old qdisc (ignore errors)
  sudo tc qdisc del dev "$IFACE" root 2>/dev/null || true

  # Apply netem if needed
  if [ -n "$NETEM_RULE" ]; then
    echo "Applying netem on $IFACE: $NETEM_RULE"
    sudo tc qdisc add dev "$IFACE" root netem $NETEM_RULE
  else
    echo "No netem (baseline)"
  fi

  # Clean old logs produced by this run
  mkdir -p logs
  rm -f logs/*.csv

# Pre-create client_positions.csv with header once
echo "timestamp_ms,player_id,x,y" > logs/client_positions.csv

  # Start server
  python3 server.py > "$OUTDIR/server_$NAME.log" 2>&1 &
  SERVER_PID=$!

  # Give server time to start
  sleep 1

  # Start two bot clients (headless)
  python3 bot_client.py > "$OUTDIR/client1_$NAME.log" 2>&1 &
  C1=$!
  python3 bot_client.py > "$OUTDIR/client2_$NAME.log" 2>&1 &
  C2=$!

  # Start CPU logger
  ./log_cpu.sh "$SERVER_PID" "$OUTDIR/cpu_$NAME.csv" &
  CPU_LOGGER=$!

  echo "Running for $DURATION seconds..."
  sleep "$DURATION"

  # Stop clients and server
  kill "$C1" "$C2" "$SERVER_PID" 2>/dev/null || true
  wait "$C1" "$C2" "$SERVER_PID" 2>/dev/null || true

  # Stop CPU logger
  kill "$CPU_LOGGER" 2>/dev/null || true

  # Clear netem
  sudo tc qdisc del dev "$IFACE" root 2>/dev/null || true

  # Compute position error + stats using logs/ in project root
  python3 compute_position_error.py
  python3 compute_stats.py

  # Archive this run's CSVs into scenario folder
  mkdir -p "$OUTDIR/$NAME"
  cp logs/*.csv "$OUTDIR/$NAME"/ 2>/dev/null || true

  # Optional: clear logs/ for next run
  rm -f logs/*.csv
}

# Run all scenarios
run_scenario "baseline" ""
run_scenario "loss2"    "loss 2%"
run_scenario "loss5"    "loss 5%"
run_scenario "delay100" "delay 100ms"
